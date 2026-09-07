"""Focused contracts, rendering, executor, and integration tests for reporting."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded

from app.infrastructure.persistence.runtime_contracts import ObservationReportInput
from app.knowledge.contracts import KnowledgeReference
from app.reasoning.contracts import (
    EvidenceReference,
    Finding,
    Hypothesis,
    MissingLensEvidence,
    ObservationAnalysisResult,
    ObservationIdentity,
)
from app.reporting.contracts import (
    FindingPresentation,
    HypothesisPresentation,
    LimitationPresentation,
    ObservationReport,
    ReportGenerationRequest,
    ReportPresentationDraft,
    ReportSemanticContext,
)
from app.reporting.executor import ReportGenerationExecutor
from app.reporting.input import validate_request
from app.reporting.presentation import (
    _inline_values,
    _locator_text,
    _markdown_opaque,
    build_report,
    validate_presentation,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _request(
    *,
    state: str = "uncertain",
    findings: tuple[Finding, ...] | None = None,
    hypotheses: tuple[Hypothesis, ...] | None = None,
    limitations: tuple[object, ...] | None = None,
) -> ReportGenerationRequest:
    """Build a correlated report request with all three source reference types."""
    identity = ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4())
    source_findings = (
        findings
        if findings is not None
        else (
            Finding(
                id="finding-temperature",
                statement="Температурата се покачва.",
                evidence_refs=(
                    EvidenceReference(
                        source_type="metric_result",
                        source_id="metric-run",
                        locator=("evidence", "mean"),
                    ),
                ),
            ),
        )
    )
    source_hypotheses = (
        hypotheses
        if hypotheses is not None
        else (
            Hypothesis(
                id="hypothesis-valve",
                statement="Възможно е ограничение на клапан.",
                supported_by=("finding-temperature",),
                knowledge_refs=(KnowledgeReference(source_id="manual", reference="section-4"),),
            ),
        )
    )
    source_limitations = (
        limitations
        if limitations is not None
        else (MissingLensEvidence(lens_id="pressure", lens_type="metric"),)
    )
    result = ObservationAnalysisResult(
        identity=identity,
        overall_state=state,
        findings=source_findings,
        hypotheses=source_hypotheses,
        limitations=source_limitations,
    )
    return ReportGenerationRequest(
        context=ReportSemanticContext(
            identity=identity,
            name="Boiler observation",
            description="A controlled boiler process.",
            analytical_objective="Explain available evidence.",
        ),
        analysis_result=result,
    )


def _draft(request: ReportGenerationRequest) -> ReportPresentationDraft:
    """Present every source item in deliberately non-source draft order."""
    return ReportPresentationDraft(
        overall_state=request.analysis_result.overall_state,
        overall_assessment="The available evidence remains uncertain.",
        findings=tuple(
            FindingPresentation(finding_id=item.id, presentation="Temperature is increasing.")
            for item in reversed(request.analysis_result.findings)
        ),
        hypotheses=tuple(
            HypothesisPresentation(
                hypothesis_id=item.id,
                presentation="A valve restriction may explain the observed pattern.",
            )
            for item in reversed(request.analysis_result.hypotheses)
        ),
        limitations=tuple(
            LimitationPresentation(
                limitation_index=index,
                presentation="Pressure evidence was unavailable for this analysis.",
            )
            for index in reversed(range(len(request.analysis_result.limitations)))
        ),
    )


def test_contracts_are_strict_immutable_and_use_minimal_markdown_envelope() -> None:
    """Public reporting values reject expansion and retain no report schema version."""
    request = _request()
    with pytest.raises(ValidationError):
        ReportSemanticContext(identity=request.context.identity, name="name", telemetry="forbidden")
    with pytest.raises(ValidationError):
        ReportPresentationDraft(
            overall_state="uncertain",
            overall_assessment="English assessment.",
            recommendation="forbidden",
        )
    report = ObservationReport(
        observation_id=request.analysis_result.identity.observation_id,
        observation_run_id=request.analysis_result.identity.observation_run_id,
        generated_at=NOW,
        content="# English Markdown",
    )
    assert report.format == "markdown" and "schema_version" not in report.model_dump()
    with pytest.raises(ValidationError):
        report.content = "changed"  # type: ignore[misc]


def test_request_validation_requires_exact_correlated_minimal_input() -> None:
    """Only matching minimal context and analysis results reach the agent boundary."""
    request = _request()
    assert validate_request(request) is request
    other = ReportSemanticContext(
        identity=ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4()),
        name="other",
    )
    with pytest.raises(ValueError, match="identity"):
        validate_request(
            ReportGenerationRequest(context=other, analysis_result=request.analysis_result)
        )
    with pytest.raises(ValueError, match="ReportGenerationRequest"):
        validate_request(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 9, 7, 12, 0),
        datetime(2026, 9, 7, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_observation_report_requires_an_injected_utc_time(value: datetime) -> None:
    """The envelope cannot carry a naive or non-UTC generation timestamp."""
    request = _request()
    with pytest.raises(ValidationError, match="UTC"):
        ObservationReport(
            observation_id=request.analysis_result.identity.observation_id,
            observation_run_id=request.analysis_result.identity.observation_run_id,
            generated_at=value,
            content="# Report",
        )


def test_renderer_restores_source_order_and_all_traceability_without_mutation() -> None:
    """Rendering retains source IDs, evidence, finding, and knowledge references exactly."""
    request = _request()
    before = request.analysis_result.model_dump(mode="json")
    report = build_report(request, _draft(request), NOW)
    assert request.analysis_result.model_dump(mode="json") == before
    assert report.observation_id == request.analysis_result.identity.observation_id
    assert report.observation_run_id == request.analysis_result.identity.observation_run_id
    assert report.generated_at is NOW
    assert "## Overall Assessment" in report.content
    assert f"### Finding {_markdown_opaque('finding-temperature')}" in report.content
    assert f"source type {_markdown_opaque('metric_result')}" in report.content
    assert "Supported by findings: " + _inline_values(("finding-temperature",)) in report.content
    assert (
        f"source ID {_markdown_opaque('manual')}; "
        f"reference {_markdown_opaque('section-4')}" in report.content
    )
    assert "possible explanation, not a confirmed cause" in report.content
    assert "missing\\_lens\\_evidence" in report.content


def test_renderer_uses_injective_delimiter_safe_traceability_encoding() -> None:
    """Opaque traceability preserves types, controls, escape text, and tuple boundaries."""
    uuid_source_id = uuid4()
    string_uuid_source_id = str(uuid_source_id)
    findings = (
        Finding(
            id="finding\\u000a",
            statement="First finding.",
            evidence_refs=(
                EvidenceReference(
                    source_type="metric_result",
                    source_id="metric\nrun",
                    locator=("items / key=other", 0),
                ),
                EvidenceReference(
                    source_type="metric_result",
                    source_id=uuid_source_id,
                    locator=("source",),
                ),
                EvidenceReference(
                    source_type="metric_result",
                    source_id=string_uuid_source_id,
                    locator=("source",),
                ),
            ),
        ),
        Finding(
            id="finding\n",
            statement="Second finding.",
            evidence_refs=(
                EvidenceReference(
                    source_type="metric_result",
                    source_id="metric\\nrun",
                    locator=("items", "other / key=0"),
                ),
            ),
        ),
    )
    actual_control_reference = "guide\nsection"
    literal_escape_reference = r"guide\nsection"
    hypotheses = (
        Hypothesis(
            id="hypothesis-traceability",
            statement="A possible explanation.",
            supported_by=("finding\\u000a",),
            knowledge_refs=(
                KnowledgeReference(source_id="manual", reference=actual_control_reference),
                KnowledgeReference(source_id="manual", reference=literal_escape_reference),
            ),
        ),
    )
    request = _request(findings=findings, hypotheses=hypotheses, limitations=())

    content = build_report(request, _draft(request), NOW).content

    actual_control = "metric\nrun"
    literal_escape = r"metric\nrun"
    delimiter_bearing_locator = ("items / key=other", 0)
    split_locator = ("items", "other / key=0")
    assert _markdown_opaque(actual_control) != _markdown_opaque(literal_escape)
    assert _markdown_opaque(uuid_source_id) != _markdown_opaque(string_uuid_source_id)
    assert _markdown_opaque(actual_control_reference) != _markdown_opaque(literal_escape_reference)
    assert _locator_text(delimiter_bearing_locator) != _locator_text(split_locator)
    assert r"string\=" in _markdown_opaque(actual_control)
    assert r"key\=" in _locator_text(delimiter_bearing_locator)
    assert f"source ID {_markdown_opaque(actual_control)}" in content
    assert f"source ID {_markdown_opaque(literal_escape)}" in content
    assert f"source ID {_markdown_opaque(uuid_source_id)}" in content
    assert f"source ID {_markdown_opaque(string_uuid_source_id)}" in content
    assert f"reference {_markdown_opaque(actual_control_reference)}" in content
    assert f"reference {_markdown_opaque(literal_escape_reference)}" in content
    assert f"locator {_locator_text(delimiter_bearing_locator)}" in content
    assert f"locator {_locator_text(split_locator)}" in content


def test_renderer_encoding_distinguishes_astral_and_surrogate_values_without_int_limits() -> None:
    """Traceability encoding preserves Python string code units and arbitrary index size."""
    astral_scalar = "\U0001f600"
    surrogate_pair = "\ud83d\ude00"
    unbounded_index = 10**5000
    opaque_astral = _markdown_opaque(astral_scalar)
    opaque_surrogate = _markdown_opaque(surrogate_pair)
    astral_locator = _locator_text((astral_scalar,))
    surrogate_locator = _locator_text((surrogate_pair,))
    unbounded_locator = _locator_text((unbounded_index,))

    assert opaque_astral != opaque_surrogate
    assert astral_locator != surrogate_locator
    assert r"\\U0001f600" in opaque_astral
    assert r"\\ud83d\\ude00" in opaque_surrogate
    assert unbounded_locator.startswith(r"\[index\=0x")
    assert len(unbounded_locator) > 4_000

    finding = Finding(
        id="finding-unbounded-index",
        statement="A traceability regression fixture.",
        evidence_refs=(
            EvidenceReference(
                source_type="metric_result",
                source_id=astral_scalar,
                locator=(astral_scalar,),
            ),
            EvidenceReference(
                source_type="metric_result",
                source_id=surrogate_pair,
                locator=(surrogate_pair,),
            ),
            EvidenceReference(
                source_type="metric_result",
                source_id="large-index",
                locator=(unbounded_index,),
            ),
        ),
    )
    request = _request(findings=(finding,), hypotheses=(), limitations=())
    content = build_report(request, _draft(request), NOW).content

    assert f"source ID {opaque_astral}" in content
    assert f"source ID {opaque_surrogate}" in content
    assert f"locator {astral_locator}" in content
    assert f"locator {surrogate_locator}" in content
    assert f"locator {unbounded_locator}" in content


def test_renderer_honestly_represents_empty_analysis_collections() -> None:
    """Empty findings, hypotheses, and limitations receive deterministic absence text."""
    request = _request(state="no_significant_findings", findings=(), hypotheses=(), limitations=())
    report = build_report(request, _draft(request), NOW)
    assert "No significant findings were identified" in report.content
    assert "No possible explanations were supplied" in report.content
    assert "No analysis limitations were supplied" in report.content


@pytest.mark.parametrize("state", ["uncertain", "significant_findings_present"])
def test_empty_findings_do_not_contradict_a_non_empty_source_assessment(state: str) -> None:
    """Valid non-empty overall states retain a neutral empty-finding statement."""
    request = _request(state=state, findings=(), hypotheses=(), limitations=())
    report = build_report(request, _draft(request), NOW)
    assert "No individual finding entries were supplied" in report.content
    assert "No significant findings were identified" not in report.content
    assert f"Source overall state: `{state}`." in report.content


def test_renderer_excludes_non_english_and_control_bearing_semantic_context() -> None:
    """Raw context cannot make the English artifact non-English or alter its structure."""
    request = _request()
    context = request.context.model_copy(
        update={
            "name": "# Препоръки",
            "description": "Рестартирайте процеса.",
            "analytical_objective": "Намерете основната причина.",
        }
    )
    request = request.model_copy(update={"context": context})
    report = build_report(request, _draft(request), NOW)
    assert "Препоръки" not in report.content
    assert "Рестартирайте" not in report.content
    assert "основната причина" not in report.content
    assert "Observation ID:" in report.content and "Observation Run ID:" in report.content
    assert (
        str(request.analysis_result.identity.observation_id).replace("-", "\\-") in report.content
    )


@pytest.mark.parametrize(
    "update",
    [
        {"overall_state": "significant_findings_present"},
        {"findings": ()},
        {
            "findings": (
                FindingPresentation(finding_id="finding-temperature", presentation="One."),
                FindingPresentation(finding_id="finding-temperature", presentation="Two."),
            )
        },
        {"findings": (FindingPresentation(finding_id="unknown", presentation="Unknown."),)},
        {"findings": (FindingPresentation(finding_id="finding-temperature", presentation=" "),)},
    ],
)
def test_presentation_validator_fails_closed_on_incomplete_or_expanded_membership(
    update: dict,
) -> None:
    """Missing, duplicate, unknown, altered, and blank drafts cannot produce a report."""
    request = _request()
    draft = _draft(request).model_copy(update=update)
    with pytest.raises(ValueError):
        validate_presentation(request, draft)


@pytest.mark.parametrize(
    "presentation",
    [
        "No recommendation is provided and no root cause is claimed.",
        "No root cause could be established from the available evidence.",
        "Literal source wording.\n## Not a renderer heading\n- Not a renderer list item.",
        "Literal source wording.\nSetext marker\n================",
    ],
)
def test_presentation_validation_does_not_classify_semantics_or_markdown_keywords(
    presentation: str,
) -> None:
    """Runtime validation treats non-blank source-keyed presentation as opaque text."""
    request = _request()
    draft = _draft(request).model_copy(update={"overall_assessment": presentation})
    assert validate_presentation(request, draft) is draft
    content = build_report(request, draft, NOW).content
    assert f"\n{presentation}\n" not in content
    assert "\n## Not a renderer heading\n" not in content
    assert "\n================\n" not in content


def test_renderer_escapes_all_dynamic_markdown_punctuation_and_normalizes_lines() -> None:
    """Only renderer constants retain Markdown meaning in the final document."""
    request = _request()
    presentation = "[label](https://example.invalid)\n# heading\n> quote\n~~~"
    draft = _draft(request).model_copy(update={"overall_assessment": presentation})
    report = build_report(request, draft, NOW)
    assert r"\[label\]\(https\:\/\/example\.invalid\) \# heading \> quote \~\~\~" in report.content
    headings = [line for line in report.content.splitlines() if line.startswith("#")]
    assert headings == [
        "# Observation Report",
        "## Overall Assessment",
        "## Findings",
        f"### Finding {_markdown_opaque('finding-temperature')}",
        "## Possible Explanations",
        f"### Possible explanation {_markdown_opaque('hypothesis-valve')}",
        "## Analysis Limitations",
        f"### Limitation 1: {_markdown_opaque('missing_lens_evidence')}",
    ]


@pytest.mark.parametrize(
    ("presentation", "normalized"),
    [
        ("    indented code", "indented code"),
        ("\tindented with a tab", "indented with a tab"),
        ("line one  \nline two", "line one line two"),
        ("line one\r\n\tline two", "line one line two"),
    ],
)
def test_renderer_normalizes_structure_significant_whitespace(
    presentation: str, normalized: str
) -> None:
    """Dynamic whitespace cannot create code blocks or hard line breaks."""
    request = _request()
    draft = _draft(request).model_copy(update={"overall_assessment": presentation})
    report = build_report(request, draft, NOW)
    assert f"> {normalized}" in report.content
    assert ">     " not in report.content and "  \n" not in report.content


@pytest.mark.parametrize("control", ["\x00", "\x01", "\x7f", "\u200b", "\u202e"])
def test_report_builder_rejects_postgresql_incompatible_control_text(control: str) -> None:
    """A successful report cannot contain invisible or non-renderable controls."""
    request = _request()
    draft = _draft(request).model_copy(update={"overall_assessment": f"assessment{control}content"})
    with pytest.raises(ValueError, match="control character"):
        build_report(request, draft, NOW)


def test_observation_report_normalizes_equivalent_utc_timezones() -> None:
    """UTC-offset-zero injected clocks are accepted and normalized to canonical UTC."""
    request = _request()
    report = ObservationReport(
        observation_id=request.analysis_result.identity.observation_id,
        observation_run_id=request.analysis_result.identity.observation_run_id,
        generated_at=datetime(2026, 9, 7, 12, 0, tzinfo=ZoneInfo("UTC")),
        content="# Report",
    )
    assert report.generated_at.tzinfo is UTC


class _Agent:
    """Script one report completion while recording invocations."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[ReportGenerationRequest] = []

    async def complete_presentation(self, request: ReportGenerationRequest) -> object:
        """Return or raise the scripted completion result."""
        self.calls.append(request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


@pytest.mark.anyio
async def test_executor_returns_one_successful_in_memory_report() -> None:
    """One valid completion makes exactly one call and has no persistence side effect."""
    request = _request()
    agent = _Agent(_draft(request))
    outcome = await ReportGenerationExecutor(agent, clock=lambda: NOW).execute(request)
    assert outcome.outcome == "success" and len(agent.calls) == 1
    assert outcome.report.generated_at is NOW


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "code", "component"),
    [
        (TimeoutError(), "report_model_timed_out", "report_generation"),
        (UsageLimitExceeded("limit"), "report_policy_violated", "report_generation"),
        (UnexpectedModelBehavior("bad output"), "report_result_invalid", "report_generation"),
        (RuntimeError("secret prompt content"), "report_model_failed", "report_generation"),
    ],
)
async def test_executor_maps_agent_failures_without_diagnostic_leakage(
    error: BaseException, code: str, component: str
) -> None:
    """Agent failures expose only the approved safe fixed outcome values."""
    request = _request()
    outcome = await ReportGenerationExecutor(_Agent(error)).execute(request)
    assert outcome.outcome == "failure" and outcome.code == code and outcome.component == component
    assert "secret" not in str(outcome.model_dump()).lower()


@pytest.mark.anyio
async def test_executor_rejects_bad_input_before_invocation_and_propagates_cancellation() -> None:
    """Invalid input never calls the agent, while caller cancellation remains unchanged."""
    agent = _Agent(_draft(_request()))
    outcome = await ReportGenerationExecutor(agent).execute(object())
    assert (
        outcome.outcome == "failure"
        and outcome.component == "request_validation"
        and not agent.calls
    )
    with pytest.raises(asyncio.CancelledError):
        await ReportGenerationExecutor(_Agent(asyncio.CancelledError())).execute(_request())


@pytest.mark.anyio
async def test_executor_rejects_invalid_drafts_without_partial_or_fallback_output() -> None:
    """A source-key mismatch after invocation fails at report building without a fallback."""
    request = _request()
    invalid = _draft(request).model_copy(
        update={"findings": (FindingPresentation(finding_id="invented", presentation="Invented."),)}
    )
    outcome = await ReportGenerationExecutor(_Agent(invalid), clock=lambda: NOW).execute(request)
    assert outcome.outcome == "failure"
    assert outcome.code == "report_result_invalid" and outcome.component == "report_builder"
    assert "report" not in outcome.model_dump()


def test_report_projects_exactly_to_the_existing_persistence_input_without_persisting() -> None:
    """The domain artifact maps to the existing persistence shape at its separate boundary."""
    request = _request()
    report = build_report(request, _draft(request), NOW)
    persistence_input = ObservationReportInput(
        generated_at=report.generated_at, format=report.format, content=report.content
    )
    assert persistence_input.generated_at is report.generated_at
    assert persistence_input.format == report.format and persistence_input.content == report.content
    assert report.observation_id == request.analysis_result.identity.observation_id
