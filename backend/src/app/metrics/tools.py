"""Deterministic optional Metric tools bound to one prepared current series."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable
from inspect import isawaitable
from statistics import median

from app.metrics.contracts import (
    FIXED_ALLOWED_TOOLS,
    MetricAgentProtocolFailure,
    MetricOptionalProjections,
    MetricToolAttempt,
    MetricToolExecutionOutcome,
    MetricToolFailed,
    MetricToolName,
    MetricToolNotApplicable,
    MetricToolOutcome,
    MetricToolRejected,
    MetricToolRejectionReason,
    MetricToolSuccess,
    MetricToolTimedOut,
    OscillationEvidence,
    OscillationToolSuccess,
    PreparedUsableSeries,
    SpikeModifiedZEvidence,
    SpikeToolSuccess,
    SpikeZeroMadEvidence,
    StuckSignalEvidence,
    StuckSignalToolSuccess,
)

ToolEvaluator = Callable[
    [PreparedUsableSeries], MetricToolExecutionOutcome | Awaitable[MetricToolExecutionOutcome]
]


def analyze_spike(prepared: PreparedUsableSeries) -> MetricToolExecutionOutcome:
    samples = prepared.samples
    if len(samples) < 5:
        return MetricToolNotApplicable(name="spike")
    values = tuple(sample.value for sample in samples)
    center = median(values)
    deviations = tuple(abs(value - center) for value in values)
    mad = median(deviations)
    if mad == 0:
        detected = tuple(sample for sample in samples if sample.value != center)
        deviation_count = len(detected)
        sparse_limit = max(1, math.floor(0.1 * len(samples)))
        if deviation_count == 0:
            state = "absent"
            detected = ()
        elif deviation_count <= sparse_limit:
            state = "present"
        else:
            state = "unknown"
            detected = ()
        return SpikeToolSuccess(
            state=state,
            evidence=SpikeZeroMadEvidence(
                deviation_count=deviation_count,
                detected_sample_count=len(detected),
                detected_timestamps=tuple(sample.timestamp for sample in detected),
            ),
        )
    scores = tuple(0.6745 * (sample.value - center) / mad for sample in samples)
    detected = tuple(
        sample for sample, score in zip(samples, scores, strict=True) if abs(score) > 3.5
    )
    return SpikeToolSuccess(
        state="present" if detected else "absent",
        evidence=SpikeModifiedZEvidence(
            detected_sample_count=len(detected),
            detected_timestamps=tuple(sample.timestamp for sample in detected),
            max_abs_modified_z=max(abs(score) for score in scores),
        ),
    )


def analyze_oscillation(prepared: PreparedUsableSeries) -> MetricToolExecutionOutcome:
    if len(prepared.samples) < 8:
        return MetricToolNotApplicable(name="oscillation")
    scale = max(abs(prepared.evidence.mean), prepared.evidence.max - prepared.evidence.min)
    deadband = 0.05 * scale
    residuals = prepared.residuals
    significant = tuple(residual for residual in residuals if abs(residual) > deadband)
    significant_count = len(significant)
    signs = tuple(1 if residual > 0 else -1 for residual in significant)
    sign_changes = sum(left != right for left, right in zip(signs, signs[1:], strict=False))
    ratio = sign_changes / (significant_count - 1) if significant_count >= 2 else 0.0
    if all(residual == 0 for residual in residuals):
        state = "absent"
    elif significant_count < 4:
        state = "unknown"
    elif sign_changes >= 3 and ratio >= 0.60:
        state = "present"
    else:
        state = "absent"
    return OscillationToolSuccess(
        state=state,
        evidence=OscillationEvidence(
            deadband=deadband,
            significant_residual_count=significant_count,
            sign_change_count=sign_changes,
            sign_change_ratio=ratio,
        ),
    )


def analyze_stuck_signal(prepared: PreparedUsableSeries) -> MetricToolExecutionOutcome:
    samples = prepared.samples
    if len(samples) < 5:
        return MetricToolNotApplicable(name="stuck_signal")
    longest_start = 0
    longest_length = 1
    run_start = 0
    for index in range(1, len(samples) + 1):
        if index < len(samples) and samples[index].value == samples[run_start].value:
            continue
        run_length = index - run_start
        if run_length > longest_length:
            longest_start = run_start
            longest_length = run_length
        run_start = index
    share = longest_length / len(samples)
    return StuckSignalToolSuccess(
        state="present" if share >= 0.80 else "absent",
        evidence=StuckSignalEvidence(
            repeated_value=samples[longest_start].value,
            longest_run_sample_count=longest_length,
            longest_run_share=share,
        ),
    )


class MetricToolRegistry:
    """One run-scoped, immutable dataset binding and its authoritative ledger."""

    descriptors = FIXED_ALLOWED_TOOLS

    def __init__(self, dataset_ref: str, prepared: PreparedUsableSeries) -> None:
        self._dataset_ref = dataset_ref
        self._prepared = prepared
        self._attempts: list[MetricToolAttempt] = []
        self._used_names: set[MetricToolName] = set()
        self._active_execution = False
        self._consumed_slots = 0
        self._next_ordinal = 1
        self._evaluators: dict[MetricToolName, ToolEvaluator] = {
            "spike": analyze_spike,
            "oscillation": analyze_oscillation,
            "stuck_signal": analyze_stuck_signal,
        }

    @property
    def dataset_ref(self) -> str:
        return self._dataset_ref

    @property
    def ledger(self) -> tuple[MetricToolAttempt, ...]:
        return tuple(sorted(self._attempts, key=lambda attempt: attempt.ordinal))

    @property
    def protocol_failure(self) -> MetricAgentProtocolFailure | None:
        if any(isinstance(attempt.outcome, MetricToolRejected) for attempt in self._attempts):
            return MetricAgentProtocolFailure()
        return None

    async def execute(self, name: str) -> MetricToolOutcome:
        """Apply request admission before evaluating the sole bound prepared-current dataset."""

        ordinal = self._reserve_ordinal()
        if self._consumed_slots >= 3:
            return self._reject(name, ordinal, "over_budget")
        if self._active_execution:
            return self._reject(name, ordinal, "parallel")
        if name not in self._evaluators:
            return self._reject(name, ordinal, "unregistered")

        registered_name: MetricToolName = name
        if registered_name in self._used_names:
            return self._reject(name, ordinal, "duplicate")

        self._consumed_slots += 1
        self._used_names.add(registered_name)
        self._active_execution = True
        try:
            outcome = self._evaluators[registered_name](self._prepared)
            if isawaitable(outcome):
                outcome = await outcome
        except TimeoutError as error:
            outcome = MetricToolTimedOut(name=registered_name, diagnostic=_diagnostic(error))
        except Exception as error:
            outcome = MetricToolFailed(name=registered_name, diagnostic=_diagnostic(error))
        finally:
            self._active_execution = False
        self._attempts.append(
            MetricToolAttempt(
                ordinal=ordinal,
                requested_name=registered_name,
                outcome=outcome,
                executed=True,
                consumed_slot=True,
            )
        )
        return outcome

    def _reserve_ordinal(self) -> int:
        ordinal = self._next_ordinal
        self._next_ordinal += 1
        return ordinal

    def _reject(
        self,
        requested_name: str,
        ordinal: int,
        reason: MetricToolRejectionReason,
    ) -> MetricToolRejected:
        rejected = MetricToolRejected(reason=reason)
        consumed_slot = reason != "over_budget"
        if consumed_slot:
            self._consumed_slots += 1
        self._attempts.append(
            MetricToolAttempt(
                ordinal=ordinal,
                requested_name=requested_name,
                outcome=rejected,
                executed=False,
                consumed_slot=consumed_slot,
            )
        )
        return rejected


def project_successful_optional_tools(
    ledger: tuple[MetricToolAttempt, ...],
) -> MetricOptionalProjections:
    """Project only successful deterministic outcomes; the ledger remains transient."""

    values: dict[str, MetricToolSuccess] = {}
    for attempt in ledger:
        if isinstance(
            attempt.outcome,
            (SpikeToolSuccess, OscillationToolSuccess, StuckSignalToolSuccess),
        ):
            values[attempt.outcome.name] = attempt.outcome
    return MetricOptionalProjections(
        spike=values.get("spike"),
        oscillation=values.get("oscillation"),
        stuck_signal=values.get("stuck_signal"),
    )


def earliest_optional_tool_failure(
    ledger: tuple[MetricToolAttempt, ...],
) -> MetricToolName | None:
    for attempt in ledger:
        if isinstance(attempt.outcome, (MetricToolFailed, MetricToolTimedOut)):
            return attempt.requested_name
    return None


def _diagnostic(error: BaseException) -> str:
    detail = str(error).strip() or type(error).__name__
    return detail[:512]
