"""Framework-neutral Alert pipeline ports."""

from __future__ import annotations

from typing import Protocol

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAgentRequest,
    AlertAnalysisWindow,
    AlertOptionalToolOutcome,
    AlertProviderOutcome,
    AlertProviderScope,
)


class AlertProvider(Protocol):
    """Acquire Alert records for exactly one frozen source, selector, and window."""

    async def acquire(
        self, scope: AlertProviderScope, window: AlertAnalysisWindow
    ) -> AlertProviderOutcome:
        """Return the typed acquisition outcome without selecting transport details."""


class AlertAnalysisAgent(Protocol):
    """Produce one strict bounded completion from the prepared Alert projection."""

    async def complete(
        self, request: AlertAgentRequest, tools: AlertOptionalToolExecutor
    ) -> AlertAgentCompletion:
        """Return findings and non-none importance without expanding the supplied scope."""


class AlertOptionalToolExecutor(Protocol):
    """Execute one run-local optional Alert analysis request."""

    async def execute(self, name: str, arguments: object = None) -> AlertOptionalToolOutcome:
        """Admit and execute an empty-object request against immutable run-local data."""
