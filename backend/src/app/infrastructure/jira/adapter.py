"""Minimal HTTP implementation of the Jira Cloud Alert provider port."""

from __future__ import annotations

import base64
import math

import httpx

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertProviderFailure,
    AlertProviderOutcome,
    AlertProviderScope,
    AlertRecordsAvailable,
)
from app.infrastructure.jira.configuration import JiraAlertProviderSettings

_FIELDS = ["summary", "created", "resolutiondate", "status", "priority"]


class HttpxJiraAlertProvider:
    """Acquire Jira Cloud issue-search pages through the AlertProvider port."""

    def __init__(
        self,
        settings: JiraAlertProviderSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def acquire(
        self, scope: AlertProviderScope, window: AlertAnalysisWindow
    ) -> AlertProviderOutcome:
        """Acquire one terminal empty Jira page for the frozen provider scope and window."""
        if scope.source != "jira_track_and_release":
            return AlertProviderFailure(diagnostic="source_not_supported")
        request_body = {
            "jql": self._jql(scope.query, window),
            "fields": _FIELDS,
            "maxResults": 100,
        }
        try:
            async with httpx.AsyncClient(
                transport=self._transport, follow_redirects=False
            ) as client:
                response = await client.post(
                    f"{self._settings.canonical_origin}/rest/api/2/search/jql",
                    json=request_body,
                    headers={"Authorization": self._basic_authorization()},
                )
        except httpx.RequestError:
            return AlertProviderFailure(diagnostic="transport_error")
        if response.status_code < 200 or response.status_code >= 300:
            return AlertProviderFailure(diagnostic=f"http_status_{response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            return AlertProviderFailure(diagnostic="response_invalid")
        if not isinstance(payload, dict) or payload.get("isLast") is not True:
            return AlertProviderFailure(diagnostic="response_invalid")
        if payload.get("nextPageToken"):
            return AlertProviderFailure(diagnostic="response_invalid")
        issues = payload.get("issues")
        if not isinstance(issues, list):
            return AlertProviderFailure(diagnostic="response_invalid")
        if issues:
            return AlertProviderFailure(diagnostic="response_not_supported")
        return AlertRecordsAvailable(source=scope.source)

    def _basic_authorization(self) -> str:
        credentials = (
            f"{self._settings.email}:{self._settings.api_token.get_secret_value()}".encode()
        )
        return f"Basic {base64.b64encode(credentials).decode('ascii')}"

    @staticmethod
    def _jql(selector: str, window: AlertAnalysisWindow) -> str:
        start = math.floor(window.from_.timestamp() * 1000)
        end = math.ceil(window.to.timestamp() * 1000)
        return f"({selector}) AND created < {end} AND (resolved IS EMPTY OR resolved > {start})"
