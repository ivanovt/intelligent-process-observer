## Context

See `proposal.md` for the traced failures and motivation. The domain contracts already require sequential Metric tool use, optional bounded retrieval, exact hypothesis provenance, and a valid empty hypothesis collection when no knowledge is available. The current adapters enforce those rules deterministically, but their short system prompts do not explain the interaction protocol in enough detail and their tool-enabled model requests do not ask OpenRouter to disable parallel tool calls.

PydanticAI 2.x exposes the cross-provider `parallel_tool_calls` model setting and documents OpenRouter support. That setting can reduce invalid model behavior, but routed providers remain probabilistic and may ignore or reject unsupported request features. Application-owned policy therefore remains the final authority.

## Goals / Non-Goals

**Goals:**

- Align Metric and hypothesis model guidance with the already accepted domain-owned interaction rules.
- Request sequential provider tool behavior only for invocations that expose function tools.
- Keep policy enforcement, grounding validation, budgets, and result mapping deterministic and unchanged.
- Make the two real traced failure modes reproducible through focused fake-model tests and verifiable through an opt-in development smoke procedure.

**Non-Goals:**

- Do not make LLM compliance a correctness boundary or relax rejection of invalid responses.
- Do not introduce retries, repair requests, automatic hypothesis filtering, forced retrieval, or a real knowledge backend.
- Do not change prompts for Alert, finding, overall-state, or report invocations beyond any mechanical reuse required by tests.
- Do not add prompt configuration/version selection, evaluation infrastructure, new model settings, public diagnostics, UI behavior, dependencies, or database state.

## Decisions

### 1. Keep explicit role guidance as adapter-owned constants

The Metric and hypothesis adapters will each use one readable module-level instruction constant. The Metric adapter will additionally use a fixed mapping of tool name to capability-specific description. Constants remain private infrastructure details and are passed to PydanticAI during agent construction; they are not added to settings, domain contracts, APIs, or persistence.

The Metric guidance will describe immutable input scope, empty arguments, one tool call per response, wait-before-next behavior, single use per tool, the three-attempt budget, and strict final completion. Its tool descriptions will explain the analytical purpose of spike, oscillation, and stuck-signal analysis without exposing raw data or changing tool schemas.

The hypothesis guidance will distinguish frozen findings from knowledge-only context, explain independent versus refinement retrieval, and explicitly state that hypotheses require exact references made available to the invocation through direct retrieval or preserved upstream Lens knowledge annotations. It will direct the model to emit an empty tuple/list when neither source provides a reference, including when it elects not to retrieve and has no preserved upstream knowledge.

Alternative considered: dynamically append guidance as user content. Rejected because model-visible run input is untrusted structured data and must not own or weaken system behavior.

Alternative considered: make the full prose a domain contract. Rejected because the accepted architecture keeps exact prompt wording implementation-owned; the OpenSpec delta contracts the required guidance semantics, not punctuation or phrasing.

### 2. Apply `parallel_tool_calls=false` only to tool-enabled invocations

The adapters will derive request-local model settings from the existing timeout/token settings. A usable Metric invocation with registered tools and every hypothesis invocation will add `parallel_tool_calls: false`. Insufficient Metric, finding, and overall-state invocations will continue with their tool-free settings.

The setting will be supplied on every model request within the tool-enabled invocation, including continuations after a tool result. It does not change tool choice, request limits, token limits, timeouts, routing configuration, or domain attempt accounting.

Alternative considered: set the flag globally for every role. Rejected because tool-free invocations do not benefit and global application would obscure which interaction boundary requires the control.

Alternative considered: rely on prompt text alone. Rejected because the provider protocol offers a direct compatible steering signal and the observed Metric response used parallel calls despite a strict downstream policy.

### 3. Preserve deterministic rejection and fail-closed grounding

No wrapper, executor, builder, or failure mapping will be changed to accept invalid output. Parallel Metric calls and parallel retrieval calls remain rejected. Invented knowledge references remain a reasoning validation failure. The change aims to prevent avoidable invalid responses before those boundaries, not reinterpret them afterward.

In particular, the implementation will not silently drop an ungrounded hypothesis. Such filtering could hide model-contract violations and would conflict with the accepted fail-closed reasoning requirement. A compliant model instead returns no hypotheses when no exact direct or preserved upstream knowledge references are available.

Alternative considered: deterministically transform every ungrounded hypothesis into an empty collection. Rejected because it weakens auditability and changes accepted reasoning failure semantics.

Alternative considered: add one model repair retry. Rejected because Metric and reasoning request ceilings explicitly require zero framework validation retries.

### 4. Verify request construction and failure fallback with deterministic models

Focused unit tests will inspect the model request settings and model-visible system guidance without calling OpenRouter. Tests will cover:

- a usable Metric request carries non-parallel tool settings and all required sequential-use guidance;
- Metric tool descriptions remain distinct and capability-specific;
- an insufficient Metric request remains tool-free;
- a hypothesis request carries non-parallel tool settings and exact direct-or-upstream reference/empty-output guidance;
- finding and overall-state requests remain tool-free;
- scripted parallel-call responses still reach the existing rejection and type-specific result paths.

Tests should assert required semantic clauses or stable constants rather than snapshotting incidental whitespace or an entire serialized provider request.

An opt-in developer procedure will launch the existing Home DEV Observation with tracing enabled and inspect the correlated Metric and hypothesis artifacts. It will confirm that the configured target model emits sequential Metric calls and does not fabricate knowledge references when neither the production retriever nor an upstream Lens makes references available. This is manual evidence only: network/model variability must not enter `make check`.

## Risks / Trade-offs

- [A routed provider ignores `parallel_tool_calls=false`] → Keep all deterministic parallel-call rejection paths and regression tests unchanged.
- [Prompt refinements reduce but cannot guarantee model compliance] → Treat trace-backed manual testing as a model compatibility signal, while correctness remains enforced by typed validation and policy.
- [Longer prompts add small token and latency overhead] → Keep instructions concise, role-specific, and limited to the interaction rules that caused observed failures.
- [Tests become coupled to prose] → Assert stable required semantics and request settings rather than exact full-string snapshots.
- [Untrusted input attempts prompt injection] → Keep guidance in the system role and explicitly identify provider/retrieved content as data; retain immutable scope enforcement.
- [The current target model remains unreliable after steering] → Use the separate existing role-specific model setting for operator experiments; any default-model change or retry/evaluation policy requires another approved change.

## Migration Plan

1. Add failing focused tests for the observed parallel Metric call and ungrounded hypothesis patterns plus request-setting/guidance expectations.
2. Refine the two adapter-owned prompts and Metric tool descriptions.
3. Add request-local non-parallel tool settings to usable Metric and hypothesis invocations.
4. Run focused backend tests.
5. Run the documented opt-in Home DEV smoke test with agent tracing enabled and inspect correlated artifacts; do not record sensitive trace content in Git.
6. Run `make check` as the final local verification gate before implementation review, archive, and pull-request preparation.

Deployment requires only the normal backend restart. No data migration, API transition, or configuration update is required. Rollback is a code revert; existing deterministic enforcement remains valid before and after rollback.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md`: Metric tools remain sequential and bounded; hypotheses remain optional and knowledge-grounded; missing RAG explanation does not invalidate findings.
- `docs/architecture/04_pipeline_and_agent_concepts.md`: deterministic orchestration and tool policy remain outside agent autonomy.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: existing partial/failure outcomes remain unchanged.
- `docs/architecture/07_observation_reasoning_agent.md`: findings freeze before optional retrieval; valid no-knowledge output contains no hypotheses.
- `docs/architecture/03_ADR_log.md`: ADR-152 keeps PydanticAI infrastructure-only; ADR-169 permits a later approved prompt-refinement change while preserving OpenRouter composition; ADR-171 supplies private trace evidence for manual verification.

The design conforms by changing only infrastructure-owned steering and tests. It introduces no new architectural boundary or unresolved decision, so architecture documents remain read-only for this change.
