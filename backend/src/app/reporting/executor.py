"""Bounded side-effect-free orchestration for report generation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded

from app.reporting.contracts import (
    ReportFailure,
    ReportGenerationOutcome,
    ReportPolicyViolation,
    ReportSuccess,
)
from app.reporting.input import validate_request
from app.reporting.ports import ReportGenerationAgent
from app.reporting.presentation import build_report, validate_presentation


class ReportGenerationExecutor:
    """Generate one validated in-memory report through an injected presentation port."""

    def __init__(
        self,
        agent: ReportGenerationAgent,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Bind one framework-neutral agent and an injectable UTC report clock."""
        self._agent = agent
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(self, value: object) -> ReportGenerationOutcome:
        """Execute at most one presentation request and fail closed on all failures."""
        try:
            request = validate_request(value)  # type: ignore[arg-type]
        except asyncio.CancelledError:
            raise
        except Exception:
            return ReportFailure(code="report_result_invalid", component="request_validation")
        try:
            draft = await self._agent.complete_presentation(request)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return ReportFailure(code="report_model_timed_out", component="report_generation")
        except (UsageLimitExceeded, ReportPolicyViolation):
            return ReportFailure(code="report_policy_violated", component="report_generation")
        except (UnexpectedModelBehavior, ValueError, TypeError):
            return ReportFailure(code="report_result_invalid", component="report_generation")
        except Exception:
            return ReportFailure(code="report_model_failed", component="report_generation")
        try:
            report = build_report(request, validate_presentation(request, draft), self._clock())
        except asyncio.CancelledError:
            raise
        except Exception:
            return ReportFailure(code="report_result_invalid", component="report_builder")
        return ReportSuccess(report=report)
