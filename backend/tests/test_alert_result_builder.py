"""Focused canonical Alert evidence-reference tests."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.alerts.analyzer import analyze_current, compare_occurrences
from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertMandatoryEvidence,
    AlertOptionalToolExecution,
    AlertProviderImportance,
    AlertProviderRecord,
    AlertProviderScope,
    AlertUnsuccessfulToolCall,
    CompletedAlertAnalysisResult,
    PartialAlertAnalysisResult,
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


def _payload(result: object) -> dict[str, object]:
    return result.model_dump(mode="python", by_alias=True, exclude_none=False)


def test_builder_enforces_exact_envelope_identity_time_provenance_and_strict_fields() -> None:
    context, records, evidence = _assembled()
    builder = AlertResultBuilder(clock=lambda: datetime(2026, 9, 1, 2, tzinfo=UTC))
    completed, _ = builder.completed(
        context, records, evidence, AlertAgentCompletion(findings=(), overall_importance="high")
    )
    partial, _ = builder.usable(
        context,
        records,
        evidence,
        AlertAgentCompletion(findings=(), overall_importance="high"),
        True,
        False,
    )
    reference_partial, _ = builder.usable(
        context,
        records,
        evidence,
        AlertAgentCompletion(findings=(), overall_importance="high"),
        False,
        True,
    )
    assert CompletedAlertAnalysisResult.model_validate(_payload(completed)) == completed
    assert PartialAlertAnalysisResult.model_validate(_payload(partial)) == partial
    assert (
        PartialAlertAnalysisResult.model_validate(_payload(reference_partial)) == reference_partial
    )
    for field, value in (
        ("schema_version", "2.0"),
        ("lens_type", "metric"),
        ("status", "partial"),
        ("unknown", "forbidden"),
    ):
        payload = _payload(completed)
        payload[field] = value
        with pytest.raises(ValidationError):
            CompletedAlertAnalysisResult.model_validate(payload)
    for identity_field, value in (
        ("observation_id", uuid4()),
        ("observation_run_id", uuid4()),
        ("lens_id", "other"),
        ("lens_run_id", uuid4()),
    ):
        with pytest.raises(ValueError):
            builder._validate_context_correlation(
                completed.model_copy(
                    update={
                        "identity": completed.identity.model_copy(update={identity_field: value})
                    }
                ),
                context,
            )
    for mutation in (
        {"analysis_timestamp": context.analysis_window.to + timedelta(seconds=1)},
        {"analysis_timestamp": context.analysis_window.to.astimezone(timezone(timedelta(hours=2)))},
        {
            "analysis_window": context.analysis_window.model_copy(
                update={"from_": context.analysis_window.from_ + timedelta(seconds=1)}
            )
        },
        {
            "analysis_window": context.analysis_window.model_copy(
                update={"to": context.analysis_window.to + timedelta(seconds=1)}
            )
        },
        {
            "analysis_window": context.analysis_window.model_copy(
                update={"to": context.analysis_window.to.astimezone(timezone(timedelta(hours=2)))}
            )
        },
        {"provenance": completed.provenance.model_copy(update={"source_provider": "other"})},
        {
            "provenance": completed.provenance.model_copy(
                update={
                    "generated_at": completed.provenance.generated_at.astimezone(
                        timezone(timedelta(hours=2))
                    )
                }
            )
        },
    ):
        mutated = completed.model_copy(update=mutation)
        with pytest.raises(ValueError):
            builder._validate_context_correlation(mutated, context)
    completed_with_reason = _payload(completed)
    completed_with_reason["reason"] = {
        "code": "invalid_records",
        "component": "current_normalization",
    }
    with pytest.raises(ValidationError):
        CompletedAlertAnalysisResult.model_validate(completed_with_reason)
    payload = _payload(partial)
    payload.pop("reason")
    with pytest.raises(ValidationError):
        PartialAlertAnalysisResult.model_validate(payload)
    for reason in (
        {"code": "result_validation_failed", "component": "alert_result_builder"},
        {"code": "invalid_records", "component": "reference_periods"},
    ):
        payload = _payload(partial)
        payload["reason"] = reason
        with pytest.raises(ValidationError):
            PartialAlertAnalysisResult.model_validate(payload)
    with pytest.raises(ValueError, match="generated_at must use UTC"):
        AlertResultBuilder(
            clock=lambda: datetime(2026, 9, 1, 2, tzinfo=timezone(timedelta(hours=2)))
        ).completed(
            context, records, evidence, AlertAgentCompletion(findings=(), overall_importance="high")
        )


def test_builder_enforces_exact_activity_status_lifecycle_duration_and_importance_invariants() -> (
    None
):
    context, records, evidence = _assembled()
    result = _build(())
    assert CompletedAlertAnalysisResult.model_validate(_payload(result)) == result
    invalid_updates = (
        {"alert_activity": evidence.alert_activity.model_copy(update={"record_count": 2})},
        {"alert_activity": evidence.alert_activity.model_copy(update={"occurrence_count": 2})},
        {
            "status_distribution": evidence.status_distribution.model_copy(
                update={"resolved": 1, "active": 0}
            )
        },
        {
            "status_distribution": evidence.status_distribution.model_copy(
                update={"active": 2, "resolved": 0, "unknown": 0}
            )
        },
        {
            "status_distribution": evidence.status_distribution.model_copy(
                update={"active": 0, "resolved": 0, "unknown": 1}
            )
        },
        {"alerts": (records[0].model_copy(update={"duration_seconds": -1.0}),)},
        {"alerts": (records[0].model_copy(update={"duration_seconds": float("inf")}),)},
        {"alerts": (records[0].model_copy(update={"duration_seconds": 1.0}),)},
        {
            "alerts": (
                records[0].model_copy(
                    update={"ended_at": context.analysis_window.to, "duration_seconds": 3600.0}
                ),
            )
        },
        {
            "duration_statistics": evidence.duration_statistics.model_copy(
                update={"min_seconds": 1.0}
            )
        },
        {
            "duration_statistics": evidence.duration_statistics.model_copy(
                update={"max_seconds": 1.0}
            )
        },
        {
            "duration_statistics": evidence.duration_statistics.model_copy(
                update={"average_seconds": 1.0}
            )
        },
        {
            "duration_statistics": evidence.duration_statistics.model_copy(
                update={"min_seconds": -1.0}
            )
        },
        {
            "duration_statistics": evidence.duration_statistics.model_copy(
                update={"max_seconds": float("inf")}
            )
        },
        {
            "provider_importance_distribution": (
                evidence.provider_importance_distribution.model_copy(
                    update={"values": {"value % space": 2}}
                )
            )
        },
        {
            "provider_importance_distribution": (
                evidence.provider_importance_distribution.model_copy(update={"type": "wrong"})
            )
        },
    )
    for update in invalid_updates:
        payload = _payload(result.model_copy(update=update))
        with pytest.raises(ValidationError):
            CompletedAlertAnalysisResult.model_validate(payload)
    for mutate in (
        lambda payload: payload["alerts"][0].update({"ended_at": "not-a-datetime"}),
        lambda payload: payload["alerts"][0].update(
            {"ended_at": context.analysis_window.from_ - timedelta(seconds=1)}
        ),
        lambda payload: payload["alerts"][0].update({"ended_at": context.analysis_window.to}),
        lambda payload: payload["alerts"][0]["status"].update({"normalized": "resolved"}),
    ):
        payload = _payload(result)
        mutate(payload)
        with pytest.raises(ValidationError):
            CompletedAlertAnalysisResult.model_validate(payload)
    missing_importance = _payload(result)
    missing_importance["provider_importance_distribution"] = None
    with pytest.raises(ValidationError):
        CompletedAlertAnalysisResult.model_validate(missing_importance)
    unexpected_importance = _payload(result)
    unexpected_importance["alerts"][0]["provider_importance"] = None
    with pytest.raises(ValidationError):
        CompletedAlertAnalysisResult.model_validate(unexpected_importance)
    zero_context = _context()
    zero, _ = AlertResultBuilder().completed_zero(zero_context, AlertMandatoryEvidence())
    assert zero.overall_importance == "none"
    malformed_zero = _payload(zero)
    malformed_zero["duration_statistics"] = {
        "min_seconds": 0.0,
        "max_seconds": 0.0,
        "average_seconds": 0.0,
    }
    with pytest.raises(ValidationError):
        CompletedAlertAnalysisResult.model_validate(malformed_zero)
    for field, value in (
        ("provider_importance_distribution", {"type": "x", "values": {"y": 1}}),
        ("overall_importance", "high"),
    ):
        malformed_zero = _payload(zero)
        malformed_zero[field] = value
        with pytest.raises(ValidationError):
            CompletedAlertAnalysisResult.model_validate(malformed_zero)
    nonzero_none = _payload(result)
    nonzero_none["overall_importance"] = "none"
    with pytest.raises(ValidationError):
        CompletedAlertAnalysisResult.model_validate(nonzero_none)

    unknown = _payload(result)
    unknown["alerts"][0]["status"]["normalized"] = "unknown"
    unknown["status_distribution"] = {"active": 0, "resolved": 0, "unknown": 1}
    controlled_unknown = CompletedAlertAnalysisResult.model_validate(unknown)
    assert controlled_unknown.status_distribution.unknown == 1


def test_builder_enforces_exact_comparison_optional_trace_and_status_sections() -> None:
    context, records, evidence = _assembled()
    context = context.model_copy(update={"reference_periods": ("1d", "7d")})
    one_day = compare_occurrences("1d", evidence, evidence)
    seven_days = compare_occurrences("7d", evidence, evidence)
    evidence = evidence.model_copy(update={"comparisons": (one_day, seven_days)})
    builder = AlertResultBuilder()
    result, _ = builder.completed(
        context, records, evidence, AlertAgentCompletion(findings=(), overall_importance="high")
    )
    assert result.comparisons == (one_day, seven_days)
    with pytest.raises(ValueError):
        builder._validate_context_correlation(
            result.model_copy(update={"comparisons": (seven_days, one_day)}), context
        )
    unexpected = compare_occurrences("14d", evidence, evidence)
    with pytest.raises(ValueError):
        builder._validate_context_correlation(
            result.model_copy(update={"comparisons": (one_day, seven_days, unexpected)}), context
        )
    for field, value in (
        ("current", 2),
        ("reference", 2),
        ("delta", 1),
        ("direction", "decreased"),
    ):
        bad_comparison = one_day.model_copy(
            update={
                "occurrence_comparison": one_day.occurrence_comparison.model_copy(
                    update={field: value}
                )
            }
        )
        with pytest.raises(ValidationError):
            CompletedAlertAnalysisResult.model_validate(
                _payload(result.model_copy(update={"comparisons": (bad_comparison, seven_days)}))
            )
    with_tools = result.model_copy(
        update={
            "optional_tool_execution": AlertOptionalToolExecution(
                unsuccessful_calls=(
                    AlertUnsuccessfulToolCall(
                        tool="recurrence_concentration_analysis", status="failed"
                    ),
                )
            )
        }
    )
    assert CompletedAlertAnalysisResult.model_validate(_payload(with_tools)) == with_tools
    for call in (
        {"tool": "recurrence_concentration_analysis", "status": "success"},
        {"tool": "recurrence_concentration_analysis", "status": "not_applicable"},
        {"tool": "recurrence_concentration_analysis", "status": "failed", "extra": "no"},
    ):
        payload = _payload(with_tools)
        payload["optional_tool_execution"] = {"unsuccessful_calls": [call]}
        with pytest.raises(ValidationError):
            CompletedAlertAnalysisResult.model_validate(payload)
    missing_findings = _payload(result)
    missing_findings.pop("findings")
    with pytest.raises(ValidationError):
        CompletedAlertAnalysisResult.model_validate(missing_findings)
