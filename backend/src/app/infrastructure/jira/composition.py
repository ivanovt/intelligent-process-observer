"""Source-isolated Jira Alert provider composition."""

from __future__ import annotations

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertProviderOutcome,
    AlertProviderScope,
    AlertProviderUnavailable,
)
from app.alerts.ports import AlertProvider
from app.infrastructure.jira.adapter import HttpxJiraAlertProvider
from app.infrastructure.jira.configuration import parse_jira_alert_provider_settings


class UnavailableAlertProvider:
    """Safe Alert provider returned when Jira configuration cannot be used."""

    def __init__(self, diagnostic: str) -> None:
        self._diagnostic = diagnostic

    async def acquire(
        self, scope: AlertProviderScope, window: AlertAnalysisWindow
    ) -> AlertProviderOutcome:
        """Return the fixed typed unavailable outcome without any transport activity."""
        return AlertProviderUnavailable(diagnostic=self._diagnostic)


class JiraAlertProviderResolver:
    """Resolve Jira providers only for the accepted Jira Track and Release source."""

    def __init__(self, raw_configuration: str | None) -> None:
        self._raw_configuration = raw_configuration

    def resolve(self, scope: AlertProviderScope) -> AlertProvider:
        """Return an AlertProvider for Jira scope or reject a non-Jira source before setup."""
        if scope.source != "jira_track_and_release":
            raise ValueError("Jira resolver does not support this source")
        if self._raw_configuration is None:
            return UnavailableAlertProvider("not_configured")
        try:
            settings = parse_jira_alert_provider_settings(self._raw_configuration)
        except (TypeError, ValueError):
            return UnavailableAlertProvider("configuration_invalid")
        return HttpxJiraAlertProvider(settings)
