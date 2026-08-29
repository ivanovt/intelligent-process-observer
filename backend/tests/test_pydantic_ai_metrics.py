from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic_ai.models.test import TestModel

from app.infrastructure.agents.pydantic_ai_metrics import PydanticAIMetricsAgent
from app.metrics.contracts import (
    MetricAgentInsufficientRequest,
    MetricAgentUsableRequest,
    MetricAnalysisWindow,
    MetricEvidence,
    MetricIdentity,
    MetricSample,
    MetricSemantics,
    MetricTrend,
    MetricVariability,
    PreparedGoodSeries,
)
from app.metrics.tools import MetricToolRegistry


def run(coroutine):
    return asyncio.run(coroutine)


def usable_request() -> tuple[MetricAgentUsableRequest, MetricToolRegistry]:
    start = datetime(2026, 8, 29, tzinfo=UTC)
    window = MetricAnalysisWindow(**{"from": start, "to": start + timedelta(minutes=2)})
    identity = MetricIdentity(
        observation_id=uuid4(),
        observation_run_id=uuid4(),
        lens_id="temperature",
        lens_run_id=uuid4(),
        metric_ref="temperature_celsius",
        unit="celsius",
    )
    prepared = PreparedGoodSeries(
        data_quality="good",
        samples=(
            MetricSample(timestamp=start, value=1.0),
            MetricSample(timestamp=start + timedelta(minutes=1), value=2.0),
            MetricSample(timestamp=start + timedelta(minutes=2), value=3.0),
        ),
        evidence=MetricEvidence(mean=2.0, std=1.0, min=1.0, max=3.0, slope=1 / 60),
        residuals=(0.0, 0.0, 0.0),
    )
    registry = MetricToolRegistry("opaque-dataset", prepared)
    return (
        MetricAgentUsableRequest(
            identity=identity,
            analysis_window=window,
            analysis_objectives=("spike",),
            data_quality="good",
            evidence=prepared.evidence,
            semantics=MetricSemantics(
                trend=MetricTrend(direction="increasing", rate="fast"),
                variability=MetricVariability(state="low"),
            ),
            allowed_tools=registry.descriptors,
            dataset_ref=registry.dataset_ref,
        ),
        registry,
    )


def test_adapter_executes_exact_registered_tools_and_completes() -> None:
    request, registry = usable_request()
    agent = PydanticAIMetricsAgent(
        TestModel(call_tools="all", custom_output_args={"state": "completed"})
    )

    outcome = run(agent.complete(request, registry))

    assert outcome.state == "completed"
    assert [attempt.requested_name for attempt in registry.ledger] == [
        "spike",
        "oscillation",
        "stuck_signal",
    ]
    assert [attempt.ordinal for attempt in registry.ledger] == [1, 2, 3]


def test_adapter_insufficient_request_has_no_tools() -> None:
    request, _ = usable_request()
    insufficient = MetricAgentInsufficientRequest(
        identity=request.identity,
        analysis_window=request.analysis_window,
        data_quality="insufficient",
    )
    agent = PydanticAIMetricsAgent(TestModel(custom_output_args={"state": "completed"}))

    outcome = run(agent.complete(insufficient))

    assert outcome.state == "completed"
