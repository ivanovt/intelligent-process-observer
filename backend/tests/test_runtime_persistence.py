from __future__ import annotations

import asyncio
import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from app.infrastructure.persistence.database import Base
from app.infrastructure.persistence.models import LensRunModel, ObservationRunModel
from app.infrastructure.persistence.repository import RuntimePersistenceRepository
from app.infrastructure.persistence.runtime_contracts import (
    LensAnalysisResultInput,
    LensResultIdentity,
    LensRunInput,
    LensRunStatus,
    LensType,
    ObservationAnalysisIdentity,
    ObservationAnalysisResultInput,
    ObservationReportInput,
    ObservationRunStatus,
    RelationshipEvaluationInput,
    StructuredReason,
    is_terminal_lens_run,
    is_terminal_observation_run,
    is_usable_lens_result,
    validate_lens_run_transition,
    validate_observation_run_transition,
)


class RecordingSession:
    def __init__(self, *, update_rowcount: int = 1) -> None:
        self.added: list[object] = []
        self.update_rowcount = update_rowcount
        self.statements: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None

    async def scalar(self, _statement) -> None:
        return None

    async def execute(self, statement):
        self.statements.append(statement)
        return type("UpdateResult", (), {"rowcount": self.update_rowcount})()


class ReturningScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def unique(self) -> ReturningScalarResult:
        return self

    def one_or_none(self) -> object:
        return self._value


class ReturningSession:
    def __init__(self, value: object) -> None:
        self._value = value

    async def scalars(self, _statement) -> ReturningScalarResult:
        return ReturningScalarResult(self._value)


def run(coroutine):
    return asyncio.run(coroutine)


def pending_observation_run() -> ObservationRunModel:
    return ObservationRunModel(
        id=uuid4(),
        observation_id=uuid4(),
        status=ObservationRunStatus.PENDING.value,
        provenance={},
        execution_context={},
    )


def pending_lens_run(observation_run: ObservationRunModel, lens_type: LensType) -> LensRunModel:
    repository = RuntimePersistenceRepository()
    return run(
        repository.create_lens_run(
            RecordingSession(),
            observation_run,
            LensRunInput(lens_id="coolant-temperature", lens_type=lens_type),
        )
    )


def result_input(lens_run, status: LensRunStatus) -> LensAnalysisResultInput:
    identity = LensResultIdentity(
        observation_id=lens_run.observation_run.observation_id,
        observation_run_id=lens_run.observation_run_id,
        lens_id=lens_run.lens_id,
        lens_run_id=lens_run.id,
        metric_ref="coolant_temperature" if lens_run.lens_type == "metric" else None,
        unit="celsius" if lens_run.lens_type == "metric" else None,
    )
    payload = {
        "schema_version": "1.0",
        "identity": identity.model_dump(mode="json", exclude_none=True),
        "lens_type": lens_run.lens_type,
        "status": {"state": status.value} if lens_run.lens_type == "metric" else status.value,
        "provenance": {"source": "test", "generated_at": "2026-08-23T01:00:00Z"},
        "optional_sections": [],
    }
    if status is LensRunStatus.PARTIAL:
        payload["reason"] = {"code": "optional_analysis_failed"}
    if lens_run.lens_type == "metric" and status is LensRunStatus.FAILED:
        payload.update(
            {
                "analysis_window": {"from": "2026-08-23T00:00:00Z", "to": "2026-08-23T01:00:00Z"},
                "status": {
                    "state": "failed",
                    "error": {"code": "acquisition_failed", "message": "Source unavailable"},
                },
            }
        )
    return LensAnalysisResultInput(
        result_type=lens_run.lens_type,
        status=status,
        schema_version="1.0",
        identity=identity,
        provenance={"source": "test", "generated_at": "2026-08-23T01:00:00Z"},
        payload=payload,
    )


def test_observation_and_lens_lifecycle_transitions() -> None:
    validate_observation_run_transition(ObservationRunStatus.PENDING, ObservationRunStatus.RUNNING)
    validate_observation_run_transition(
        ObservationRunStatus.RUNNING, ObservationRunStatus.COMPLETED
    )
    validate_observation_run_transition(
        ObservationRunStatus.RUNNING,
        ObservationRunStatus.FAILED,
        StructuredReason(code="analysis_failed"),
    )
    validate_observation_run_transition(
        ObservationRunStatus.RUNNING,
        ObservationRunStatus.CANCELLED,
        StructuredReason(code="execution_cancelled"),
    )
    validate_lens_run_transition(LensRunStatus.PENDING, LensRunStatus.RUNNING)
    for terminal_status in (LensRunStatus.COMPLETED,):
        validate_lens_run_transition(LensRunStatus.RUNNING, terminal_status)
    for terminal_status in (LensRunStatus.PARTIAL, LensRunStatus.FAILED):
        validate_lens_run_transition(
            LensRunStatus.RUNNING,
            terminal_status,
            StructuredReason(code="analysis_failed"),
        )
    for current in (LensRunStatus.PENDING, LensRunStatus.RUNNING):
        validate_lens_run_transition(
            current,
            LensRunStatus.CANCELLED,
            StructuredReason(code="execution_cancelled"),
        )

    assert is_terminal_observation_run(ObservationRunStatus.CANCELLED) is True
    assert is_terminal_lens_run(LensRunStatus.CANCELLED) is True
    assert is_usable_lens_result(LensRunStatus.CANCELLED) is False

    with pytest.raises(ValueError):
        validate_observation_run_transition(
            ObservationRunStatus.PENDING, ObservationRunStatus.FAILED
        )
    with pytest.raises(ValueError):
        validate_lens_run_transition(LensRunStatus.RUNNING, LensRunStatus.RUNNING)
    with pytest.raises(ValueError, match="structured reason"):
        validate_observation_run_transition(
            ObservationRunStatus.RUNNING, ObservationRunStatus.FAILED
        )
    with pytest.raises(ValueError, match="structured reason"):
        validate_lens_run_transition(LensRunStatus.RUNNING, LensRunStatus.PARTIAL)
    with pytest.raises(ValueError, match="execution_cancelled"):
        validate_lens_run_transition(
            LensRunStatus.RUNNING,
            LensRunStatus.CANCELLED,
            StructuredReason(code="analysis_failed"),
        )
    for transition in (validate_observation_run_transition, validate_lens_run_transition):
        with pytest.raises(ValueError, match="cannot include a component"):
            transition(
                ObservationRunStatus.RUNNING
                if transition is validate_observation_run_transition
                else LensRunStatus.RUNNING,
                ObservationRunStatus.CANCELLED
                if transition is validate_observation_run_transition
                else LensRunStatus.CANCELLED,
                StructuredReason(code="execution_cancelled", component="orchestrator"),
            )
    with pytest.raises(ValueError):
        validate_lens_run_transition(
            LensRunStatus.CANCELLED,
            LensRunStatus.COMPLETED,
        )
    with pytest.raises(ValidationError):
        StructuredReason(code="failure", message="diagnostic text")


def test_result_contract_enforces_type_specific_failure_eligibility() -> None:
    identity = LensResultIdentity(
        observation_id=uuid4(),
        observation_run_id=uuid4(),
        lens_id="alerts",
        lens_run_id=uuid4(),
    )

    for result_type in (LensType.ALERT, LensType.LOG):
        with pytest.raises(ValidationError):
            LensAnalysisResultInput(
                result_type=result_type,
                status=LensRunStatus.FAILED,
                schema_version="1.0",
                identity=identity,
                provenance={},
                payload={},
            )

    with pytest.raises(ValidationError):
        LensAnalysisResultInput(
            result_type=LensType.METRIC,
            status=LensRunStatus.FAILED,
            schema_version="1.0",
            identity=identity,
            provenance={},
            payload={},
        )


def test_failed_metric_result_is_persisted_but_not_usable() -> None:
    repository = RuntimePersistenceRepository()
    session = RecordingSession()
    observation_run = pending_observation_run()
    lens_run = pending_lens_run(observation_run, LensType.METRIC)
    lens_run.status = LensRunStatus.FAILED.value
    failed_result = result_input(lens_run, LensRunStatus.FAILED)

    result = run(repository.persist_lens_analysis_result(session, lens_run, failed_result))

    assert result.status == LensRunStatus.FAILED
    assert result.is_usable is False
    assert is_usable_lens_result(LensRunStatus.FAILED) is False
    assert result.payload["status"]["error"] == {
        "code": "acquisition_failed",
        "message": "Source unavailable",
    }


def test_completed_and_partial_metric_results_are_usable() -> None:
    repository = RuntimePersistenceRepository()
    for status in (LensRunStatus.COMPLETED, LensRunStatus.PARTIAL):
        observation_run = pending_observation_run()
        lens_run = pending_lens_run(observation_run, LensType.METRIC)
        lens_run.status = status.value
        if status is LensRunStatus.PARTIAL:
            lens_run.reason = {"code": "optional_analysis_failed", "component": None}

        result = run(
            repository.persist_lens_analysis_result(
                RecordingSession(), lens_run, result_input(lens_run, status)
            )
        )

        assert result.is_usable is True
        assert is_usable_lens_result(status) is True


def test_repository_rejects_mismatched_identity_type_status_and_parent_aggregate() -> None:
    repository = RuntimePersistenceRepository()
    observation_run = pending_observation_run()
    log_lens_run = pending_lens_run(observation_run, LensType.LOG)
    log_lens_run.status = LensRunStatus.PARTIAL.value
    log_lens_run.reason = {"code": "optional_analysis_failed", "component": None}
    mismatched = result_input(log_lens_run, LensRunStatus.PARTIAL).model_copy(
        update={"result_type": LensType.METRIC}
    )

    with pytest.raises(ValueError, match="type"):
        run(repository.persist_lens_analysis_result(RecordingSession(), log_lens_run, mismatched))

    wrong_status = result_input(log_lens_run, LensRunStatus.PARTIAL).model_copy(
        update={"status": LensRunStatus.COMPLETED}
    )
    with pytest.raises(ValueError, match="status"):
        run(repository.persist_lens_analysis_result(RecordingSession(), log_lens_run, wrong_status))

    parent = log_lens_run.observation_run
    cases = (
        (
            "observation identity",
            LensResultIdentity(
                observation_id=uuid4(),
                observation_run_id=parent.id,
                lens_id=log_lens_run.lens_id,
                lens_run_id=log_lens_run.id,
            ),
        ),
        (
            "ObservationRun identity",
            LensResultIdentity(
                observation_id=parent.observation_id,
                observation_run_id=uuid4(),
                lens_id=log_lens_run.lens_id,
                lens_run_id=log_lens_run.id,
            ),
        ),
        (
            "Lens identity",
            LensResultIdentity(
                observation_id=parent.observation_id,
                observation_run_id=parent.id,
                lens_id="different-lens",
                lens_run_id=log_lens_run.id,
            ),
        ),
        (
            "LensRun identity",
            LensResultIdentity(
                observation_id=parent.observation_id,
                observation_run_id=parent.id,
                lens_id=log_lens_run.lens_id,
                lens_run_id=uuid4(),
            ),
        ),
    )
    for message, identity in cases:
        mismatched = result_input(log_lens_run, LensRunStatus.PARTIAL).model_copy(
            update={"identity": identity}
        )
        with pytest.raises(ValueError, match=message):
            run(
                repository.persist_lens_analysis_result(
                    RecordingSession(), log_lens_run, mismatched
                )
            )


def test_metric_contract_rejects_duplicate_identity_and_provenance_mismatches() -> None:
    observation_run = pending_observation_run()
    lens_run = pending_lens_run(observation_run, LensType.METRIC)
    valid = result_input(lens_run, LensRunStatus.COMPLETED)
    for field, value in (
        ("observation_id", str(uuid4())),
        ("observation_run_id", str(uuid4())),
        ("lens_id", "other-lens"),
        ("lens_run_id", str(uuid4())),
        ("metric_ref", "other_metric"),
        ("unit", "kelvin"),
    ):
        payload = valid.payload | {"identity": valid.payload["identity"] | {field: value}}
        with pytest.raises(ValidationError, match="identity"):
            LensAnalysisResultInput(**(valid.model_dump() | {"payload": payload}))
    with pytest.raises(ValidationError, match="provenance"):
        LensAnalysisResultInput(
            **(
                valid.model_dump()
                | {"payload": valid.payload | {"provenance": {"source": "other"}}}
            )
        )

    failed = result_input(lens_run, LensRunStatus.FAILED)
    for missing in ("analysis_window", "status"):
        payload = failed.payload.copy()
        payload.pop(missing)
        with pytest.raises(ValidationError):
            LensAnalysisResultInput(**(failed.model_dump() | {"payload": payload}))
    for error_field in ("code", "message"):
        payload = failed.payload | {
            "status": {
                "state": "failed",
                "error": failed.payload["status"]["error"] | {error_field: ""},
            }
        }
        with pytest.raises(ValidationError, match="status.error"):
            LensAnalysisResultInput(**(failed.model_dump() | {"payload": payload}))
    for field in ("from", "to"):
        payload = failed.payload | {
            "analysis_window": failed.payload["analysis_window"] | {field: ""}
        }
        with pytest.raises(ValidationError, match="analysis_window"):
            LensAnalysisResultInput(**(failed.model_dump() | {"payload": payload}))
    for field in ("source", "generated_at"):
        provenance = failed.provenance | {field: ""}
        payload = failed.payload | {"provenance": provenance}
        with pytest.raises(ValidationError, match="provenance"):
            LensAnalysisResultInput(
                **(failed.model_dump() | {"provenance": provenance, "payload": payload})
            )


def test_partial_lens_result_reason_is_required_and_matches_lens_run() -> None:
    repository = RuntimePersistenceRepository()
    observation_run = pending_observation_run()
    lens_run = pending_lens_run(observation_run, LensType.METRIC)
    lens_run.status = LensRunStatus.PARTIAL.value
    valid = result_input(lens_run, LensRunStatus.PARTIAL)

    payload_without_reason = valid.payload.copy()
    payload_without_reason.pop("reason")
    with pytest.raises(ValidationError, match="structured reason"):
        LensAnalysisResultInput(**(valid.model_dump() | {"payload": payload_without_reason}))

    with pytest.raises(ValueError, match="Partial LensRun requires"):
        run(repository.persist_lens_analysis_result(RecordingSession(), lens_run, valid))

    lens_run.reason = {"code": "different_reason", "component": None}
    with pytest.raises(ValueError, match="does not match"):
        run(repository.persist_lens_analysis_result(RecordingSession(), lens_run, valid))

    lens_run.reason = {"code": "optional_analysis_failed", "component": None}
    result = run(repository.persist_lens_analysis_result(RecordingSession(), lens_run, valid))
    assert result.payload["reason"] == {"code": "optional_analysis_failed"}


def test_failed_alert_and_log_runs_reject_result_attachment() -> None:
    repository = RuntimePersistenceRepository()
    observation_run = pending_observation_run()
    for lens_type in (LensType.ALERT, LensType.LOG):
        lens_run = pending_lens_run(observation_run, lens_type)
        lens_run.status = LensRunStatus.FAILED.value
        with pytest.raises(ValueError, match="status"):
            run(
                repository.persist_lens_analysis_result(
                    RecordingSession(), lens_run, result_input(lens_run, LensRunStatus.COMPLETED)
                )
            )


def test_cancelled_lens_run_rejects_result_attachment() -> None:
    repository = RuntimePersistenceRepository()
    observation_run = pending_observation_run()
    lens_run = pending_lens_run(observation_run, LensType.METRIC)
    lens_run.status = LensRunStatus.CANCELLED.value
    lens_run.reason = {"code": "execution_cancelled", "component": None}

    with pytest.raises(ValueError, match="Cancelled LensRun"):
        run(
            repository.persist_lens_analysis_result(
                RecordingSession(), lens_run, result_input(lens_run, LensRunStatus.COMPLETED)
            )
        )


def test_terminal_lifecycle_operations_persist_structured_reasons() -> None:
    repository = RuntimePersistenceRepository()
    session = RecordingSession()
    observation_run = pending_observation_run()
    run(repository.advance_observation_run(session, observation_run, ObservationRunStatus.RUNNING))
    run(
        repository.advance_observation_run(
            session,
            observation_run,
            ObservationRunStatus.FAILED,
            reason=StructuredReason(code="analysis_failed", component="join"),
        )
    )
    assert observation_run.reason == {"code": "analysis_failed", "component": "join"}

    lens_run = pending_lens_run(pending_observation_run(), LensType.METRIC)
    run(repository.advance_lens_run(session, lens_run, LensRunStatus.RUNNING))
    run(
        repository.advance_lens_run(
            session,
            lens_run,
            LensRunStatus.PARTIAL,
            reason=StructuredReason(code="optional_analysis_failed"),
        )
    )
    assert lens_run.reason == {"code": "optional_analysis_failed", "component": None}

    cancelled_observation_run = pending_observation_run()
    run(
        repository.advance_observation_run(
            session, cancelled_observation_run, ObservationRunStatus.RUNNING
        )
    )
    run(
        repository.advance_observation_run(
            session,
            cancelled_observation_run,
            ObservationRunStatus.CANCELLED,
            reason=StructuredReason(code="execution_cancelled"),
        )
    )
    assert cancelled_observation_run.reason == {"code": "execution_cancelled", "component": None}

    cancelled_lens_run = pending_lens_run(pending_observation_run(), LensType.METRIC)
    run(
        repository.advance_lens_run(
            session,
            cancelled_lens_run,
            LensRunStatus.CANCELLED,
            reason=StructuredReason(code="execution_cancelled"),
        )
    )
    assert cancelled_lens_run.reason == {"code": "execution_cancelled", "component": None}


@pytest.mark.parametrize(
    ("run_factory", "advance", "target"),
    (
        (pending_observation_run, "advance_observation_run", ObservationRunStatus.RUNNING),
        (
            lambda: pending_lens_run(pending_observation_run(), LensType.METRIC),
            "advance_lens_run",
            LensRunStatus.RUNNING,
        ),
    ),
)
def test_lifecycle_transition_rejects_a_stale_persisted_state(
    run_factory, advance: str, target: ObservationRunStatus | LensRunStatus
) -> None:
    repository = RuntimePersistenceRepository()
    session = RecordingSession(update_rowcount=0)
    runtime_run = run_factory()

    with pytest.raises(ValueError, match="persisted lifecycle state changed"):
        run(getattr(repository, advance)(session, runtime_run, target))

    assert runtime_run.status == "pending"
    assert runtime_run.reason is None
    assert len(session.statements) == 1


def test_missing_artifact_is_distinct_from_valid_empty_optional_sections() -> None:
    repository = RuntimePersistenceRepository()
    observation_run = pending_observation_run()
    completed_log_run = pending_lens_run(observation_run, LensType.LOG)
    completed_log_run.status = LensRunStatus.COMPLETED.value
    persisted_result = run(
        repository.persist_lens_analysis_result(
            RecordingSession(),
            completed_log_run,
            result_input(completed_log_run, LensRunStatus.COMPLETED),
        )
    )
    failed_alert_run = pending_lens_run(observation_run, LensType.ALERT)
    failed_alert_run.status = LensRunStatus.FAILED.value

    assert persisted_result.payload["optional_sections"] == []
    assert failed_alert_run.analysis_result is None


def test_observation_level_artifacts_and_early_failure_absence() -> None:
    repository = RuntimePersistenceRepository()
    session = RecordingSession()
    observation_run = pending_observation_run()
    observation_run.status = ObservationRunStatus.COMPLETED.value
    analysis = run(
        repository.persist_observation_analysis_result(
            session,
            observation_run,
            ObservationAnalysisResultInput(
                schema_version="1.0",
                identity=ObservationAnalysisIdentity(
                    observation_id=observation_run.observation_id,
                    observation_run_id=observation_run.id,
                ),
                payload={
                    "schema_version": "1.0",
                    "identity": {
                        "observation_id": str(observation_run.observation_id),
                        "observation_run_id": str(observation_run.id),
                    },
                    "overall_state": "no_significant_findings",
                    "findings": [],
                    "hypotheses": [],
                    "limitations": [],
                },
            ),
        )
    )
    report = run(
        repository.persist_observation_report(
            session,
            observation_run,
            analysis,
            ObservationReportInput(
                generated_at=datetime(2026, 8, 23, tzinfo=UTC),
                format="markdown",
                content="# Report",
            ),
        )
    )
    evaluation = run(
        repository.persist_relationship_evaluation(
            session,
            observation_run,
            RelationshipEvaluationInput(
                relationship_id="temperature-pressure-link",
                payload={
                    "relationship": {
                        "id": "temperature-pressure-link",
                        "name": "Temperature and pressure link",
                        "description": "Pressure follows temperature changes",
                        "participants": ["coolant-temperature", "line-pressure"],
                    },
                    "applicability": "applicable",
                    "expected": {"condition": "pressure follows temperature"},
                    "observed": {
                        "participant_states": {
                            "coolant-temperature": "elevated",
                            "line-pressure": "elevated",
                        },
                        "evidence_refs": ["metric:coolant-temperature"],
                    },
                    "evaluation": {"state": "consistent"},
                },
            ),
        )
    )
    early_failed_run = pending_observation_run()
    early_failed_run.status = ObservationRunStatus.FAILED.value
    early_failed_lens_run = pending_lens_run(early_failed_run, LensType.METRIC)
    early_failed_lens_run.status = LensRunStatus.FAILED.value
    run(
        repository.persist_lens_analysis_result(
            RecordingSession(),
            early_failed_lens_run,
            result_input(early_failed_lens_run, LensRunStatus.FAILED),
        )
    )
    retrieved_early_failed_run = run(
        repository.get_observation_run(ReturningSession(early_failed_run), early_failed_run.id)
    )

    assert report.observation_analysis_result is analysis
    assert evaluation.relationship_id == "temperature-pressure-link"
    assert retrieved_early_failed_run is early_failed_run
    assert retrieved_early_failed_run.observation_analysis_result is None
    assert retrieved_early_failed_run.lens_runs[0].analysis_result is not None
    assert retrieved_early_failed_run.lens_runs[0].analysis_result.is_usable is False


def test_observation_analysis_contract_rejects_payload_identity_mismatches() -> None:
    identity = ObservationAnalysisIdentity(observation_id=uuid4(), observation_run_id=uuid4())
    payload = {
        "schema_version": "1.0",
        "identity": {
            "observation_id": str(identity.observation_id),
            "observation_run_id": str(identity.observation_run_id),
        },
        "overall_state": "uncertain",
        "findings": [],
        "hypotheses": [],
        "limitations": [],
    }
    for field in ("observation_id", "observation_run_id"):
        invalid_payload = payload | {"identity": payload["identity"] | {field: str(uuid4())}}
        with pytest.raises(ValidationError, match="identity"):
            ObservationAnalysisResultInput(
                schema_version="1.0", identity=identity, payload=invalid_payload
            )

    persisted_boundary_input = ObservationAnalysisResultInput(
        schema_version="1.0",
        identity=identity,
        payload={
            "schema_version": "1.0",
            "identity": payload["identity"],
            "producer_extension": {"not": "persistence validation"},
        },
    )
    assert persisted_boundary_input.payload["producer_extension"] == {
        "not": "persistence validation"
    }


def test_runtime_schema_and_migration_have_required_cardinality() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20260823_01_add_runtime_persistence.py"
    )
    spec = importlib.util.spec_from_file_location("runtime_persistence_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.down_revision == "20260822_01"
    assert {
        "observation_runs",
        "lens_runs",
        "lens_analysis_results",
        "relationship_evaluations",
        "observation_analysis_results",
        "observation_reports",
    }.issubset(Base.metadata.tables)
    for table_name, columns in {
        "lens_analysis_results": {"lens_run_id"},
        "observation_analysis_results": {"observation_run_id"},
        "observation_reports": {"observation_analysis_result_id"},
    }.items():
        table = Base.metadata.tables[table_name]
        assert any(
            isinstance(constraint, UniqueConstraint)
            and {column.name for column in constraint.columns} == columns
            for constraint in table.constraints
        )
    assert "observation_id" not in Base.metadata.tables["lens_runs"].c
    assert "observation_run_id" not in Base.metadata.tables["lens_analysis_results"].c
    assert "provenance" not in Base.metadata.tables["lens_analysis_results"].c
    assert "observation_run_id" not in Base.metadata.tables["observation_reports"].c


def test_lens_run_schema_has_type_aware_runtime_identity() -> None:
    lens_run_constraints = Base.metadata.tables["lens_runs"].constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_lens_runs_observation_run_id_lens_type_lens_id"
        and tuple(column.name for column in constraint.columns)
        == ("observation_run_id", "lens_type", "lens_id")
        for constraint in lens_run_constraints
    )
