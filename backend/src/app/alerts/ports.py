"""Framework-neutral Alert pipeline ports."""

from __future__ import annotations

from typing import Protocol

from app.alerts.contracts import (
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
    """Future bounded reasoning port; VS-01 must not invoke it."""
