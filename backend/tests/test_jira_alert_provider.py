import asyncio
import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.alerts.contracts import (
    AlertAnalysisWindow,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderScope,
)
from app.alerts.pipeline import AlertAnalysisPipeline
from app.infrastructure.jira.adapter import HttpxJiraAlertProvider
from app.infrastructure.jira.configuration import JiraAlertProviderSettings


def _provider(handler) -> HttpxJiraAlertProvider:
    return HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net/jira",
            email="bot@example.invalid",
            api_token="token",
        ),
        transport=httpx.MockTransport(handler),
    )


def _scope() -> AlertProviderScope:
    return AlertProviderScope(source="jira_track_and_release", query="project = IPO")


def _window() -> AlertAnalysisWindow:
    return AlertAnalysisWindow(
        **{"from": datetime(2026, 9, 1, tzinfo=UTC), "to": datetime(2026, 9, 1, 1, tzinfo=UTC)}
    )


def test_empty_terminal_search_uses_exact_site_root_v2_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"isLast": True, "issues": []})

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    assert outcome.source == "jira_track_and_release"
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://foo.atlassian.net/rest/api/2/search/jql"
    assert request.method == "POST"
    assert json.loads(request.content) == {
        "jql": (
            "(project = IPO) AND created < 1788224400000 "
            "AND (resolved IS EMPTY OR resolved > 1788220800000)"
        ),
        "fields": ["summary", "created", "resolutiondate", "status", "priority"],
        "maxResults": 100,
    }


def test_empty_search_uses_preemptive_basic_auth_without_secret_leakage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Basic " + base64.b64encode(
            b"bot@example.invalid:token"
        ).decode("ascii")
        assert "token" not in str(request.url)
        return httpx.Response(200, json={"isLast": True, "issues": []})

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    assert outcome.records == ()


def test_redirect_is_not_followed_or_forwarded_credentials() -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(302, headers={"Location": "https://foreign.example/steal"})

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    assert hosts == ["foo.atlassian.net"]
    assert outcome.state == "failed"


def test_composed_provider_completes_existing_zero_record_pipeline() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"isLast": True, "issues": []})

    class FailOnCallAgent:
        async def complete(self, *args: object) -> object:
            raise AssertionError("zero-record path must not invoke agent")

    context = AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=uuid4(), observation_run_id=uuid4(), lens_id="jira", lens_run_id=uuid4()
        ),
        provider_scope=_scope(),
        analysis_window=_window(),
        lens_name="Jira",
    )
    outcome = asyncio.run(
        AlertAnalysisPipeline(provider=_provider(handler), agent=FailOnCallAgent()).analyze(context)
    )
    assert outcome.status.value == "completed"
    assert outcome.artifact.payload["alert_activity"]["record_count"] == 0
