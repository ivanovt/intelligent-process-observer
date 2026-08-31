"""Pure deterministic analysis of persisted Metric result projections."""

from __future__ import annotations

from collections import Counter
from typing import Literal
from uuid import UUID

from app.metrics.contracts import (
    MetricCurrentEvidence,
    MetricHistory,
    MetricHistoryCandidate,
    MetricHistoryEvidence,
    MetricHistoryPolicy,
    MetricLensExecutionContext,
)

HistoryTransition = Literal["increasing", "decreasing", "stable", "unknown"]


def classify_transition(
    previous: float,
    current: float,
    tolerance: float,
) -> HistoryTransition:
    """Classify one pair with ADR-159's pair-relative near-zero guard."""

    if previous == 0 and current == 0:
        return "stable"
    pair_scale = max(abs(previous), abs(current))
    if abs(previous) <= tolerance * pair_scale:
        return "unknown"
    relative_change = (current - previous) / abs(previous)
    if abs(relative_change) <= tolerance:
        return "stable"
    return "increasing" if relative_change > tolerance else "decreasing"


def select_history_candidates(
    context: MetricLensExecutionContext,
    candidates: tuple[MetricHistoryCandidate, ...],
) -> tuple[MetricHistoryCandidate, ...]:
    """Filter and order History by event time, independent of persistence order."""

    eligible = [
        candidate
        for candidate in candidates
        if candidate.lens_run_id != context.identity.lens_run_id
        and candidate.status in {"completed", "partial"}
        and candidate.data_quality in {"good", "degraded"}
        and candidate.mean is not None
        and candidate.analysis_window.to < context.analysis_window.to
    ]
    ordered = sorted(
        eligible,
        key=lambda candidate: (
            candidate.analysis_window.to,
            candidate.analysis_window.from_,
            str(candidate.lens_run_id),
        ),
    )
    selected = ordered[-context.history_policy.lookback_runs :]
    return tuple(selected)


def analyze_history(
    context: MetricLensExecutionContext,
    candidates: tuple[MetricHistoryCandidate, ...],
    current_evidence: MetricCurrentEvidence,
) -> tuple[MetricHistory, MetricHistoryEvidence] | None:
    """Produce accepted History sections, or normal omission when none are eligible."""

    selected = select_history_candidates(context, candidates)
    if not selected:
        return None
    assert all(candidate.mean is not None for candidate in selected)
    means = [candidate.mean for candidate in selected]
    means.append(current_evidence.mean)
    transitions = tuple(
        classify_transition(previous, current, context.history_policy.level_change_tolerance)
        for previous, current in zip(means, means[1:], strict=False)
    )
    return _history_sections(
        run_ids=tuple(candidate.lens_run_id for candidate in selected),
        transitions=transitions,
        policy=context.history_policy,
    )


def _history_sections(
    *,
    run_ids: tuple[UUID, ...],
    transitions: tuple[HistoryTransition, ...],
    policy: MetricHistoryPolicy,
) -> tuple[MetricHistory, MetricHistoryEvidence]:
    counts = Counter(transitions)
    classifiable = tuple(transition for transition in transitions if transition != "unknown")
    classifiable_count = len(classifiable)
    direction = _direction(classifiable, classifiable_count)
    pattern, direction_changes = _pattern(classifiable)
    evidence = MetricHistoryEvidence(
        level_change_tolerance=policy.level_change_tolerance,
        classifiable_transitions=classifiable_count,
        unknown_transitions=counts["unknown"],
        increasing_transitions=counts["increasing"],
        decreasing_transitions=counts["decreasing"],
        stable_transitions=counts["stable"],
        direction_changes=direction_changes,
    )
    return MetricHistory(direction=direction, pattern=pattern, run_ids=run_ids), evidence


def _direction(
    classifiable: tuple[HistoryTransition, ...],
    count: int,
) -> Literal["increasing", "decreasing", "stable", "mixed", "unknown"]:
    if count == 0:
        return "unknown"
    counts = Counter(classifiable)
    for value in ("increasing", "decreasing", "stable"):
        if counts[value] / count >= 0.70:
            return value
    return "mixed"


def _pattern(
    classifiable: tuple[HistoryTransition, ...],
) -> tuple[Literal["sustained", "reversing", "oscillating", "mixed", "unknown"], int]:
    directional = tuple(value for value in classifiable if value != "stable")
    runs: list[HistoryTransition] = []
    for value in directional:
        if not runs or runs[-1] != value:
            runs.append(value)
    direction_changes = max(0, len(runs) - 1)
    if len(classifiable) < 2:
        return "unknown", direction_changes
    if len(runs) >= 3:
        return "oscillating", direction_changes
    if len(runs) == 2:
        return "reversing", direction_changes
    counts = Counter(classifiable)
    if any(counts[value] / len(classifiable) >= 0.70 for value in counts):
        return "sustained", direction_changes
    return "mixed", direction_changes
