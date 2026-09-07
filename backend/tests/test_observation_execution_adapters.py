from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.alerts.contracts import (
    AlertProviderFailure,
    AlertRecordsAvailable,
)
from app.execution import (
    AlertLensExecutionAdapter,
    AlertLensSnapshot,
    AnalysisWindow,
    ExecutionPolicy,
    LensExecutionAssignment,
    MetricLensExecutionAdapter,
    MetricLensSnapshot,
    metric_execution_context,
)
from app.infrastructure.persistence.models import (
    LensAnalysisResultModel,
    LensRunModel,
    ObservationRunModel,
)
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensRunStatus,
    LensType,
    StructuredReason,
)
from app.metrics.contracts import MetricMandatoryAnalysisFailure, PreparedInsufficientSeries
from app.metrics.pipeline import MetricPreTransactionAnalysis
from app.metrics.result_builder import MetricResultBuilder


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

    async def analyze(self, context: object) -> MetricPreTransactionAnalysis:
        self.phases.append("metric_analysis")
        self.context = context
        builder = MetricResultBuilder()
        if self.status is LensRunStatus.FAILED:
            _, terminal_result = builder.failed(
                context, MetricMandatoryAnalysisFailure(diagnostic="test failure")
            )
            return MetricPreTransactionAnalysis(
                context=context,
                prepared=None,
                semantics=None,
                dataset_ref=None,
                insufficient_agent_outcome=None,
                terminal_result=terminal_result,
                failure=MetricMandatoryAnalysisFailure(diagnostic="test failure"),
            )
        _, terminal_result = builder.completed_insufficient(context)
        if self.status is LensRunStatus.PARTIAL:
            payload = deepcopy(terminal_result.payload)
            payload["status"] = {"state": "partial"}
            payload["reason"] = {"code": "reference_unavailable", "component": "test"}
            terminal_result = LensAnalysisResultInput(
                **(
                    terminal_result.model_dump()
                    | {"status": LensRunStatus.PARTIAL, "payload": payload}
                )
            )
        return MetricPreTransactionAnalysis(
            context=context,
            prepared=PreparedInsufficientSeries(data_quality="insufficient", samples=()),
            semantics=None,
            dataset_ref=None,
            insufficient_agent_outcome=None,
            terminal_result=terminal_result,
        )

    async def persist_terminal(
        self, session: object, lens_run: LensRunModel, analysis: object
    ) -> LensAnalysisResultModel:
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
        return _persisted(lens_run, analysis.terminal_result)


class Repository:
    def __init__(self) -> None:
        self.artifacts: list[object] = []

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
    ) -> LensAnalysisResultModel:
        self.artifacts.append(result)
        return _persisted(lens_run, result)


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
        MetricLensExecutionAdapter(
            session_factory=factory,
            pipeline=pipeline,
            repository=Repository(),  # type: ignore[arg-type]
        ).execute(assignment, _policy())
    )

    assert outcome.status == "completed"
    assert outcome.reason is None
    assert outcome.artifact is not None
    assert outcome.artifact.status is LensRunStatus.COMPLETED
    assert phases == ["metric_analysis", "terminal_transaction", "metric_history_and_persist"]
    assert pipeline.context.identity.observation_run_id == assignment.observation_run_id
    assert pipeline.context.identity.lens_run_id == assignment.lens_run_id
    assert pipeline.context.provider_scope.query == "avg(cpu_temperature)"
    assert pipeline.context.analysis_window.from_ == assignment.analysis_window.from_
    assert factory.transactions[0].committed is True


def test_metric_adapter_collects_terminal_outcomes_with_persisted_artifacts() -> None:
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
                repository=Repository(),  # type: ignore[arg-type]
            ).execute(assignment, _policy())
        )
        assert outcome.status == target.value
        assert outcome.reason is not None
        assert outcome.reason.code == expected_reason
        assert outcome.artifact is not None
        assert outcome.artifact.status is target


def test_alert_adapter_persists_completed_artifact_path_with_exact_context() -> None:
    assignment, lens_run, parent = _alert_assignment()
    phases: list[str] = []
    resolver = Resolver(AlertRecordsAvailable(source="jira_track_and_release", records=()))

    repository = Repository()
    outcome = asyncio.run(
        AlertLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), phases),
            repository=repository,  # type: ignore[arg-type]
            provider_resolver=resolver,
            agent=Agent(),  # type: ignore[arg-type]
        ).execute(assignment, _policy())
    )

    assert outcome.status == "completed"
    assert outcome.artifact is not None
    assert outcome.artifact.to_persistence_envelope().payload == repository.artifacts[0].payload
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
    repository = Repository()
    outcome = asyncio.run(
        AlertLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), []),
            repository=repository,  # type: ignore[arg-type]
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
    assert outcome.artifact is not None
    assert outcome.artifact.status is LensRunStatus.PARTIAL
    assert outcome.artifact.to_persistence_envelope().payload == repository.artifacts[0].payload


def test_metric_adapter_normalizes_timeout_with_wrapper_reason_and_assigned_artifact() -> None:
    assignment, lens_run, parent = _metric_assignment()
    repository = Repository()

    class SlowMetricPipeline(MetricPipeline):
        async def analyze(self, context: object) -> object:
            await asyncio.sleep(0.02)
            return await super().analyze(context)

    outcome = asyncio.run(
        MetricLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), []),
            pipeline=SlowMetricPipeline([], LensRunStatus.COMPLETED),
            repository=repository,  # type: ignore[arg-type]
        ).execute(
            assignment, ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=0.001)
        )
    )

    assert outcome.status == "failed"
    assert outcome.reason is not None
    assert (outcome.reason.code, outcome.reason.component) == ("timeout", "metric")
    artifact = repository.artifacts[0]
    assert artifact.status is LensRunStatus.FAILED
    assert artifact.identity.observation_run_id == assignment.observation_run_id
    assert artifact.identity.lens_run_id == assignment.lens_run_id
    assert artifact.payload["status"]["error"] == {
        "code": "mandatory_metric_analysis_failed",
        "message": "Mandatory metric analysis failed.",
    }
    assert artifact.payload["analysis_window"] == {
        "from": "2026-09-01T00:00:00Z",
        "to": "2026-09-01T01:00:00Z",
    }
    assert artifact.provenance["source"] == "prometheus"
    assert outcome.artifact is not None
    assert outcome.artifact.to_persistence_envelope().payload == artifact.payload


def test_metric_adapter_collects_history_replacement_returned_by_terminal_persistence() -> None:
    assignment, lens_run, parent = _metric_assignment()
    phases: list[str] = []

    class HistoryReplacingMetricPipeline(MetricPipeline):
        async def persist_terminal(
            self, session: object, lens_run: LensRunModel, analysis: object
        ) -> LensAnalysisResultModel:
            lens_run.status = LensRunStatus.COMPLETED.value
            payload = deepcopy(analysis.terminal_result.payload)
            payload["history"] = {"source": "persisted-history", "sample_count": 3}
            replacement = LensAnalysisResultInput(
                **(analysis.terminal_result.model_dump() | {"payload": payload})
            )
            assert "history" not in analysis.terminal_result.payload
            self.persisted = _persisted(lens_run, replacement)
            return self.persisted

    pipeline = HistoryReplacingMetricPipeline(phases, LensRunStatus.COMPLETED)
    outcome = asyncio.run(
        MetricLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), phases),
            pipeline=pipeline,
            repository=Repository(),  # type: ignore[arg-type]
        ).execute(assignment, _policy())
    )

    assert outcome.artifact is not None
    assert outcome.artifact.payload["history"] == {
        "source": "persisted-history",
        "sample_count": 3,
    }
    pipeline.persisted.payload["history"]["source"] = "mutated-model"
    assert outcome.artifact.payload["history"]["source"] == "persisted-history"


def test_metric_adapter_rejects_corrupt_returned_terminal_artifact_models() -> None:
    """Returned terminal models must correlate exactly to the assigned durable LensRun."""

    for contradiction in ("lens_run_id", "type", "status", "payload_identity"):
        assignment, lens_run, parent = _metric_assignment()

        class CorruptReturningMetricPipeline(MetricPipeline):
            def __init__(self, artifact_contradiction: str) -> None:
                super().__init__([], LensRunStatus.COMPLETED)
                self.artifact_contradiction = artifact_contradiction

            async def persist_terminal(
                self, session: object, lens_run: LensRunModel, analysis: object
            ) -> LensAnalysisResultModel:
                lens_run.status = LensRunStatus.COMPLETED.value
                persisted = _persisted(lens_run, analysis.terminal_result)
                if self.artifact_contradiction == "lens_run_id":
                    persisted.lens_run_id = uuid4()
                elif self.artifact_contradiction == "type":
                    persisted.result_type = LensType.ALERT.value
                elif self.artifact_contradiction == "status":
                    persisted.status = LensRunStatus.PARTIAL.value
                else:
                    persisted.payload["identity"]["lens_run_id"] = str(uuid4())
                return persisted

        factory = Factory(_session(lens_run, parent), [])
        with pytest.raises(ValueError):
            asyncio.run(
                MetricLensExecutionAdapter(
                    session_factory=factory,
                    pipeline=CorruptReturningMetricPipeline(contradiction),
                    repository=Repository(),  # type: ignore[arg-type]
                ).execute(assignment, _policy())
            )
        assert factory.transactions[0].committed is False


def test_metric_adapter_normalizes_unexpected_and_mismatched_analysis() -> None:
    for behavior, expected in (("raise", "analysis_failed"), ("mismatch", "identity_mismatch")):
        assignment, lens_run, parent = _metric_assignment()
        repository = Repository()

        class FailingMetricPipeline(MetricPipeline):
            def __init__(self, mode: str) -> None:
                super().__init__([], LensRunStatus.COMPLETED)
                self.mode = mode

            async def analyze(self, context: object) -> object:
                if self.mode == "raise":
                    raise RuntimeError("provider credentials: secret")
                return object()

        outcome = asyncio.run(
            MetricLensExecutionAdapter(
                session_factory=Factory(_session(lens_run, parent), []),
                pipeline=FailingMetricPipeline(behavior),
                repository=repository,  # type: ignore[arg-type]
            ).execute(assignment, _policy())
        )
        assert outcome.status == "failed"
        assert outcome.reason is not None
        assert (outcome.reason.code, outcome.reason.component) == (expected, "metric")
        assert repository.artifacts[0].payload["status"]["error"]["code"] == (
            "mandatory_metric_analysis_failed"
        )


def test_metric_adapter_normalizes_invalid_producer_analysis_contract_matrix() -> None:
    """Reject malformed Metric producer results before their terminal path can run."""

    cases = (
        "wrong_analysis_type",
        "wrong_terminal_type",
        "wrong_terminal_lens_type",
        "incomplete_assigned_identity",
        "different_assigned_identity",
        "failure_with_completed_artifact",
        "success_with_failed_artifact",
    )

    for name in cases:
        assignment, lens_run, parent = _metric_assignment()
        repository = Repository()
        context = metric_execution_context(assignment)
        completed = asyncio.run(MetricPipeline([], LensRunStatus.COMPLETED).analyze(context))
        failed = asyncio.run(MetricPipeline([], LensRunStatus.FAILED).analyze(context))
        invalid_identity = completed.terminal_result.identity.model_copy(
            update={"metric_ref": None}
        )
        wrong_identity = completed.terminal_result.identity.model_copy(
            update={"observation_run_id": uuid4()}
        )
        producer_analysis = {
            "wrong_analysis_type": object(),
            "wrong_terminal_type": replace(completed, terminal_result=object()),
            "wrong_terminal_lens_type": replace(
                completed,
                terminal_result=completed.terminal_result.model_copy(
                    update={"result_type": LensType.ALERT}
                ),
            ),
            "incomplete_assigned_identity": replace(
                completed,
                terminal_result=completed.terminal_result.model_copy(
                    update={"identity": invalid_identity}
                ),
            ),
            "different_assigned_identity": replace(
                completed,
                terminal_result=completed.terminal_result.model_copy(
                    update={"identity": wrong_identity}
                ),
            ),
            "failure_with_completed_artifact": replace(
                completed,
                failure=MetricMandatoryAnalysisFailure(diagnostic="producer contradiction"),
            ),
            "success_with_failed_artifact": replace(failed, failure=None),
        }[name]

        class RejectedProducerPipeline(MetricPipeline):
            def __init__(self, analysis: object) -> None:
                super().__init__([], LensRunStatus.COMPLETED)
                self.analysis = analysis

            async def analyze(self, context: object) -> object:
                return self.analysis

            async def persist_terminal(
                self, session: object, lens_run: LensRunModel, analysis: object
            ) -> None:
                raise AssertionError("rejected producer artifact must not be terminalized")

        outcome = asyncio.run(
            MetricLensExecutionAdapter(
                session_factory=Factory(_session(lens_run, parent), []),
                pipeline=RejectedProducerPipeline(producer_analysis),
                repository=repository,  # type: ignore[arg-type]
            ).execute(assignment, _policy())
        )

        assert outcome.status == "failed"
        assert outcome.reason is not None
        assert (outcome.reason.code, outcome.reason.component) == ("identity_mismatch", "metric")
        assert len(repository.artifacts) == 1
        assert repository.artifacts[0] is not getattr(producer_analysis, "terminal_result", None)
        assert repository.artifacts[0].status is LensRunStatus.FAILED
        assert repository.artifacts[0].payload["status"]["error"]["code"] == (
            "mandatory_metric_analysis_failed"
        )


def test_alert_adapter_normalizes_invalid_producer_outcome_without_artifact() -> None:
    assignment, lens_run, parent = _alert_assignment()
    repository = Repository()

    # Provider resolution is part of the adapter-owned pre-terminalization boundary.
    class BrokenResolver:
        def resolve(self, scope: object) -> object:
            raise RuntimeError("sensitive provider response")

    outcome = asyncio.run(
        AlertLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), []),
            repository=repository,  # type: ignore[arg-type]
            provider_resolver=BrokenResolver(),  # type: ignore[arg-type]
            agent=Agent(),  # type: ignore[arg-type]
        ).execute(assignment, _policy())
    )
    assert outcome.status == "failed"
    assert outcome.reason is not None
    assert (outcome.reason.code, outcome.reason.component) == ("analysis_failed", "alert")
    assert repository.artifacts == []


def test_alert_adapter_normalizes_timeout_and_rejected_producer_outcome() -> None:
    assignment, lens_run, parent = _alert_assignment()
    repository = Repository()

    class SlowProvider:
        async def acquire(self, scope: object, window: object) -> object:
            await asyncio.sleep(0.02)
            return AlertRecordsAvailable(source="jira_track_and_release", records=())

    class SlowResolver:
        def resolve(self, scope: object) -> SlowProvider:
            return SlowProvider()

    timeout = asyncio.run(
        AlertLensExecutionAdapter(
            session_factory=Factory(_session(lens_run, parent), []),
            repository=repository,  # type: ignore[arg-type]
            provider_resolver=SlowResolver(),  # type: ignore[arg-type]
            agent=Agent(),  # type: ignore[arg-type]
        ).execute(
            assignment, ExecutionPolicy(max_parallel_lens_runs=1, lens_deadline_seconds=0.001)
        )
    )
    assert timeout.reason is not None
    assert (timeout.reason.code, timeout.reason.component) == ("timeout", "alert")
    assert repository.artifacts == []

    assignment, lens_run, parent = _alert_assignment()
    repository = Repository()

    class RejectedPipeline:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def analyze(self, context: object) -> object:
            return object()

    with patch("app.execution.adapters.AlertAnalysisPipeline", RejectedPipeline):
        outcome = asyncio.run(
            AlertLensExecutionAdapter(
                session_factory=Factory(_session(lens_run, parent), []),
                repository=repository,  # type: ignore[arg-type]
                provider_resolver=Resolver(
                    AlertRecordsAvailable(source="jira_track_and_release", records=())
                ),
                agent=Agent(),  # type: ignore[arg-type]
            ).execute(assignment, _policy())
        )
    assert outcome.reason is not None
    assert (outcome.reason.code, outcome.reason.component) == ("identity_mismatch", "alert")
    assert repository.artifacts == []


def test_metric_terminal_failure_and_cancellation_propagate_without_normalization() -> None:
    assignment, lens_run, parent = _metric_assignment()

    class FailingTerminalMetricPipeline(MetricPipeline):
        async def persist_terminal(
            self, session: object, lens_run: LensRunModel, analysis: object
        ) -> None:
            raise RuntimeError("database write failed")

    factory = Factory(_session(lens_run, parent), [])
    try:
        asyncio.run(
            MetricLensExecutionAdapter(
                session_factory=factory,
                pipeline=FailingTerminalMetricPipeline([], LensRunStatus.COMPLETED),
                repository=Repository(),  # type: ignore[arg-type]
            ).execute(assignment, _policy())
        )
    except RuntimeError as error:
        assert str(error) == "database write failed"
    else:
        raise AssertionError("terminal write failure must propagate")
    assert factory.transactions[0].committed is False

    class CancelledMetricPipeline(MetricPipeline):
        async def analyze(self, context: object) -> object:
            raise asyncio.CancelledError()

    try:
        asyncio.run(
            MetricLensExecutionAdapter(
                session_factory=Factory(_session(lens_run, parent), []),
                pipeline=CancelledMetricPipeline([], LensRunStatus.COMPLETED),
                repository=Repository(),  # type: ignore[arg-type]
            ).execute(assignment, _policy())
        )
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("cancellation must propagate")


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


def _persisted(lens_run: LensRunModel, artifact: object) -> LensAnalysisResultModel:
    return LensAnalysisResultModel(
        lens_run_id=lens_run.id,
        result_type=artifact.result_type.value,
        status=artifact.status.value,
        schema_version=artifact.schema_version,
        payload=artifact.payload,
    )
