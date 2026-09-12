"""Deterministic validation and rendering of report presentation drafts."""

from __future__ import annotations

import string
import unicodedata
from collections.abc import Hashable, Iterable
from datetime import datetime, timedelta
from re import findall, fullmatch
from uuid import UUID

from app.reasoning.contracts import EvidenceReference, Hypothesis, Limitation
from app.reporting.contracts import (
    ObservationReport,
    ReportGenerationRequest,
    ReportPresentationDraft,
)

_MARKDOWN_ESCAPE_TABLE = str.maketrans(
    {character: f"\\{character}" for character in string.punctuation}
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
    for item in (*draft.findings, *draft.hypotheses, *draft.limitations):
        _validate_presentation_text(item.presentation)
    return draft


def build_report(
    request: ReportGenerationRequest, draft: ReportPresentationDraft, generated_at: datetime
) -> ObservationReport:
    """Build one immutable Markdown report from validated source-keyed presentation."""
    validated = validate_presentation(request, draft)
    if generated_at.tzinfo is None or generated_at.utcoffset() != timedelta(0):
        raise ValueError("generated_at must be UTC")
    result = request.analysis_result
    finding_text = {item.finding_id: item.presentation for item in validated.findings}
    hypothesis_text = {item.hypothesis_id: item.presentation for item in validated.hypotheses}
    limitation_text = {item.limitation_index: item.presentation for item in validated.limitations}
    lines = [
        "# Observation Report",
        "",
        f"Observation ID: {_markdown_opaque(result.identity.observation_id)}",
        f"Observation Run ID: {_markdown_opaque(result.identity.observation_run_id)}",
    ]
    lines.extend(
        (
            "",
            "## Overall Assessment",
            *_presentation_lines(validated.overall_assessment),
            "",
            f"Source overall state: `{result.overall_state}`.",
            "",
            "## Findings",
        )
    )
    if not result.findings:
        lines.append(_empty_findings_text(result.overall_state))
    for finding in result.findings:
        lines.extend(
            (
                "",
                f"### Finding ID: {_markdown_opaque(finding.id)}",
                *_presentation_lines(finding_text[finding.id]),
            )
        )
        lines.extend(_reference_lines("Evidence references", finding.evidence_refs))
    lines.extend(("", "## Possible Explanations"))
    if not result.hypotheses:
        lines.append(
            "No knowledge-grounded possible explanation was produced by the supplied "
            "analysis result."
        )
    for hypothesis in result.hypotheses:
        lines.extend(
            (
                "",
                f"### Possible explanation ID: {_markdown_opaque(hypothesis.id)}",
                *_presentation_lines(hypothesis_text[hypothesis.id]),
                "This is a possible explanation, not a confirmed cause.",
                "Supported by findings: " + _inline_values(hypothesis.supported_by),
            )
        )
        lines.extend(_knowledge_reference_lines(hypothesis))
    lines.extend(("", "## Analysis Limitations"))
    if not result.limitations:
        lines.append("No analysis limitation was identified in the supplied result.")
    for index, limitation in enumerate(result.limitations):
        lines.extend(
            (
                "",
                f"### Limitation {index + 1} (code: {_markdown_opaque(limitation.code)})",
                *_presentation_lines(limitation_text[index]),
                _limitation_details(limitation),
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
    return _normalize_prose(value).translate(_MARKDOWN_ESCAPE_TABLE)


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


def _reference_lines(label: str, references: tuple[EvidenceReference, ...]) -> list[str]:
    """Format canonical finding evidence references without model-authored content."""
    return [label + ":"] + [
        "- "
        + f"Source type: {_markdown_opaque(reference.source_type)}; "
        + f"source ID: {_markdown_opaque(reference.source_id)}; "
        + f"locator: {_locator_text(reference.locator)}"
        for reference in references
    ]


def _knowledge_reference_lines(hypothesis: Hypothesis) -> list[str]:
    """Format canonical hypothesis knowledge references from the source artifact."""
    return ["Knowledge references:"] + [
        f"- Source ID: {_markdown_opaque(reference.source_id)}; "
        f"reference: {_markdown_opaque(reference.reference)}"
        for reference in hypothesis.knowledge_refs
    ]


def _inline_values(values: tuple[str, ...]) -> str:
    """Render source identifiers as individually inspectable exact code values."""
    return "[" + ", ".join(_markdown_opaque(value) for value in values) + "]"


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
