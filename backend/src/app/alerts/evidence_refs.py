"""Canonical Alert finding-evidence URI parsing and final-target resolution."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.alerts.contracts import AlertMandatoryEvidence, CanonicalAlertRecord

_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_HEX = frozenset("0123456789ABCDEF")


class EvidenceReferenceError(ValueError):
    """Report a malformed, non-canonical, ambiguous, or unavailable evidence reference."""


@dataclass(frozen=True)
class EvidenceReferenceTarget:
    """Decoded identity of one canonical evidence-reference target."""

    kind: str
    values: tuple[str, ...]


def encode_dynamic_segment(value: str) -> str:
    """Encode one dynamic URI segment using canonical UTF-8 uppercase escapes."""
    return "".join(
        char if char in _UNRESERVED else f"%{byte:02X}"
        for byte in value.encode("utf-8")
        for char in (chr(byte),)
    )


def _decode_dynamic_segment(segment: str) -> str:
    if not segment:
        raise EvidenceReferenceError("dynamic evidence-reference segment is empty")
    raw = bytearray()
    index = 0
    while index < len(segment):
        character = segment[index]
        if character in _UNRESERVED:
            raw.append(ord(character))
            index += 1
        elif character == "%":
            if index + 2 >= len(segment) or any(
                c not in _HEX for c in segment[index + 1 : index + 3]
            ):
                raise EvidenceReferenceError("evidence-reference escape must be uppercase %HH")
            raw.append(int(segment[index + 1 : index + 3], 16))
            index += 3
        else:
            raise EvidenceReferenceError(
                "dynamic evidence-reference segment is not canonical ASCII"
            )
    try:
        decoded = bytes(raw).decode("utf-8")
    except UnicodeDecodeError as error:
        raise EvidenceReferenceError(
            "dynamic evidence-reference segment is not valid UTF-8"
        ) from error
    if not decoded or encode_dynamic_segment(decoded) != segment:
        raise EvidenceReferenceError(
            "dynamic evidence-reference segment is not canonically encoded"
        )
    return decoded


def parse_evidence_reference(reference: str) -> EvidenceReferenceTarget:
    """Parse an exact canonical Alert evidence URI without URL normalization."""
    if not reference.isascii() or any(ord(char) < 0x20 or ord(char) == 0x7F for char in reference):
        raise EvidenceReferenceError("evidence reference must be printable ASCII")
    if "?" in reference or "#" in reference or not reference.startswith("alert://"):
        raise EvidenceReferenceError("evidence reference has an invalid URI prefix or suffix")
    remainder = reference.removeprefix("alert://")
    if not remainder or "@" in remainder.split("/", 1)[0] or ":" in remainder.split("/", 1)[0]:
        raise EvidenceReferenceError("evidence reference authority is invalid")
    segments = remainder.split("/")
    if segments[0] == "current" and len(segments) == 2:
        return EvidenceReferenceTarget("current", (_decode_dynamic_segment(segments[1]),))
    if (
        segments[:2] == ["aggregate", "alert_activity"]
        and len(segments) == 3
        and segments[2]
        in {
            "record_count",
            "occurrence_count",
        }
    ):
        return EvidenceReferenceTarget("activity", (segments[2],))
    if (
        segments[:2] == ["aggregate", "status_distribution"]
        and len(segments) == 3
        and segments[2]
        in {
            "active",
            "resolved",
            "unknown",
        }
    ):
        return EvidenceReferenceTarget("status", (segments[2],))
    if (
        segments[:2] == ["aggregate", "duration_statistics"]
        and len(segments) == 3
        and segments[2]
        in {
            "min_seconds",
            "max_seconds",
            "average_seconds",
        }
    ):
        return EvidenceReferenceTarget("duration", (segments[2],))
    if segments[:2] == ["aggregate", "provider_importance"] and len(segments) == 4:
        return EvidenceReferenceTarget(
            "importance",
            (_decode_dynamic_segment(segments[2]), _decode_dynamic_segment(segments[3])),
        )
    if segments[0] == "comparison" and len(segments) == 2:
        return EvidenceReferenceTarget("comparison", (_decode_dynamic_segment(segments[1]),))
    raise EvidenceReferenceError("evidence reference has an invalid static path shape")


def resolve_evidence_reference(
    reference: str,
    records: tuple[CanonicalAlertRecord, ...],
    evidence: AlertMandatoryEvidence,
) -> None:
    """Require a canonical URI to identify exactly one assembled persisted target."""
    target = parse_evidence_reference(reference)
    if target.kind == "current":
        matches = sum(record.id == target.values[0] for record in records)
    elif target.kind in {"activity", "status"}:
        matches = 1
    elif target.kind == "duration":
        matches = int(evidence.duration_statistics is not None)
    elif target.kind == "importance":
        distribution = evidence.provider_importance_distribution
        matches = int(
            distribution is not None
            and distribution.type == target.values[0]
            and target.values[1] in distribution.values
        )
    else:
        matches = sum(comparison.offset == target.values[0] for comparison in evidence.comparisons)
    if matches != 1:
        raise EvidenceReferenceError(
            "evidence reference does not resolve to exactly one final target"
        )


def resolve_evidence_references(
    references: tuple[str, ...],
    records: tuple[CanonicalAlertRecord, ...],
    evidence: AlertMandatoryEvidence,
) -> None:
    """Validate every finding reference against the assembled result target index."""
    if any(count != 1 for count in Counter(record.id for record in records).values()):
        raise EvidenceReferenceError("current Alert IDs must identify exactly one final target")
    for reference in references:
        resolve_evidence_reference(reference, records, evidence)
