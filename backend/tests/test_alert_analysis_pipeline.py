import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertOccurrenceComparison,
    AlertProviderFailure,
    AlertProviderImportance,
    AlertProviderRecord,
    AlertProviderScope,
    AlertProviderTimeout,
    AlertRecordsAvailable,
    AlertReferenceComparison,
)
from app.alerts.pipeline import AlertAnalysisPipeline
from app.alerts.result_builder import AlertResultBuilder
from app.alerts.tools import AlertOptionalToolRegistry, duration_outliers
from app.infrastructure.agents.pydantic_ai_alerts import PydanticAIAlertAnalysisAgent


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
        assert payload["alerts"] == []
        assert payload["alert_activity"] == {"record_count": 0, "occurrence_count": 0}
        assert payload["status_distribution"] == {"active": 0, "resolved": 0, "unknown": 0}
        assert payload["comparisons"] == []
        assert payload["findings"] == []
        assert payload["overall_importance"] == "none"
        assert "duration_statistics" not in payload
        assert "provider_importance_distribution" not in payload
        assert agent.calls == 0

    asyncio.run(scenario())


def _record(
    identifier: str,
    *,
    started: datetime,
    ended: datetime | None,
    occurrences: int | None,
    importance: str = "High",
) -> AlertProviderRecord:
    return AlertProviderRecord(
        id=identifier,
        title=f"Title {identifier}",
        description="canonical description",
        started_at=started,
        ended_at=ended,
        source_status="native-status",
        occurrence_count=occurrences,
        source_ref=f"ref:{identifier}",
        provider_importance=AlertProviderImportance(type="priority", value=importance),
    )


class RecordsProvider(FakeProvider):
    def __init__(self, records: tuple[AlertProviderRecord, ...]) -> None:
        super().__init__()
        self.records = records

    async def acquire(
        self, scope: AlertProviderScope, window: AlertAnalysisWindow
    ) -> AlertRecordsAvailable:
        self.calls.append((scope, window))
        return AlertRecordsAvailable(source=scope.source, records=self.records)


class CapturingAgent:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def complete(self, request: object) -> AlertAgentCompletion:
        self.calls.append(request)
        return AlertAgentCompletion(
            findings=(
                AlertFinding(
                    id="f-1",
                    statement="Observed",
                    evidence_refs=("alert://aggregate/alert_activity/record_count",),
                ),
            ),
            overall_importance="high",
        )


def test_overlap_normalization_and_full_lifecycle_durations() -> None:
    async def scenario() -> None:
        context = _context()
        provider = RecordsProvider(
            (
                _record(
                    "active",
                    started=datetime(2026, 8, 31, 23, tzinfo=UTC),
                    ended=None,
                    occurrences=None,
                ),
                _record(
                    "resolved",
                    started=datetime(2026, 8, 31, 23, 30, tzinfo=UTC),
                    ended=datetime(2026, 9, 1, 0, 30, tzinfo=UTC),
                    occurrences=3,
                ),
            )
        )
        outcome = await AlertAnalysisPipeline(provider=provider, agent=CapturingAgent()).analyze(
            context
        )
        alerts = outcome.artifact.payload["alerts"]
        assert [(item["status"]["normalized"], item["duration_seconds"]) for item in alerts] == [
            ("active", 7200.0),
            ("resolved", 3600.0),
        ]

    asyncio.run(scenario())


def test_mandatory_evidence_uses_effective_occurrences_and_record_statuses() -> None:
    async def scenario() -> None:
        context = _context()
        provider = RecordsProvider(
            (
                _record(
                    "active",
                    started=datetime(2026, 8, 31, 23, tzinfo=UTC),
                    ended=None,
                    occurrences=None,
                    importance="Highest",
                ),
                _record(
                    "resolved",
                    started=datetime(2026, 8, 31, 23, 30, tzinfo=UTC),
                    ended=datetime(2026, 9, 1, 0, 30, tzinfo=UTC),
                    occurrences=3,
                    importance="Low",
                ),
            )
        )
        outcome = await AlertAnalysisPipeline(provider=provider, agent=CapturingAgent()).analyze(
            context
        )
        payload = outcome.artifact.payload
        assert payload["alert_activity"] == {"record_count": 2, "occurrence_count": 4}
        assert payload["status_distribution"] == {"active": 1, "resolved": 1, "unknown": 0}
        assert payload["duration_statistics"] == {
            "min_seconds": 3600.0,
            "max_seconds": 7200.0,
            "average_seconds": 5400.0,
        }
        assert payload["provider_importance_distribution"] == {
            "type": "priority",
            "values": {"Highest": 1, "Low": 1},
        }

    asyncio.run(scenario())


def test_nonzero_zero_occurrence_invokes_agent_with_exact_projection() -> None:
    async def scenario() -> None:
        context = _context().model_copy(
            update={"lens_name": "Exact name", "lens_description": "Exact description"}
        )
        agent = CapturingAgent()
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(
                (
                    _record(
                        "zero",
                        started=datetime(2026, 8, 31, 23, tzinfo=UTC),
                        ended=None,
                        occurrences=0,
                    ),
                )
            ),
            agent=agent,
        ).analyze(context)
        request = agent.calls[0]
        assert request.lens_name == "Exact name" and request.lens_description == "Exact description"
        assert (
            request.current_records[0].id == "zero" and request.mandatory_evidence.record_count == 1
        )
        assert request.mandatory_evidence.occurrence_count == 0 and request.comparisons == ()
        assert set(request.model_dump()) == {
            "lens_name",
            "lens_description",
            "current_records",
            "mandatory_evidence",
            "comparisons",
        }
        assert outcome.artifact.payload["overall_importance"] == "high"

    asyncio.run(scenario())


def test_lifecycle_overlap_uses_strict_window_boundaries() -> None:
    async def scenario() -> None:
        context = _context()
        records = (
            _record("equal-start", started=context.analysis_window.to, ended=None, occurrences=1),
            _record(
                "equal-end",
                started=datetime(2026, 8, 31, 23, tzinfo=UTC),
                ended=context.analysis_window.from_,
                occurrences=1,
            ),
            _record(
                "before",
                started=datetime(2026, 8, 31, 22, tzinfo=UTC),
                ended=datetime(2026, 8, 31, 23, tzinfo=UTC),
                occurrences=1,
            ),
            _record(
                "after", started=datetime(2026, 9, 1, 2, tzinfo=UTC), ended=None, occurrences=1
            ),
            _record(
                "inside-start",
                started=datetime(2026, 9, 1, 0, 0, 0, 1, tzinfo=UTC),
                ended=None,
                occurrences=1,
            ),
            _record(
                "inside-end",
                started=datetime(2026, 8, 31, 23, tzinfo=UTC),
                ended=datetime(2026, 9, 1, 0, 0, 0, 1, tzinfo=UTC),
                occurrences=1,
            ),
        )
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(records), agent=CapturingAgent()
        ).analyze(context)
        assert [record["id"] for record in outcome.artifact.payload["alerts"]] == [
            "inside-start",
            "inside-end",
        ]

    asyncio.run(scenario())


def test_nonempty_all_out_of_scope_differs_from_empty_success() -> None:
    async def scenario() -> None:
        context = _context()
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(
                (_record("outside", started=context.analysis_window.to, ended=None, occurrences=1),)
            ),
            agent=FailOnCallAgent(),
        ).analyze(context)
        assert outcome.status.value == "failed"
        assert outcome.reason is not None and outcome.reason.model_dump() == {
            "code": "invalid_records",
            "component": "current_normalization",
        }
        assert outcome.artifact is None
        empty_pipeline = AlertAnalysisPipeline(provider=FakeProvider(), agent=FailOnCallAgent())
        empty = await empty_pipeline.analyze(context)
        assert empty.status.value == "completed" and empty.artifact is not None

    asyncio.run(scenario())


class FailOnUseBuilder:
    def usable(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("failed Alert paths must not invoke the result builder")


def _assert_failed(outcome: object, code: str) -> None:
    assert outcome.status.value == "failed"
    assert outcome.reason is not None and outcome.reason.code == code
    assert outcome.artifact is None


def test_current_acquisition_failures_map_exact_reason_and_stop() -> None:
    class Provider:
        def __init__(self, response: object) -> None:
            self.response = response

        async def acquire(self, *args: object) -> object:
            if isinstance(self.response, Exception):
                raise self.response
            return self.response

    async def scenario() -> None:
        cases = (
            (AlertProviderFailure(diagnostic="typed error"), "current_query_failed"),
            (AlertProviderTimeout(diagnostic="typed timeout"), "current_query_timeout"),
            (RuntimeError("thrown error"), "current_query_failed"),
            (TimeoutError("thrown timeout"), "current_query_timeout"),
        )

        def fail_analyzer(records: object) -> object:
            raise AssertionError("current acquisition failures must not invoke the analyzer")

        for response, expected in cases:
            outcome = await AlertAnalysisPipeline(
                provider=Provider(response),
                agent=FailOnCallAgent(),
                result_builder=FailOnUseBuilder(),
                analyzer=fail_analyzer,
            ).analyze(_context())
            _assert_failed(outcome, expected)

    asyncio.run(scenario())


def test_all_invalid_current_stops_before_analysis() -> None:
    async def scenario() -> None:
        response = AlertRecordsAvailable(
            source="fixture-source",
            records=(
                {"id": "missing-title", "started_at": "2026-09-01T00:00:00Z"},
                {"id": "bad-start", "title": "Bad", "started_at": "nope"},
                _record(
                    "duplicate", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
                ),
                _record(
                    "duplicate", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
                ),
            ),
        )
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(response.records),
            agent=FailOnCallAgent(),
            result_builder=FailOnUseBuilder(),
            analyzer=lambda _: (_ for _ in ()).throw(AssertionError("analyzer must not run")),
        ).analyze(_context())
        _assert_failed(outcome, "invalid_records")

    asyncio.run(scenario())


def test_mandatory_analysis_failure_stops_agent_and_builder() -> None:
    async def scenario() -> None:
        context = _context().model_copy(update={"reference_periods": ("1d",)})
        provider = OffsetProvider(
            {
                context.analysis_window.from_: AlertRecordsAvailable(
                    source="fixture-source",
                    records=(
                        _record(
                            "valid",
                            started=datetime(2026, 9, 1, tzinfo=UTC),
                            ended=None,
                            occurrences=1,
                        ),
                    ),
                ),
                datetime(2026, 8, 31, tzinfo=UTC): AlertRecordsAvailable(source="fixture-source"),
            }
        )

        def fail_after_reference_acquisition(records: object) -> object:
            assert [call[1].from_ for call in provider.calls] == [
                context.analysis_window.from_,
                datetime(2026, 8, 31, tzinfo=UTC),
            ]
            raise RuntimeError("mandatory failure")

        outcome = await AlertAnalysisPipeline(
            provider=provider,
            agent=FailOnCallAgent(),
            result_builder=FailOnUseBuilder(),
            analyzer=fail_after_reference_acquisition,
        ).analyze(context)
        _assert_failed(outcome, "deterministic_analysis_failed")

    asyncio.run(scenario())


def test_reference_analysis_failure_stops_agent_and_builder() -> None:
    class Builder:
        def __init__(self) -> None:
            self.calls = 0

        def usable(self, *args: object, **kwargs: object) -> object:
            self.calls += 1
            raise AssertionError("deterministic reference failures must not build a result")

    async def scenario() -> None:
        context = _context().model_copy(update={"reference_periods": ("1d",)})
        mixed_reference_records = (
            _record(
                "reference-priority",
                started=datetime(2026, 8, 31, tzinfo=UTC),
                ended=None,
                occurrences=1,
            ),
            _record(
                "reference-severity",
                started=datetime(2026, 8, 31, tzinfo=UTC),
                ended=None,
                occurrences=1,
            ).model_copy(
                update={
                    "provider_importance": AlertProviderImportance(type="severity", value="High")
                }
            ),
        )
        provider = OffsetProvider(
            {
                context.analysis_window.from_: AlertRecordsAvailable(
                    source="fixture-source",
                    records=(
                        _record(
                            "current",
                            started=datetime(2026, 9, 1, tzinfo=UTC),
                            ended=None,
                            occurrences=1,
                        ),
                    ),
                ),
                datetime(2026, 8, 31, tzinfo=UTC): AlertRecordsAvailable(
                    source="fixture-source", records=mixed_reference_records
                ),
            }
        )
        agent, builder = FailOnCallAgent(), Builder()

        outcome = await AlertAnalysisPipeline(
            provider=provider, agent=agent, result_builder=builder
        ).analyze(context)

        _assert_failed(outcome, "deterministic_analysis_failed")
        assert agent.calls == 0
        assert builder.calls == 0

    asyncio.run(scenario())


def test_required_agent_failures_are_rejected_before_builder() -> None:
    class Agent:
        def __init__(self, response: object) -> None:
            self.response = response

        async def complete(self, request: object) -> object:
            if isinstance(self.response, Exception):
                raise self.response
            return self.response

    async def scenario() -> None:
        malformed_finding = {"findings": [{"id": "f"}], "overall_importance": "high"}
        empty_evidence_finding = {
            "findings": [{"id": "f", "statement": "ungrounded", "evidence_refs": []}],
            "overall_importance": "high",
        }
        cases = (
            (RuntimeError("agent error"), "agent_failed"),
            (TimeoutError("agent timeout"), "agent_timeout"),
            ({"findings": [], "overall_importance": "none"}, "agent_failed"),
            ({"findings": [], "overall_importance": "invalid"}, "agent_failed"),
            ({"findings": [], "overall_importance": "high", "unexpected": True}, "agent_failed"),
            ({"findings": []}, "agent_failed"),
            (malformed_finding, "agent_failed"),
            (empty_evidence_finding, "agent_failed"),
        )
        provider = RecordsProvider(
            (_record("valid", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1),)
        )
        for response, expected in cases:
            outcome = await AlertAnalysisPipeline(
                provider=provider, agent=Agent(response), result_builder=FailOnUseBuilder()
            ).analyze(_context())
            _assert_failed(outcome, expected)

    asyncio.run(scenario())


def test_agent_projection_is_exactly_bounded() -> None:
    with pytest.raises(ValidationError):
        AlertAgentCompletion(findings=(), overall_importance="none")
    with pytest.raises(ValidationError):
        AlertAgentCompletion.model_validate(
            {"findings": [], "overall_importance": "high", "raw_payload": "forbidden"}
        )


class OffsetProvider(FakeProvider):
    def __init__(self, responses: dict[datetime, object]) -> None:
        super().__init__()
        self.responses = responses

    async def acquire(self, scope: AlertProviderScope, window: AlertAnalysisWindow) -> object:
        self.calls.append((scope, window))
        response = self.responses[window.from_]
        if isinstance(response, Exception):
            raise response
        return response


def test_references_are_independent_ordered_and_precede_zero_gate() -> None:
    async def scenario() -> None:
        context = _context().model_copy(update={"reference_periods": ("7d", "1d", "14d")})
        responses = {
            context.analysis_window.from_: AlertRecordsAvailable(
                source="fixture-source",
                records=(
                    _record(
                        "current",
                        started=datetime(2026, 9, 1, tzinfo=UTC),
                        ended=None,
                        occurrences=3,
                    ),
                ),
            ),
            datetime(2026, 8, 25, tzinfo=UTC): AlertRecordsAvailable(
                source="fixture-source",
                records=(
                    _record(
                        "higher",
                        started=datetime(2026, 8, 25, tzinfo=UTC),
                        ended=None,
                        occurrences=5,
                    ),
                ),
            ),
            datetime(2026, 8, 31, tzinfo=UTC): RuntimeError("unavailable"),
            datetime(2026, 8, 18, tzinfo=UTC): AlertRecordsAvailable(
                source="fixture-source",
                records=(
                    _record(
                        "lower",
                        started=datetime(2026, 8, 18, tzinfo=UTC),
                        ended=None,
                        occurrences=1,
                    ),
                ),
            ),
        }
        provider, agent = OffsetProvider(responses), CapturingAgent()
        outcome = await AlertAnalysisPipeline(provider=provider, agent=agent).analyze(context)
        assert [call[1].from_ for call in provider.calls] == [
            context.analysis_window.from_,
            datetime(2026, 8, 25, tzinfo=UTC),
            datetime(2026, 8, 31, tzinfo=UTC),
            datetime(2026, 8, 18, tzinfo=UTC),
        ]
        assert [item["offset"] for item in outcome.artifact.payload["comparisons"]] == ["7d", "14d"]
        assert [
            item["occurrence_comparison"]["direction"]
            for item in outcome.artifact.payload["comparisons"]
        ] == ["decreased", "increased"]
        assert outcome.status.value == "partial" and len(agent.calls) == 1

        zero_responses = responses | {
            context.analysis_window.from_: AlertRecordsAvailable(source="fixture-source")
        }
        zero_provider, zero_agent = OffsetProvider(zero_responses), FailOnCallAgent()
        zero_outcome = await AlertAnalysisPipeline(
            provider=zero_provider, agent=zero_agent
        ).analyze(context)
        assert [item["offset"] for item in zero_outcome.artifact.payload["comparisons"]] == [
            "7d",
            "14d",
        ]
        assert zero_outcome.status.value == "partial" and zero_agent.calls == 0

    asyncio.run(scenario())


def test_invalid_current_subset_selects_current_normalization_partial() -> None:
    async def scenario() -> None:
        context = _context()
        valid = _record(
            "valid", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
        )
        invalid_records = (
            {"title": "Missing ID", "started_at": "2026-09-01T00:00:00Z"},
            {"id": "missing-title", "started_at": "2026-09-01T00:00:00Z"},
            {"id": "bad-start", "title": "Bad start", "started_at": "not-a-time"},
            {
                "id": "bad-end",
                "title": "Bad end",
                "started_at": "2026-09-01T00:00:00Z",
                "ended_at": "not-a-time",
            },
            {
                "id": "reversed",
                "title": "Reversed",
                "started_at": "2026-09-01T00:30:00Z",
                "ended_at": "2026-09-01T00:00:00Z",
            },
        )
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider((valid, *invalid_records)), agent=CapturingAgent()
        ).analyze(context)
        assert outcome.status.value == "partial"
        assert outcome.reason is not None and outcome.reason.model_dump() == {
            "code": "invalid_records",
            "component": "current_normalization",
        }
        assert [item["id"] for item in outcome.artifact.payload["alerts"]] == ["valid"]
        assert outcome.artifact.payload["alert_activity"] == {
            "record_count": 1,
            "occurrence_count": 1,
        }

    asyncio.run(scenario())


def test_unavailable_and_duplicate_reference_sets_omit_only_their_offsets() -> None:
    async def scenario() -> None:
        context = _context().model_copy(
            update={"reference_periods": ("7d", "1d", "14d", "2d", "3d")}
        )
        current = AlertRecordsAvailable(
            source="fixture-source",
            records=(
                _record(
                    "current", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=3
                ),
            ),
        )
        provider = OffsetProvider(
            {
                context.analysis_window.from_: current,
                datetime(2026, 8, 25, tzinfo=UTC): RuntimeError("reference error"),
                datetime(2026, 8, 31, tzinfo=UTC): TimeoutError("reference timeout"),
                datetime(2026, 8, 18, tzinfo=UTC): AlertRecordsAvailable(
                    source="fixture-source", records=({"id": "malformed", "started_at": "bad"},)
                ),
                datetime(2026, 8, 30, tzinfo=UTC): AlertRecordsAvailable(
                    source="fixture-source",
                    records=(
                        _record(
                            "duplicate",
                            started=datetime(2026, 8, 30, tzinfo=UTC),
                            ended=None,
                            occurrences=99,
                        ),
                        _record(
                            "reference-unique",
                            started=datetime(2026, 8, 30, tzinfo=UTC),
                            ended=None,
                            occurrences=1,
                        ),
                        _record(
                            "duplicate",
                            started=datetime(2026, 8, 30, tzinfo=UTC),
                            ended=None,
                            occurrences=99,
                        ),
                    ),
                ),
                datetime(2026, 8, 29, tzinfo=UTC): AlertRecordsAvailable(
                    source="fixture-source",
                    records=(
                        _record(
                            "successful-reference",
                            started=datetime(2026, 8, 29, tzinfo=UTC),
                            ended=None,
                            occurrences=1,
                        ),
                    ),
                ),
            }
        )
        outcome = await AlertAnalysisPipeline(provider=provider, agent=CapturingAgent()).analyze(
            context
        )
        assert [call[1].from_ for call in provider.calls] == [
            context.analysis_window.from_,
            datetime(2026, 8, 25, tzinfo=UTC),
            datetime(2026, 8, 31, tzinfo=UTC),
            datetime(2026, 8, 18, tzinfo=UTC),
            datetime(2026, 8, 30, tzinfo=UTC),
            datetime(2026, 8, 29, tzinfo=UTC),
        ]
        assert outcome.status.value == "partial"
        assert outcome.reason is not None and outcome.reason.model_dump() == {
            "code": "reference_unavailable",
            "component": "reference_periods",
        }
        assert outcome.artifact.payload["comparisons"] == [
            {
                "offset": "3d",
                "occurrence_comparison": {
                    "current": 3,
                    "reference": 1,
                    "delta": 2,
                    "direction": "increased",
                },
            }
        ]
        assert [item["id"] for item in outcome.artifact.payload["alerts"]] == ["current"]
        assert "duplicate" not in str(outcome.artifact.payload)
        assert "reference-unique" not in str(outcome.artifact.payload)
        assert "successful-reference" not in str(outcome.artifact.payload)

    asyncio.run(scenario())


def test_duplicate_collision_rejects_every_member() -> None:
    async def scenario() -> None:
        context = _context()
        records = (
            _record(
                "duplicate", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
            ),
            _record("unique", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1),
            _record(
                "duplicate", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
            ),
        )
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(records), agent=CapturingAgent()
        ).analyze(context)
        assert [item["id"] for item in outcome.artifact.payload["alerts"]] == ["unique"]
        assert outcome.status.value == "partial"

    asyncio.run(scenario())


def test_successful_empty_reference_yields_zero_comparison() -> None:
    async def scenario() -> None:
        context = _context().model_copy(update={"reference_periods": ("1d",)})
        current = AlertRecordsAvailable(
            source="fixture-source",
            records=(
                _record(
                    "current", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=3
                ),
            ),
        )
        provider = OffsetProvider(
            {
                context.analysis_window.from_: current,
                datetime(2026, 8, 31, tzinfo=UTC): AlertRecordsAvailable(source="fixture-source"),
            }
        )
        outcome = await AlertAnalysisPipeline(provider=provider, agent=CapturingAgent()).analyze(
            context
        )
        assert outcome.status.value == "completed"
        assert outcome.artifact.payload["comparisons"] == [
            {
                "offset": "1d",
                "occurrence_comparison": {
                    "current": 3,
                    "reference": 0,
                    "delta": 3,
                    "direction": "increased",
                },
            }
        ]

    asyncio.run(scenario())


def test_all_references_unavailable_remains_usable_partial() -> None:
    async def scenario() -> None:
        context = _context().model_copy(update={"reference_periods": ("1d", "7d", "14d")})
        current = AlertRecordsAvailable(
            source="fixture-source",
            records=(
                _record(
                    "current", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
                ),
            ),
        )
        provider = OffsetProvider(
            {
                context.analysis_window.from_: current,
                datetime(2026, 8, 31, tzinfo=UTC): RuntimeError("error"),
                datetime(2026, 8, 25, tzinfo=UTC): RuntimeError("timeout"),
                datetime(2026, 8, 18, tzinfo=UTC): AlertRecordsAvailable(
                    source="fixture-source", records=({"id": "bad", "started_at": "bad"},)
                ),
            }
        )
        outcome = await AlertAnalysisPipeline(provider=provider, agent=CapturingAgent()).analyze(
            context
        )
        assert outcome.status.value == "partial"
        assert outcome.reason is not None and outcome.reason.model_dump() == {
            "code": "reference_unavailable",
            "component": "reference_periods",
        }
        assert outcome.artifact.payload["comparisons"] == []

    asyncio.run(scenario())


def test_current_incompleteness_precedes_reference_unavailability() -> None:
    async def scenario() -> None:
        context = _context().model_copy(update={"reference_periods": ("1d",)})
        provider = OffsetProvider(
            {
                context.analysis_window.from_: AlertRecordsAvailable(
                    source="fixture-source",
                    records=(
                        _record(
                            "current",
                            started=datetime(2026, 9, 1, tzinfo=UTC),
                            ended=None,
                            occurrences=1,
                        ),
                        {"id": "bad", "started_at": "bad"},
                    ),
                ),
                datetime(2026, 8, 31, tzinfo=UTC): RuntimeError("unavailable"),
            }
        )
        outcome = await AlertAnalysisPipeline(provider=provider, agent=CapturingAgent()).analyze(
            context
        )
        assert outcome.reason is not None and outcome.reason.model_dump() == {
            "code": "invalid_records",
            "component": "current_normalization",
        }
        assert "reference_unavailable" not in str(outcome.artifact.payload)

    asyncio.run(scenario())


def test_optional_failure_timeout_continue_with_minimal_trace() -> None:
    class ToolUsingAgent:
        async def complete(self, request: object, tools: object) -> AlertAgentCompletion:
            await tools.execute("recurrence_concentration_analysis", {})
            await tools.execute("duration_outlier_analysis", {})
            await tools.execute("reference_pattern_analysis", {})
            await tools.execute("recurrence_concentration_analysis", {})
            return AlertAgentCompletion(
                findings=(
                    AlertFinding(
                        id="f-1",
                        statement="Observed",
                        evidence_refs=("alert://aggregate/alert_activity/record_count",),
                    ),
                ),
                overall_importance="high",
            )

    async def scenario() -> None:
        records = (
            _record("valid", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1),
        )

        def registry(records: tuple[object, ...], evidence: object) -> AlertOptionalToolRegistry:
            def failed() -> object:
                raise RuntimeError("transient")

            def timed_out() -> object:
                raise TimeoutError("transient")

            return AlertOptionalToolRegistry(
                records,
                evidence,
                evaluators={
                    "recurrence_concentration_analysis": timed_out,
                    "duration_outlier_analysis": lambda: duration_outliers(records),
                    "reference_pattern_analysis": failed,
                },
            )

        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(records),
            agent=ToolUsingAgent(),
            tool_registry_factory=registry,
        ).analyze(_context())
        payload = outcome.artifact.payload
        assert outcome.status.value == "completed"
        assert payload["optional_tool_execution"] == {
            "unsuccessful_calls": [
                {"tool": "recurrence_concentration_analysis", "status": "timeout"},
                {"tool": "reference_pattern_analysis", "status": "failed"},
                {"tool": "recurrence_concentration_analysis", "status": "timeout"},
            ]
        }
        serialized = str(payload)
        assert "diagnostic" not in serialized and "ordinal" not in serialized
        assert "'outcome': 'not_applicable'" not in serialized
        assert "'outcome': 'success'" not in serialized

    asyncio.run(scenario())


def test_unresolvable_finding_reference_stops_before_persistence() -> None:
    class Agent:
        async def complete(self, request: object) -> AlertAgentCompletion:
            return AlertAgentCompletion(
                findings=(
                    AlertFinding(
                        id="transient-only",
                        statement="not persisted",
                        evidence_refs=("alert://optional/recurrence",),
                    ),
                ),
                overall_importance="high",
            )

    async def scenario() -> None:
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(
                (
                    _record(
                        "valid", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
                    ),
                )
            ),
            agent=Agent(),
        ).analyze(_context())
        _assert_failed(outcome, "result_validation_failed")
        assert outcome.reason.component == "alert_result_builder"

    asyncio.run(scenario())


def test_representative_builder_failures_map_exact_reason() -> None:
    class CorruptingBuilder(AlertResultBuilder):
        def __init__(self, failure: str) -> None:
            super().__init__()
            self.failure = failure

        def _validate_completed_result(self, result: object, context: object) -> object:
            if self.failure == "identity":
                result = result.model_copy(
                    update={"identity": result.identity.model_copy(update={"lens_id": "wrong"})}
                )
            else:
                result = result.model_copy(
                    update={
                        "alert_activity": result.alert_activity.model_copy(
                            update={"occurrence_count": result.alert_activity.occurrence_count + 1}
                        )
                    }
                )
            return super()._validate_completed_result(result, context)

    class MalformedAgent:
        async def complete(self, request: object) -> object:
            return {"findings": "not-a-list", "overall_importance": "high"}

    async def scenario() -> None:
        provider = RecordsProvider(
            (_record("valid", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1),)
        )
        for failure in ("identity", "activity"):
            outcome = await AlertAnalysisPipeline(
                provider=provider, agent=CapturingAgent(), result_builder=CorruptingBuilder(failure)
            ).analyze(_context())
            _assert_failed(outcome, "result_validation_failed")
            assert outcome.reason.component == "alert_result_builder" and outcome.artifact is None
        outcome = await AlertAnalysisPipeline(provider=provider, agent=MalformedAgent()).analyze(
            _context()
        )
        _assert_failed(outcome, "agent_failed")

    asyncio.run(scenario())


def test_contextual_builder_comparison_failure_maps_to_artifact_free_terminal_outcome() -> None:
    class UnconfiguredComparisonBuilder(AlertResultBuilder):
        def _validate_completed_result(self, result: object, context: object) -> object:
            current = result.alert_activity.occurrence_count
            comparison = AlertReferenceComparison(
                offset="1d",
                occurrence_comparison=AlertOccurrenceComparison(
                    current=current,
                    reference=0,
                    delta=current,
                    direction="increased" if current else "unchanged",
                ),
            )
            return super()._validate_completed_result(
                result.model_copy(update={"comparisons": (comparison,)}), context
            )

    async def scenario() -> None:
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(
                (
                    _record(
                        "valid",
                        started=datetime(2026, 9, 1, tzinfo=UTC),
                        ended=None,
                        occurrences=1,
                    ),
                )
            ),
            agent=CapturingAgent(),
            result_builder=UnconfiguredComparisonBuilder(),
        ).analyze(_context())

        _assert_failed(outcome, "result_validation_failed")
        assert outcome.reason.component == "alert_result_builder"
        assert outcome.artifact is None

    asyncio.run(scenario())


def test_pydantic_ai_invalid_completion_error_and_timeout_map_to_agent_failures() -> None:
    class Provider:
        async def acquire(
            self, scope: AlertProviderScope, window: AlertAnalysisWindow
        ) -> AlertRecordsAvailable:
            return AlertRecordsAvailable(
                source=scope.source,
                records=(
                    _record(
                        "valid",
                        started=datetime(2026, 9, 1, tzinfo=UTC),
                        ended=None,
                        occurrences=1,
                    ),
                ),
            )

    def invalid(_: object, info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"findings": (), "overall_importance": "none"},
                )
            ]
        )

    def failed(_: object, __: AgentInfo) -> ModelResponse:
        raise RuntimeError("model failed")

    def timed_out(_: object, __: AgentInfo) -> ModelResponse:
        raise TimeoutError("model timed out")

    async def scenario() -> None:
        for model, code in (
            (FunctionModel(invalid), "agent_failed"),
            (FunctionModel(failed), "agent_failed"),
            (FunctionModel(timed_out), "agent_timeout"),
        ):
            outcome = await AlertAnalysisPipeline(
                provider=Provider(), agent=PydanticAIAlertAnalysisAgent(model)
            ).analyze(_context())
            _assert_failed(outcome, code)
            assert outcome.artifact is None

    asyncio.run(scenario())


def test_mutated_agent_completion_with_empty_evidence_refs_fails_before_builder() -> None:
    class Agent:
        async def complete(self, request: object) -> AlertAgentCompletion:
            return AlertAgentCompletion.model_construct(
                findings=(
                    AlertFinding.model_construct(
                        id="ungrounded", statement="no supporting evidence", evidence_refs=()
                    ),
                ),
                overall_importance="high",
            )

    async def scenario() -> None:
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(
                (
                    _record(
                        "valid",
                        started=datetime(2026, 9, 1, tzinfo=UTC),
                        ended=None,
                        occurrences=1,
                    ),
                )
            ),
            agent=Agent(),
            result_builder=FailOnUseBuilder(),
        ).analyze(_context())
        _assert_failed(outcome, "agent_failed")
        assert outcome.artifact is None

    asyncio.run(scenario())


def test_zero_record_builder_failure_maps_to_artifact_free_builder_failure() -> None:
    class ZeroRejectingBuilder(AlertResultBuilder):
        def _validate_completed_result(self, result: object, context: object) -> object:
            raise ValueError("zero result invariant rejected")

    async def scenario() -> None:
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(()),
            agent=FailOnCallAgent(),
            result_builder=ZeroRejectingBuilder(),
        ).analyze(_context())
        _assert_failed(outcome, "result_validation_failed")
        assert outcome.reason.component == "alert_result_builder"
        assert outcome.artifact is None

    asyncio.run(scenario())


def test_pre_transaction_work_finishes_before_persistence_composition() -> None:
    """Record a representative usable path before the caller opens its transaction."""

    async def scenario() -> None:
        phases: list[str] = []

        class ToolUsingAgent:
            async def complete(self, request: object, tools: object) -> AlertAgentCompletion:
                await tools.execute("recurrence_concentration_analysis", {})
                phases.append("optional_tool_execution")
                return AlertAgentCompletion(
                    findings=(
                        AlertFinding(
                            id="phase-order",
                            statement="grounded",
                            evidence_refs=("alert://current/phase-order",),
                        ),
                    ),
                    overall_importance="high",
                )

        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(
                (
                    _record(
                        "phase-order",
                        started=datetime(2026, 8, 31, 23, tzinfo=UTC),
                        ended=None,
                        occurrences=1,
                    ),
                )
            ),
            agent=ToolUsingAgent(),
            record_phase=phases.append,
        ).analyze(_context())
        assert outcome.artifact is not None
        phases.append("caller_transaction_open")
        phases.append("terminal_persistence")
        phases.append("caller_commit")
        assert phases == [
            "provider_acquisition",
            "current_normalization",
            "reference_acquisition",
            "mandatory_analysis",
            "zero_record_gate",
            "agent_completion",
            "optional_tool_execution",
            "result_build",
            "caller_transaction_open",
            "terminal_persistence",
            "caller_commit",
        ]

    asyncio.run(scenario())
