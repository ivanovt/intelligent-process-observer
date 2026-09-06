"""Boundary tests for the native Observation reasoning input scope."""
# ruff: noqa: E501

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertMandatoryEvidence,
    AlertProviderScope,
)
from app.alerts.result_builder import AlertResultBuilder
from app.infrastructure.persistence.runtime_contracts import StructuredReason
from app.metrics.contracts import (
    MetricAnalysisWindow,
    MetricEvidence,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)
from app.metrics.result_builder import MetricResultBuilder
from app.reasoning.contracts import (
    ObservationIdentity,
    ObservationReasoningInput,
    ObservationSemanticContext,
    ReasoningLens,
    UnavailableLens,
)
from app.reasoning.input import insufficient_metric_as_unavailable, validate_input
from app.relationships.contracts import ApplicableRelationshipEvaluation, DirectionEvidence

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _metric_context(
    observation_id: UUID, run_id: UUID, lens_id: str = "metric"
) -> MetricLensExecutionContext:
    return MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id=lens_id,
            lens_run_id=uuid4(),
            metric_ref="process.temperature",
            unit="C",
        ),
        provider_scope=MetricProviderScope(
            adapter_type="prometheus", source_id="plant", query="temp"
        ),
        analysis_window=MetricAnalysisWindow(**{"from": NOW, "to": NOW + timedelta(minutes=1)}),
        analysis_objectives=(),
        reference_periods=(),
    )


def _metric_results(observation_id: UUID, run_id: UUID):
    context = _metric_context(observation_id, run_id)
    builder = MetricResultBuilder(clock=lambda: NOW)
    prepared = PreparedGoodSeries(
        data_quality="good",
        samples=(),
        evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=0.0),
        residuals=(),
    )
    semantics = MetricSemantics(
        trend=MetricTrend(direction="stable", rate="not_classified"),
        variability=MetricVariability(state="low"),
    )
    sufficient, _ = builder.completed_sufficient(context, prepared, semantics)
    partial, _ = builder.partial_reference_unavailable(context, prepared, semantics, (), ())
    insufficient, _ = builder.completed_insufficient(context)
    return sufficient, partial, insufficient


def _alert_context(
    observation_id: UUID, run_id: UUID, lens_id: str = "alert"
) -> AlertLensExecutionContext:
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=observation_id,
            observation_run_id=run_id,
            lens_id=lens_id,
            lens_run_id=uuid4(),
        ),
        provider_scope=AlertProviderScope(source="alerts", query="project = plant"),
        analysis_window=AlertAnalysisWindow(**{"from": NOW, "to": NOW + timedelta(minutes=1)}),
        lens_name="Plant alerts",
    )


def _alert_results(observation_id: UUID, run_id: UUID):
    context = _alert_context(observation_id, run_id)
    builder = AlertResultBuilder(clock=lambda: NOW)
    complete, _ = builder.completed_zero(context, AlertMandatoryEvidence())
    partial, _ = builder.usable(
        context,
        (),
        AlertMandatoryEvidence(),
        None,
        current_rejected=True,
        reference_unavailable=False,
        zero=True,
    )
    return complete, partial


def _input(*, usable_results=(), unavailable_lenses=(), lenses=None, relationships=()):
    observation_id, run_id = uuid4(), uuid4()
    if lenses is None:
        lenses = tuple(
            ReasoningLens(
                lens_id=result.identity.lens_id,
                lens_type=result.lens_type,
                name=result.identity.lens_id,
            )
            for result in usable_results
        ) + tuple(
            ReasoningLens(lens_id=item.lens_id, lens_type=item.lens_type, name=item.lens_id)
            for item in unavailable_lenses
        )
    return ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="Observation",
            lenses=lenses,
        ),
        usable_results=usable_results,
        unavailable_lenses=unavailable_lenses,
        relationships=relationships,
    )


@pytest.mark.parametrize(
    "variant", ("metric_complete", "metric_partial", "alert_complete", "alert_partial")
)
def test_validate_input_accepts_every_usable_metric_and_alert_variant(variant: str) -> None:
    """The scope admits exactly the four native usable Metric and Alert variants."""
    observation_id, run_id = uuid4(), uuid4()
    metric_complete, metric_partial, _ = _metric_results(observation_id, run_id)
    alert_complete, alert_partial = _alert_results(observation_id, run_id)
    result = {
        "metric_complete": metric_complete,
        "metric_partial": metric_partial,
        "alert_complete": alert_complete,
        "alert_partial": alert_partial,
    }[variant]
    value = ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="Observation",
            lenses=(
                ReasoningLens(
                    lens_id=result.identity.lens_id,
                    lens_type=result.lens_type,
                    name=result.identity.lens_id,
                ),
            ),
        ),
        usable_results=(result,),
    )

    assert validate_input(value) is value
    assert value.usable_results[0].identity.observation_id == observation_id
    assert value.usable_results[0].identity.observation_run_id == run_id


def test_insufficient_metric_is_unavailable_not_usable_and_preserves_identity() -> None:
    """Completed-insufficient Metrics deterministically leave the usable evidence scope."""
    observation_id, run_id = uuid4(), uuid4()
    _, _, insufficient = _metric_results(observation_id, run_id)
    unavailable = insufficient_metric_as_unavailable(insufficient)

    assert unavailable == UnavailableLens(
        lens_id=insufficient.identity.lens_id,
        lens_type="metric",
        origin="completed_insufficient_metric",
        reason=StructuredReason(code="insufficient_data"),
    )
    value = ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="Observation",
            lenses=(ReasoningLens(lens_id="metric", lens_type="metric", name="Metric"),),
        ),
        unavailable_lenses=(unavailable,),
    )
    with pytest.raises(ValueError, match="at least one usable"):
        validate_input(value)


def test_unavailable_reason_is_strict_and_preserves_metric_and_alert_values() -> None:
    """Unavailable metadata keeps opaque producer codes without free-text fields."""
    metric = UnavailableLens(
        lens_id="metric",
        lens_type="metric",
        origin="caller_unavailable",
        reason={"code": "upstream_503", "component": "current"},
    )
    alert = UnavailableLens(
        lens_id="alert",
        lens_type="alert",
        origin="caller_unavailable",
        reason={"code": "jira_throttled", "component": "fetch"},
    )
    assert metric.reason.code == "upstream_503" and metric.reason.component == "current"
    assert alert.reason.code == "jira_throttled" and alert.reason.component == "fetch"
    for reason in ({"code": ""}, {"component": "fetch"}, {"code": "x", "diagnostic": "secret"}):
        with pytest.raises(ValidationError):
            UnavailableLens(
                lens_id="alert", lens_type="alert", origin="caller_unavailable", reason=reason
            )


def test_completed_insufficient_origin_is_reserved_for_the_projector_shape() -> None:
    """Only the deterministic Metric insufficiency value may use its origin."""
    for value in (
        {
            "lens_id": "metric",
            "lens_type": "metric",
            "origin": "completed_insufficient_metric",
            "reason": {"code": "upstream_unavailable"},
        },
        {
            "lens_id": "metric",
            "lens_type": "metric",
            "origin": "completed_insufficient_metric",
            "reason": {"code": "insufficient_data", "component": "history"},
        },
        {
            "lens_id": "alert",
            "lens_type": "alert",
            "origin": "completed_insufficient_metric",
            "reason": {"code": "insufficient_data"},
        },
    ):
        with pytest.raises(ValidationError, match="completed insufficient Metric"):
            UnavailableLens.model_validate(value)


def test_context_rejects_log_unsupported_and_infrastructure_fields_before_partition() -> None:
    """Semantic context remains compact and rejects deferred or infrastructure input."""
    identity = ObservationIdentity(observation_id=uuid4(), observation_run_id=uuid4())
    log_context = ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=identity,
            name="Observation",
            lenses=(ReasoningLens(lens_id="log", lens_type="log", name="Log"),),
        ),
        unavailable_lenses=(
            UnavailableLens(
                lens_id="log", lens_type="metric", origin="caller_unavailable", reason={"code": "x"}
            ),
        ),
    )
    with pytest.raises(ValueError, match="Log Lens"):
        validate_input(log_context)
    with pytest.raises(ValidationError):
        ReasoningLens.model_validate({"lens_id": "x", "lens_type": "relationship", "name": "X"})
    with pytest.raises(ValidationError):
        ObservationSemanticContext.model_validate(
            {"identity": identity, "name": "x", "lenses": (), "provider": "secret"}
        )


def test_validate_input_rejects_scope_partition_duplicates_missing_unknown_and_cross_run() -> None:
    """Native evidence must exactly partition the configured Lens scope for one run."""
    observation_id, run_id = uuid4(), uuid4()
    metric, _, _ = _metric_results(observation_id, run_id)
    alert, _ = _alert_results(observation_id, run_id)
    context = ObservationSemanticContext(
        identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
        name="Observation",
        lenses=(
            ReasoningLens(lens_id="metric", lens_type="metric", name="Metric"),
            ReasoningLens(lens_id="alert", lens_type="alert", name="Alert"),
        ),
    )
    unavailable = UnavailableLens(
        lens_id="alert",
        lens_type="alert",
        origin="caller_unavailable",
        reason={"code": "failed", "component": "fetch"},
    )
    valid = ObservationReasoningInput(
        context=context, usable_results=(metric,), unavailable_lenses=(unavailable,)
    )
    assert validate_input(valid) is valid
    for value, message in (
        (
            ObservationReasoningInput(
                context=context, usable_results=(metric, metric), unavailable_lenses=(unavailable,)
            ),
            "duplicate",
        ),
        (
            ObservationReasoningInput(
                context=context,
                usable_results=(metric,),
                unavailable_lenses=(
                    unavailable,
                    UnavailableLens(
                        lens_id="alert",
                        lens_type="alert",
                        origin="caller_unavailable",
                        reason={"code": "x"},
                    ),
                ),
            ),
            "duplicate",
        ),
        (
            ObservationReasoningInput(
                context=context,
                usable_results=(metric,),
                unavailable_lenses=(
                    UnavailableLens(
                        lens_id="metric",
                        lens_type="metric",
                        origin="caller_unavailable",
                        reason={"code": "x"},
                    ),
                ),
            ),
            "overlap",
        ),
        (ObservationReasoningInput(context=context, usable_results=(metric,)), "exactly partition"),
        (
            ObservationReasoningInput(
                context=context,
                usable_results=(metric,),
                unavailable_lenses=(
                    UnavailableLens(
                        lens_id="other",
                        lens_type="alert",
                        origin="caller_unavailable",
                        reason={"code": "x"},
                    ),
                ),
            ),
            "exactly partition",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            validate_input(value)
    other_metric, _, _ = _metric_results(observation_id, uuid4())
    with pytest.raises(ValueError, match="identity"):
        validate_input(
            ObservationReasoningInput(
                context=context, usable_results=(other_metric,), unavailable_lenses=(unavailable,)
            )
        )


def test_validate_input_uses_type_local_lens_identities() -> None:
    """A Metric and Alert may share an ID without collapsing their identities."""
    observation_id, run_id = uuid4(), uuid4()
    metric_context = _metric_context(observation_id, run_id, lens_id="shared")
    alert_context = _alert_context(observation_id, run_id, lens_id="shared")
    metric_builder = MetricResultBuilder(clock=lambda: NOW)
    metric, _ = metric_builder.completed_sufficient(
        metric_context,
        PreparedGoodSeries(
            data_quality="good",
            samples=(),
            evidence=MetricEvidence(mean=1.0, std=0.0, min=1.0, max=1.0, slope=0.0),
            residuals=(),
        ),
        MetricSemantics(
            trend=MetricTrend(direction="stable", rate="not_classified"),
            variability=MetricVariability(state="low"),
        ),
    )
    alert, _ = AlertResultBuilder(clock=lambda: NOW).completed_zero(
        alert_context, AlertMandatoryEvidence()
    )
    value = ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="Observation",
            lenses=(
                ReasoningLens(lens_id="shared", lens_type="metric", name="Metric shared"),
                ReasoningLens(lens_id="shared", lens_type="alert", name="Alert shared"),
            ),
        ),
        usable_results=(metric, alert),
    )

    assert validate_input(value) is value


def test_validate_input_preserves_order_and_rejects_duplicate_relationship_ids() -> None:
    """Validated collections retain caller order and Relationship IDs remain unique."""
    observation_id, run_id = uuid4(), uuid4()
    metric, _, _ = _metric_results(observation_id, run_id)
    relationship = ApplicableRelationshipEvaluation(
        relationship_id="r",
        name="R",
        description=None,
        conditions=(
            DirectionEvidence(lens_id="metric", expected="stable", observed="stable", match=True),
        ),
        expectations=(),
        state="consistent",
    )
    value = ObservationReasoningInput(
        context=ObservationSemanticContext(
            identity=ObservationIdentity(observation_id=observation_id, observation_run_id=run_id),
            name="O",
            lenses=(ReasoningLens(lens_id="metric", lens_type="metric", name="Metric"),),
        ),
        usable_results=(metric,),
        relationships=(relationship,),
    )
    assert validate_input(value).relationships == (relationship,)
    with pytest.raises(ValueError, match="relationship ids"):
        validate_input(value.model_copy(update={"relationships": (relationship, relationship)}))
