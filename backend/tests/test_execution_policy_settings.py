from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.execution import ObservationExecutionOrchestrator


def test_public_execution_policy_settings_have_approved_positive_defaults() -> None:
    settings = Settings()

    assert settings.max_parallel_lens_runs == 4
    assert settings.lens_deadline_seconds == 300


def test_public_execution_policy_settings_accept_server_side_overrides() -> None:
    settings = Settings(max_parallel_lens_runs=2, lens_deadline_seconds=45.5)

    assert settings.max_parallel_lens_runs == 2
    assert settings.lens_deadline_seconds == 45.5


def test_agent_trace_is_disabled_by_default_without_creating_a_trace_directory(
    tmp_path, monkeypatch
) -> None:
    """Settings construction has no sensitive trace filesystem side effect."""
    import app.core.settings as settings_module

    monkeypatch.setattr(settings_module, "_REPOSITORY_ROOT", tmp_path)
    settings = Settings()

    assert settings.agent_trace_enabled is False
    assert settings.agent_trace_root == tmp_path / "tmp" / "agent-traces"
    assert not settings.agent_trace_root.exists()


def test_agent_trace_enabled_is_valid_only_for_development_before_composition() -> None:
    """Production-like modes cannot select sensitive tracing composition."""
    assert Settings(app_env="development", agent_trace_enabled=True).agent_trace_enabled is True

    for app_env in ("production", "test", "staging", "Development"):
        with pytest.raises(ValidationError, match="agent_trace_enabled"):
            Settings(app_env=app_env, agent_trace_enabled=True)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_parallel_lens_runs", 0),
        ("max_parallel_lens_runs", -1),
        ("lens_deadline_seconds", 0),
        ("lens_deadline_seconds", -1),
    ],
)
def test_public_execution_policy_settings_reject_non_positive_values(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_synchronous_orchestrator_contract_keeps_policy_internal() -> None:
    parameters = inspect.signature(ObservationExecutionOrchestrator.execute).parameters

    assert tuple(parameters) == ("self", "request", "policy")
    assert "max_parallel_lens_runs" not in parameters
    assert "lens_deadline_seconds" not in parameters
