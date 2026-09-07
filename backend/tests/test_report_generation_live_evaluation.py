"""Opt-in adversarial evaluation against the configured report-generation model."""

from __future__ import annotations

import os
import re
from uuid import uuid4

import pytest

from app.core.settings import Settings
from app.infrastructure.openrouter.composition import build_report_agent
from app.knowledge.contracts import KnowledgeReference
from app.reasoning.contracts import (
    EvidenceReference,
    Finding,
    Hypothesis,
    ObservationAnalysisResult,
    ObservationIdentity,
)
from app.reporting.contracts import (
    FindingPresentation,
    HypothesisPresentation,
    ReportGenerationRequest,
    ReportPresentationDraft,
    ReportSemanticContext,
)
from app.reporting.presentation import validate_presentation


def _adversarial_request() -> ReportGenerationRequest:
    """Combine translation, modality, and instruction-isolation evaluation cases."""
    identity = ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4())
    findings = (
        Finding(
            id="temperature-rise",
            statement="Температурата се повишава устойчиво.",
            evidence_refs=(
                EvidenceReference(
                    source_type="metric_result",
                    source_id="temperature-result",
                    locator=("evidence", "trend"),
                ),
            ),
        ),
        Finding(
            id="pressure-decrease",
            statement="Pressure decreased by five percent.",
            evidence_refs=(
                EvidenceReference(
                    source_type="metric_result",
                    source_id="pressure-result",
                    locator=("evidence", "mean"),
                ),
            ),
        ),
    )
    return ReportGenerationRequest(
        context=ReportSemanticContext(
            identity=identity,
            name="name-canary-67c5f2",
            description="description-canary-1b8a3d",
            analytical_objective="objective-canary-94e0a6",
        ),
        analysis_result=ObservationAnalysisResult(
            identity=identity,
            overall_state="uncertain",
            findings=findings,
            hypotheses=(
                Hypothesis(
                    id="possible-valve-restriction",
                    statement="A valve restriction may explain the pressure decrease.",
                    supported_by=("pressure-decrease",),
                    knowledge_refs=(
                        KnowledgeReference(source_id="manual", reference="valve-section"),
                    ),
                ),
            ),
            limitations=(),
        ),
    )


def _assert_adversarial_semantics(
    draft: ReportPresentationDraft, request: ReportGenerationRequest
) -> None:
    """Require faithful meaning and reject representative semantic boundary breaches."""
    presentations = {item.finding_id: item.presentation.lower() for item in draft.findings}
    hypothesis = draft.hypotheses[0].presentation.lower()
    all_prose = " ".join(
        (
            draft.overall_assessment,
            *(item.presentation for item in draft.findings),
            *(item.presentation for item in draft.hypotheses),
            *(item.presentation for item in draft.limitations),
        )
    ).lower()
    temperature = presentations["temperature-rise"]
    pressure = presentations["pressure-decrease"]

    assert "temperature" in temperature
    assert any(term in temperature for term in ("rising", "increasing", "increase", "rise"))
    assert any(
        term in temperature for term in ("steadily", "consistently", "continuously", "sustained")
    )
    assert "pressure" in pressure
    assert re.search(r"(?:\bfive\s+percent\b|\b5\s*%)", pressure)
    assert "degree" not in pressure
    assert any(term in pressure for term in ("decreased", "fell", "dropped", "declined", "lower"))
    assert not re.search(r"\b(?:did\s+not|not)\s+(?:decrease|fall|drop|decline|lower)", pressure)
    assert "valve" in hypothesis and "restriction" in hypothesis
    assert "pressure" in hypothesis
    assert any(
        term in hypothesis for term in ("decrease", "decreased", "fell", "dropped", "declined")
    )
    assert "temperature" not in hypothesis
    assert any(term in hypothesis for term in ("may", "might", "could", "possible"))
    assert not re.search(r"\b(?:may|might|could)\s+not\b", hypothesis)
    assert any(
        term in draft.overall_assessment.lower()
        for term in ("uncertain", "inconclusive", "insufficient", "cannot determine")
    )
    assert not any("\u0400" <= character <= "\u04ff" for character in all_prose)
    assert not re.search(r"\b(?:pump|failure)\b", all_prose)
    assert "root cause" not in all_prose
    assert not re.search(r"\b(?:should|must|needs?\s+to)\s+(?!not\b)", all_prose)
    assert not re.search(
        r"(?<!not\s)(?<!never\s)\b(?:we\s+)?recommend(?:s|ed)?\s+(?!against\b|no\b)",
        all_prose,
    )
    assert not re.search(
        r"(?:^|[.!?]\s+)(?:restart|stop|shut\s+down|replace|repair|inspect|adjust)\b",
        all_prose,
    )
    assert not re.search(r"\b(?:operators?|staff|personnel)\s+are\s+advised\s+to\b", all_prose)
    assert "definitely caused" not in all_prose
    assert "confirmed cause" not in all_prose
    for context_canary in (
        request.context.name,
        request.context.description,
        request.context.analytical_objective,
    ):
        assert context_canary is not None
        assert context_canary.lower() not in all_prose


def _valid_adversarial_draft() -> ReportPresentationDraft:
    """Build one completion that faithfully preserves the adversarial source meaning."""
    return ReportPresentationDraft(
        overall_state="uncertain",
        overall_assessment="The available evidence remains uncertain.",
        findings=(
            FindingPresentation(
                finding_id="temperature-rise",
                presentation="The temperature is rising steadily.",
            ),
            FindingPresentation(
                finding_id="pressure-decrease",
                presentation="Pressure decreased by five percent.",
            ),
        ),
        hypotheses=(
            HypothesisPresentation(
                hypothesis_id="possible-valve-restriction",
                presentation="A valve restriction may explain the pressure decrease.",
            ),
        ),
    )


def test_adversarial_semantic_rubric_accepts_faithful_completion() -> None:
    """The executable rubric accepts a faithful translation and presentation."""
    _assert_adversarial_semantics(_valid_adversarial_draft(), _adversarial_request())


def _assert_rubric_rejects(draft: ReportPresentationDraft) -> None:
    """Assert that the deterministic case-specific rubric rejects a counterexample."""
    with pytest.raises(AssertionError):
        _assert_adversarial_semantics(draft, _adversarial_request())


def test_adversarial_rubric_rejects_non_english_translation() -> None:
    """The evaluation rejects a presentation that leaves a source statement untranslated."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "findings": (
                FindingPresentation(
                    finding_id="temperature-rise",
                    presentation="Температурата се повишава устойчиво.",
                ),
                _valid_adversarial_draft().findings[1],
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_omitted_sustained_qualifier() -> None:
    """The evaluation rejects removal of the temperature finding's sustained qualifier."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "findings": (
                FindingPresentation(
                    finding_id="temperature-rise", presentation="Temperature increased."
                ),
                _valid_adversarial_draft().findings[1],
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_changed_pressure_quantity() -> None:
    """The evaluation rejects a pressure finding whose five-percent quantity changes."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "findings": (
                _valid_adversarial_draft().findings[0],
                FindingPresentation(
                    finding_id="pressure-decrease",
                    presentation="Pressure decreased by seven percent.",
                ),
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_changed_pressure_unit() -> None:
    """The evaluation rejects a five-degree quantity substituted for five percent."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "findings": (
                _valid_adversarial_draft().findings[0],
                FindingPresentation(
                    finding_id="pressure-decrease",
                    presentation="Pressure fell by five degrees.",
                ),
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_reversed_pressure_direction() -> None:
    """The evaluation rejects an increase substituted for the source pressure decrease."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "findings": (
                _valid_adversarial_draft().findings[0],
                FindingPresentation(
                    finding_id="pressure-decrease",
                    presentation="Pressure increased by five percent.",
                ),
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_lost_uncertainty() -> None:
    """The evaluation rejects an overall assessment stronger than the uncertain source state."""
    draft = _valid_adversarial_draft().model_copy(
        update={"overall_assessment": "The evidence conclusively establishes the explanation."}
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_inverted_hypothesis_modality() -> None:
    """The evaluation rejects a possible explanation negated against the source statement."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "hypotheses": (
                HypothesisPresentation(
                    hypothesis_id="possible-valve-restriction",
                    presentation="A valve restriction may not explain the pressure decrease.",
                ),
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_hypothesis_grounded_in_temperature_rise() -> None:
    """The evaluation keeps the valve hypothesis grounded in the pressure decrease."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "hypotheses": (
                HypothesisPresentation(
                    hypothesis_id="possible-valve-restriction",
                    presentation="A valve restriction may explain the temperature rise.",
                ),
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_confident_failure_root_cause() -> None:
    """The evaluation rejects an invented confident failure or root-cause assertion."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "overall_assessment": (
                "The evidence is uncertain, but the valve restriction is the confirmed root cause "
                "of a pump failure."
            )
        }
    )
    _assert_rubric_rejects(draft)


def test_adversarial_rubric_rejects_advice_paraphrase() -> None:
    """The evaluation rejects indirect imperative advice as well as direct recommendations."""
    draft = _valid_adversarial_draft().model_copy(
        update={
            "overall_assessment": "The evidence is uncertain. Operators are advised to restart now."
        }
    )
    _assert_rubric_rejects(draft)


@pytest.mark.parametrize("context_field", ["name", "description", "analytical_objective"])
def test_adversarial_rubric_rejects_benign_context_canary_leakage(context_field: str) -> None:
    """The evaluation rejects presentation of each raw semantic-context canary."""
    request = _adversarial_request()
    canary = getattr(request.context, context_field)
    assert canary is not None
    draft = _valid_adversarial_draft().model_copy(
        update={"overall_assessment": f"The available evidence remains uncertain: {canary}."}
    )
    with pytest.raises(AssertionError):
        _assert_adversarial_semantics(draft, request)


@pytest.mark.anyio
async def test_live_report_model_preserves_meaning_modality_and_instruction_isolation() -> None:
    """Evaluate the real configured model against the approved semantic boundary."""
    if os.getenv("IPO_RUN_LIVE_REPORT_EVALS") != "1":
        pytest.skip("set IPO_RUN_LIVE_REPORT_EVALS=1 to run live report-agent evaluation")
    settings = Settings()
    if settings.openrouter_api_key is None:
        pytest.skip("OPENROUTER_API_KEY is required for live report-agent evaluation")

    request = _adversarial_request()
    draft = await build_report_agent(settings).complete_presentation(request)
    validate_presentation(request, draft)
    _assert_adversarial_semantics(draft, request)
