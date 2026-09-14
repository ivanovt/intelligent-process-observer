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
    ReportAnalysisWindow,
    ReportGenerationRequest,
    ReportPresentationDraft,
    ReportSemanticContext,
)
from app.reporting.executor import ReportGenerationExecutor
from app.reporting.input import validate_request
from app.reporting.presentation import (
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
    operational_context: str | None = None,
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
            operational_context=operational_context,
        ),
        analysis_result=result,
        analysis_window=ReportAnalysisWindow(
            **{
                "from": datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
                "to": datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
            }
        ),
    )


def _draft(request: ReportGenerationRequest) -> ReportPresentationDraft:
    """Present every source item in deliberately non-source draft order."""
    return ReportPresentationDraft(
        overall_state=request.analysis_result.overall_state,
        overall_assessment="The available evidence remains uncertain.",
        objective_summary="Assess the available process evidence.",
        findings=tuple(
            FindingPresentation(
                finding_id=item.id,
                heading="Temperature increase observed",
                presentation="Temperature is increasing.",
            )
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
            ReportGenerationRequest(
                context=other,
                analysis_result=request.analysis_result,
                analysis_window=request.analysis_window,
            )
        )
    with pytest.raises(ValueError, match="ReportGenerationRequest"):
        validate_request(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "window",
    [
        {"to": NOW},
        {
            "from": datetime(2026, 9, 7, 10, 0),
            "to": datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
        },
        {
            "from": datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
            "to": datetime(2026, 9, 7, 12, 0, tzinfo=timezone(timedelta(hours=1))),
        },
        {
            "from": datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
            "to": datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
        },
        {
            "from": datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
            "to": datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
        },
    ],
)
def test_report_request_rejects_missing_or_invalid_observed_windows(window: dict) -> None:
    """The reporting boundary admits only a complete, positive exact UTC window."""
    request = _request()
    with pytest.raises(ValidationError):
        ReportGenerationRequest(
            context=request.context,
            analysis_result=request.analysis_result,
            analysis_window=window,  # type: ignore[arg-type]
        )


def test_report_request_rejects_undeclared_input() -> None:
    """Raw evidence and other undeclared values cannot cross the report boundary."""
    request = _request()
    with pytest.raises(ValidationError, match="telemetry"):
        ReportGenerationRequest(
            context=request.context,
            analysis_result=request.analysis_result,
            analysis_window=request.analysis_window,
            telemetry="forbidden",
        )  # type: ignore[call-arg]


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


def test_renderer_uses_draft_order_and_retains_complete_traceability_without_mutation() -> None:
    """Rendering uses draft order while retaining source IDs, evidence, and knowledge exactly."""
    request = _request()
    before = request.analysis_result.model_dump(mode="json")
    report = build_report(request, _draft(request), NOW)
    assert request.analysis_result.model_dump(mode="json") == before
    assert report.observation_id == request.analysis_result.identity.observation_id
    assert report.observation_run_id == request.analysis_result.identity.observation_run_id
    assert report.generated_at is NOW
    assert "## Objective" in report.content and "## Overall Assessment" in report.content
    assert "### 1. Temperature increase observed" in report.content
    assert f"- Source finding ID: {_markdown_opaque('finding-temperature')}" in report.content
    assert f"Evidence source type: {_markdown_opaque('metric_result')}" in report.content
    assert "Supported by findings: 1" in report.content
    assert (
        f"Knowledge source ID: {_markdown_opaque('manual')}; "
        f"reference: {_markdown_opaque('section-4')}" in report.content
    )
    assert "possible explanation, not a confirmed cause" in report.content
    assert "- Code: `missing_lens_evidence`" in report.content


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
    assert _markdown_opaque(uuid_source_id) == _markdown_opaque(string_uuid_source_id)
    assert _markdown_opaque(actual_control_reference) != _markdown_opaque(literal_escape_reference)
    assert _locator_text(delimiter_bearing_locator) != _locator_text(split_locator)
    assert _markdown_opaque(actual_control) == r"`metric\nrun`"
    assert _markdown_opaque(literal_escape) == r"`metric\\nrun`"
    assert _locator_text(delimiter_bearing_locator) == '`["items / key=other"][0]`'
    assert _locator_text(split_locator) == '`items["other / key=0"]`'
    assert f"source ID: {_markdown_opaque(actual_control)}" in content
    assert f"source ID: {_markdown_opaque(literal_escape)}" in content
    assert f"source ID: {_markdown_opaque(uuid_source_id)}" in content
    assert f"source ID: {_markdown_opaque(string_uuid_source_id)}" in content
    assert f"reference: {_markdown_opaque(actual_control_reference)}" in content
    assert f"reference: {_markdown_opaque(literal_escape_reference)}" in content
    assert f"Locator: {_locator_text(delimiter_bearing_locator)}" in content
    assert f"Locator: {_locator_text(split_locator)}" in content
    assert "uuid=" not in content and "string=" not in content and "0x" not in content


def test_renderer_contains_hostile_identifiers_and_locator_segments_as_inline_code() -> None:
    """Untrusted traceability values cannot create Markdown blocks or active markup."""
    hostile_id = "`</code>\n## injected heading\n- injected list"
    hostile_locator = ("evidence", '`<script>alert("x")</script>\n[link](https://bad.invalid)')
    finding = Finding(
        id=hostile_id,
        statement="A hostile traceability fixture.",
        evidence_refs=(
            EvidenceReference(
                source_type="metric_result", source_id=hostile_id, locator=hostile_locator
            ),
        ),
    )
    request = _request(findings=(finding,), hypotheses=(), limitations=())

    content = build_report(request, _draft(request), NOW).content

    assert _markdown_opaque(hostile_id).startswith("``")
    assert _markdown_opaque(hostile_id).endswith("``")
    assert _locator_text(hostile_locator).startswith("``")
    assert r"\n## injected heading" in content
    assert r"\n[link](https://bad.invalid)" in content
    assert "<script>alert" in content
    assert [line for line in content.splitlines() if line.startswith("## ")] == [
        "## Objective",
        "## Overall Assessment",
        "## Findings",
        "## Possible Explanations",
        "## Analysis Limitations",
        "## Technical Appendix",
    ]
    assert not any(line.startswith("- injected list") for line in content.splitlines())


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
    assert astral_scalar in opaque_astral
    assert r"\uD83D\uDE00" in opaque_surrogate
    assert unbounded_locator.startswith("`[")
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

    assert f"source ID: {opaque_astral}" in content
    assert f"source ID: {opaque_surrogate}" in content
    assert f"Locator: {astral_locator}" in content
    assert f"Locator: {surrogate_locator}" in content
    assert f"Locator: {unbounded_locator}" in content


def test_renderer_honestly_represents_empty_analysis_collections() -> None:
    """Empty findings, hypotheses, and limitations receive deterministic absence text."""
    request = _request(state="no_significant_findings", findings=(), hypotheses=(), limitations=())
    report = build_report(request, _draft(request), NOW)
    assert "No significant findings were identified" in report.content
    assert "No knowledge-grounded possible explanation was produced" in report.content
    assert "No analysis limitation was identified in the supplied result" in report.content
    assert "persist" not in report.content.lower()


@pytest.mark.parametrize("state", ["uncertain", "significant_findings_present"])
def test_empty_findings_do_not_contradict_a_non_empty_source_assessment(state: str) -> None:
    """Valid non-empty overall states retain a neutral empty-finding statement."""
    request = _request(state=state, findings=(), hypotheses=(), limitations=())
    report = build_report(request, _draft(request), NOW)
    assert "No individual finding entries were supplied" in report.content
    assert "No significant findings were identified" not in report.content
    assert f"- Source overall state: `{state}`" in report.content


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
    assert str(request.analysis_result.identity.observation_id) in report.content


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
    ("context_objective", "objective_summary", "heading"),
    [
        ("Assess temperature stability.", None, "Temperature increase"),
        ("Assess temperature stability.", "   ", "Temperature increase"),
        (None, "An invented objective.", "Temperature increase"),
        ("Assess temperature stability.", "Safe summary.", None),
        ("Assess temperature stability.", "Safe summary.", "   "),
        ("Assess temperature stability.", "Safe summary.", "bad\x00heading"),
    ],
)
def test_presentation_validator_requires_objective_summary_and_safe_finding_heading(
    context_objective: str | None, objective_summary: str | None, heading: str | None
) -> None:
    """Objective summaries and required headings are nonblank safe presentation text."""
    request = _request()
    request = request.model_copy(
        update={
            "context": request.context.model_copy(
                update={"analytical_objective": context_objective}
            )
        }
    )
    draft = _draft(request).model_copy(
        update={
            "objective_summary": objective_summary,
            "findings": (
                FindingPresentation(
                    finding_id="finding-temperature",
                    heading=heading,
                    presentation="Temperature is increasing.",
                ),
            ),
        }
    )
    with pytest.raises(ValueError):
        validate_presentation(request, draft)


def test_renderer_uses_validated_finding_order_and_groups_exact_repeated_evidence() -> None:
    """Readable numbers retain exact source ownership, pair grouping, and locator multiplicity."""
    source_a = Finding(
        id="auxiliary",
        statement="Auxiliary event.",
        evidence_refs=(
            EvidenceReference(source_type="metric_result", source_id="metric-a", locator=("one",)),
        ),
    )
    source_b = Finding(
        id="objective",
        statement="Objective event.",
        evidence_refs=(
            EvidenceReference(source_type="metric_result", source_id="metric-a", locator=("two",)),
            EvidenceReference(source_type="metric_result", source_id="metric-a", locator=("two",)),
            EvidenceReference(source_type="alert_result", source_id="alert-b", locator=("three",)),
        ),
    )
    hypothesis = Hypothesis(
        id="explanation",
        statement="Possible explanation.",
        supported_by=("objective", "auxiliary"),
        knowledge_refs=(KnowledgeReference(source_id="manual", reference="section-7"),),
    )
    request = _request(findings=(source_a, source_b), hypotheses=(hypothesis,), limitations=())
    draft = ReportPresentationDraft(
        overall_state="uncertain",
        overall_assessment="The evidence is uncertain.",
        objective_summary="Assess the supplied evidence.",
        findings=(
            FindingPresentation(
                finding_id="objective",
                heading="Objective event",
                presentation="The objective event was observed.",
            ),
            FindingPresentation(
                finding_id="auxiliary",
                heading="Auxiliary event observed",
                presentation="The auxiliary event was observed.",
            ),
        ),
        hypotheses=(
            HypothesisPresentation(
                hypothesis_id="explanation",
                presentation="The pattern may have an explanation.",
            ),
        ),
    )

    content = build_report(request, draft, NOW).content

    assert content.index("### 1. Objective event") < content.index(
        "### 2. Auxiliary event observed"
    )
    assert "### 2. Finding 2" not in content
    assert "Supported by findings: 1, 2" in content
    finding_one = content.split("### Finding 1 traceability", 1)[1].split(
        "### Finding 2 traceability", 1
    )[0]
    assert finding_one.count("Evidence source type: `metric_result`; source ID: `metric-a`") == 1
    assert finding_one.count("Locator: `two`") == 2
    assert "Evidence source type: `alert_result`; source ID: `alert-b`" in finding_one
    assert "Source finding ID: `objective`" in finding_one
    assert "Knowledge source ID: `manual`; reference: `section-7`" in content


def test_renderer_numbers_multiple_possible_explanations_for_appendix_mapping() -> None:
    """Each narrative explanation has the same readable number as its appendix entry."""
    hypotheses = (
        Hypothesis(
            id="first-explanation",
            statement="First possible explanation.",
            supported_by=("finding-temperature",),
            knowledge_refs=(KnowledgeReference(source_id="manual", reference="section-1"),),
        ),
        Hypothesis(
            id="second-explanation",
            statement="Second possible explanation.",
            supported_by=("finding-temperature",),
            knowledge_refs=(KnowledgeReference(source_id="manual", reference="section-2"),),
        ),
    )
    request = _request(hypotheses=hypotheses)
    draft = _draft(request).model_copy(
        update={
            "hypotheses": (
                HypothesisPresentation(
                    hypothesis_id="first-explanation", presentation="First explanation prose."
                ),
                HypothesisPresentation(
                    hypothesis_id="second-explanation", presentation="Second explanation prose."
                ),
            )
        }
    )

    content = build_report(request, draft, NOW).content

    assert content.index("### Possible explanation 1") < content.index("### Possible explanation 2")
    assert content.index("### Possible explanation 1 traceability") < content.index(
        "### Possible explanation 2 traceability"
    )
    assert (
        "### Possible explanation 1 traceability\n- Source hypothesis ID: `first-explanation`"
        in content
    )
    assert (
        "### Possible explanation 2 traceability\n- Source hypothesis ID: `second-explanation`"
        in content
    )


def test_presentation_rejects_direct_raw_operational_context_copy_before_rendering() -> None:
    """A source-key-valid draft cannot copy the complete operator note into an item."""
    note = (
        "This observation covers the primary feedwater loop during controlled startup; "
        "do not treat this note as evidence."
    )
    request = _request(operational_context=note)
    original = _draft(request).findings[0]
    copied = _draft(request).model_copy(
        update={
            "findings": (
                FindingPresentation(
                    finding_id=original.finding_id,
                    heading=original.heading,
                    presentation=note,
                ),
            )
        }
    )

    with pytest.raises(ValueError, match="raw operational context"):
        build_report(request, copied, NOW)


@pytest.mark.parametrize("term", ["pump", "primary pump"])
def test_presentation_allows_short_contextual_term_but_rejects_standalone_copy(term: str) -> None:
    """A shared short term may occur in prose but cannot become its own report content."""
    request = _request(operational_context=term)
    grounded = _draft(request).model_copy(
        update={
            "overall_assessment": (
                f"{term.title()} temperature increased in the available evidence."
            )
        }
    )

    assert build_report(request, grounded, NOW).content

    copied = _draft(request).model_copy(update={"overall_assessment": term})
    with pytest.raises(ValueError, match="raw operational context"):
        build_report(request, copied, NOW)


def test_presentation_skips_non_renderable_operational_context_comparison() -> None:
    """A valid stored note with format controls does not reject an otherwise valid report."""
    request = _request(operational_context="Pump\u200b startup context")

    assert build_report(request, _draft(request), NOW).content


def test_presentation_skips_non_renderable_source_statement_comparison() -> None:
    """Source format controls cannot make an otherwise valid report fail validation."""
    finding = Finding(
        id="finding-pump",
        statement="Pump\u200b temperature increased.",
        evidence_refs=(
            EvidenceReference(
                source_type="metric_result", source_id="metric-run", locator=("evidence", "mean")
            ),
        ),
    )
    request = _request(
        findings=(finding,), hypotheses=(), limitations=(), operational_context="pump"
    )
    draft = ReportPresentationDraft(
        overall_state=request.analysis_result.overall_state,
        overall_assessment="The available evidence remains uncertain.",
        objective_summary="Assess the available process evidence.",
        findings=(
            FindingPresentation(
                finding_id=finding.id,
                heading="Pump temperature increase",
                presentation="Pump temperature increased.",
            ),
        ),
    )

    assert build_report(request, draft, NOW).content


def test_presentation_allows_source_backed_contextual_terminology() -> None:
    """A term shared with the note can faithfully present the matching source item."""
    finding = Finding(
        id="finding-primary-loop",
        statement="Primary loop temperature is increasing.",
        evidence_refs=(
            EvidenceReference(
                source_type="metric_result", source_id="metric-run", locator=("evidence", "mean")
            ),
        ),
    )
    request = _request(
        findings=(finding,),
        hypotheses=(),
        limitations=(),
        operational_context="During startup, operators call this equipment the primary loop.",
    )
    draft = ReportPresentationDraft(
        overall_state=request.analysis_result.overall_state,
        overall_assessment="The available evidence remains uncertain.",
        objective_summary="Assess the available process evidence.",
        findings=(
            FindingPresentation(
                finding_id=finding.id,
                heading="Primary loop temperature increase",
                presentation=finding.statement,
            ),
        ),
    )

    report = build_report(request, draft, NOW)

    assert finding.statement in report.content


def test_presentation_allows_matching_canonical_source_statement() -> None:
    """A note contained in its source statement remains renderable under that source key."""
    finding = Finding(
        id="finding-primary-loop",
        statement="Primary loop temperature is increasing in the current analysis window.",
        evidence_refs=(
            EvidenceReference(
                source_type="metric_result", source_id="metric-run", locator=("evidence", "mean")
            ),
        ),
    )
    request = _request(
        findings=(finding,),
        hypotheses=(),
        limitations=(),
        operational_context="Primary loop temperature is increasing",
    )
    draft = ReportPresentationDraft(
        overall_state=request.analysis_result.overall_state,
        overall_assessment="The available evidence remains uncertain.",
        objective_summary="Assess the available process evidence.",
        findings=(
            FindingPresentation(
                finding_id=finding.id,
                heading="Primary loop temperature increase",
                presentation=request.context.operational_context,
            ),
        ),
    )

    report = build_report(request, draft, NOW)

    assert request.context.operational_context in report.content


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


def test_renderer_escapes_active_dynamic_markdown_syntax_without_blanket_punctuation() -> None:
    """Dynamic active syntax is inert while ordinary prose punctuation remains readable."""
    request = _request()
    presentation = "[label](https://example.invalid)\n# heading\n> quote\n~~~"
    draft = _draft(request).model_copy(update={"overall_assessment": presentation})
    report = build_report(request, draft, NOW)
    assert r"\[label\](https://example.invalid) # heading \> quote ~~~" in report.content
    headings = [line for line in report.content.splitlines() if line.startswith("#")]
    assert headings == [
        "# Observation Report",
        "## Objective",
        "## Overall Assessment",
        "## Findings",
        "### 1. Temperature increase observed",
        "## Possible Explanations",
        "### Possible explanation 1",
        "## Analysis Limitations",
        "### Limitation 1",
        "## Technical Appendix",
        "### Report details",
        "### Finding 1 traceability",
        "### Possible explanation 1 traceability",
        "### Limitation 1 traceability",
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
