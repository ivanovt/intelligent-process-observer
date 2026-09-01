import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderScope,
    AlertRecordsAvailable,
)
from app.alerts.pipeline import AlertAnalysisPipeline


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[AlertProviderScope, AlertAnalysisWindow]] = []

    async def acquire(
        self, scope: AlertProviderScope, window: AlertAnalysisWindow
    ) -> AlertRecordsAvailable:
        self.calls.append((scope, window))
        return AlertRecordsAvailable(source=scope.source)


class FailOnCallAgent:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *args: object) -> object:
        self.calls += 1
        raise AssertionError("zero-record Alert path must not invoke the agent")


def _context() -> AlertLensExecutionContext:
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=uuid4(),
            observation_run_id=uuid4(),
            lens_id="target",
            lens_run_id=uuid4(),
        ),
        provider_scope=AlertProviderScope(source="fixture-source", query="target-query"),
        analysis_window=AlertAnalysisWindow(
            **{"from": datetime(2026, 9, 1, tzinfo=UTC), "to": datetime(2026, 9, 1, 1, tzinfo=UTC)}
        ),
        lens_name="Target lens",
    )


def test_running_context_is_the_only_pipeline_scope() -> None:
    async def scenario() -> None:
        context = _context()
        provider, agent = FakeProvider(), FailOnCallAgent()
        outcome = await AlertAnalysisPipeline(provider=provider, agent=agent).analyze(context)
        assert provider.calls == [(context.provider_scope, context.analysis_window)]
        assert outcome.artifact.identity.lens_run_id == context.identity.lens_run_id
        assert outcome.artifact.identity.lens_id == "target"
        assert agent.calls == 0

    asyncio.run(scenario())


def test_alert_pipeline_rejects_every_non_running_status_before_acquisition() -> None:
    async def scenario() -> None:
        for status in ("pending", "completed", "partial", "failed"):
            provider, agent = FakeProvider(), FailOnCallAgent()
            context = _context().model_copy(update={"lens_run_status": status})
            with pytest.raises(ValueError, match="running LensRun"):
                await AlertAnalysisPipeline(provider=provider, agent=agent).analyze(context)
            assert provider.calls == [] and agent.calls == 0

    asyncio.run(scenario())


def test_zero_record_path_skips_agent_and_builds_strict_result() -> None:
    async def scenario() -> None:
        agent = FailOnCallAgent()
        outcome = await AlertAnalysisPipeline(provider=FakeProvider(), agent=agent).analyze(
            _context()
        )
        payload = outcome.artifact.payload
        assert payload["activity"]["record_count"] == 0
        assert payload["findings"] == []
        assert payload["overall_importance"] == "none"
        assert "duration" not in payload and "provider_importance" not in payload
        assert agent.calls == 0

    asyncio.run(scenario())
