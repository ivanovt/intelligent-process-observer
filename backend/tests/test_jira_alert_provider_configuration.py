import asyncio
import json
from datetime import UTC, datetime

import pytest

from app.alerts.contracts import AlertAnalysisWindow, AlertProviderScope, AlertProviderUnavailable
from app.core.settings import Settings
from app.infrastructure.jira.adapter import HttpxJiraAlertProvider
from app.infrastructure.jira.composition import JiraAlertProviderResolver, UnavailableAlertProvider
from app.infrastructure.jira.configuration import (
    JiraAlertProviderSettings,
    canonical_jira_origin,
)


def _scope(source: str = "jira_track_and_release") -> AlertProviderScope:
    return AlertProviderScope(source=source, query="project = IPO")


def _window() -> AlertAnalysisWindow:
    return AlertAnalysisWindow(
        **{"from": datetime(2026, 9, 1, tzinfo=UTC), "to": datetime(2026, 9, 1, 1, tzinfo=UTC)}
    )


def test_optional_jira_configuration_never_breaks_global_settings_or_startup(monkeypatch) -> None:
    monkeypatch.setenv("JIRA_ALERT_PROVIDER", "{token-bearing-malformed")
    settings = Settings()
    assert settings.jira_alert_provider_raw == "{token-bearing-malformed"
    resolver = JiraAlertProviderResolver(settings.jira_alert_provider_raw)
    provider = resolver.resolve(_scope())
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert isinstance(outcome, AlertProviderUnavailable)
    assert outcome.diagnostic == "configuration_invalid"


def test_unavailable_provider_is_typed_and_safe() -> None:
    provider = JiraAlertProviderResolver(None).resolve(_scope())
    assert callable(provider.acquire)
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert isinstance(outcome, AlertProviderUnavailable)
    assert outcome.diagnostic == "not_configured"


@pytest.mark.parametrize(
    "site_url",
    [
        "https://foo.atlassian.net",
        "https://foo.atlassian.net/",
        "https://foo.atlassian.net/jira",
        "https://foo.atlassian.net/jira/",
        "https://FOO.atlassian.net/jira/",
    ],
)
def test_jira_site_url_allowlist_and_canonical_origin_are_exact(site_url: str) -> None:
    assert canonical_jira_origin(site_url) == "https://foo.atlassian.net"


@pytest.mark.parametrize(
    "site_url",
    [
        "http://foo.atlassian.net",
        "https://user@foo.atlassian.net",
        "https://foo.atlassian.net:443",
        "https://foo.atlassian.net?query=1",
        "https://foo.atlassian.net#fragment",
        "https://127.0.0.1",
        "https://foo.bar.atlassian.net",
        "https://foo.atlassian.net/other",
        "https://api.atlassian.com/ex/jira/cloud-id",
    ],
)
def test_unsafe_site_urls_are_rejected(site_url: str) -> None:
    with pytest.raises(ValueError, match="invalid Jira site URL"):
        canonical_jira_origin(site_url)


@pytest.mark.parametrize(
    "site_url",
    [
        "https://foo.atlassian.net:",
        "HTTPS://foo.atlassian.net:",
        " https://foo.atlassian.net",
        "https://foo.atlassian.net ",
        "https://foo .atlassian.net",
        "https://foo.atlassian.net/ jira",
        "https://foo.atlassian.net/\u00a0jira",
    ],
)
def test_raw_site_url_syntax_rejected_before_parser_normalization(site_url: str) -> None:
    with pytest.raises(ValueError, match="invalid Jira site URL"):
        canonical_jira_origin(site_url)


@pytest.mark.parametrize("control", [*(chr(codepoint) for codepoint in range(32)), "\x7f"])
def test_ascii_controls_are_rejected_before_parser_normalization(control: str) -> None:
    with pytest.raises(ValueError, match="invalid Jira site URL"):
        canonical_jira_origin(f"https://foo.atlassian.net/{control}jira")


@pytest.mark.parametrize(
    "site_url",
    [
        "https://foo.atlassian.net:",
        "https://foo.atlassian.net\t/jira",
        "https://foo.atlassian.net/jira\n",
    ],
)
def test_raw_site_url_syntax_never_constructs_a_provider(site_url: str) -> None:
    raw = json.dumps(
        {
            "site_url": site_url,
            "email": "bot@example.invalid",
            "api_token": "secret",
        }
    )

    provider = JiraAlertProviderResolver(raw).resolve(_scope())

    assert isinstance(provider, UnavailableAlertProvider)


def test_valid_and_invalid_jira_resolution_always_returns_an_alert_provider() -> None:
    valid = '{"site_url":"https://foo.atlassian.net/jira","email":"bot@example.invalid","api_token":"secret"}'
    assert isinstance(JiraAlertProviderResolver(valid).resolve(_scope()), HttpxJiraAlertProvider)
    invalid = JiraAlertProviderResolver(
        '{"site_url":"https://evil.example","email":"bot","api_token":"secret"}'
    ).resolve(_scope())
    assert isinstance(invalid, UnavailableAlertProvider)
    assert callable(invalid.acquire)


def test_configuration_is_closed_and_secret_safe() -> None:
    raw = '{"site_url":"https://foo.atlassian.net","email":"sentinel@example.invalid","api_token":"sentinel-token","cloud_id":"no"}'
    provider = JiraAlertProviderResolver(raw).resolve(_scope())
    outcome = asyncio.run(provider.acquire(_scope(), _window()))
    assert isinstance(outcome, AlertProviderUnavailable)
    assert outcome.diagnostic == "configuration_invalid"
    assert "sentinel" not in repr(provider)


def test_settings_provider_repr_and_diagnostics_do_not_leak_credentials() -> None:
    email = "sentinel-email@example.invalid"
    token = "sentinel-api-token"
    settings = JiraAlertProviderSettings(
        site_url="https://foo.atlassian.net",
        email=email,
        api_token=token,
    )
    provider = HttpxJiraAlertProvider(settings)
    unavailable = JiraAlertProviderResolver(
        json.dumps(
            {
                "site_url": "https://foo.atlassian.net",
                "email": email,
                "api_token": token,
                "unsupported": True,
            }
        )
    ).resolve(_scope())
    outcome = asyncio.run(unavailable.acquire(_scope(), _window()))

    for rendered in (repr(settings), repr(provider), repr(outcome), outcome.diagnostic):
        assert email not in rendered
        assert token not in rendered


def test_jira_provider_resolution_is_isolated_to_jira_track_and_release_source() -> None:
    raw = '{"site_url":"https://foo.atlassian.net","email":"bot@example.invalid","api_token":"secret"}'
    with pytest.raises(ValueError, match="does not support"):
        JiraAlertProviderResolver(raw).resolve(_scope("another_source"))
