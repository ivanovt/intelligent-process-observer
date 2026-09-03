import asyncio
import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.alerts.contracts import (
    AlertAgentCompletion,
    AlertAnalysisWindow,
    AlertFinding,
    AlertIdentity,
    AlertLensExecutionContext,
    AlertProviderScope,
)
from app.alerts.normalization import normalize_current
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


def _issue(
    key: str = "IPO-1",
    *,
    created: str = "2026-08-31T23:00:00.000+00:00",
    resolved: str | None = "2026-09-01T00:30:00.000+00:00",
    status: str = "In Progress",
    priority: str | None = "Highest",
) -> dict[str, object]:
    fields: dict[str, object] = {
        "summary": "Lifecycle issue",
        "created": created,
        "resolutiondate": resolved,
        "status": {"name": status},
    }
    if priority is not None:
        fields["priority"] = {"name": priority}
    return {"key": key, "fields": fields}


def test_jql_bounds_form_a_candidate_superset_and_normalization_owns_exact_overlap() -> None:
    requests: list[httpx.Request] = []
    window = AlertAnalysisWindow(
        **{
            "from": datetime(2026, 9, 1, 0, 0, 0, 500, tzinfo=UTC),
            "to": datetime(2026, 9, 1, 1, 0, 0, 500, tzinfo=UTC),
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "isLast": True,
                "issues": [
                    _issue("candidate-only", resolved="2026-09-01T00:00:00.000+00:00"),
                    _issue("overlap", resolved="2026-09-01T00:00:00.001+00:00"),
                ],
            },
        )

    outcome = asyncio.run(_provider(handler).acquire(_scope(), window))
    assert json.loads(requests[0].content)["jql"] == (
        "(project = IPO) AND created < 1788224400001 "
        "AND (resolved IS EMPTY OR resolved > 1788220800000)"
    )
    assert "status" not in json.loads(requests[0].content)["jql"].lower()
    assert [record.id for record in normalize_current(outcome, window, window.to)] == ["overlap"]


def test_issue_mapping_preserves_approved_native_lifecycle_fields() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"isLast": True, "issues": [_issue()]})

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    record = outcome.records[0]
    assert record.id == "IPO-1"
    assert record.title == "Lifecycle issue"
    assert record.started_at == datetime(2026, 8, 31, 23, tzinfo=UTC)
    assert record.ended_at == datetime(2026, 9, 1, 0, 30, tzinfo=UTC)
    assert record.source_status == "In Progress"
    assert record.provider_importance.model_dump() == {"type": "priority", "value": "Highest"}
    assert record.description is None and record.occurrence_count is None


def test_malformed_issues_remain_minimal_record_level_normalization_inputs() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "isLast": True,
                "issues": [
                    _issue(),
                    "not-an-issue",
                    {"key": "bad", "fields": "not-an-object", "large": "x" * 1000},
                    {"key": None, "fields": {"summary": "bad", "created": "not-a-date"}},
                ],
            },
        )

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    assert outcome.records[1:] == (
        {},
        {"id": "bad"},
        {"id": None, "title": "bad", "started_at": "not-a-date"},
    )
    assert [record.id for record in normalize_current(outcome, _window(), _window().to)] == [
        "IPO-1"
    ]


def test_present_malformed_priority_remains_an_invalid_normalization_input() -> None:
    empty_name = _issue("empty-priority", priority="")
    non_string_name = _issue("numeric-priority")
    non_string_name["fields"]["priority"] = {"name": 1}  # type: ignore[index]
    missing_name = _issue("missing-priority")
    missing_name["fields"]["priority"] = {}  # type: ignore[index]
    non_object = _issue("non-object-priority")
    non_object["fields"]["priority"] = "Highest"  # type: ignore[index]

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "isLast": True,
                "issues": [_issue(), empty_name, non_string_name, missing_name, non_object],
            },
        )

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    malformed_records = outcome.records[1:]
    assert [record["provider_importance"] for record in malformed_records] == [
        {"type": "priority", "value": ""},
        {"type": "priority", "value": 1},
        {"type": "priority", "value": None},
        {"type": "priority", "value": None},
    ]
    assert [record.id for record in normalize_current(outcome, _window(), _window().to)] == [
        "IPO-1"
    ]


def test_absent_optional_priority_is_omitted() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"isLast": True, "issues": [_issue(priority=None)]})

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    assert outcome.records[0].provider_importance is None


def test_source_ref_is_canonical_and_independent_of_input_path() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"isLast": True, "issues": [_issue("IPO / Ю")]})

    root = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(handler),
    )
    for provider in (root, _provider(handler)):
        outcome = asyncio.run(provider.acquire(_scope(), _window()))
        assert (
            outcome.records[0].source_ref == "https://foo.atlassian.net/browse/IPO%20%2F%20%D0%AE"
        )


class _CapturingAgent:
    def __init__(self) -> None:
        self.requests: list[object] = []

    async def complete(self, request: object) -> AlertAgentCompletion:
        self.requests.append(request)
        return AlertAgentCompletion(
            findings=(
                AlertFinding(
                    id="finding",
                    statement="Observed canonical record",
                    evidence_refs=("alert://aggregate/alert_activity/record_count",),
                ),
            ),
            overall_importance="low",
        )


def _context(*, references: tuple[str, ...] = ()) -> AlertLensExecutionContext:
    return AlertLensExecutionContext(
        identity=AlertIdentity(
            observation_id=uuid4(), observation_run_id=uuid4(), lens_id="jira", lens_run_id=uuid4()
        ),
        provider_scope=_scope(),
        analysis_window=_window(),
        lens_name="Jira",
        reference_periods=references,
    )


def test_real_provider_preserves_latest_reference_lifecycle_behind_existing_port() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"isLast": True, "issues": [_issue("current")]})
        return httpx.Response(
            200,
            json={
                "isLast": True,
                "issues": [_issue("reference", resolved="2026-09-01T00:30:00.000+00:00")],
            },
        )

    agent = _CapturingAgent()
    outcome = asyncio.run(
        AlertAnalysisPipeline(provider=_provider(handler), agent=agent).analyze(
            _context(references=("1h",))
        )
    )
    assert outcome.status.value == "completed"
    assert len(requests) == 2
    bodies = [json.loads(request.content) for request in requests]
    assert all(body["fields"] == bodies[0]["fields"] for body in bodies)
    assert bodies[0]["jql"] != bodies[1]["jql"]
    assert outcome.artifact.payload["comparisons"] == [
        {
            "offset": "1h",
            "occurrence_comparison": {
                "current": 1,
                "reference": 1,
                "delta": 0,
                "direction": "unchanged",
            },
        }
    ]
    assert [record.id for record in agent.requests[0].current_records] == ["current"]


def test_jira_query_error_uses_existing_current_and_reference_semantics() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json={"errorMessages": ["ORDER BY is invalid here"]})

    failed = asyncio.run(
        AlertAnalysisPipeline(provider=_provider(handler), agent=_CapturingAgent()).analyze(
            _context().model_copy(
                update={
                    "provider_scope": AlertProviderScope(
                        source="jira_track_and_release", query="project = IPO ORDER BY created DESC"
                    )
                }
            )
        )
    )
    assert failed.status.value == "failed" and failed.reason.code == "current_query_failed"
    assert json.loads(requests[0].content)["jql"].startswith(
        "(project = IPO ORDER BY created DESC)"
    )

    calls = 0

    def mixed_handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200 if calls == 1 else 400,
            json={"isLast": True, "issues": [_issue()]}
            if calls == 1
            else {"errorMessages": ["bad"]},
        )

    partial = asyncio.run(
        AlertAnalysisPipeline(provider=_provider(mixed_handler), agent=_CapturingAgent()).analyze(
            _context(references=("1h",))
        )
    )
    assert partial.status.value == "partial" and partial.reason.code == "reference_unavailable"


def test_successful_stale_or_empty_view_is_not_reconciled_or_failed() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"isLast": True, "issues": []})

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    assert outcome.records == ()
    assert "reconcileIssues" not in json.loads(requests[0].content)


def test_jira_transport_stays_outside_agent_and_alert_result() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"isLast": True, "issues": [_issue()], "raw": {"secret": "no"}}
        )

    agent = _CapturingAgent()
    outcome = asyncio.run(
        AlertAnalysisPipeline(provider=_provider(handler), agent=agent).analyze(_context())
    )
    assert outcome.status.value == "completed"
    assert "raw" not in str(agent.requests[0])
    assert "raw" not in str(outcome.artifact.payload)
    assert "token" not in str(agent.requests[0]) + str(outcome.artifact.payload)


def test_cursor_pagination_exhausts_all_pages_with_stable_request_scope() -> None:
    requests: list[dict[str, object]] = []
    pages = [
        {"isLast": False, "nextPageToken": "first", "issues": [_issue("one")]},
        {"isLast": False, "nextPageToken": "second", "issues": [_issue("two")]},
        {"isLast": True, "issues": [_issue("three")]},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=pages[len(requests) - 1])

    outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
    assert [record.id for record in outcome.records] == ["one", "two", "three"]
    assert [body.get("nextPageToken") for body in requests] == [None, "first", "second"]
    assert all(body["jql"] == requests[0]["jql"] for body in requests)
    assert all(body["fields"] == requests[0]["fields"] for body in requests)
    assert all(body["maxResults"] == 100 for body in requests)


def test_inconsistent_pagination_envelopes_fail_without_truncated_success() -> None:
    cases = (
        {"issues": []},
        {"isLast": "false", "issues": []},
        {"isLast": False, "issues": []},
        {"isLast": False, "nextPageToken": "", "issues": []},
        {"isLast": True, "nextPageToken": "unexpected", "issues": []},
        {"isLast": True, "nextPageToken": 0, "issues": []},
        {"isLast": True, "nextPageToken": False, "issues": []},
        {"isLast": True, "nextPageToken": [], "issues": []},
        {"isLast": True, "nextPageToken": {}, "issues": []},
        {"isLast": True, "issues": {}},
    )
    for page in cases:
        requests: list[httpx.Request] = []

        def handler(
            request: httpx.Request,
            page: dict[str, object] = page,
            requests: list[httpx.Request] = requests,
        ) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=page)

        outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
        assert outcome.state == "failed"
        assert len(requests) == 1

    requests = []
    pages = [
        {"isLast": False, "nextPageToken": "again", "issues": [_issue("one")]},
        {"isLast": False, "nextPageToken": "again", "issues": [_issue("two")]},
    ]

    def repeated_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=pages[len(requests) - 1])

    outcome = asyncio.run(_provider(repeated_handler).acquire(_scope(), _window()))
    assert outcome.state == "failed"
    assert len(requests) == 2


def test_terminal_pagination_accepts_only_absent_null_or_empty_string_token() -> None:
    pages = (
        {"isLast": True, "issues": []},
        {"isLast": True, "nextPageToken": None, "issues": []},
        {"isLast": True, "nextPageToken": "", "issues": []},
    )
    for page in pages:
        outcome = asyncio.run(
            _provider(lambda _, page=page: httpx.Response(200, json=page)).acquire(
                _scope(), _window()
            )
        )

        assert outcome.source == "jira_track_and_release"
        assert outcome.records == ()


def test_volume_cap_accepts_only_exact_terminal_one_thousand() -> None:
    exact_pages = [
        {
            "isLast": False,
            "nextPageToken": str(index),
            "issues": [_issue(f"i-{index}-{row}") for row in range(100)],
        }
        for index in range(9)
    ] + [{"isLast": True, "issues": [_issue(f"i-9-{row}") for row in range(100)]}]
    exact_requests: list[httpx.Request] = []

    def exact_handler(request: httpx.Request) -> httpx.Response:
        exact_requests.append(request)
        return httpx.Response(200, json=exact_pages[len(exact_requests) - 1])

    exact = asyncio.run(_provider(exact_handler).acquire(_scope(), _window()))
    assert len(exact.records) == 1000
    assert len(exact_requests) == 10

    for page in (
        {"isLast": True, "issues": [_issue(str(row)) for row in range(1001)]},
        {
            "isLast": False,
            "nextPageToken": "more",
            "issues": [_issue(str(row)) for row in range(1000)],
        },
    ):
        requests: list[httpx.Request] = []

        def handler(
            request: httpx.Request,
            page: dict[str, object] = page,
            requests: list[httpx.Request] = requests,
        ) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=page)

        outcome = asyncio.run(_provider(handler).acquire(_scope(), _window()))
        assert outcome.state == "failed"
        assert len(requests) == 1


def test_pagination_failures_use_existing_current_and_reference_paths() -> None:
    current_failure = asyncio.run(
        AlertAnalysisPipeline(
            provider=_provider(lambda _: httpx.Response(200, json={"isLast": False, "issues": []})),
            agent=_CapturingAgent(),
        ).analyze(_context())
    )
    assert current_failure.status.value == "failed"
    assert current_failure.reason.code == "current_query_failed"

    calls = 0

    def reference_failure(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"isLast": True, "issues": [_issue()]}
            if calls == 1
            else {"isLast": False, "issues": []},
        )

    reference = asyncio.run(
        AlertAnalysisPipeline(
            provider=_provider(reference_failure), agent=_CapturingAgent()
        ).analyze(_context(references=("1h",)))
    )
    assert reference.status.value == "partial"
    assert reference.reason.code == "reference_unavailable"


class _ControlledClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _CancellationObservableStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.closed = False
        self.cancelled = False

    async def __aiter__(self):
        self.started.set()
        try:
            yield b'{"isLast":true,"issues":['
            await self.release.wait()
            yield b"]}"
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def aclose(self) -> None:
        self.closed = True


def test_hard_attempt_deadline_cancels_slow_progress_body_and_cleans_up() -> None:
    clock = _ControlledClock()
    stream = _CancellationObservableStream()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream)

    async def deadline_runner(operation, deadline: float) -> httpx.Response:
        assert deadline == 15
        task = asyncio.create_task(operation)
        await stream.started.wait()
        clock.now += deadline
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        raise TimeoutError

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(handler),
        monotonic=clock,
        run_with_deadline=deadline_runner,
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert outcome.state == "timeout"
    assert stream.cancelled and stream.closed


def test_hard_acquire_deadline_spans_pages_and_stops_new_work() -> None:
    clock = _ControlledClock()
    requests: list[httpx.Request] = []
    stream = _CancellationObservableStream()

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200, json={"isLast": False, "nextPageToken": "next", "issues": []}
            )
        return httpx.Response(200, stream=stream)

    calls = 0

    async def deadline_runner(operation, deadline: float) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert deadline == 15
        if calls == 1:
            response = await operation
            clock.now = 45
            return response
        task = asyncio.create_task(operation)
        await stream.started.wait()
        clock.now = 60
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        raise TimeoutError

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(handler),
        monotonic=clock,
        run_with_deadline=deadline_runner,
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert outcome.state == "timeout"
    assert len(requests) == 2
    assert stream.cancelled and stream.closed


def test_attempt_requires_a_complete_fifteen_second_remaining_budget() -> None:
    calls = 0
    times = iter((0.0, 45.001))

    def clock() -> float:
        return next(times)

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"isLast": True, "issues": []})

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(handler),
        monotonic=clock,
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert outcome.state == "timeout"
    assert calls == 0

    exact_calls = 0
    exact_times = iter((0.0, 45.0))

    def exact_clock() -> float:
        return next(exact_times)

    def exact_handler(_: httpx.Request) -> httpx.Response:
        nonlocal exact_calls
        exact_calls += 1
        return httpx.Response(200, json={"isLast": True, "issues": []})

    exact_provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(exact_handler),
        monotonic=exact_clock,
    )
    exact_outcome = asyncio.run(exact_provider.acquire(_scope(), _window()))
    assert exact_outcome.records == ()
    assert exact_calls == 1


def test_current_hard_deadline_preserves_timeout_reason() -> None:
    async def deadline_runner(operation, _: float) -> httpx.Response:
        operation.close()
        raise TimeoutError

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(lambda _: httpx.Response(200)),
        run_with_deadline=deadline_runner,
    )
    outcome = asyncio.run(
        AlertAnalysisPipeline(provider=provider, agent=_CapturingAgent()).analyze(_context())
    )
    assert outcome.status.value == "failed"
    assert outcome.reason.code == "current_query_timeout"
    assert outcome.artifact is None


def test_reference_hard_deadline_degrades_only_reference() -> None:
    calls = 0

    async def deadline_runner(operation, _: float) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return await operation
        operation.close()
        raise TimeoutError

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"isLast": True, "issues": [_issue()]})
        ),
        run_with_deadline=deadline_runner,
    )
    outcome = asyncio.run(
        AlertAnalysisPipeline(provider=provider, agent=_CapturingAgent()).analyze(
            _context(references=("1h",))
        )
    )
    assert outcome.status.value == "partial"
    assert outcome.reason.code == "reference_unavailable"


def test_retryability_and_attempt_counts_are_closed_and_exact() -> None:
    retriable = (429, 502, 503, 504)
    excluded = (400, 401, 403, 404, 500, 501, 505)

    for status in retriable + excluded:
        calls = 0
        waits: list[float] = []

        async def sleep(delay: float, waits: list[float] = waits) -> None:
            waits.append(delay)

        def handler(_: httpx.Request, status: int = status) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                status,
                headers={"X-Provider-Secret": "SECRET_PROVIDER_HEADER"},
                content=b"SECRET_PROVIDER_BODY",
            )

        provider = HttpxJiraAlertProvider(
            JiraAlertProviderSettings(
                site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
            ),
            transport=httpx.MockTransport(handler),
            sleep=sleep,
        )
        outcome = asyncio.run(provider.acquire(_scope(), _window()))
        assert outcome.state == "failed"
        assert calls == (3 if status in retriable else 1)
        assert waits == ([0.5, 1.0] if status in retriable else [])
        assert "SECRET_PROVIDER_BODY" not in outcome.diagnostic
        assert "SECRET_PROVIDER_HEADER" not in outcome.diagnostic


def test_retry_after_raw_header_grammar_and_waits_are_exact() -> None:
    cases = (
        ([(b"Retry-After", b" \t005\t ")], [5.0]),
        ([(b"Retry-After", b"15")], [15.0]),
        ([(b"Retry-After", b"16")], []),
        ([(b"Retry-After", b"0")], [0.5]),
        ([(b"Retry-After", b"+5")], [0.5]),
        ([(b"Retry-After", b"1.5")], [0.5]),
        ([(b"Retry-After", b"1, 2")], [0.5]),
        ([(b"Retry-After", b"3"), (b"Retry-After", b"4")], [0.5]),
        ([(b"Retry-After", b"Wed, 21 Oct 2015 07:28:00 GMT")], [0.5]),
    )
    for headers, expected_waits in cases:
        calls = 0
        waits: list[float] = []

        async def sleep(delay: float, waits: list[float] = waits) -> None:
            waits.append(delay)

        def handler(_: httpx.Request, headers=headers) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, headers=headers)
            return httpx.Response(200, json={"isLast": True, "issues": []})

        provider = HttpxJiraAlertProvider(
            JiraAlertProviderSettings(
                site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
            ),
            transport=httpx.MockTransport(handler),
            sleep=sleep,
        )
        outcome = asyncio.run(provider.acquire(_scope(), _window()))
        if headers == [(b"Retry-After", b"16")]:
            assert outcome.state == "timeout" and calls == 1
        else:
            assert outcome.records == () and calls == 2
        assert waits == expected_waits


def test_fallback_retry_waits_and_maximum_attempts_are_exact() -> None:
    calls = 0
    waits: list[float] = []

    async def sleep(delay: float) -> None:
        waits.append(delay)

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("credential=SECRET")

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert outcome.state == "failed"
    assert outcome.diagnostic == "transport_error"
    assert calls == 3
    assert waits == [0.5, 1.0]


def test_retry_delay_cap_and_remaining_budget_admission_return_timeout() -> None:
    clock = _ControlledClock()
    calls = 0
    waits: list[float] = []

    async def sleep(delay: float) -> None:
        waits.append(delay)
        clock.now += delay

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        clock.now = 30.1
        return httpx.Response(503, headers={"Retry-After": "15"})

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(handler),
        monotonic=clock,
        sleep=sleep,
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert outcome.state == "timeout"
    assert calls == 1 and waits == []

    clock.now = 0
    calls = 0

    def exact_handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            clock.now = 30
            return httpx.Response(503, headers={"Retry-After": "15"})
        return httpx.Response(200, json={"isLast": True, "issues": []})

    exact = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(exact_handler),
        monotonic=clock,
        sleep=sleep,
    )
    assert asyncio.run(exact.acquire(_scope(), _window())).records == ()
    assert calls == 2 and waits == [15.0]


def test_hard_acquire_deadline_includes_pages_attempts_and_retry_waits() -> None:
    clock = _ControlledClock()
    calls = 0
    waits: list[float] = []

    async def sleep(delay: float) -> None:
        waits.append(delay)
        clock.now = 60

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200, json={"isLast": False, "nextPageToken": "next", "issues": []}
            )
        return httpx.Response(503)

    provider = HttpxJiraAlertProvider(
        JiraAlertProviderSettings(
            site_url="https://foo.atlassian.net", email="bot@example.invalid", api_token="token"
        ),
        transport=httpx.MockTransport(handler),
        monotonic=clock,
        sleep=sleep,
    )
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert outcome.state == "timeout"
    assert calls == 2 and waits == [0.5]


def test_retry_terminal_outcomes_preserve_current_and_reference_semantics() -> None:
    current = asyncio.run(
        AlertAnalysisPipeline(
            provider=_provider(lambda _: httpx.Response(503)), agent=_CapturingAgent()
        ).analyze(_context())
    )
    assert current.status.value == "failed"
    assert current.reason.code == "current_query_failed"

    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"isLast": True, "issues": [_issue()]})
        return httpx.Response(503)

    reference = asyncio.run(
        AlertAnalysisPipeline(provider=_provider(handler), agent=_CapturingAgent()).analyze(
            _context(references=("1h",))
        )
    )
    assert reference.status.value == "partial"
    assert reference.reason.code == "reference_unavailable"
    assert calls == 4
