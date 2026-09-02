"""Minimal HTTP implementation of the Jira Cloud Alert provider port."""

from __future__ import annotations

import base64
import math
from datetime import datetime

import httpx

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertProviderFailure,
    AlertProviderOutcome,
    AlertProviderRecord,
    AlertProviderScope,
    AlertRecordsAvailable,
)
from app.alerts.evidence_refs import encode_dynamic_segment
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
        """Acquire one terminal Jira page for the frozen provider scope and window."""
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
        return AlertRecordsAvailable(
            source=scope.source,
            records=tuple(self._map_issue(issue) for issue in issues),
        )

    def _basic_authorization(self) -> str:
        credentials = (
            f"{self._settings.email.get_secret_value()}:"
            f"{self._settings.api_token.get_secret_value()}"
        ).encode()
        return f"Basic {base64.b64encode(credentials).decode('ascii')}"

    @staticmethod
    def _jql(selector: str, window: AlertAnalysisWindow) -> str:
        """Build the Jira candidate predicate without changing the opaque selector."""
        start = math.floor(window.from_.timestamp() * 1000)
        end = math.ceil(window.to.timestamp() * 1000)
        return f"({selector}) AND created < {end} AND (resolved IS EMPTY OR resolved > {start})"

    def _map_issue(self, issue: object) -> AlertProviderRecord | dict[str, object]:
        """Project one Jira issue into a record or a minimal normalization input."""
        if not isinstance(issue, dict):
            return {}
        fields = issue.get("fields")
        if not isinstance(fields, dict):
            return self._minimal_record(issue, {})
        record = self._minimal_record(issue, fields)
        for field in ("started_at", "ended_at"):
            if isinstance(record.get(field), str):
                try:
                    record[field] = datetime.fromisoformat(record[field].replace("Z", "+00:00"))
                except ValueError:
                    pass
        key = issue.get("key")
        if isinstance(key, str) and key:
            record["source_ref"] = (
                f"{self._settings.canonical_origin}/browse/{encode_dynamic_segment(key)}"
            )
        try:
            return AlertProviderRecord.model_validate(record)
        except ValueError:
            return record

    @staticmethod
    def _minimal_record(
        issue: dict[object, object], fields: dict[object, object]
    ) -> dict[str, object]:
        """Keep only canonical-mappable values from one malformed Jira issue."""
        record: dict[str, object] = {}
        if "key" in issue:
            record["id"] = issue["key"]
        for jira_field, canonical_field in (
            ("summary", "title"),
            ("created", "started_at"),
            ("resolutiondate", "ended_at"),
        ):
            if jira_field in fields:
                record[canonical_field] = fields[jira_field]
        status = fields.get("status")
        if isinstance(status, dict) and "name" in status:
            record["source_status"] = status["name"]
        if "priority" in fields:
            priority = fields["priority"]
            record["provider_importance"] = {
                "type": "priority",
                "value": priority["name"]
                if isinstance(priority, dict) and "name" in priority
                else None,
            }
        return record
