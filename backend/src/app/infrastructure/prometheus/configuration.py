"""Private production-target validation for Prometheus Metric acquisition."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

_DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9._~-]+")
_AUTHORITY = re.compile(r"(?:[A-Za-z0-9.-]+(?::[0-9]+)?|\[[0-9A-Fa-f:.]+\](?::[0-9]+)?)")


@dataclass(frozen=True)
class _ValidatedPrometheusTarget:
    """A production-safe origin and normalized path prefix for a future request."""

    origin: str
    prefix: str


def _validate_prometheus_target(base_url: str) -> _ValidatedPrometheusTarget | None:
    """Return a safe target only when the configured URL has an unambiguous form."""

    if not base_url or any(
        ord(character) < 0x21 or ord(character) > 0x7E for character in base_url
    ):
        return None
    if "?" in base_url or "#" in base_url:
        return None
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        return None
    if not _valid_components(base_url, parsed, port):
        return None

    host = parsed.hostname
    if host is None or not _valid_host(host):
        return None
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
        return None

    prefix = _validated_prefix(parsed.path)
    if prefix is None:
        return None
    authority = parsed.netloc
    origin = f"{parsed.scheme}://{authority}"
    return _ValidatedPrometheusTarget(origin=origin, prefix=prefix)


def _valid_components(base_url: str, parsed: SplitResult, port: int | None) -> bool:
    if parsed.scheme not in {"https", "http"} or not base_url.startswith(f"{parsed.scheme}://"):
        return False
    if not parsed.netloc or "@" in parsed.netloc or "\\" in parsed.netloc:
        return False
    if _AUTHORITY.fullmatch(parsed.netloc) is None:
        return False
    has_userinfo = parsed.username is not None or parsed.password is not None
    has_invalid_port = port is not None and not 1 <= port <= 65535
    if has_userinfo or has_invalid_port:
        return False
    return parsed.query == "" and parsed.fragment == ""


def _valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host.endswith(".") or len(host) > 253:
            return False
        return all(_DNS_LABEL.fullmatch(label) is not None for label in host.split("."))
    return True


def _validated_prefix(path: str) -> str | None:
    if path in {"", "/"}:
        return ""
    if not path.startswith("/") or "\\" in path or "%" in path:
        return None
    normalized = path[:-1] if path.endswith("/") else path
    segments = normalized[1:].split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        return None
    if any(_PATH_SEGMENT.fullmatch(segment) is None for segment in segments):
        return None
    return normalized
