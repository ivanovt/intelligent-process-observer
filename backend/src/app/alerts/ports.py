"""Framework-neutral Alert pipeline ports."""

from __future__ import annotations

from typing import Protocol

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAgentRequest,
    AlertAnalysisWindow,
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

    async def complete(self, request: AlertAgentRequest) -> AlertAgentCompletion:
        """Return findings and non-none importance without expanding the supplied scope."""
