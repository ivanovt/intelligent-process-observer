"""Focused public-safe runtime projection tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.alerts.contracts import (
    AlertActivity,
    AlertAnalysisWindow,
    AlertIdentity,
    AlertResultProvenance,
    AlertStatusDistribution,
    CompletedAlertAnalysisResult,
)
from app.infrastructure.persistence.models import (
    LensAnalysisResultModel,
    LensRunModel,
    ObservationAnalysisResultModel,
    ObservationReportModel,
    ObservationRunModel,
    RelationshipEvaluationModel,
)
from app.infrastructure.persistence.repository import (
    ObservationRunDetailRecord,
    ObservationRunSummaryRecord,
)
from app.observation_runs.projection import (
    RuntimeProjectionInvalid,
    project_observation_run_detail,
    project_observation_run_summary,
)
from app.reasoning.contracts import ObservationAnalysisResult, ObservationIdentity
from app.relationships.contracts import ApplicableRelationshipEvaluation, DirectionEvidence
from app.reporting.contracts import ObservationReport


def test_detail_projects_exact_artifacts_in_persisted_and_canonical_order() -> None:
    observation_id = uuid4()
    run_id = uuid4()
    started = datetime(2026, 9, 9, 12, tzinfo=UTC)
    run = _run(observation_id, run_id, started)
    alert_lens = _alert_lens(observation_id, run_id, started)
    metric_lens = LensRunModel(
        id=uuid4(),
        observation_run_id=run_id,
        lens_id="z-metric",
        lens_type="metric",
        status="pending",
        provenance={},
        execution_context={},
    )
    run.lens_runs = [alert_lens, metric_lens]
    first = _relationship("first")
    second = _relationship("second")
    run.relationship_evaluations = [
        RelationshipEvaluationModel(
            id=uuid4(),
            observation_run_id=run_id,
            relationship_id="second",
            position=1,
            payload=second,
        ),
        RelationshipEvaluationModel(
            id=uuid4(),
            observation_run_id=run_id,
            relationship_id="first",
            position=0,
            payload=first,
        ),
    ]
    analysis = _analysis(observation_id, run_id)
    analysis_model = ObservationAnalysisResultModel(
        id=uuid4(),
        observation_run_id=run_id,
        schema_version="1.0",
        payload=analysis.model_dump(mode="json"),
    )
    report = ObservationReport(
        observation_id=observation_id,
        observation_run_id=run_id,
        generated_at=started + timedelta(minutes=4),
        content="# Safe report",
    )
    analysis_model.report = ObservationReportModel(
        id=uuid4(),
        observation_analysis_result_id=analysis_model.id,
        generated_at=report.generated_at,
        format=report.format,
        content=report.content,
    )
    run.observation_analysis_result = analysis_model

    result = project_observation_run_detail(
        ObservationRunDetailRecord(observation_run=run, observation_name="Safe observation"),
        now=started + timedelta(minutes=5),
    )

    assert [item.lens_type for item in result.lens_runs] == ["metric", "alert"]
    assert [item.relationship_id for item in result.relationship_evaluations] == ["first", "second"]
    assert result.lens_runs[1].result == _alert_result(
        observation_id, run_id, alert_lens.id, started
    )
    assert result.summary.analytical_state == "no_significant_findings"
    assert result.summary.duration_seconds == 300
    assert result.report == report


def test_summary_validates_complete_analysis_before_deriving_state() -> None:
    observation_id, run_id = uuid4(), uuid4()
    run = _run(observation_id, run_id, datetime(2026, 9, 9, 12, tzinfo=UTC))
    payload = _analysis(observation_id, run_id).model_dump(mode="json")
    payload["unexpected"] = "not public"

    with pytest.raises(RuntimeProjectionInvalid):
        project_observation_run_summary(
            ObservationRunSummaryRecord(
                observation_run=run,
                observation_name="Safe observation",
                analysis_schema_version="1.0",
                analysis_payload=payload,
            )
        )


def test_detail_fails_closed_for_artifact_correlation_and_never_exposes_private_context() -> None:
    observation_id, run_id = uuid4(), uuid4()
    started = datetime(2026, 9, 9, 12, tzinfo=UTC)
    run = _run(observation_id, run_id, started)
    run.execution_context["secret"] = "TOP-SECRET"
    alert_lens = _alert_lens(observation_id, run_id, started)
    alert_lens.execution_context["query"] = "private selector"
    run.lens_runs = [alert_lens]

    detail = project_observation_run_detail(
        ObservationRunDetailRecord(observation_run=run, observation_name="Safe observation"),
        now=started,
    )
    serialized = detail.model_dump_json()
    assert "TOP-SECRET" not in serialized
    assert "private selector" not in serialized

    assert alert_lens.analysis_result is not None
    alert_lens.analysis_result.payload["identity"]["lens_run_id"] = str(uuid4())
    with pytest.raises(RuntimeProjectionInvalid):
        project_observation_run_detail(
            ObservationRunDetailRecord(observation_run=run, observation_name="Safe observation")
        )


def test_missing_artifacts_stay_absent_and_terminal_duration_uses_finished_at() -> None:
    observation_id, run_id = uuid4(), uuid4()
    started = datetime(2026, 9, 9, 12, tzinfo=UTC)
    run = _run(observation_id, run_id, started)
    run.status = "failed"
    run.reason = {"code": "execution_failed", "component": None}
    run.finished_at = started + timedelta(seconds=7)
    failed_alert = LensRunModel(
        id=uuid4(),
        observation_run_id=run_id,
        lens_id="failed-alert",
        lens_type="alert",
        status="failed",
        reason={"code": "analysis_failed", "component": None},
        started_at=started,
        finished_at=started + timedelta(seconds=2),
        provenance={},
        execution_context={},
    )
    run.lens_runs = [failed_alert]

    detail = project_observation_run_detail(
        ObservationRunDetailRecord(observation_run=run, observation_name="Safe observation"),
        now=started + timedelta(days=1),
    )

    assert detail.analysis is None
    assert detail.report is None
    assert detail.lens_runs[0].result is None
    assert detail.summary.duration_seconds == 7
    assert detail.lens_runs[0].duration_seconds == 2


def _run(observation_id, run_id, started: datetime) -> ObservationRunModel:
    return ObservationRunModel(
        id=run_id,
        observation_id=observation_id,
        status="running",
        reason=None,
        provenance={"provider": "private"},
        execution_context={
            "analysis_window": {
                "from": (started - timedelta(hours=1)).isoformat(),
                "to": started.isoformat(),
            },
            "query": "opaque private query",
        },
        created_at=started,
        started_at=started,
    )


def _alert_lens(observation_id, run_id, started: datetime) -> LensRunModel:
    lens_id = uuid4()
    result = _alert_result(observation_id, run_id, lens_id, started)
    lens = LensRunModel(
        id=lens_id,
        observation_run_id=run_id,
        lens_id="a-alert",
        lens_type="alert",
        status="completed",
        reason=None,
        started_at=started,
        finished_at=started + timedelta(seconds=1),
        provenance={"provider": "private"},
        execution_context={},
    )
    lens.analysis_result = LensAnalysisResultModel(
        id=uuid4(),
        lens_run_id=lens_id,
        result_type="alert",
        status="completed",
        schema_version="1.0",
        payload=result.model_dump(mode="json"),
    )
    return lens


def _alert_result(
    observation_id, run_id, lens_run_id, timestamp: datetime
) -> CompletedAlertAnalysisResult:
    return CompletedAlertAnalysisResult(
        identity=AlertIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id="a-alert",
            lens_run_id=lens_run_id,
        ),
        analysis_timestamp=timestamp,
        analysis_window=AlertAnalysisWindow(
            **{"from": timestamp - timedelta(hours=1), "to": timestamp}
        ),
        alerts=(),
        alert_activity=AlertActivity(record_count=0, occurrence_count=0),
        status_distribution=AlertStatusDistribution(active=0, resolved=0, unknown=0),
        findings=(),
        overall_importance="none",
        provenance=AlertResultProvenance(source_provider="jira", generated_at=timestamp),
    )


def _analysis(observation_id, run_id) -> ObservationAnalysisResult:
    return ObservationAnalysisResult(
        identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
        overall_state="no_significant_findings",
        findings=(),
        hypotheses=(),
        limitations=(),
    )


def _relationship(relationship_id: str) -> dict[str, object]:
    return ApplicableRelationshipEvaluation(
        relationship_id=relationship_id,
        name=relationship_id.title(),
        description=None,
        conditions=(
            DirectionEvidence(lens_id="metric", expected="stable", observed="stable", match=True),
        ),
        expectations=(),
        state="consistent",
    ).model_dump(mode="json")
