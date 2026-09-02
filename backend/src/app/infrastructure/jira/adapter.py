"""Minimal HTTP implementation of the Jira Cloud Alert provider port."""

from __future__ import annotations

import asyncio
import base64
import math
import time
from collections.abc import Awaitable, Callable
from datetime import datetime

import httpx

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertProviderFailure,
    AlertProviderOutcome,
    AlertProviderRecord,
    AlertProviderScope,
    AlertProviderTimeout,
    AlertRecordsAvailable,
)
from app.alerts.evidence_refs import encode_dynamic_segment
from app.infrastructure.jira.configuration import JiraAlertProviderSettings

_FIELDS = ["summary", "created", "resolutiondate", "status", "priority"]
_ATTEMPT_DEADLINE_SECONDS = 15.0
_ACQUISITION_DEADLINE_SECONDS = 60.0

_DeadlineRunner = Callable[[Awaitable[httpx.Response], float], Awaitable[httpx.Response]]


class HttpxJiraAlertProvider:
    """Acquire Jira Cloud issue-search pages through the AlertProvider port."""

    def __init__(
        self,
        settings: JiraAlertProviderSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        run_with_deadline: _DeadlineRunner | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._monotonic = monotonic
        self._run_with_deadline = run_with_deadline or self._default_deadline_runner

    async def acquire(
        self, scope: AlertProviderScope, window: AlertAnalysisWindow
    ) -> AlertProviderOutcome:
        """Acquire all bounded Jira pages for the frozen provider scope and window."""
        if scope.source != "jira_track_and_release":
            return AlertProviderFailure(diagnostic="source_not_supported")
        request_body = {
            "jql": self._jql(scope.query, window),
            "fields": _FIELDS,
            "maxResults": 100,
        }
        records: list[AlertProviderRecord | dict[str, object]] = []
        seen_tokens: set[str] = set()
        next_page_token: str | None = None
        acquisition_deadline = self._monotonic() + _ACQUISITION_DEADLINE_SECONDS
        try:
            async with httpx.AsyncClient(
                transport=self._transport, follow_redirects=False
            ) as client:
                while True:
                    remaining = acquisition_deadline - self._monotonic()
                    if remaining < _ATTEMPT_DEADLINE_SECONDS:
                        return AlertProviderTimeout(diagnostic="deadline_exceeded")
                    if next_page_token is None:
                        page_request = request_body
                    else:
                        page_request = {**request_body, "nextPageToken": next_page_token}
                    response = await self._run_with_deadline(
                        self._complete_attempt(client, page_request),
                        min(_ATTEMPT_DEADLINE_SECONDS, remaining),
                    )
                    if response.status_code < 200 or response.status_code >= 300:
                        return AlertProviderFailure(
                            diagnostic=f"http_status_{response.status_code}"
                        )
                    try:
                        payload = response.json()
                    except ValueError:
                        return AlertProviderFailure(diagnostic="response_invalid")
                    page = self._validated_page(payload, seen_tokens)
                    if page is None:
                        return AlertProviderFailure(diagnostic="response_invalid")
                    issues, is_last, next_page_token = page
                    if len(records) + len(issues) > 1000:
                        return AlertProviderFailure(diagnostic="response_invalid")
                    records.extend(self._map_issue(issue) for issue in issues)
                    if len(records) == 1000 and not is_last:
                        return AlertProviderFailure(diagnostic="response_invalid")
                    if is_last:
                        return AlertRecordsAvailable(source=scope.source, records=tuple(records))
        except TimeoutError:
            return AlertProviderTimeout(diagnostic="deadline_exceeded")
        except httpx.RequestError:
            return AlertProviderFailure(diagnostic="transport_error")

    @staticmethod
    async def _default_deadline_runner(
        operation: Awaitable[httpx.Response], deadline_seconds: float
    ) -> httpx.Response:
        """Run one complete HTTP operation under its hard wall-clock deadline."""
        return await asyncio.wait_for(operation, timeout=deadline_seconds)

    async def _complete_attempt(
        self, client: httpx.AsyncClient, page_request: dict[str, object]
    ) -> httpx.Response:
        """Send one page request and read its complete body before returning it."""
        async with client.stream(
            "POST",
            f"{self._settings.canonical_origin}/rest/api/2/search/jql",
            json=page_request,
            headers={"Authorization": self._basic_authorization()},
        ) as response:
            content = await response.aread()
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=content,
                request=response.request,
            )

    @staticmethod
    def _validated_page(
        payload: object, seen_tokens: set[str]
    ) -> tuple[list[object], bool, str | None] | None:
        """Validate one Jira cursor envelope before retaining any of its issues."""
        if not isinstance(payload, dict):
            return None
        is_last = payload.get("isLast")
        issues = payload.get("issues")
        if not isinstance(is_last, bool) or not isinstance(issues, list):
            return None
        token = payload.get("nextPageToken")
        if is_last:
            if token is not None and (not isinstance(token, str) or token != ""):
                return None
            return issues, True, None
        if not isinstance(token, str) or not token or token in seen_tokens:
            return None
        seen_tokens.add(token)
        return issues, False, token

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
