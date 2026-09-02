"""Private configuration validation for the Jira Cloud Alert provider."""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

_SITE_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class JiraAlertProviderSettings(BaseModel):
    """Validated private credentials and canonical origin for one Jira Cloud site."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    site_url: str
    email: SecretStr
    api_token: SecretStr

    @field_validator("site_url")
    @classmethod
    def require_safe_site_url(cls, value: str) -> str:
        """Reject unsafe Jira targets before any provider can be constructed."""
        canonical_jira_origin(value)
        return value

    @field_validator("email")
    @classmethod
    def require_non_blank_email(cls, value: SecretStr) -> SecretStr:
        """Require a non-blank ordinary-user account email."""
        if not value.get_secret_value().strip():
            raise ValueError("email must not be blank")
        return value

    @field_validator("api_token")
    @classmethod
    def require_non_blank_token(cls, value: SecretStr) -> SecretStr:
        """Require a non-blank classic-token secret without exposing it."""
        if not value.get_secret_value():
            raise ValueError("api_token must not be empty")
        return value

    @property
    def canonical_origin(self) -> str:
        """Return the validated pathless site origin used for all Jira URLs."""
        return canonical_jira_origin(self.site_url)


def parse_jira_alert_provider_settings(raw: str) -> JiraAlertProviderSettings:
    """Parse one serialized provider profile without leaking parse details to callers."""
    payload = json.loads(raw)
    return JiraAlertProviderSettings.model_validate(payload)


def canonical_jira_origin(site_url: str) -> str:
    """Validate a Jira Cloud site URL and return its safe pathless origin."""
    parts = urlsplit(site_url)
    if parts.scheme != "https" or parts.username is not None or parts.password is not None:
        raise ValueError("invalid Jira site URL")
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError("invalid Jira site URL") from error
    if port is not None or parts.query or parts.fragment:
        raise ValueError("invalid Jira site URL")
    host = parts.hostname
    if host is None or not host.isascii():
        raise ValueError("invalid Jira site URL")
    host = host.lower()
    suffix = ".atlassian.net"
    if not host.endswith(suffix):
        raise ValueError("invalid Jira site URL")
    label = host[: -len(suffix)]
    if "." in label or not _SITE_LABEL.fullmatch(label):
        raise ValueError("invalid Jira site URL")
    if parts.path not in {"", "/", "/jira", "/jira/"}:
        raise ValueError("invalid Jira site URL")
    return f"https://{host}"
