"""Framework-neutral aggregation for the final balanced live matrix."""

from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Any

FRAMEWORKS = ("pydantic_ai", "langchain")

CAPACITY_FAILURE_MARKERS = (
    "429",
    "insufficient_quota",
    "quota",
    "capacity",
    "upstream",
    "provider unavailable",
    "provider_unavailable",
    "infrastructure",
    "routing",
)


def is_capacity_failure(outcome: dict[str, Any]) -> bool:
    """Classify only provider/capacity failures, not model schema violations."""

    if "runtime_error" not in outcome:
        return False
    text = str(outcome.get("runtime_error_detail", "")).lower()
    return any(marker in text for marker in CAPACITY_FAILURE_MARKERS)


def preflight_allows_matrix(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """The full matrix may start unless either preflight hit capacity infrastructure."""

    blockers: list[str] = []
    outcomes = report.get("outcomes", {})
    for framework in FRAMEWORKS:
        framework_cases = outcomes.get(framework, {})
        simple_runs = framework_cases.get("simple_evidence", [])
        if not simple_runs:
            blockers.append(f"{framework}: missing preflight outcome")
            continue
        outcome = simple_runs[0]
        if is_capacity_failure(outcome):
            blockers.append(
                f"{framework}: {outcome.get('runtime_error')} "
                f"{outcome.get('runtime_error_detail', '')}"
            )
    return not blockers, blockers


def _framework_runs(report: dict[str, Any], framework: str) -> list[dict[str, Any]]:
    return [run for runs in report.get("outcomes", {}).get(framework, {}).values() for run in runs]


def _summary_for_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [run for run in runs if "runtime_error" not in run]
    attempts = [int(run["behavioral_observations"]["tool_attempt_count"]) for run in completed]

    def hard(key: str) -> int:
        return sum(bool(run["hard_correctness"].get(key)) for run in completed)

    provider_failures = sum(is_capacity_failure(run) for run in runs)
    runtime_failures = sum("runtime_error" in run for run in runs) - provider_failures
    trace_statuses = Counter(
        trace["status"] for run in completed for trace in run.get("tool_attempts", [])
    )
    failure_or_timeout_runs = [
        run
        for run in completed
        if any(trace["status"] in {"failed", "timeout"} for trace in run.get("tool_attempts", []))
    ]
    return {
        "recorded_outcomes": len(runs),
        "completed_outcomes": len(completed),
        "structured_output_valid": hard("structured_output_valid"),
        "evidence_refs_valid": hard("evidence_refs_valid"),
        "contract_correct": sum(bool(run.get("contract_correct")) for run in completed),
        "semantic_success": sum(bool(run.get("semantic_quality_passed")) for run in completed),
        "budget_violations": sum(
            not bool(run["hard_correctness"].get("budget_compliant")) for run in completed
        ),
        "unknown_tool_calls": sum(
            not bool(run["hard_correctness"].get("known_tools_only")) for run in completed
        ),
        "scope_violations": sum(
            not bool(run["hard_correctness"].get("scope_compliant")) for run in completed
        ),
        "framework_runtime_failures": runtime_failures,
        "provider_failures": provider_failures,
        "total_optional_tool_attempts": sum(attempts),
        "mean_optional_tool_attempts": mean(attempts) if attempts else None,
        "median_optional_tool_attempts": median(attempts) if attempts else None,
        "repeated_tool_call_count": sum(
            int(run["behavioral_observations"]["repeated_tool_calls"]) for run in completed
        ),
        "apparently_unnecessary_tool_call_count": sum(
            int(run["behavioral_observations"]["apparently_unnecessary_tool_calls"])
            for run in completed
        ),
        "failure_timeout_attempt_counts": {
            "failed": trace_statuses["failed"],
            "timeout": trace_statuses["timeout"],
        },
        "failure_timeout_continuation_success": {
            "eligible_runs": len(failure_or_timeout_runs),
            "contract_correct_runs": sum(
                bool(run.get("contract_correct")) for run in failure_or_timeout_runs
            ),
        },
    }


def summarize_matrix(report: dict[str, Any]) -> dict[str, Any]:
    """Return total and per-fixture observations without inferring significance."""

    repetitions = int(report.get("repetitions_per_framework_per_case", 0))
    selected_cases = list(report.get("selected_cases", []))
    expected_per_framework = len(selected_cases) * repetitions
    framework_summaries = {
        framework: _summary_for_runs(_framework_runs(report, framework)) for framework in FRAMEWORKS
    }
    per_fixture: dict[str, dict[str, Any]] = {}
    for case in selected_cases:
        per_fixture[case] = {}
        for framework in FRAMEWORKS:
            runs = report.get("outcomes", {}).get(framework, {}).get(case, [])
            completed = [run for run in runs if "runtime_error" not in run]
            importances = [
                run["output"]["overall_importance"] for run in completed if "output" in run
            ]
            per_fixture[case][framework] = {
                "summary": _summary_for_runs(runs),
                "overall_importance_values": importances,
                "overall_importance_consistent": len(set(importances)) <= 1 and bool(importances),
            }

    all_runs = [run for framework in FRAMEWORKS for run in _framework_runs(report, framework)]
    truncated = any(
        "truncat" in str(run.get("runtime_error_detail", "")).lower() for run in all_runs
    )
    capacity_failures = any(is_capacity_failure(run) for run in all_runs)
    matrix_valid = (
        not truncated
        and not capacity_failures
        and all(
            framework_summaries[framework]["recorded_outcomes"] == expected_per_framework
            for framework in FRAMEWORKS
        )
    )
    return {
        "matrix_valid_for_framework_selection": matrix_valid,
        "invalidity_reasons": [
            *(["output truncation"] if truncated else []),
            *(["provider or capacity failure"] if capacity_failures else []),
            *(
                ["asymmetric or incomplete outcome count"]
                if any(
                    framework_summaries[framework]["recorded_outcomes"] != expected_per_framework
                    for framework in FRAMEWORKS
                )
                else []
            ),
        ],
        "expected_outcomes_per_framework": expected_per_framework,
        "frameworks": framework_summaries,
        "per_fixture": per_fixture,
    }
