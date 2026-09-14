"""Deterministic validation and rendering of report presentation drafts."""

from __future__ import annotations

import unicodedata
from collections.abc import Hashable, Iterable
from datetime import UTC, datetime, timedelta
from re import findall, fullmatch
from uuid import UUID

from app.reasoning.contracts import EvidenceReference, Hypothesis, Limitation
from app.reporting.contracts import (
    ObservationReport,
    ReportGenerationRequest,
    ReportPresentationDraft,
)


def validate_presentation(
    request: ReportGenerationRequest, draft: ReportPresentationDraft
) -> ReportPresentationDraft:
    """Require exact source-key coverage before any Markdown is rendered."""
    if not isinstance(draft, ReportPresentationDraft):
        raise ValueError("report presentation must use the strict draft contract")
    source = request.analysis_result
    if draft.overall_state != source.overall_state:
        raise ValueError("presentation overall state must match the analysis result")
    _validate_presentation_text(draft.overall_assessment)
    _validate_no_raw_operational_context_disclosure(
        request.context.operational_context, draft.overall_assessment
    )
    objective = request.context.analytical_objective
    objective_is_present = bool(objective and objective.strip())
    if objective_is_present != (draft.objective_summary is not None):
        raise ValueError("presentation objective summary must match the admitted objective")
    if draft.objective_summary is not None:
        _validate_presentation_text(draft.objective_summary)
        _validate_no_raw_operational_context_disclosure(
            request.context.operational_context, draft.objective_summary
        )
    _validate_exact_keys(
        "finding IDs",
        (item.id for item in source.findings),
        (item.finding_id for item in draft.findings),
    )
    _validate_exact_keys(
        "hypothesis IDs",
        (item.id for item in source.hypotheses),
        (item.hypothesis_id for item in draft.hypotheses),
    )
    _validate_exact_keys(
        "limitation positions",
        range(len(source.limitations)),
        (item.limitation_index for item in draft.limitations),
    )
    source_findings = {item.id: item for item in source.findings}
    source_hypotheses = {item.id: item for item in source.hypotheses}
    for item in draft.findings:
        _validate_presentation_text(item.presentation)
        _validate_no_raw_operational_context_disclosure(
            request.context.operational_context,
            item.presentation,
            source_statement=source_findings[item.finding_id].statement,
        )
    for item in draft.hypotheses:
        _validate_presentation_text(item.presentation)
        _validate_no_raw_operational_context_disclosure(
            request.context.operational_context,
            item.presentation,
            source_statement=source_hypotheses[item.hypothesis_id].statement,
        )
    for item in draft.limitations:
        _validate_presentation_text(item.presentation)
        _validate_no_raw_operational_context_disclosure(
            request.context.operational_context, item.presentation
        )
    for item in draft.findings:
        _required_finding_heading(item.heading)
        _validate_no_raw_operational_context_disclosure(
            request.context.operational_context,
            item.heading,
            source_statement=source_findings[item.finding_id].statement,
        )
    return draft


def build_report(
    request: ReportGenerationRequest, draft: ReportPresentationDraft, generated_at: datetime
) -> ObservationReport:
    """Build one immutable Markdown report from validated source-keyed presentation."""
    validated = validate_presentation(request, draft)
    if generated_at.tzinfo is None or generated_at.utcoffset() != timedelta(0):
        raise ValueError("generated_at must be UTC")
    result = request.analysis_result
    findings = tuple(validated.findings)
    finding_text = {item.finding_id: item.presentation for item in findings}
    finding_heading = {
        item.finding_id: _required_finding_heading(item.heading) for item in findings
    }
    hypothesis_text = {item.hypothesis_id: item.presentation for item in validated.hypotheses}
    limitation_text = {item.limitation_index: item.presentation for item in validated.limitations}
    finding_numbers = {item.finding_id: index for index, item in enumerate(findings, start=1)}
    lines = ["# Observation Report", ""]
    if validated.objective_summary is not None:
        lines.extend(("## Objective", *_presentation_lines(validated.objective_summary), ""))
    else:
        lines.append("No analytical objective was supplied for this Observation.")
        lines.append("")
    lines.extend(
        (
            f"Observation ID excerpt: {_markdown_opaque(str(result.identity.observation_id)[:8])} "
            "(orientation only; not a unique identifier).",
            "Observed window (UTC): "
            f"{_markdown_opaque(_utc_timestamp(request.analysis_window.from_))} to "
            f"{_markdown_opaque(_utc_timestamp(request.analysis_window.to))}.",
        )
    )
    lines.extend(
        (
            "",
            "## Overall Assessment",
            *_presentation_lines(validated.overall_assessment),
            "",
            f"Analytical state: {_state_label(result.overall_state)}.",
            "",
            "## Findings",
        )
    )
    if not result.findings:
        lines.append(_empty_findings_text(result.overall_state))
    for index, presented_finding in enumerate(findings, start=1):
        heading = finding_heading[presented_finding.finding_id]
        lines.extend(
            (
                "",
                f"### {index}. {_markdown_prose(heading)}",
                *_presentation_lines(finding_text[presented_finding.finding_id]),
            )
        )
    lines.extend(("", "## Possible Explanations"))
    if not result.hypotheses:
        lines.append(
            "No knowledge-grounded possible explanation was produced by the supplied "
            "analysis result."
        )
    for index, hypothesis in enumerate(result.hypotheses, start=1):
        supported_numbers = tuple(
            finding_numbers[finding_id] for finding_id in hypothesis.supported_by
        )
        lines.extend(
            (
                "",
                f"### Possible explanation {index}",
                *_presentation_lines(hypothesis_text[hypothesis.id]),
                "This is a possible explanation, not a confirmed cause.",
                "Supported by findings: " + _finding_numbers(supported_numbers),
            )
        )
    lines.extend(("", "## Analysis Limitations"))
    if not result.limitations:
        lines.append("No analysis limitation was identified in the supplied result.")
    for index, _limitation in enumerate(result.limitations):
        lines.extend(
            (
                "",
                f"### Limitation {index + 1}",
                *_presentation_lines(limitation_text[index]),
            )
        )
    lines.extend(("", "## Technical Appendix", "", "### Report details"))
    lines.extend(
        (
            f"- Full Observation ID: {_markdown_opaque(result.identity.observation_id)}",
            f"- Full Observation Run ID: {_markdown_opaque(result.identity.observation_run_id)}",
            f"- Source overall state: {_markdown_opaque(result.overall_state)}",
            f"- Generated at (UTC): {_markdown_opaque(_utc_timestamp(generated_at))}",
        )
    )
    source_findings = {item.id: item for item in result.findings}
    for index, presented_finding in enumerate(findings, start=1):
        finding = source_findings[presented_finding.finding_id]
        lines.extend(
            (
                "",
                f"### Finding {index} traceability",
                f"- Source finding ID: {_markdown_opaque(finding.id)}",
            )
        )
        lines.extend(_grouped_evidence_lines(finding.evidence_refs))
    for index, hypothesis in enumerate(result.hypotheses, start=1):
        lines.extend(("", f"### Possible explanation {index} traceability"))
        lines.extend(
            (
                f"- Source hypothesis ID: {_markdown_opaque(hypothesis.id)}",
                "- Supported source finding IDs: " + _inline_values(hypothesis.supported_by),
            )
        )
        lines.extend(_knowledge_reference_lines(hypothesis))
    for index, limitation in enumerate(result.limitations, start=1):
        lines.extend(
            (
                "",
                f"### Limitation {index} traceability",
                f"- Code: {_markdown_opaque(limitation.code)}",
                f"- {_limitation_details(limitation)}",
            )
        )
    return ObservationReport(
        observation_id=result.identity.observation_id,
        observation_run_id=result.identity.observation_run_id,
        generated_at=generated_at,
        content="\n".join(lines),
    )


def _validate_exact_keys(
    label: str, source: Iterable[Hashable], presented: Iterable[Hashable]
) -> None:
    """Reject duplicate, unknown, or missing presentation source keys."""
    source_keys = tuple(source)
    presented_keys = tuple(presented)
    if len(source_keys) != len(set(source_keys)):
        raise ValueError(f"source {label} must be unique")
    if len(presented_keys) != len(set(presented_keys)) or set(presented_keys) != set(source_keys):
        raise ValueError(f"presentation must contain exact unique {label}")


def _validate_presentation_text(value: str) -> None:
    """Reject blank model prose without trying to classify its meaning."""
    if not value.strip():
        raise ValueError("presentation text must not be blank")
    _normalize_prose(value)


def _validate_no_raw_operational_context_disclosure(
    operational_context: str | None, value: str | None, *, source_statement: str | None = None
) -> None:
    """Reject complete raw-note copying unless it is the matching canonical source statement."""
    if operational_context is None or value is None:
        return
    normalized_context = _normalized_comparable_text(operational_context)
    if normalized_context is None:
        return
    normalized_value = _normalize_prose(value)
    comparable_context = normalized_context.casefold()
    if comparable_context not in normalized_value.casefold():
        return
    normalized_source = (
        _normalized_comparable_text(source_statement) if source_statement is not None else None
    )
    if normalized_source is not None and comparable_context in normalized_source.casefold():
        return
    if normalized_value.casefold() != comparable_context and _is_short_contextual_term(
        normalized_context
    ):
        return
    raise ValueError("presentation must not disclose raw operational context")


def _normalized_comparable_text(value: str) -> str | None:
    """Normalize text for comparison only when it is valid report prose."""
    try:
        return _normalize_prose(value)
    except ValueError:
        return None


def _is_short_contextual_term(value: str) -> bool:
    """Identify a compact term-like note that may occur within grounded report prose."""
    return (
        len(value) <= 48
        and len(value.split()) <= 4
        and not any(character in value for character in ".!?;:\n\r")
    )


def _required_finding_heading(value: str | None) -> str:
    """Require a source-grounded, nonblank heading for every presented finding."""
    if value is None:
        raise ValueError("presentation finding heading must be supplied")
    _validate_presentation_text(value)
    return value


def _presentation_lines(value: str) -> list[str]:
    """Contain normalized model prose inside one renderer-owned blockquote."""
    return [f"> {_markdown_prose(value)}"]


def _empty_findings_text(overall_state: str) -> str:
    """Describe an empty finding set without contradicting the source assessment."""
    if overall_state == "no_significant_findings":
        return "No significant findings were identified in the available analysis result."
    return "No individual finding entries were supplied by the analysis result."


def _markdown_prose(value: str) -> str:
    """Render model prose as normalized escaped Markdown content."""
    normalized = _normalize_prose(value)
    # The value is always emitted after a renderer-owned prefix.  Escape only syntax
    # that could create markup, links, HTML, or a block boundary in that context.
    escaped: list[str] = []
    for character in normalized:
        if character in "\\`[]<>*_":
            escaped.append("\\" + character)
        else:
            escaped.append(character)
    return "".join(escaped)


def _normalize_prose(value: str) -> str:
    """Collapse structural whitespace and reject invisible or non-renderable controls."""
    if any(
        unicodedata.category(character) == "Cf"
        or (unicodedata.category(character) == "Cc" and not character.isspace())
        for character in value
    ):
        raise ValueError("report text contains a non-renderable control character")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("report text must contain visible content")
    return normalized


def _markdown_opaque(value: UUID | str | int) -> str:
    """Render an opaque value as exact, inert, human-readable inline code."""
    if isinstance(value, UUID):
        serialized_value = str(value)
    elif type(value) is str:
        serialized_value = value
    elif type(value) is int:
        serialized_value = _decimal_integer(value)
    else:  # pragma: no cover - callers are constrained by domain contracts.
        raise TypeError("unsupported opaque value type")
    return _markdown_inline_code(_display_text(serialized_value))


def _markdown_inline_code(value: str) -> str:
    """Fence a renderer-owned value so untrusted content cannot own Markdown syntax."""
    longest_run = max((len(run) for run in findall(r"`+", value)), default=0)
    fence = "`" * (longest_run + 1)
    return f"{fence}{value}{fence}"


def _decimal_integer(value: int) -> str:
    """Render an arbitrarily large integer in decimal without interpreter digit limits."""
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    remaining = abs(value)
    digits: list[str] = []
    while remaining:
        remaining, digit = divmod(remaining, 10)
        digits.append(chr(ord("0") + digit))
    return sign + "".join(reversed(digits))


def _display_text(value: str, *, quote_for_locator: bool = False) -> str:
    """Encode controls reversibly while leaving ordinary visible text readable."""
    rendered: list[str] = []
    for character in value:
        if character == "\\":
            rendered.append("\\\\")
        elif quote_for_locator and character == '"':
            rendered.append('\\"')
        elif character == "\n":
            rendered.append("\\n")
        elif character == "\r":
            rendered.append("\\r")
        elif character == "\t":
            rendered.append("\\t")
        elif character == "\f":
            rendered.append("\\f")
        elif character == "\v":
            rendered.append("\\v")
        elif unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
            rendered.append(f"\\u{ord(character):04X}")
        else:
            rendered.append(character)
    return "".join(rendered)


def _grouped_evidence_lines(references: tuple[EvidenceReference, ...]) -> list[str]:
    """Group exact evidence by source pair while retaining locator multiplicity and order."""
    groups: dict[tuple[str, UUID | str], list[EvidenceReference]] = {}
    for reference in references:
        groups.setdefault((reference.source_type, reference.source_id), []).append(reference)
    lines: list[str] = []
    for (source_type, source_id), grouped_references in groups.items():
        lines.append(
            f"- Evidence source type: {_markdown_opaque(source_type)}; "
            f"source ID: {_markdown_opaque(source_id)}"
        )
        lines.extend(
            f"- Locator: {_locator_text(reference.locator)}" for reference in grouped_references
        )
    return lines


def _knowledge_reference_lines(hypothesis: Hypothesis) -> list[str]:
    """Format canonical hypothesis knowledge references from the source artifact."""
    return ["- Knowledge references:"] + [
        f"- Knowledge source ID: {_markdown_opaque(reference.source_id)}; "
        f"reference: {_markdown_opaque(reference.reference)}"
        for reference in hypothesis.knowledge_refs
    ]


def _inline_values(values: tuple[str, ...]) -> str:
    """Render source identifiers as individually inspectable exact code values."""
    return "[" + ", ".join(_markdown_opaque(value) for value in values) + "]"


def _finding_numbers(values: tuple[int, ...]) -> str:
    """Render report-local finding numbers as readable cross-references."""
    return ", ".join(str(value) for value in values)


def _state_label(overall_state: str) -> str:
    """Return the fixed human label for the source analytical state."""
    return {
        "no_significant_findings": "No significant findings identified",
        "significant_findings_present": "Significant findings present",
        "uncertain": "Uncertain",
    }[overall_state]


def _utc_timestamp(value: datetime) -> str:
    """Preserve an exact UTC timestamp in a concise stable display form."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _locator_text(locator: tuple[str | int, ...]) -> str:
    """Render exact locator segments in conventional dotted and decimal-index notation."""
    parts: list[str] = []
    for segment in locator:
        if type(segment) is int:
            parts.append(f"[{_decimal_integer(segment)}]")
        elif fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", segment):
            parts.append(("." if parts else "") + segment)
        else:
            parts.append(f'["{_display_text(segment, quote_for_locator=True)}"]')
    return _markdown_inline_code("".join(parts))


def _limitation_details(limitation: Limitation) -> str:
    """Render the exact structured limitation fields in a deterministic form."""
    details = [
        f"lens ID {_markdown_opaque(limitation.lens_id)}",
        f"lens type {_markdown_opaque(limitation.lens_type)}",
    ]
    if limitation.code == "partial_lens_analysis" and limitation.component is not None:
        details.append(f"component {_markdown_opaque(limitation.component)}")
    return "Source limitation: " + "; ".join(details) + "."
