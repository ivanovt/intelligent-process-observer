"""Fail-closed public projections for persisted Observation run artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.infrastructure.persistence.models import LensAnalysisResultModel, LensRunModel
from app.infrastructure.persistence.repository import (
    ObservationRunDetailRecord,
    ObservationRunSummaryRecord,
)
from app.observation_runs.contracts import (
    AlertLensRunResult,
    MetricLensRunResult,
    ObservationRunAnalysisWindow,
    ObservationRunDetail,
    ObservationRunLensRun,
    ObservationRunObservation,
    ObservationRunSummary,
)
from app.reasoning.contracts import ObservationAnalysisResult
from app.relationships.contracts import RelationshipEvaluation
from app.reporting.contracts import ObservationReport


class RuntimeProjectionInvalid(ValueError):
    """Signal an invalid durable artifact without surfacing its diagnostics publicly."""


_METRIC_RESULT_ADAPTER = TypeAdapter(MetricLensRunResult)
_ALERT_RESULT_ADAPTER = TypeAdapter(AlertLensRunResult)
_RELATIONSHIP_ADAPTER = TypeAdapter(RelationshipEvaluation)


def project_observation_run_summary(
    record: ObservationRunSummaryRecord, *, now: datetime | None = None
) -> ObservationRunSummary:
    """Return one strict public summary or fail closed on corrupt durable state."""

    analytical_state = _validated_analytical_state(
        record.analysis_schema_version, record.analysis_payload, record.observation_run.id
    )
    return _summary(
        record.observation_run,
        record.observation_name,
        analytical_state=analytical_state,
        now=now,
    )


def project_observation_run_detail(
    record: ObservationRunDetailRecord, *, now: datetime | None = None
) -> ObservationRunDetail:
    """Return every admitted persisted artifact from one eager aggregate snapshot."""

    observation_run = record.observation_run
    analysis_model = observation_run.observation_analysis_result
    analysis = _validated_analysis(
        None if analysis_model is None else analysis_model.schema_version,
        None if analysis_model is None else analysis_model.payload,
        observation_run.id,
        observation_run.observation_id,
    )
    report = _validated_report(
        analysis_model,
        analysis,
        observation_run.id,
        observation_run.observation_id,
    )
    lens_runs = tuple(
        _project_lens_run(item, observation_run.id, observation_run.observation_id, now=now)
        for item in sorted(
            observation_run.lens_runs,
            key=lambda item: (_lens_type_order(item.lens_type), item.lens_id, str(item.id)),
        )
    )
    relationships = _project_relationships(
        observation_run.relationship_evaluations, observation_run.id
    )
    return _strict_model(
        ObservationRunDetail,
        {
            "summary": _summary(
                observation_run,
                record.observation_name,
                analytical_state=None if analysis is None else analysis.overall_state,
                now=now,
            ),
            "lens_runs": lens_runs,
            "relationship_evaluations": relationships,
            "analysis": analysis,
            "report": report,
        },
    )


def _summary(
    observation_run: Any,
    observation_name: object,
    *,
    analytical_state: str | None,
    now: datetime | None,
) -> ObservationRunSummary:
    """Whitelist one parent row without retaining execution context or provenance."""

    window = _analysis_window(observation_run.execution_context)
    return _strict_model(
        ObservationRunSummary,
        {
            "id": observation_run.id,
            "observation": _strict_model(
                ObservationRunObservation,
                {"id": observation_run.observation_id, "name": observation_name},
            ),
            "analysis_window": window,
            "status": observation_run.status,
            "reason": observation_run.reason,
            "analytical_state": analytical_state,
            "created_at": observation_run.created_at,
            "started_at": observation_run.started_at,
            "finished_at": observation_run.finished_at,
            "duration_seconds": _duration(
                observation_run.started_at, observation_run.finished_at, now=now
            ),
            "href": f"/api/v1/observation-runs/{observation_run.id}",
        },
    )


def _project_lens_run(
    lens_run: LensRunModel,
    observation_run_id: object,
    observation_id: object,
    *,
    now: datetime | None,
) -> ObservationRunLensRun:
    """Project one type-aware Lens lifecycle record and its optional exact artifact."""

    if lens_run.observation_run_id != observation_run_id:
        raise RuntimeProjectionInvalid("LensRun parent correlation is invalid")
    result = _validated_lens_result(lens_run, observation_run_id, observation_id)
    return _strict_model(
        ObservationRunLensRun,
        {
            "id": lens_run.id,
            "lens_id": lens_run.lens_id,
            "lens_type": lens_run.lens_type,
            "status": lens_run.status,
            "reason": lens_run.reason,
            "started_at": lens_run.started_at,
            "finished_at": lens_run.finished_at,
            "duration_seconds": _duration(lens_run.started_at, lens_run.finished_at, now=now),
            "result": result,
        },
    )


def _validated_lens_result(
    lens_run: LensRunModel, observation_run_id: object, observation_id: object
) -> MetricLensRunResult | AlertLensRunResult | None:
    """Revalidate one stored artifact and correlate every identity and lifecycle field."""

    stored: LensAnalysisResultModel | None = lens_run.analysis_result
    if stored is None:
        return None
    if stored.lens_run_id != lens_run.id:
        raise RuntimeProjectionInvalid("Lens artifact parent correlation is invalid")
    if stored.schema_version != "1.0" or stored.result_type != lens_run.lens_type:
        raise RuntimeProjectionInvalid("Lens artifact envelope is invalid")
    if stored.status != lens_run.status:
        raise RuntimeProjectionInvalid("Lens artifact lifecycle correlation is invalid")
    if lens_run.lens_type == "metric":
        result = _strict_model(_METRIC_RESULT_ADAPTER, stored.payload)
        status = result.status.state
    elif lens_run.lens_type == "alert":
        result = _strict_model(_ALERT_RESULT_ADAPTER, stored.payload)
        status = result.status
    else:
        raise RuntimeProjectionInvalid("Unsupported persisted Lens artifact type")
    identity = result.identity
    if (
        identity.observation_id != observation_id
        or identity.observation_run_id != observation_run_id
        or identity.lens_id != lens_run.lens_id
        or identity.lens_run_id != lens_run.id
        or status != lens_run.status
    ):
        raise RuntimeProjectionInvalid("Lens artifact payload correlation is invalid")
    return result


def _validated_analytical_state(
    schema_version: str | None, payload: dict[str, object] | None, observation_run_id: object
) -> str | None:
    """Derive state only from a complete validated Observation analysis artifact."""

    analysis = _validated_analysis(schema_version, payload, observation_run_id, None)
    return None if analysis is None else analysis.overall_state


def _validated_analysis(
    schema_version: str | None,
    payload: dict[str, object] | None,
    observation_run_id: object,
    observation_id: object | None,
) -> ObservationAnalysisResult | None:
    """Validate the named schema-1.0 analysis contract and its runtime identity."""

    if payload is None:
        if schema_version is not None:
            raise RuntimeProjectionInvalid("Observation analysis envelope is incomplete")
        return None
    if schema_version != "1.0":
        raise RuntimeProjectionInvalid("Observation analysis schema is unsupported")
    analysis = _strict_model(ObservationAnalysisResult, payload)
    if analysis.identity.observation_run_id != observation_run_id:
        raise RuntimeProjectionInvalid("Observation analysis run correlation is invalid")
    if observation_id is not None and analysis.identity.observation_id != observation_id:
        raise RuntimeProjectionInvalid("Observation analysis observation correlation is invalid")
    return analysis


def _validated_report(
    analysis_model: Any,
    analysis: ObservationAnalysisResult | None,
    observation_run_id: object,
    observation_id: object,
) -> ObservationReport | None:
    """Validate the report only through its correlated Observation analysis parent."""

    if analysis_model is None:
        return None
    report_model = analysis_model.report
    if report_model is None:
        return None
    if analysis is None or report_model.observation_analysis_result_id != analysis_model.id:
        raise RuntimeProjectionInvalid("Observation report source correlation is invalid")
    report = _strict_model(
        ObservationReport,
        {
            "observation_id": observation_id,
            "observation_run_id": observation_run_id,
            "generated_at": report_model.generated_at,
            "format": report_model.format,
            "content": report_model.content,
        },
    )
    return report


def _project_relationships(
    items: object, observation_run_id: object
) -> tuple[RelationshipEvaluation, ...]:
    """Validate stored relationship artifacts in their immutable persisted ordinal order."""

    ordered = sorted(items, key=lambda item: item.position)
    if [item.position for item in ordered] != list(range(len(ordered))):
        raise RuntimeProjectionInvalid("Relationship evaluation ordinal sequence is invalid")
    projections: list[RelationshipEvaluation] = []
    for item in ordered:
        if item.observation_run_id != observation_run_id:
            raise RuntimeProjectionInvalid("Relationship evaluation parent correlation is invalid")
        result = _strict_model(_RELATIONSHIP_ADAPTER, item.payload)
        if result.relationship_id != item.relationship_id:
            raise RuntimeProjectionInvalid("Relationship evaluation identity is invalid")
        projections.append(result)
    return tuple(projections)


def _analysis_window(execution_context: object) -> ObservationRunAnalysisWindow:
    """Extract and strictly validate only the immutable run window from private context."""

    if not isinstance(execution_context, dict):
        raise RuntimeProjectionInvalid("Run execution context is invalid")
    window = execution_context.get("analysis_window")
    if not isinstance(window, dict):
        raise RuntimeProjectionInvalid("Run analysis window is unavailable")
    return _strict_model(ObservationRunAnalysisWindow, window)


def _duration(started_at: object, finished_at: object, *, now: datetime | None) -> float | None:
    """Derive a duration only from a valid start and a truthful terminal/display time."""

    if started_at is None:
        return None
    if not isinstance(started_at, datetime):
        raise RuntimeProjectionInvalid("Run start timestamp is invalid")
    end = finished_at if finished_at is not None else (now or datetime.now(UTC))
    if not isinstance(end, datetime):
        raise RuntimeProjectionInvalid("Run finish timestamp is invalid")
    seconds = (end - started_at).total_seconds()
    if seconds < 0:
        raise RuntimeProjectionInvalid("Run duration is invalid")
    return seconds


def _lens_type_order(value: str) -> int:
    """Return the accepted canonical Lens type ordering for public detail."""

    if value == "metric":
        return 0
    if value == "alert":
        return 1
    raise RuntimeProjectionInvalid("Unsupported LensRun type")


def _strict_model(adapter: Any, value: object) -> Any:
    """Validate JSON persistence values with strict domain models and safe errors."""

    try:
        if isinstance(adapter, TypeAdapter):
            try:
                return adapter.validate_python(value, by_name=True)
            except ValidationError:
                return adapter.validate_json(json.dumps(value, default=str), by_name=True)
        try:
            return adapter.model_validate(value, by_name=True)
        except ValidationError:
            return adapter.model_validate_json(json.dumps(value, default=str), by_name=True)
    except (TypeError, ValueError, ValidationError) as error:
        raise RuntimeProjectionInvalid("Persisted runtime projection is invalid") from error
