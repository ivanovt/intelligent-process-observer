from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.metrics.contracts import (
    MetricAgentCompletion,
    MetricAnalysisWindow,
    MetricCurrentEvidence,
    MetricHistoryCandidate,
    MetricHistoryCandidates,
    MetricHistoryPolicy,
    MetricIdentity,
    MetricLensExecutionContext,
    MetricProviderScope,
    MetricSample,
    MetricSeriesAvailable,
)
from app.metrics.history import analyze_history, classify_transition, select_history_candidates
from app.metrics.pipeline import MetricAnalysisPipeline
from app.metrics.result_builder import MetricResultBuilder

WINDOW_START = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def run(coroutine):
    return asyncio.run(coroutine)


def context(*, policy: MetricHistoryPolicy | None = None) -> MetricLensExecutionContext:
    return MetricLensExecutionContext(
        identity=MetricIdentity(
            observation_id=uuid4(),
            observation_run_id=uuid4(),
            lens_id="coolant-temperature",
            lens_run_id=uuid4(),
            metric_ref="coolant_temperature",
            unit="celsius",
        ),
        provider_scope=MetricProviderScope(
            adapter_type="prometheus", source_id="plant-prometheus", query="temperature"
        ),
        analysis_window=MetricAnalysisWindow(
            **{"from": WINDOW_START, "to": WINDOW_START + timedelta(minutes=3)}
        ),
        analysis_objectives=(),
        reference_periods=(),
        history_policy=policy or MetricHistoryPolicy(),
    )


def candidate(
    *,
    lens_run_id: UUID | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    mean: float | None = 10.0,
    status: str = "completed",
    data_quality: str | None = "good",
) -> MetricHistoryCandidate:
    return MetricHistoryCandidate(
        lens_run_id=lens_run_id or uuid4(),
        analysis_window=MetricAnalysisWindow(
            **{
                "from": start or WINDOW_START - timedelta(minutes=5),
                "to": end or WINDOW_START - timedelta(minutes=1),
            }
        ),
        status=status,
        data_quality=data_quality,
        mean=mean,
    )


def test_history_defaults_and_event_time_selection_exclude_ineligible_candidates() -> None:
    execution_context = context(
        policy=MetricHistoryPolicy(lookback_runs=2, level_change_tolerance=0.1)
    )
    tie_end = WINDOW_START - timedelta(minutes=1)
    first = candidate(start=WINDOW_START - timedelta(minutes=6), end=tie_end, mean=10.0)
    second = candidate(start=WINDOW_START - timedelta(minutes=5), end=tie_end, mean=20.0)
    newest = candidate(
        start=WINDOW_START - timedelta(minutes=2),
        end=WINDOW_START + timedelta(minutes=2),
        mean=30.0,
    )
    current = candidate(
        lens_run_id=execution_context.identity.lens_run_id,
        mean=40.0,
    )
    failed = candidate(mean=None, status="failed", data_quality=None)
    insufficient = candidate(mean=None, data_quality="insufficient")
    later = candidate(end=WINDOW_START + timedelta(minutes=4), mean=50.0)

    selected = select_history_candidates(
        execution_context,
        (newest, later, failed, first, current, insufficient, second),
    )

    assert MetricHistoryPolicy().model_dump() == {
        "lookback_runs": 5,
        "level_change_tolerance": 0.05,
    }
    assert [item.lens_run_id for item in selected] == [second.lens_run_id, newest.lens_run_id]
    assert newest.analysis_window.to < execution_context.analysis_window.to


@pytest.mark.parametrize(
    ("status", "data_quality", "mean"),
    [
        ("completed", "good", None),
        ("completed", "degraded", None),
        ("completed", "insufficient", 10.0),
        ("completed", None, None),
        ("completed", None, 10.0),
        ("partial", "good", None),
        ("partial", "degraded", None),
        ("partial", "insufficient", None),
        ("partial", "insufficient", 10.0),
        ("partial", None, None),
        ("partial", None, 10.0),
        ("failed", None, 10.0),
        ("failed", "good", None),
        ("failed", "good", 10.0),
        ("failed", "degraded", None),
        ("failed", "degraded", 10.0),
        ("failed", "insufficient", None),
        ("failed", "insufficient", 10.0),
    ],
)
def test_history_candidate_rejects_invalid_result_variant_combinations(
    status: str, data_quality: str | None, mean: float | None
) -> None:
    with pytest.raises(ValueError):
        candidate(status=status, data_quality=data_quality, mean=mean)


def test_history_selection_excludes_candidate_ending_at_current_window_end() -> None:
    execution_context = context()
    ending_at_current_end = candidate(
        end=execution_context.analysis_window.to,
        mean=10.0,
    )

    selected = select_history_candidates(execution_context, (ending_at_current_end,))

    assert selected == ()


def test_history_selection_uses_lexical_lens_run_id_for_full_event_time_ties() -> None:
    execution_context = context(policy=MetricHistoryPolicy(lookback_runs=2))
    tied_start = WINDOW_START - timedelta(minutes=5)
    tied_end = WINDOW_START - timedelta(minutes=1)
    lexical_first = candidate(
        lens_run_id=UUID("00000000-0000-0000-0000-000000000001"),
        start=tied_start,
        end=tied_end,
    )
    lexical_second = candidate(
        lens_run_id=UUID("00000000-0000-0000-0000-000000000002"),
        start=tied_start,
        end=tied_end,
    )

    selected = select_history_candidates(
        execution_context,
        (lexical_second, lexical_first),
    )

    assert [item.lens_run_id for item in selected] == [
        lexical_first.lens_run_id,
        lexical_second.lens_run_id,
    ]


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (0.0, 0.0, "stable"),
        (5.0, 100.0, "unknown"),
        (5.00001, 100.0, "increasing"),
        (100.0, 105.0, "stable"),
        (100.0, 95.0, "stable"),
        (100.0, 105.00001, "increasing"),
        (100.0, 94.99999, "decreasing"),
    ],
)
def test_history_transition_boundaries_are_exact(
    previous: float, current: float, expected: str
) -> None:
    assert classify_transition(previous, current, 0.05) == expected


@pytest.mark.parametrize(
    ("means", "direction", "pattern", "changes"),
    [
        ((100.0, 200.0, 400.0), "increasing", "sustained", 0),
        ((100.0, 100.0, 100.0), "stable", "sustained", 0),
        ((100.0, 200.0, 100.0), "mixed", "reversing", 1),
        ((100.0, 200.0, 400.0, 200.0, 100.0), "mixed", "reversing", 1),
        ((100.0, 200.0, 200.0, 100.0), "mixed", "reversing", 1),
        ((100.0, 200.0, 10000.0, 5000.0), "mixed", "reversing", 1),
        ((100.0, 200.0, 100.0, 200.0), "mixed", "oscillating", 2),
        ((100.0, 50.0, 100.0, 50.0), "mixed", "oscillating", 2),
        ((100.0, 200.0, 200.0, 400.0), "mixed", "mixed", 0),
        ((100.0, 100.0, 10000.0, 10000.0), "stable", "sustained", 0),
        ((1.0, 100.0, 50.0), "decreasing", "unknown", 0),
    ],
)
def test_history_direction_pattern_and_stable_neutral_rules(
    means: tuple[float, ...], direction: str, pattern: str, changes: int
) -> None:
    execution_context = context(policy=MetricHistoryPolicy(lookback_runs=5))
    historical = tuple(
        candidate(
            start=WINDOW_START - timedelta(minutes=len(means) - index + 1),
            end=WINDOW_START - timedelta(minutes=len(means) - index),
            mean=mean,
        )
        for index, mean in enumerate(means[:-1])
    )
    history, evidence = analyze_history(
        execution_context,
        historical,
        MetricCurrentEvidence(mean=means[-1], std=0.0, min=means[-1], max=means[-1], slope=0.0),
    ) or pytest.fail("History candidates should be selected")

    assert history.direction == direction
    assert history.pattern == pattern
    assert evidence.direction_changes == changes
    assert evidence.classifiable_transitions + evidence.unknown_transitions == len(history.run_ids)


def test_history_unknown_between_directions_is_removed_before_pattern_detection() -> None:
    execution_context = context(policy=MetricHistoryPolicy(lookback_runs=5))
    means = (100.0, 200.0, 10000.0, 5000.0)
    historical = tuple(
        candidate(
            start=WINDOW_START - timedelta(minutes=len(means) - index + 1),
            end=WINDOW_START - timedelta(minutes=len(means) - index),
            mean=mean,
        )
        for index, mean in enumerate(means[:-1])
    )

    history, evidence = analyze_history(
        execution_context,
        historical,
        MetricCurrentEvidence(mean=means[-1], std=0.0, min=means[-1], max=means[-1], slope=0.0),
    ) or pytest.fail("History candidates should be selected")

    assert history.pattern == "reversing"
    assert evidence.classifiable_transitions == 2
    assert evidence.unknown_transitions == 1
    assert evidence.direction_changes == 1


class FakeProvider:
    async def acquire(self, scope, window):
        return MetricSeriesAvailable(
            source="prometheus",
            samples=(
                MetricSample(timestamp=window.from_, value=10.0),
                MetricSample(timestamp=window.from_ + timedelta(minutes=1), value=20.0),
                MetricSample(timestamp=window.to, value=40.0),
            ),
        )


class FakeAgent:
    async def complete(self, request, tools=None):
        return MetricAgentCompletion()


class FakeHistoryReader:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    async def load(self, session, execution_context):
        self.calls.append((session, execution_context))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class RecordingRepository:
    def __init__(self):
        self.persisted = []

    async def advance_lens_run(self, session, lens_run, target, *, reason=None):
        lens_run.status = target.value
        lens_run.reason = None if reason is None else reason.model_dump(mode="json")

    async def persist_lens_analysis_result(self, session, lens_run, result):
        self.persisted.append(result)
        return SimpleNamespace(payload=result.payload, status=result.status.value)


def _pipeline(reader: FakeHistoryReader, repository: RecordingRepository) -> MetricAnalysisPipeline:
    return MetricAnalysisPipeline(
        provider=FakeProvider(),
        agent=FakeAgent(),
        history_reader=reader,
        repository=repository,
        result_builder=MetricResultBuilder(lambda: WINDOW_START + timedelta(minutes=5)),
    )


def test_fake_reader_history_is_persisted_inside_the_terminal_phase() -> None:
    execution_context = context()
    reader = FakeHistoryReader(
        MetricHistoryCandidates(
            candidates=(
                candidate(
                    end=WINDOW_START + timedelta(minutes=2),
                    start=WINDOW_START - timedelta(minutes=1),
                    mean=1.0,
                ),
            )
        )
    )
    repository = RecordingRepository()
    pipeline = _pipeline(reader, repository)
    analysis = run(pipeline.analyze(execution_context))
    lens_run = SimpleNamespace(status="running", reason=None)

    artifact = run(pipeline.persist_terminal(object(), lens_run, analysis))

    assert artifact.status == "completed"
    assert lens_run.status == "completed"
    assert len(reader.calls) == 1
    payload = repository.persisted[0].payload
    assert payload["history"]["run_ids"] == [str(reader.outcome.candidates[0].lens_run_id)]
    assert payload["evidence"]["history"] == {
        "level_change_tolerance": 0.05,
        "classifiable_transitions": 0,
        "unknown_transitions": 1,
        "increasing_transitions": 0,
        "decreasing_transitions": 0,
        "stable_transitions": 0,
        "direction_changes": 0,
    }
    assert payload["history"]["direction"] == "unknown"
    assert payload["history"]["pattern"] == "unknown"


def test_history_computation_failure_persists_only_the_history_partial(monkeypatch) -> None:
    import app.metrics.pipeline as pipeline_module

    execution_context = context()
    reader = FakeHistoryReader(MetricHistoryCandidates(candidates=(candidate(mean=10.0),)))
    repository = RecordingRepository()
    monkeypatch.setattr(
        pipeline_module,
        "analyze_history",
        lambda *_: (_ for _ in ()).throw(RuntimeError("unexpected computation failure")),
    )
    analysis = run(_pipeline(reader, repository).analyze(execution_context))
    lens_run = SimpleNamespace(status="running", reason=None)

    artifact = run(_pipeline(reader, repository).persist_terminal(object(), lens_run, analysis))

    assert artifact.status == "partial"
    assert lens_run.reason == {"code": "history_analysis_failed", "component": "history"}
    assert repository.persisted[0].payload["reason"] == lens_run.reason
    assert "history" not in repository.persisted[0].payload
    assert "history" not in repository.persisted[0].payload["evidence"]


def test_reader_failure_propagates_without_transition_or_artifact() -> None:
    execution_context = context()
    reader = FakeHistoryReader(RuntimeError("repository query failed"))
    repository = RecordingRepository()
    pipeline = _pipeline(reader, repository)
    analysis = run(pipeline.analyze(execution_context))
    lens_run = SimpleNamespace(status="running", reason=None)

    with pytest.raises(RuntimeError, match="repository query failed"):
        run(pipeline.persist_terminal(object(), lens_run, analysis))

    assert lens_run.status == "running"
    assert lens_run.reason is None
    assert repository.persisted == []
    assert len(reader.calls) == 1
    assert reader.calls[0][1] == execution_context
