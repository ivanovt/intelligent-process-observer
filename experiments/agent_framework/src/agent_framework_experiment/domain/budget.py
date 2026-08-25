"""Authoritative framework-neutral analytical-tool budget enforcement."""

from __future__ import annotations

from threading import Lock


class ToolBudgetExhausted(RuntimeError):
    """Raised before an eleventh analytical invocation can start."""


class ToolBudget:
    def __init__(self, limit: int = 10) -> None:
        self._limit = limit
        self._attempts = 0
        self._lock = Lock()

    @property
    def attempts(self) -> int:
        with self._lock:
            return self._attempts

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._limit - self._attempts

    def reserve_attempt(self) -> int:
        """Reserve an attempt before a tool runs; all terminal results consume it."""

        with self._lock:
            if self._attempts >= self._limit:
                raise ToolBudgetExhausted(f"analytical tool budget of {self._limit} exhausted")
            self._attempts += 1
            return self._attempts
