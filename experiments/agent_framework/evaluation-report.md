# Alert Analysis Agent Framework Evaluation Report

Status: **implementation evidence prepared; first live comparison invalid**.
No framework is selected by this report until the configured live runs exist.

## OpenRouter DeepSeek V4 Pro attempts — 2026-08-24

The model and provider variation was explicitly configured as
`deepseek/deepseek-v4-pro`, `high` reasoning effort, OpenRouter Chat
Completions, 2,000 maximum output tokens, a 60-second request timeout, no
client/framework retries, and `provider.allow_fallbacks=false`.

The initial matrix completed all 36 requests but showed a shared
evidence-reference-format weakness. A single clarified, experiment-local
evidence-reference instruction was then applied identically to both adapters
and the full matrix was rerun. That second matrix is invalid for framework
selection because OpenRouter rate-limited the selected upstream capacity:

| Framework | Valid checks passed | Invalid observations | Invalid cause |
| --- | ---: | ---: | --- |
| PydanticAI | 4 / 18 | 14 / 18 | 10 structured-output validation failures with framework retries correctly disabled; 4 model HTTP failures |
| LangChain | 5 / 18 | 10 / 18 | OpenRouter HTTP 429 upstream-provider rate limits |

The local files `results/openrouter-deepseek-v4-pro-high-live-results.json` and
`results/openrouter-deepseek-v4-pro-high-evidence-policy-v2.json` retain all
individual outcomes. Do not compare the pass totals or score frameworks from
this partial/rate-limited run. A later run needs stable available capacity and
the same complete matrix for both variants.

The DeepSeek model is an experiment candidate only; it does not select a future
production model or modify the architecture package.

## Invalid OpenAI Responses attempt — 2026-08-24

The configured 36-request matrix was started after loading the local API key:
six selected semantic fixtures × three repetitions × two frameworks. All runs
were invalid because the provider returned HTTP 429 with
`insufficient_quota` for `gpt-5.6-terra`:

| Framework | Invalid runs | Framework-visible error |
| --- | ---: | --- |
| PydanticAI | 18 / 18 | `ModelHTTPError` carrying the provider 429 response |
| LangChain | 18 / 18 | `OpenAIRateLimitError` carrying the provider 429 response |

The individual results are retained locally in `results/live-results.json`.
This is neither a semantic run nor framework evidence; replenish/enable the
relevant API project quota and rerun the full balanced matrix before scoring.

## Run record

| Item | Required record |
| --- | --- |
| Current shared configuration | OpenRouter Chat Completions API, `deepseek/deepseek-v4-pro`, high reasoning, temperature unset, parallel calls disabled, 2,000 output tokens, 60 s model timeout, 1 s tool timeout, client/framework retries 0, OpenRouter provider fallback disabled |
| Live repetitions | Three per selected semantic fixture per framework |
| Individual outcomes | `results/live-results.json` (not committed if it contains sensitive operational data) |
| Truncation | Record invalid run; increase token limit equally and rerun |
| Comparison rule | No exact natural-language equality requirement; evaluate contracts, evidence, tools, budget, failures, and semantic success |

## Implementation evidence before live runs

| Topic | Concrete evidence |
| --- | --- |
| Bounded attempts | `domain/budget.py` reserves one of ten attempts before execution; `tools/executor.py` records it and blocks attempt 11. |
| Normal failure states | `tools/executor.py` converts controlled exceptions and timeout into shared `ToolExecutionResult` values and records a trace. |
| Trace | `ToolAttemptTrace` records order, tool name, status, and latency. |
| Identical tools | Both adapters expose `recurrence_concentration`, `duration_outlier`, and `reference_pattern_analysis`, all delegated to `AnalyticalToolExecutor`. |
| Effective retries | PydanticAI builds `AsyncOpenAI(max_retries=0)` plus `Agent(retries=0)`; LangChain builds `ChatOpenAI(max_retries=0)` with no retry middleware. Both send OpenRouter `allow_fallbacks: false`; tests inspect both. |
| Typed output | Both adapters require `AlertAnalysisAgentOutput`; the production `AlertAnalysisResult` builder remains out of scope. |
| Scripted parity | `tests/test_adapter_contracts.py` compares output plus invocation order/name/status across adapters; latency remains observational. |

## Weighted scorecard

Score each category from 1 (poor) to 5 (excellent) after reviewing the
individual live outcomes. Weighted result is `weight × score / 5`.

| Category | Weight | PydanticAI score | LangChain score | Objective observations and implementation evidence |
| --- | ---: | ---: | ---: | --- |
| Bounded-agent semantics | 25% | Pending | Pending | Confirm traces, ten-attempt cutoff, no scope expansion, normal failures. |
| Development speed and simplicity | 20% | Pending | Pending | Count framework-specific LOC and note configuration/adapter complexity. |
| Tool handling and loop control | 15% | Pending | Pending | Inspect repeat calls, post-failure continuation, over-budget behavior, no parallel calls. |
| Testability | 15% | Pending | Pending | Assess scripted parity, controlled timeout/failure tests, and injection seams. |
| Structured contracts and typing | 10% | Pending | Pending | Verify shared Pydantic output and framework validation behavior. |
| Debugging and trajectory visibility | 10% | Pending | Pending | Compare trace visibility plus native framework trajectories. |
| Future Observation Reasoning / RAG suitability | 5% | Pending | Pending | Record only evidence from this spike; do not extrapolate a winner if inconclusive. |
| **Weighted total** | **100%** | **Pending** | **Pending** | Do not select a winner within normal run-to-run variation. |

## Required comparison observations

Fill these in using source counts and the three-repetition results.

| Observation | PydanticAI | LangChain |
| --- | --- | --- |
| Framework-specific lines of code | 105 lines in `agents/pydantic_ai/agent.py` | 100 lines in `agents/langchain/agent.py` |
| Special adapters/workarounds | Explicit OpenRouter-base-URL `AsyncOpenAI`/`OpenAIProvider` construction; PydanticAI `Agent(retries=0)` | Explicit OpenRouter-base-URL `ChatOpenAI(use_responses_api=False)` construction; `ToolStrategy` output binding |
| Ease of unit testing | Deterministic shared scripted trajectory and Chat Completions client configuration construction pass locally; live agent still needs API-backed proof | Deterministic shared scripted trajectory and Chat Completions payload construction pass locally; live agent still needs API-backed proof |
| Ease of inspecting tool trajectory | Common executor trace is identical; native PydanticAI trajectory must be assessed live | Common executor trace is identical; native LangGraph trajectory must be assessed live |
| Difficulty enforcing domain tool budget | Same: adapter delegates to `AnalyticalToolExecutor`; the domain blocks call 11 before tool execution | Same: adapter delegates to `AnalyticalToolExecutor`; the domain blocks call 11 before tool execution |
| Failure-handling behavior | Shared executor returns `failed`/`timeout`/`not_applicable` and adapter returns it to the model | Shared executor returns `failed`/`timeout`/`not_applicable` and adapter returns it to the model |

## Interpretation rule

If the score difference is within normal per-fixture/per-repetition variation,
report a close or inconclusive result. In that case, a separate Observation
Reasoning/RAG spike is required before choosing a production framework.
