"""Focused canonical Alert evidence-reference tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.alerts.analyzer import analyze_current, compare_occurrences
from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderImportance,
    AlertProviderRecord,
    AlertProviderScope,
)
from app.alerts.evidence_refs import EvidenceReferenceError, encode_dynamic_segment
from app.alerts.normalization import normalize_current
from app.alerts.result_builder import AlertResultBuilder


def _context() -> AlertLensExecutionContext:
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=uuid4(),
            observation_run_id=uuid4(),
            lens_id="alerts",
            lens_run_id=uuid4(),
        ),
        provider_scope=AlertProviderScope(source="fixture", query="opaque"),
        analysis_window=AlertAnalysisWindow(
            **{"from": datetime(2026, 9, 1, tzinfo=UTC), "to": datetime(2026, 9, 1, 1, tzinfo=UTC)}
        ),
        lens_name="Alert fixture",
    )


def _assembled(
    *,
    duplicate_current: bool = False,
    duplicate_comparison: bool = False,
    omit_duration: bool = False,
    omit_importance: bool = False,
):
    context = _context()
    records = normalize_current(
        type(
            "Response",
            (),
            {
                "records": (
                    AlertProviderRecord(
                        id="id / % Ж",
                        title="fixture",
                        started_at=context.analysis_window.from_,
                        source_status="active",
                        provider_importance=AlertProviderImportance(
                            type="type / Ж", value="value % space"
                        ),
                    ),
                )
                * (2 if duplicate_current else 1)
            },
        )(),
        context.analysis_window,
        context.analysis_window.to,
    )
    evidence = analyze_current(records[:1])
    reference = compare_occurrences("1d / Ж", evidence, evidence)
    return (
        context,
        records,
        evidence.model_copy(
            update={
                "comparisons": (reference,) * (2 if duplicate_comparison else 1),
                "duration_statistics": None if omit_duration else evidence.duration_statistics,
                "provider_importance_distribution": (
                    None if omit_importance else evidence.provider_importance_distribution
                ),
            }
        ),
    )


def _build(refs: tuple[str, ...], **kwargs: object) -> object:
    context, records, evidence = _assembled(**kwargs)
    return AlertResultBuilder().completed(
        context,
        records,
        evidence,
        AlertAgentCompletion(
            findings=(AlertFinding(id="f", statement="grounded", evidence_refs=refs),),
            overall_importance="high",
        ),
    )[0]


def test_all_canonical_evidence_target_forms_resolve() -> None:
    alert_id = encode_dynamic_segment("id / % Ж")
    importance_type = encode_dynamic_segment("type / Ж")
    importance_value = encode_dynamic_segment("value % space")
    offset = encode_dynamic_segment("1d / Ж")
    refs = (
        f"alert://current/{alert_id}",
        "alert://aggregate/alert_activity/record_count",
        "alert://aggregate/alert_activity/occurrence_count",
        "alert://aggregate/status_distribution/active",
        "alert://aggregate/status_distribution/resolved",
        "alert://aggregate/status_distribution/unknown",
        "alert://aggregate/duration_statistics/min_seconds",
        "alert://aggregate/duration_statistics/max_seconds",
        "alert://aggregate/duration_statistics/average_seconds",
        f"alert://aggregate/provider_importance/{importance_type}/{importance_value}",
        f"alert://comparison/{offset}",
    )
    result = _build(refs)
    assert all(ref.isascii() for ref in refs)
    assert result.findings[0].evidence_refs == refs


def test_evidence_refs_reject_every_noncanonical_grammar_case() -> None:
    valid = "alert://current/id%20%2F%20%25%20%D0%96"
    invalid = (
        "alert://current/id / % Ж",
        "alert://current/id%20%2f",
        "alert://current/id%",
        "alert://current/id%2",
        "alert://current/%FF",
        "alert://current/id%41",
        "alert://current/",
        "alert://current/id?x=y",
        "alert://current/id#fragment",
        "ALERT://current/id",
        "Alert://current/id",
        "alert://CURRENT/id",
        "alert://user@current/id",
        "alert://current:1/id",
        "alert://aggregate/alert_activity",
        "alert://aggregate/alert_activity/record_count/extra",
        "alert://aggregate/wrong/record_count",
        "alert://comparison",
        "alert://comparison/1d/extra",
        "alert://current/id%00",
    )
    assert _build((valid,))
    for reference in invalid:
        with pytest.raises(EvidenceReferenceError):
            _build((reference,))


def test_builder_rejects_unavailable_unresolved_transient_or_ambiguous_targets() -> None:
    for reference, kwargs in (
        ("alert://current/missing", {}),
        ("alert://comparison/missing", {}),
        ("alert://aggregate/provider_importance/missing/value", {}),
        ("alert://comparison/1d%20%2F%20%D0%96", {"duplicate_comparison": True}),
        ("alert://current/id%20%2F%20%25%20%D0%96", {"duplicate_current": True}),
        ("alert://optional/recurrence", {}),
        ("alert://aggregate/duration_statistics/min_seconds", {"omit_duration": True}),
        (
            "alert://aggregate/provider_importance/type%20%2F%20%D0%96/value%20%25%20space",
            {"omit_importance": True},
        ),
    ):
        with pytest.raises(EvidenceReferenceError):
            _build((reference,), **kwargs)
