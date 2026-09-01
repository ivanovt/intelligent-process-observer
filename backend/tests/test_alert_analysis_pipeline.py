import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderImportance,
    AlertProviderRecord,
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
                AlertFinding(id="f-1", statement="Observed", evidence_refs=("alert_activity",)),
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


def test_scope_exclusions_do_not_make_result_partial() -> None:
    async def scenario() -> None:
        context = _context()
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider(
                (_record("outside", started=context.analysis_window.to, ended=None, occurrences=1),)
            ),
            agent=FailOnCallAgent(),
        ).analyze(context)
        assert (
            outcome.status.value == "completed"
            and "invalid_records" not in outcome.artifact.payload
        )

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
        empty = AlertRecordsAvailable(source="fixture-source")
        responses = {
            context.analysis_window.from_: empty,
            datetime(2026, 8, 25, tzinfo=UTC): AlertRecordsAvailable(
                source="fixture-source",
                records=(
                    _record(
                        "low", started=datetime(2026, 8, 25, tzinfo=UTC), ended=None, occurrences=1
                    ),
                ),
            ),
            datetime(2026, 8, 31, tzinfo=UTC): RuntimeError("unavailable"),
            datetime(2026, 8, 18, tzinfo=UTC): AlertRecordsAvailable(
                source="fixture-source",
                records=(
                    _record(
                        "high", started=datetime(2026, 8, 18, tzinfo=UTC), ended=None, occurrences=2
                    ),
                ),
            ),
        }
        provider, agent = OffsetProvider(responses), FailOnCallAgent()
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
        ] == ["decreased", "decreased"]
        assert outcome.status.value == "partial" and agent.calls == 0

    asyncio.run(scenario())


def test_invalid_current_subset_selects_current_normalization_partial() -> None:
    async def scenario() -> None:
        context = _context()
        valid = _record(
            "valid", started=datetime(2026, 9, 1, tzinfo=UTC), ended=None, occurrences=1
        )
        malformed = {"id": "bad", "title": "Bad", "started_at": "not-a-time"}
        outcome = await AlertAnalysisPipeline(
            provider=RecordsProvider((valid, malformed)), agent=CapturingAgent()
        ).analyze(context)
        assert outcome.status.value == "partial"
        assert outcome.reason is not None and outcome.reason.model_dump() == {
            "code": "invalid_records",
            "component": "current_normalization",
        }
        assert [item["id"] for item in outcome.artifact.payload["alerts"]] == ["valid"]

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
