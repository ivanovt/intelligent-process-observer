"""Bounded side-effect-free orchestration for report generation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded

from app.core.diagnostics import DiagnosticEvent, OperationalEventEmitter
from app.reporting.contracts import (
    ReportFailure,
    ReportGenerationOutcome,
    ReportGenerationRequest,
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
        trace_recorder: object | None = None,
        emitter: OperationalEventEmitter | None = None,
    ) -> None:
        """Bind one framework-neutral agent and an injectable UTC report clock."""
        self._agent = agent
        self._clock = clock or (lambda: datetime.now(UTC))
        self._trace_recorder = trace_recorder
        self._emitter = emitter or OperationalEventEmitter()

    async def execute(self, value: object) -> ReportGenerationOutcome:
        """Execute at most one presentation request and fail closed on all failures."""
        try:
            request = validate_request(value)  # type: ignore[arg-type]
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._emit_failure(None, "report_request_invalid", "request_validation", error)
            return ReportFailure(code="report_result_invalid", component="request_validation")
        try:
            draft = await self._agent.complete_presentation(request)
        except asyncio.CancelledError:
            raise
        except TimeoutError as error:
            self._emit_failure(request, "report_timeout", "report_generation", error)
            return ReportFailure(code="report_model_timed_out", component="report_generation")
        except (UsageLimitExceeded, ReportPolicyViolation) as error:
            self._emit_failure(request, "report_policy_rejected", "report_generation", error)
            return ReportFailure(code="report_policy_violated", component="report_generation")
        except (UnexpectedModelBehavior, ValueError, TypeError) as error:
            self._emit_failure(request, "report_schema_rejected", "report_generation", error)
            return ReportFailure(code="report_result_invalid", component="report_generation")
        except Exception as error:
            self._emit_failure(request, "report_internal_failed", "report_generation", error)
            return ReportFailure(code="report_model_failed", component="report_generation")
        try:
            report = build_report(request, validate_presentation(request, draft), self._clock())
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._emit_failure(request, "report_render_rejected", "report_builder", error)
            await self._record_validation(
                request.context.identity.observation_run_id, outcome="rejected", detail=str(error)
            )
            return ReportFailure(code="report_result_invalid", component="report_builder")
        await self._record_validation(
            request.context.identity.observation_run_id, outcome="accepted"
        )
        return ReportSuccess(report=report)

    async def _record_validation(
        self, observation_run_id, *, outcome: str, detail: str | None = None
    ) -> None:
        """Append the deterministic report-render outcome when a trace sink is enabled."""
        append = getattr(self._trace_recorder, "append_validation", None)
        if append is not None:
            try:
                await append(
                    observation_run_id=observation_run_id,
                    phase="report_render",
                    category="report_render",
                    outcome=outcome,
                    detail=detail,
                )
            except Exception:
                return

    def _emit_failure(
        self,
        request: ReportGenerationRequest | None,
        category: str,
        component: str,
        error: BaseException,
    ) -> None:
        """Emit safe normalized report failure metadata without presentation content."""
        self._emitter.emit(
            DiagnosticEvent(
                event="report_failure_normalized",
                category=category,
                observation_run_id=(
                    request.context.identity.observation_run_id if request is not None else None
                ),
                agent_role="report",
                phase="generation",
                component=component,
                exception_type=type(error).__name__,
            )
        )
