"""Framework-neutral port for one report presentation completion."""

from __future__ import annotations

from typing import Protocol

from app.reporting.contracts import ReportGenerationRequest, ReportPresentationDraft


class ReportGenerationAgent(Protocol):
    """Complete one strict presentation draft from an admitted report request."""

    async def complete_presentation(
        self, request: ReportGenerationRequest
    ) -> ReportPresentationDraft:
        """Return one source-keyed presentation completion without side effects."""
