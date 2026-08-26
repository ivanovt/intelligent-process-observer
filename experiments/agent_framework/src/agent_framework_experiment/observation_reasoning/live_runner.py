"""Balanced live runner for the Observation Reasoning framework spike."""

from __future__ import annotations

import argparse
import asyncio
import faulthandler
import logging
import os
import signal
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from agent_framework_experiment.observation_reasoning.agents.langchain import (
    LangChainReasoningAgent,
)
from agent_framework_experiment.observation_reasoning.agents.pydantic_ai import (
    PydanticAIReasoningAgent,
)
from agent_framework_experiment.observation_reasoning.domain import ReasoningSettings
from agent_framework_experiment.observation_reasoning.evaluation import evaluate
from agent_framework_experiment.observation_reasoning.fixtures import (
    LIVE_CASES,
    deterministic_retriever,
)
from agent_framework_experiment.observation_reasoning.retrieval import RetrievalExecutor
from agent_framework_experiment.shared.runtime import checkpoint_json, sanitize_error_detail


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "matrix"), default="matrix")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--diagnostic-log", type=Path)
    args = parser.parse_args()
    if not os.environ.get("OPENROUTER_KEY"):
        raise SystemExit("OPENROUTER_KEY is required; no request was made.")
    settings = ReasoningSettings()
    cases = LIVE_CASES[:1] if args.mode == "preflight" else LIVE_CASES
    repetitions = 1 if args.mode == "preflight" else args.repetitions
    output = args.output or Path(
        "results/observation-reasoning-capacity-preflight.json"
        if args.mode == "preflight"
        else "results/observation-reasoning-final-matrix.json"
    )
    diagnostic_log = args.diagnostic_log or output.with_suffix(".runner.log")
    diagnostic_log.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("observation_reasoning.live_runner")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(logging.FileHandler(diagnostic_log, encoding="utf-8"))
    logger.handlers[0].setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    fault_file = diagnostic_log.open("a", encoding="utf-8")
    faulthandler.enable(fault_file)
    logger.info("runner_started pid=%s mode=%s", os.getpid(), args.mode)

    def signal_handler(signum, _frame) -> None:
        logger.error("runner_received_signal signal=%s", signum)
        for handler in logger.handlers:
            handler.flush()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    report: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "mode": args.mode,
        "configuration": settings.model_dump(mode="json"),
        "selected_cases": [case.name for case in cases],
        "repetitions_per_framework_per_case": repetitions,
        "outcomes": {},
    }

    def checkpoint() -> None:
        checkpoint_json(output, report)
        logger.info("checkpoint_written output=%s", output)

    checkpoint()
    agents = {
        "pydantic_ai": PydanticAIReasoningAgent(settings),
        "langchain": LangChainReasoningAgent(settings),
    }
    for name in agents:
        report["outcomes"][name] = {case.name: [] for case in cases}
    for case in cases:
        for repetition in range(1, repetitions + 1):
            order = ("pydantic_ai", "langchain") if repetition % 2 else ("langchain", "pydantic_ai")
            for name in order:
                agent = agents[name]
                executor = RetrievalExecutor(
                    timeout_seconds=settings.retrieval_timeout_seconds,
                    retriever=deterministic_retriever,
                )
                started = perf_counter()
                logger.info(
                    "outcome_started framework=%s case=%s repetition=%s",
                    name,
                    case.name,
                    repetition,
                )
                try:
                    result = await agent.analyze(case.input_data, executor)
                    run = evaluate(case.input_data, result, executor)
                    run["execution_latency_ms"] = (perf_counter() - started) * 1_000
                    run["model_turns"] = 1 if not result.findings else 2
                except Exception as error:
                    logger.exception(
                        "outcome_failed framework=%s case=%s repetition=%s",
                        name,
                        case.name,
                        repetition,
                    )
                    run = {
                        "runtime_error": type(error).__name__,
                        "runtime_error_detail": sanitize_error_detail(str(error)),
                        "invalid_run": True,
                    }
                run["repetition"] = repetition
                report["outcomes"][name][case.name].append(run)
                checkpoint()
                logger.info(
                    "outcome_finished framework=%s case=%s repetition=%s",
                    name,
                    case.name,
                    repetition,
                )
    checkpoint()
    logger.info("runner_completed")
    fault_file.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
