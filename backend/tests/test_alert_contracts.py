from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.alerts.analyzer import analyze_current
from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAgentRequest,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertMandatoryEvidence,
    AlertProviderImportance,
    AlertProviderRecord,
    AlertProviderScope,
)
from app.alerts.normalization import normalize_current
from app.alerts.result_builder import AlertResultBuilder


def _context() -> AlertLensExecutionContext:
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=uuid4(),
            observation_run_id=uuid4(),
            lens_id="release-alerts",
            lens_run_id=uuid4(),
        ),
        provider_scope=AlertProviderScope(source="fake-alerts", query="project = RELEASE"),
        analysis_window=AlertAnalysisWindow(
            **{"from": datetime(2026, 9, 1, tzinfo=UTC), "to": datetime(2026, 9, 1, 1, tzinfo=UTC)}
        ),
        lens_name="Release alerts",
    )


def test_foundational_alert_models_are_strict_and_preserve_runtime_identity() -> None:
    context = _context()
    assert context.identity.lens_run_id
    with pytest.raises(ValidationError):
        AlertProviderScope(source="fake", query="x", transient="forbidden")


def test_zero_record_result_has_exact_sections() -> None:
    context = _context()
    result, outcome = AlertResultBuilder(
        clock=lambda: datetime(2026, 9, 1, 2, tzinfo=UTC)
    ).completed_zero(context, AlertMandatoryEvidence())
    payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert set(payload) == {
        "schema_version",
        "lens_type",
        "status",
        "identity",
        "analysis_timestamp",
        "analysis_window",
        "alerts",
        "alert_activity",
        "status_distribution",
        "comparisons",
        "findings",
        "overall_importance",
        "provenance",
    }
    assert payload["analysis_timestamp"] == "2026-09-01T01:00:00Z"
    assert payload["identity"] == context.identity.model_dump(mode="json")
    assert payload["analysis_window"] == {
        "start": "2026-09-01T00:00:00Z",
        "end": "2026-09-01T01:00:00Z",
    }
    assert payload["provenance"] == {
        "source_provider": "fake-alerts",
        "generated_at": "2026-09-01T02:00:00Z",
    }
    assert payload["alerts"] == []
    assert payload["alert_activity"] == {"record_count": 0, "occurrence_count": 0}
    assert payload["status_distribution"] == {"active": 0, "resolved": 0, "unknown": 0}
    assert payload["comparisons"] == []
    assert payload["findings"] == []
    assert payload["overall_importance"] == "none"
    assert "duration_statistics" not in payload
    assert "provider_importance_distribution" not in payload
    assert outcome.artifact.status.value == "completed"


def test_representative_nonzero_alert_result_is_strict() -> None:
    context = _context()
    record = AlertProviderRecord(
        id="ALERT-1",
        title="Connection saturation",
        description="canonical",
        started_at=datetime(2026, 9, 1, tzinfo=UTC),
        ended_at=datetime(2026, 9, 1, 0, 10, tzinfo=UTC),
        source_status="Closed",
        provider_importance=AlertProviderImportance(type="priority", value="Highest"),
        occurrence_count=3,
        source_ref="jira:ALERT-1",
    )
    canonical = normalize_current(
        type("Response", (), {"records": (record,)})(),
        context.analysis_window,
        context.analysis_window.to,
    )
    result, _ = AlertResultBuilder(clock=lambda: datetime(2026, 9, 1, 2, tzinfo=UTC)).completed(
        context,
        canonical,
        analyze_current(canonical),
        AlertAgentCompletion(
            findings=(
                AlertFinding(
                    id="finding-1",
                    statement="Grounded",
                    evidence_refs=("alert://current/ALERT-1",),
                ),
            ),
            overall_importance="high",
        ),
    )
    payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert set(payload) == {
        "schema_version",
        "lens_type",
        "status",
        "identity",
        "analysis_timestamp",
        "analysis_window",
        "alerts",
        "alert_activity",
        "status_distribution",
        "duration_statistics",
        "provider_importance_distribution",
        "comparisons",
        "findings",
        "overall_importance",
        "provenance",
    }
    assert payload["alerts"][0]["source_ref"] == "jira:ALERT-1" and "query" not in str(payload)


def test_agent_request_and_completion_contracts_are_strict() -> None:
    context = _context()
    record = AlertProviderRecord(
        id="ALERT-1",
        title="Title",
        started_at=datetime(2026, 9, 1, tzinfo=UTC),
        source_status="Open",
    )
    records = normalize_current(
        type("Response", (), {"records": (record,)})(),
        context.analysis_window,
        context.analysis_window.to,
    )
    request = AlertAgentRequest(
        lens_name="exact",
        lens_description="description",
        current_records=records,
        mandatory_evidence=analyze_current(records),
    )
    assert set(request.model_dump()) == {
        "lens_name",
        "lens_description",
        "current_records",
        "mandatory_evidence",
        "comparisons",
    }
    with pytest.raises(ValidationError):
        AlertAgentRequest.model_validate({**request.model_dump(), "query": "forbidden"})
    with pytest.raises(ValidationError):
        AlertAgentCompletion.model_validate(
            {"findings": [], "overall_importance": "high", "unknown": True}
        )
    with pytest.raises(ValidationError):
        AlertAgentCompletion.model_validate({"findings": []})
    with pytest.raises(ValidationError):
        AlertAgentCompletion(
            findings=(
                AlertFinding(id="same", statement="x", evidence_refs=()),
                AlertFinding(id="same", statement="y", evidence_refs=()),
            ),
            overall_importance="high",
        )
