# Agent Framework Evaluation Experiment

This isolated experiment compares PydanticAI and LangChain for the bounded Alert
Analysis Agent, using one fixed model configuration for both adapters. It is not
production application code and did not select a production framework on its own.

The Alert spike conclusion remains **CLOSE / INCONCLUSIVE**. The subsequent
Observation Reasoning / RAG spike also remained experimentally inconclusive.
The separate human architecture tie-break selected PydanticAI for the MVP;
see [`framework_decision.md`](framework_decision.md) and ADR-152. That decision
does not reinterpret either experiment as a PydanticAI benchmark victory.

## Scope and guardrails

- `domain/`, `tools/`, `fixtures/`, and `evaluation/` are framework-neutral.
- The only framework imports are under `agents/pydantic_ai/` and
  `agents/langchain/`.
- Both adapters receive one immutable `AlertAnalysisInput`, expose only the
  same three optional analytical tools, and return the same
  `AlertAnalysisAgentOutput` Pydantic model.
- `AnalyticalToolExecutor` owns the authoritative ten-attempt budget. It
  reserves an attempt before execution, traces success/failed/timeout/
  not_applicable outcomes, permits repeats, and blocks an eleventh request.
- The three deterministic tools use supplied Alert Lens data only. There is no
  provider fetch, metrics, logs, RAG, or scope expansion.
- Expected failure and timeout states are `ToolExecutionResult` values, not
  framework-level errors. A framework adapter only converts an over-budget
  request to a small `blocked` observation after the domain has rejected it.

The input excludes the zero-current-record case because the accepted Alerts
Pipeline bypasses this agent there.

## Experiment configuration

Both live adapters are configured identically:

| Setting | Value |
| --- | --- |
| Provider/API | OpenRouter Chat Completions API |
| Model | `openai/gpt-5.6-terra` |
| Reasoning effort | `medium` |
| Temperature | unset |
| Parallel tool calls | disabled |
| Maximum output tokens | 2,000 initially |
| Client/framework retries | disabled (`0`) |
| OpenRouter provider routing | OpenAI locked where supported; provider fallbacks disabled |
| Model request timeout | 60 seconds |
| Analytical tool timeout | 1 second |

OpenRouter's documented OpenAI-compatible endpoint is Chat Completions, so this
provider variation cannot use the previously configured Responses API. Both
adapters use `https://openrouter.ai/api/v1`, the same model slug, and an
explicit `provider` body with `allow_fallbacks: false`. PydanticAI uses an explicit
`openai.AsyncOpenAI(max_retries=0, timeout=60)` client supplied to
`OpenAIProvider`, plus `Agent(retries=0)`. LangChain uses
`ChatOpenAI(use_responses_api=False, max_retries=0, timeout=60)` and has no
retry middleware installed. `tests/test_adapter_contracts.py` verifies the
effective client/model configuration and the Chat Completions payload.

These are experiment configuration values only. They are not a production-model
choice or an architecture decision.

The duration tool deliberately uses Python
`statistics.quantiles(..., method="inclusive")`. This is an experiment-local
convention, not a production architecture decision. Its fixture has seven
durations of 10 and one duration of 100, which remains an outlier across common
reasonable quartile conventions. Before production Alert tooling reuses this
code, exact quartile interpolation remains a decision to make.

## Run

From this directory:

```bash
uv sync --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

For a live comparison, set `OPENROUTER_KEY` in your local environment and run:

```bash
PYTHONPATH=src uv run python -m agent_framework_experiment.evaluation.live_runner \
  --mode preflight --output results/final-openrouter-terra-capacity-preflight.json
```

Only when both one-request preflight outcomes are served without a capacity,
quota, routing, or provider-infrastructure failure, run the complete matrix:

```bash
PYTHONPATH=src uv run python -m agent_framework_experiment.evaluation.live_runner \
  --mode matrix --repetitions 3 \
  --output results/final-openrouter-terra-live-results.json
```

The matrix runs six semantic fixtures three times per framework (36 requests)
and preserves every individual outcome. It records hard contract correctness,
behavioral tool-use observations, semantic-quality checks, evidence references,
the common trace, and runtime errors. It intentionally does not compare finding
prose verbatim or require optional tools to be called.

If a run is truncated at 2,000 output tokens, mark it invalid in the results.
Raise `max_output_tokens` in `ExperimentSettings` equally for both variants,
rerun the affected comparison, and record the changed shared configuration.

The architecture leaves the exact serialized `evidence_refs` grammar open. For
this experiment only, `domain/evidence_catalog.py` generates an explicit catalog
from each immutable fixture input, such as `activity.current_count` and
`alerts.A-REC.occurrence_count`. A successful optional tool adds its own fixed
IDs (for example, `tool.duration_outlier.upper_bound`) to the available catalog.
Failed, timeout, and not-applicable calls add no successful analytical IDs. The
catalog is an experiment-local evaluator aid, not a production result contract,
schema, or architecture decision.

## Layout

```text
src/agent_framework_experiment/
  domain/                 immutable contracts, instructions, budget
  tools/                  deterministic analytical functions and executor
  fixtures/               identical nonzero Alert Lens cases
  agents/pydantic_ai/     PydanticAI binding only
  agents/langchain/       LangChain binding only
  evaluation/             framework-neutral evaluator, aggregation, and runner
tests/                    deterministic semantics and adapter configuration
evaluation_report.md      final evidence report
```

`evaluation-report.md` and prior result files are historical evidence only. They
are retained for traceability and are not valid framework-selection matrices.
