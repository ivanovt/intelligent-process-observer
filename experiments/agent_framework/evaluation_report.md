# Alert Analysis Agent Framework Evaluation Report

## 1. Experiment objective

This isolated engineering experiment compares **PydanticAI** and **LangChain**
for the bounded Alert Analysis Agent. It evaluates framework integration with
the same immutable input, deterministic tools, instructions, output model, and
fixed OpenRouter GPT-5.6 Terra configuration.

It does not compare models, select a production model, modify production code,
or establish a production evidence-reference grammar.

## 2. Architecture constraints

The experiment implements the accepted Alert architecture without changing it:

- the agent is Lens-local and descriptive; it cannot fetch provider data,
  inspect metrics or logs, use RAG, expand scope, diagnose root cause, or make
  recommendations;
- the agent returns only `findings` and `overall_importance`; the deterministic
  production builder remains the owner of `AlertAnalysisResult` assembly;
- the only optional analytical tools are recurrence concentration, duration
  outlier, and reference pattern analysis;
- zero to ten attempts are allowed, repeats are allowed, and each outcome
  (`success`, `failed`, `timeout`, `not_applicable`) consumes the shared budget;
- failed, timeout, and not-applicable optional results are normal outcomes and
  do not abort usable analysis;
- every finding reference must resolve within the same Alert analysis context.

The architecture deliberately leaves the canonical serialized evidence-reference
grammar, optional-tool derived-reference mapping, tool request serialization,
and production timeout values open. This experiment does not close those
decisions.

## 3. Shared framework-neutral implementation

`domain/`, `tools/`, `fixtures/`, and `evaluation/` contain no PydanticAI or
LangChain abstractions. Both thin adapters receive the same frozen
`AlertAnalysisInput`, expose the same three executor-backed tools, use the same
`AlertAnalysisAgentOutput`, and return the common `AgentRunResult` trace.

`AnalyticalToolExecutor` owns the authoritative `ToolBudget(limit=10)`, reserves
before tool execution, converts controlled exceptions and timeouts to normal
`ToolExecutionResult` values, and records invocation order, tool name, status,
and latency. An eleventh request is blocked by the domain before tool execution.

The duration implementation uses `statistics.quantiles(..., method="inclusive")`.
This is an experiment-local quartile convention. The duration fixture (seven
durations of 10 and one duration of 100) remains a high-side outlier under common
reasonable quartile methods. Production reuse still needs an explicit quartile
interpolation decision.

## 4. Deterministic and scripted framework evidence

The experiment suite passed with **17 tests**:

- deterministic tool fixtures cover recurrence, the robust duration outlier,
  insufficient-duration `not_applicable`, dominant and mixed reference patterns;
- controlled failure and controlled timeout tests prove continuation and trace
  recording without timing-sensitive ordinary tool tests;
- budget tests prove reservation-before-execution, attempt 10 allowed, attempt
  11 blocked, and repeated invocation allowed;
- scripted PydanticAI/LangChain trajectories have exact parity for output and
  trace order/name/status (latency remains observational);
- a second scripted parity test proves both adapters preserve failed, timeout,
  `not_applicable`, repeated calls, ten recorded attempts, and one blocked call;
- adapter-configuration tests inspect `AsyncOpenAI(max_retries=0)`,
  `Agent(retries=0)`, `ChatOpenAI(max_retries=0)`, no LangGraph retry policy,
  60-second request timeouts, disabled parallel calls, OpenAI provider order,
  disabled fallbacks, and the medium reasoning setting.

This is strong evidence of equivalent bounded mechanics because those mechanics
are deliberately owned by common domain code rather than a framework limit.

## 5. Historical exploratory and invalid runs

The following artifacts are retained for traceability only. They do not enter
the final scorecard or framework-selection evidence.

| Artifact / attempt | Status | Why it is not a valid selection matrix |
| --- | --- | --- |
| `results/live-results.json` | Invalid direct OpenAI GPT-5.6 Terra attempt | All live requests received provider HTTP 429 `insufficient_quota`. |
| `results/openrouter-terra-live-results.json` | Historical OpenRouter GPT-5.6 Terra attempt | The old evaluator combined optional tool expectations with hard correctness and used an implicit evidence-reference convention. |
| `results/openrouter-deepseek-v4-pro-high-live-results.json` | Exploratory | Different model configuration; it is outside this framework-only comparison. |
| `results/openrouter-deepseek-v4-pro-high-evidence-policy-v2.json` | Exploratory/invalid | Different model configuration plus rate-limit/validation disruption; it is outside this framework-only comparison. |

The historical runs revealed the evidence-reference-format weakness corrected
below. They are not model comparisons and do not support a framework ranking.

## 6. Final evidence-catalog methodology

The evaluator now builds an explicit **experiment-local evidence catalog** from
the actual immutable fixture content. Example base IDs include:

```text
activity.current_count
alerts.A-1.status
alerts.A-1.provider_importance
reference_occurrence_comparisons.A-R1.direction
```

They contain no values and use record identifiers rather than list indexes. A
successful tool exposes deterministic result IDs only then, for example:

```text
tool.recurrence_concentration.dominant_share
tool.duration_outlier.upper_bound
tool.reference_pattern_analysis.direction_counts
```

The identical shared agent instruction requires exact copying from the supplied
`available_evidence_ids`: no invented IDs, rewrites, appended values, indexing,
or synthesized paths. Successful tool responses include newly available IDs;
failed, timeout, and not-applicable outcomes expose none.

The catalog is an experiment measurement aid only. It is not the production
`AlertAnalysisResult` evidence-reference contract, a production schema, or an
architecture decision.

Deterministic catalog tests prove allowed base IDs are accepted; unknown and
value-appended IDs are rejected; tool IDs are unavailable before execution;
successful tool IDs are accepted after execution; and failed, timeout, and
not-applicable calls never expose successful analytical IDs. Both adapters use
the same canonical serialized input and catalog.

## 7. Corrected evaluation semantics

The evaluator records three separate dimensions rather than a single combined
pass flag.

### Hard framework correctness

These checks can make an individual live result incorrect: valid structured
output and controlled vocabulary; exact catalog membership for evidence refs;
known tools only; domain budget compliance; Lens scope compliance; normal
failure-result handling; no fabricated/unavailable evidence; no forbidden
reasoning; and an `overall_importance` satisfying the shared output contract.

### Tool-use behavioral observations

These are recorded but do not automatically invalidate a run: optional-tool
opportunities not used, arguably unnecessary calls, invocation count/order,
repeats, blocked calls, empty findings, and natural-language variation. The
architecture allows 0..10 optional calls and `findings=[]`.

### Semantic output quality

The evaluator checks that the output is descriptive and Lens-local, grounded in
available evidence, free of prohibited reasoning, and has contract-valid overall
importance. It does not require particular wording, finding IDs/order/count, or
a prescribed tool trajectory.

## 8. Final GPT-5.6 Terra comparison

### Fixed configuration

| Setting | Shared value |
| --- | --- |
| Provider/API | OpenRouter Chat Completions API |
| Model | `openai/gpt-5.6-terra` |
| Provider routing | `openai` order where supported; fallbacks disabled |
| Reasoning effort | medium |
| Temperature | unset |
| Parallel tool calls | disabled |
| Maximum output tokens | 2,000 |
| Provider/client retries | 0 |
| Framework retries | 0 |
| Model request timeout | 60 seconds |
| Analytical tool timeout | 1 second |

The PydanticAI/OpenAI client is explicitly `AsyncOpenAI(max_retries=0)` and the
agent is `Agent(retries=0)`. The LangChain client is explicitly
`ChatOpenAI(max_retries=0, use_responses_api=False)` with no retry policy on its
model or tools nodes. Both send `parallel_tool_calls=false` and the same
OpenRouter provider body.

### Capacity preflight

Non-scored `simple_evidence` preflight results are retained in
`results/final-openrouter-terra-capacity-preflight.json` and the corrected-runner
confirmation `results/final-openrouter-terra-capacity-preflight-attempt-2.json`.
Both PydanticAI and LangChain returned valid shared structured output without a
quota, HTTP 429, routing, capacity, provider-unavailability, or infrastructure
failure. The final matrix was therefore allowed to start.

### Matrix validity

`results/final-openrouter-terra-live-results.json` is the final coherent matrix:
six semantic fixtures × three repetitions × two frameworks = **36 requests**.
It used the fixed configuration above. It is valid for framework selection:

- 18 recorded outcomes per framework;
- no provider failures, runtime failures, truncation, or asymmetric cells;
- no retries or replacement of individual cells;
- no unknown tools, budget violations, or scope violations.

### Framework summaries

| Observation | PydanticAI | LangChain |
| --- | ---: | ---: |
| Valid structured outputs | 18 / 18 | 18 / 18 |
| Evidence-valid outputs | 18 / 18 | 17 / 18 |
| Contract-correct outputs | 18 / 18 | 17 / 18 |
| Semantic-success outputs | 18 / 18 | 17 / 18 |
| Budget / unknown-tool / scope violations | 0 / 0 / 0 | 0 / 0 / 0 |
| Framework runtime / provider failures | 0 / 0 | 0 / 0 |
| Optional tool attempts | 19 | 20 |
| Mean / median attempts per run | 1.06 / 1 | 1.11 / 1 |
| Repeated calls | 0 | 0 |
| Apparently unnecessary calls | 3 | 3 |
| Failed/timeout live attempts | 0 / 0 | 0 / 0 |
| Failure/timeout continuation | No eligible live fixture; deterministic tests pass | No eligible live fixture; deterministic tests pass |

The one LangChain evidence failure is in
`dominant_increased_reference_pattern`, repetition 1. The response cited
`reference_occurrence_comparisons.A-R-R1.direction` even though the exact
catalog ID was `reference_occurrence_comparisons.A-R1.direction`. The other
references, output structure, tool execution, and overall importance were
valid. This is a one-off model-generated identifier typo, not a demonstrated
framework behavior: both adapters received the same catalog and the remaining
35 outcomes met the evidence rule.

### Per-fixture observations

| Fixture | PydanticAI | LangChain |
| --- | --- | --- |
| `simple_evidence` | 3/3 contract-correct; all `high`; one not-applicable tool call each run | 3/3 contract-correct; all `high`; one not-applicable tool call each run |
| `recurrence_concentration` | 3/3; all `moderate`; 4 attempts total | 3/3; all `moderate`; 3 attempts total |
| `duration_outlier` | 3/3; all `moderate`; duration tool succeeded each run | 3/3; all `moderate`; duration tool succeeded each run |
| `insufficient_duration` | 3/3; all `low`; mixed valid optional trajectories | 3/3; all `low`; mixed valid optional trajectories |
| `dominant_increased_reference_pattern` | 3/3; all `high` | 2/3 evidence-valid; all `high`; the single catalog typo above |
| `mixed_reference_pattern` | 3/3; all `moderate` | 3/3; all `moderate` |

Overall importance was consistent across all three repetitions for every
fixture/framework pair. Differences in optional tool ordering and whether an
extra tool was used are behavioral observations, not semantic failures.

## 9. Implementation comparison

| Topic | PydanticAI | LangChain |
| --- | --- | --- |
| Framework-specific LOC | 121 in `agents/pydantic_ai/agent.py` | 117 in `agents/langchain/agent.py` |
| Main adapter pieces | `AsyncOpenAI`, `OpenAIProvider`, `OpenAIChatModel`, `Agent` | `ChatOpenAI`, `create_agent`, `@tool`, `ToolStrategy` |
| OpenRouter workaround | Explicit compatible OpenAI client/provider and provider preferences in model settings | Explicit `use_responses_api=False`, OpenRouter base URL, provider preferences in `extra_body` |
| Dependency/context injection | Executor passed directly into per-run tool closures | Executor captured in per-run decorated tool closures |
| Structured output | Direct `output_type=AlertAnalysisAgentOutput` | `ToolStrategy(AlertAnalysisAgentOutput)` |
| Scripted substitution | Shared `run_scripted_trajectory` with injected executor | Same shared scripted path with injected executor |
| Tool exposure | Three async functions delegate directly to executor | Three decorated async functions delegate directly to executor |
| Domain budget integration | No framework limit is trusted; executor blocks attempt 11 | Same |
| Debug/trajectory evidence | Common trace is retained; native messages are not persisted by this experiment | Common trace is retained; returned graph state is not persisted by this experiment |
| Failure ergonomics | Shared normal result returns avoid framework exceptions | Same shared normal result returns avoid framework exceptions |

The dependency footprint is intentionally isolated in this experiment’s own
`pyproject.toml`; the production backend declares none of PydanticAI, LangChain,
or `langchain-openai`. The common executor, catalog, fixtures, contracts, and
evaluation code are excluded from the framework-specific LOC comparison.

## 10. Weighted framework score

Scores are 1 (poor) to 5 (excellent). They express engineering integration
evidence, not prose quality. The small numerical difference below is not a
defensible production-selection separation.

| Criterion | Weight | PydanticAI | LangChain | Evidence |
| --- | ---: | ---: | ---: | --- |
| Bounded-agent semantics | 25% | 4 | 4 | Static shared budget and scripted parity prove both preserve all required mechanics; final matrix had 0 budget violations. |
| Development speed and simplicity | 20% | 4 | 4 | Adapter sizes are comparable (121 vs 117 LOC); each needs one OpenRouter compatibility configuration path. |
| Tool handling and loop control | 15% | 4 | 4 | Both expose only the same three executor-backed tools; final matrix had no unknown tools/repeats/budget issue, and scripted tests cover failure/timeout/blocked cases. |
| Testability | 15% | 4 | 4 | Both use the same injected executor and deterministic scripted trajectory; live behavior is independently recorded. |
| Structured contracts and typing | 10% | 5 | 4 | Both produced 18/18 structured outputs. PydanticAI’s direct output model binding is marginally simpler than LangChain’s `ToolStrategy`; the single catalog typo is treated as model variation, not a framework deduction. |
| Debugging and trajectory visibility | 10% | 3 | 3 | The common trace is equally complete. Neither adapter persists its richer native trajectory, so this spike does not prove a native debugging advantage. |
| Future Observation Reasoning / RAG suitability | 5% | 3 | 3 | Both have clean per-run context injection, bounded tools, and typed outputs. Alert evidence alone does not establish a RAG advantage. |
| **Weighted total** | **100%** | **79 / 100** | **77 / 100** | The two-point difference is implementation ergonomics, not a meaningful separation. |

Evidence types used above: static implementation evidence, deterministic/scripted
test evidence, and the final fixed GPT-5.6 Terra live matrix only. Historical
and exploratory artifacts do not contribute to any score.

## 11. Final framework experiment conclusion

**FINAL EXPERIMENT CONCLUSION: CLOSE / INCONCLUSIVE**

Both frameworks satisfy the bounded Alert Agent requirements under the same
valid live matrix. The small score difference is explained by direct structured
output binding versus `ToolStrategy`, while the decisive runtime semantics are
intentionally common domain behavior. The isolated evidence-reference typo in
one live response is not repeatable framework evidence. No production framework
should be selected from this Alert spike alone.

## 12. Contemporaneous next action

At the time this Alert-only report was completed, the next action was the
planned Observation Reasoning / RAG framework spike. It subsequently ran; the
current human decision is recorded in the next section and ADR-152.

## 13. Post-experiment human architecture decision

The Alert experiment conclusion above remains **CLOSE / INCONCLUSIVE**. It is
not retrospectively a PydanticAI victory. The subsequent Observation Reasoning /
RAG spike also remained experimentally inconclusive. Both experiments showed
that PydanticAI and LangChain can satisfy the required bounded-agent semantics
when the critical contracts and execution constraints remain framework-neutral.

After review of both completed spikes, the human architecture decision selected
PydanticAI for the MVP as a project-fit tie-break: the backend already uses
Pydantic for typed contracts, PydanticAI binds structured outputs directly to
Pydantic models, adapter implementation sizes were comparable, and LangChain's
broader orchestration abstraction showed no compensating benefit in the MVP
scenarios. Budgets, evidence validation, findings freeze, retrieval constraints,
and other critical runtime semantics remain domain-owned rather than
framework-owned.

LangChain remains a technically viable alternative. The decision does not select
a production model, provider, vector database, embedding model, RAG backend,
retrieval-ranking strategy, observability product, or production
evidence-reference grammar. See [`framework_decision.md`](framework_decision.md)
and ADR-152 for the authoritative decision record and the shared Reasoning/RAG
refinement follow-up.
