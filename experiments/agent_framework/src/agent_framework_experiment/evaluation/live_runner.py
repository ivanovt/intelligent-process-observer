"""Run selected semantic fixtures three times per framework and record each outcome."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from agent_framework_experiment.agents.langchain import LangChainAlertAnalysisAgent
from agent_framework_experiment.agents.pydantic_ai import PydanticAIAlertAnalysisAgent
from agent_framework_experiment.domain.contracts import AlertAnalysisInput, ExperimentSettings
from agent_framework_experiment.evaluation.evaluator import evaluate_live_result
from agent_framework_experiment.fixtures.cases import ALL_CASES, ExperimentCase
from agent_framework_experiment.shared.runtime import checkpoint_json, sanitize_error_detail


class LiveAgent(Protocol):
    async def analyze(self, input_data: AlertAnalysisInput): ...


SELECTED_LIVE_CASES = tuple(
    case for case in ALL_CASES if case.name not in {"optional_tool_failure", "budget_exhaustion"}
)


def _agents(settings: ExperimentSettings) -> dict[str, LiveAgent]:
    return {
        "pydantic_ai": PydanticAIAlertAnalysisAgent(settings),
        "langchain": LangChainAlertAnalysisAgent(settings),
    }


async def run_case(
    agent: LiveAgent,
    case: ExperimentCase,
    repetitions: int,
    *,
    on_outcome: Callable[[dict[str, object]], None] | None = None,
) -> list[dict[str, object]]:
    outcomes: list[dict[str, object]] = []
    for repetition in range(1, repetitions + 1):
        try:
            result = await agent.analyze(case.input_data)
            outcome = evaluate_live_result(case, result)
            outcome["repetition"] = repetition
        except Exception as error:  # The report must retain invalid/truncated run evidence too.
            outcome = {
                "case": case.name,
                "repetition": repetition,
                "runtime_error": type(error).__name__,
                "runtime_error_detail": sanitize_error_detail(str(error)),
                "invalid_run": True,
            }
        outcomes.append(outcome)
        if on_outcome:
            on_outcome(outcome)
    return outcomes


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "matrix"), default="matrix")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not os.environ.get("OPENROUTER_KEY"):
        raise SystemExit(
            "OPENROUTER_KEY is required for an OpenRouter comparison; no request was made."
        )

    settings = ExperimentSettings()
    output = args.output or Path(
        "results/final-openrouter-terra-capacity-preflight.json"
        if args.mode == "preflight"
        else "results/final-openrouter-terra-live-results.json"
    )
    selected_cases = (SELECTED_LIVE_CASES[0],) if args.mode == "preflight" else SELECTED_LIVE_CASES
    repetitions = 1 if args.mode == "preflight" else args.repetitions
    report: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "mode": args.mode,
        "configuration": settings.model_dump(mode="json"),
        "selected_cases": [case.name for case in selected_cases],
        "repetitions_per_framework_per_case": repetitions,
        "outcomes": {},
    }
    output.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint() -> None:
        checkpoint_json(output, report)

    checkpoint()
    for framework, agent in _agents(settings).items():
        report["outcomes"][framework] = {}
        checkpoint()
        for case in selected_cases:
            report["outcomes"][framework][case.name] = []

            def record_outcome(
                outcome: dict[str, object],
                framework_name: str = framework,
                case_name: str = case.name,
            ) -> None:
                report["outcomes"][framework_name][case_name].append(outcome)
                checkpoint()

            await run_case(agent, case, repetitions, on_outcome=record_outcome)
    checkpoint()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
