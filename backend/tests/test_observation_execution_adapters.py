from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.alerts.contracts import AlertProviderFailure, AlertRecordsAvailable
from app.execution import (
    AlertLensExecutionAdapter,
    AlertLensSnapshot,
    AnalysisWindow,
    ExecutionPolicy,
    LensExecutionAssignment,
    MetricLensExecutionAdapter,
    MetricLensSnapshot,
)
from app.infrastructure.persistence.models import LensRunModel, ObservationRunModel
from app.infrastructure.persistence.runtime_contracts import LensRunStatus, StructuredReason


class Transaction(AbstractAsyncContextManager["Session"]):
    def __init__(self, session: Session) -> None:
        self.session = session
        self.committed = False

    async def __aenter__(self) -> Session:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.committed = exc_type is None
        return False


class Session:
    def __init__(self, values: dict[tuple[type[object], object], object]) -> None:
        self.values = values

    async def get(self, model: type[object], identity: object) -> object | None:
        return self.values.get((model, identity))


class Factory:
    def __init__(self, session: Session, phases: list[str]) -> None:
        self.session = session
        self.phases = phases
        self.transactions: list[Transaction] = []

    def begin(self) -> Transaction:
        self.phases.append("terminal_transaction")
        transaction = Transaction(self.session)
        self.transactions.append(transaction)
        return transaction


class MetricPipeline:
    def __init__(self, phases: list[str], status: LensRunStatus) -> None:
        self.phases = phases
        self.status = status
        self.context = None

    async def analyze(self, context: object) -> object:
        self.phases.append("metric_analysis")
        self.context = context
        return SimpleNamespace(context=context)

    async def persist_terminal(
        self, session: object, lens_run: LensRunModel, analysis: object
    ) -> None:
        assert analysis.context == self.context
        self.phases.append("metric_history_and_persist")
        lens_run.status = self.status.value
        lens_run.reason = (
            {"code": "reference_unavailable", "component": "reference_periods"}
            if self.status is LensRunStatus.PARTIAL
            else {"code": "mandatory_metric_analysis_failed"}
            if self.status is LensRunStatus.FAILED
            else None
        )


class Repository:
    async def advance_lens_run(
        self,
        session: object,
        lens_run: LensRunModel,
        target: LensRunStatus,
        *,
        reason: StructuredReason | None = None,
    ) -> LensRunModel:
        lens_run.status = target.value
        lens_run.reason = reason.model_dump() if reason is not None else None
        return lens_run

    async def persist_lens_analysis_result(
        self, session: object, lens_run: LensRunModel, result: object
    ) -> object:
        return object()


class Resolver:
    def __init__(self, response: object) -> None:
        self.response = response
        self.scope = None

    def resolve(self, scope: object) -> Provider:
        self.scope = scope
        return Provider(self.response)


class Provider:
    def __init__(self, response: object) -> None:
        self.responses = list(response) if isinstance(response, tuple) else [response]

    async def acquire(self, scope: object, window: object) -> object:
        return self.responses.pop(0)


class Agent:
    async def complete(self, request: object, tools: object) -> object:
        raise AssertionError("zero-record Alert analysis must not invoke the agent")


def test_metric_adapter_projects_context_and_excludes_terminal_work_from_deadline_phase() -> None:
    assignment, lens_run, parent = _metric_assignment()
    phases: list[str] = []
    factory = Factory(_session(lens_run, parent), phases)
    pipeline = MetricPipeline(phases, LensRunStatus.COMPLETED)

    outcome = asyncio.run(
        MetricLensExecutionAdapter(session_factory=factory, pipeline=pipeline).execute(
            assignment, _policy()
        )
    )

    assert outcome.status == "completed"
    assert outcome.reason is None
    assert phases == ["metric_analysis", "terminal_transaction", "metric_history_and_persist"]
    assert pipeline.context.identity.observation_run_id == assignment.observation_run_id
    assert pipeline.context.identity.lens_run_id == assignment.lens_run_id
    assert pipeline.context.provider_scope.query == "avg(cpu_temperature)"
    assert pipeline.context.analysis_window.from_ == assignment.analysis_window.from_
    assert factory.transactions[0].committed is True


def test_metric_adapter_collects_normal_partial_and_failed_pipeline_outcomes() -> None:
    for target, expected_reason in (
        (LensRunStatus.PARTIAL, "reference_unavailable"),
        (LensRunStatus.FAILED, "mandatory_metric_analysis_failed"),
    ):
        assignment, lens_run, parent = _metric_assignment()
        phases: list[str] = []
        outcome = asyncio.run(
            MetricLensExecutionAdapter(
                session_factory=Factory(_session(lens_run, parent), phases),
                pipeline=MetricPipeline(phases, target),
            ).execute(assignment, _policy())
        )
        assert outcome.status == target.value
        assert outcome.reason is not None
        assert outcome.reason.code == expected_reason


def test_alert_adapter_persists_completed_artifact_path_with_exact_context() -> None:
    assignment, lens_run, parent = _alert_assignment()
    phases: list[str] = []
    resolver = Resolver(AlertRecordsAvailable(source="jira_track_and_release", records=()))

    outcome = asyncio.run(
        AlertLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), phases),
            repository=Repository(),  # type: ignore[arg-type]
            provider_resolver=resolver,
            agent=Agent(),  # type: ignore[arg-type]
        ).execute(assignment, _policy())
    )

    assert outcome.status == "completed"
    assert resolver.scope.source == "jira_track_and_release"
    assert resolver.scope.query == "project = OPS"
    assert phases == ["terminal_transaction"]


def test_alert_adapter_persists_normal_failed_outcome_without_an_artifact() -> None:
    assignment, lens_run, parent = _alert_assignment()
    outcome = asyncio.run(
        AlertLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), []),
            repository=Repository(),  # type: ignore[arg-type]
            provider_resolver=Resolver(AlertProviderFailure(diagnostic="unavailable")),
            agent=Agent(),  # type: ignore[arg-type]
        ).execute(assignment, _policy())
    )

    assert outcome.status == "failed"
    assert outcome.reason is not None
    assert outcome.reason.code == "current_query_failed"


def test_alert_adapter_persists_normal_partial_outcome() -> None:
    assignment, lens_run, parent = _alert_assignment(reference_periods=("1h",))
    outcome = asyncio.run(
        AlertLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), []),
            repository=Repository(),  # type: ignore[arg-type]
            provider_resolver=Resolver(
                (
                    AlertRecordsAvailable(source="jira_track_and_release", records=()),
                    AlertProviderFailure(diagnostic="reference unavailable"),
                )
            ),
            agent=Agent(),  # type: ignore[arg-type]
        ).execute(assignment, _policy())
    )

    assert outcome.status == "partial"
    assert outcome.reason is not None
    assert outcome.reason.code == "reference_unavailable"


def _metric_assignment() -> tuple[LensExecutionAssignment, LensRunModel, ObservationRunModel]:
    lens = MetricLensSnapshot(
        lens_id="cpu",
        name="CPU",
        description=None,
        metric_id="cpu_temperature",
        adapter_type="prometheus",
        source_id="primary",
        query="avg(cpu_temperature)",
        unit="celsius",
        analysis_objectives=("detect drift",),
        reference_periods=("1h",),
    )
    return _runtime_assignment(lens)


def _alert_assignment(
    *, reference_periods: tuple[str, ...] = ()
) -> tuple[LensExecutionAssignment, LensRunModel, ObservationRunModel]:
    lens = AlertLensSnapshot(
        lens_id="ops",
        name="Operations",
        description="Open incidents",
        source="jira_track_and_release",
        selector_query="project = OPS",
        analysis_objectives=("summarize",),
        reference_periods=reference_periods,
    )
    return _runtime_assignment(lens)


def _runtime_assignment(
    lens: object,
) -> tuple[LensExecutionAssignment, LensRunModel, ObservationRunModel]:
    observation_id, observation_run_id, lens_run_id = uuid4(), uuid4(), uuid4()
    assignment = LensExecutionAssignment(
        observation_id=observation_id,
        observation_run_id=observation_run_id,
        lens_run_id=lens_run_id,
        analysis_window=AnalysisWindow(
            datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 1, 1, tzinfo=UTC)
        ),
        lens=lens,  # type: ignore[arg-type]
    )
    parent = ObservationRunModel(
        id=observation_run_id, observation_id=observation_id, status="running"
    )
    lens_run = LensRunModel(
        id=lens_run_id,
        observation_run_id=observation_run_id,
        lens_id=assignment.lens.lens_id,
        lens_type=assignment.lens.lens_type,
        status="running",
    )
    return assignment, lens_run, parent


def _session(lens_run: LensRunModel, parent: ObservationRunModel) -> Session:
    return Session(
        {(LensRunModel, lens_run.id): lens_run, (ObservationRunModel, parent.id): parent}
    )


def _policy() -> ExecutionPolicy:
    return ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=1.0)
