"""Evidence-safe scenarios for the bounded Observation synthesis evaluation."""

from __future__ import annotations

SYNTHESIS_EVALUATION_CASES: dict[str, dict[str, object]] = {
    "direct_connectivity_with_auxiliary_logging": {
        "objective": "Assess whether connected devices remained stable.",
        "lenses": (
            {
                "lens_id": "connected_devices",
                "type": "metric",
                "role": "direct_objective_evidence",
                "current": "The connected-device count remained stable.",
                "reference": "The count was consistent with the reference window.",
                "history": "Recent history also shows a sustained stable level.",
            },
            {
                "lens_id": "pod_logging",
                "type": "log",
                "role": "auxiliary_evidence",
                "current": "Pod logging activity spiked during the window.",
            },
        ),
        "relationship_evaluations": (),
        "expected": {
            "direct_and_auxiliary_are_separate": True,
            "direct_temporal_evidence_may_be_consolidated": True,
            "forbidden_cross_lens_claims": (
                "The logging spike caused the connectivity state.",
                "The logging spike confirms the connectivity state.",
                "The logging spike contradicts the connectivity state.",
            ),
        },
    },
    "conflicting_temporal_evidence": {
        "lens_id": "connected_devices",
        "current": "The current connected-device count is stable.",
        "reference": "The reference comparison is stable.",
        "history": "History contains a distinct intermittent decrease.",
        "expected": {
            "compatible_current_and_reference_may_be_consolidated": True,
            "distinct_history_conflict_must_remain_explicit": True,
        },
    },
    "symmetric_relative_change": {
        "current_mean": 2.28,
        "reference_mean": 1.04,
        "relative_level_change": 0.7456,
        "formula": (
            "2 * (current_mean - reference_mean) / (abs(current_mean) + abs(reference_mean))"
        ),
        "accepted_presentations": (
            "The symmetric relative change is approximately 0.746.",
            "The current mean is 2.28 and the reference mean is 1.04.",
        ),
        "forbidden_presentations": ("The current mean is 74.56% higher.",),
    },
    "stable_only_findings": {
        "findings": ("The directly relevant connected-device evidence remained stable.",),
        "limitations": (),
        "expected_overall_state": "no_significant_findings",
        "rule": "A descriptive stable finding does not force significance by count.",
    },
    "material_limitations_with_findings": {
        "findings": ("The directly relevant connected-device evidence remained stable.",),
        "limitations": (
            {
                "code": "missing_lens_evidence",
                "lens_id": "pod_logging",
                "meaning": "Auxiliary logging evidence was unavailable.",
            },
        ),
        "expected_overall_state": "uncertain",
        "rule": "Material evidence unavailability may leave the overall assessment uncertain.",
    },
    "forbidden_semantics": {
        "forbidden_presentations": (
            "The logging spike caused the connectivity state.",
            "This is a severe connectivity incident.",
            "We are highly confident that connectivity failed.",
            "Restart the pod to resolve the issue.",
            "The root cause is the pod logging spike.",
        ),
        "rule": (
            "Do not introduce causal, severity, confidence, recommendation, "
            "or root-cause semantics."
        ),
    },
}
