from datetime import UTC, datetime
from uuid import uuid4

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


def _context() -> AlertLensExecutionContext:
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=uuid4(),
            observation_run_id=uuid4(),
            lens_id="release-alerts",
            lens_run_id=uuid4(),
        ),
        provider_scope=AlertProviderScope(source="fake-alerts", query="project = RELEASE"),
        analysis_window=AlertAnalysisWindow(
            **{"from": datetime(2026, 9, 1, tzinfo=UTC), "to": datetime(2026, 9, 1, 1, tzinfo=UTC)}
        ),
        lens_name="Release alerts",
    )


def test_foundational_alert_models_are_strict_and_preserve_runtime_identity() -> None:
    context = _context()
    assert context.identity.lens_run_id
    with pytest.raises(ValidationError):
        AlertProviderScope(source="fake", query="x", transient="forbidden")


def test_zero_record_result_has_exact_sections() -> None:
    result, outcome = AlertResultBuilder(
        clock=lambda: datetime(2026, 9, 1, tzinfo=UTC)
    ).completed_zero(_context(), AlertMandatoryEvidence())
    payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert payload["activity"] == {
        "record_count": 0,
        "occurrence_count": 0,
        "status_counts": {"active": 0, "resolved": 0, "unknown": 0},
    }
    assert payload["findings"] == []
    assert payload["overall_importance"] == "none"
    assert "duration" not in payload and "provider_importance" not in payload
    assert outcome.artifact.status.value == "completed"
