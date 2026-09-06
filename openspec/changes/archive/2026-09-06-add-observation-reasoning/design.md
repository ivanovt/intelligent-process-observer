## Context

See `proposal.md` for motivation and `specs/observation-reasoning/spec.md` for required behavior.

The production backend already has strict immutable Metric and Alert analytical contracts, a deterministic Relationship evaluator with self-contained outputs, generic persistence envelopes for ObservationAnalysisResult, PydanticAI adapters behind framework-neutral agent ports, and a source-agnostic `BoundedRetrievalExecutor`. It does not have a top-level Observation workflow, a Reasoning domain model, a shared evidence-reference grammar, a concrete knowledge retriever, or production model composition.

The architecture fixes the semantic sequence and boundaries but deliberately leaves exact reasoning serialization, evidence and knowledge reference syntax, limitation ownership, production model/provider, and retrieval-sufficiency handling open. The user decisions captured by this change close those implementation choices without editing the architecture package: deterministic fine-grained evidence catalog and limitations, a three-stage process with up to three isolated model invocations, Metric-insufficient-as-unavailable behavior, candidate-knowledge semantics, fail-closed reasoning, current Metric/Alert-only scope, and configurable OpenRouter production composition.

The branch also contains the previously requested roadmap synchronization. It is unrelated to the production design and must not be treated as additional feature scope.

## Goals / Non-Goals

**Goals:**

- Make evidence-only finding formation and findings-before-retrieval mechanically enforceable.
- Reuse the accepted result contracts rather than define generic lossy Lens summaries.
- Give final findings stable resolvable references without modifying upstream result schemas.
- Make availability limitations complete, deterministic, and independent of model behavior.
- Reuse exactly one bounded retrieval executor per non-empty finding set and validate final knowledge provenance against its outcomes.
- Add one production model composition path that is simple by default and easy to switch through configuration.
- Keep deterministic execution and contracts testable with injected fakes and no network.

**Non-Goals:**

- Add Log result placeholders or implement the architecture's future upstream Log knowledge reuse.
- Select or implement a knowledge corpus, retriever, index, ingestion flow, permissions model, or citation grammar beyond opaque existing KnowledgeReference values.
- Implement strict JOIN, the zero-usable-results gate, persistence, ObservationRun lifecycle, HTTP error mapping, report generation, or scheduling.
- Build a generic multi-provider abstraction above OpenRouter, an agent graph framework, an eval framework, or persisted model/retrieval traces.
- Add retries that can hide or multiply domain model-request and retrieval budgets.

## Decisions

### 1. Add one `app.reasoning` domain/application capability

Create a package parallel to `app.metrics`, `app.alerts`, `app.relationships`, and `app.knowledge`. Keep strict contracts and ports in `contracts.py` and `ports.py`; isolate deterministic input validation/projection, evidence catalog construction, limitation projection, result building, and phase coordination into small focused modules only where their responsibilities warrant separation.

The package consumes native accepted Metric, Alert, Relationship, and Knowledge contracts. It must not re-declare shadow copies or accept arbitrary dictionaries as successful domain inputs. Persistence envelopes may serialize the final result later but remain outside the Reasoning domain validator.

Alternative considered: put reasoning inside `app.observations`. Rejected because the existing observations package owns definition/API behavior, while reasoning is a runtime analytical capability with its own contracts and future execution integration.

Alternative considered: start with one large service module. Rejected because evidence projection, phase policy, and final validation are independent deterministic boundaries that need direct tests, but avoid creating broader service/repository abstractions.

### 2. Use strict framework-neutral phase and result contracts

Define frozen strict Pydantic models for:

- Observation/ObservationRun identity;
- compact Observation and Lens semantic context;
- unavailable Lens metadata carrying the accepted structured runtime reason;
- deterministic limitation variants;
- structured evidence references and transient catalog entries;
- finding-invocation request and completion;
- frozen findings;
- hypothesis-invocation request and completion;
- knowledge-isolated overall-state request and completion;
- hypotheses and `ObservationAnalysisResult` 1.0;
- success/failure execution outcomes.

Use discriminated unions for result/failure variants and for source-specific usable inputs. Public classes and protocol methods receive concise behavior-focused docstrings. No contract imports PydanticAI or OpenRouter types.

The reasoning request admits only `CompletedSufficientMetricResult`, `PartialMetricResult`, `CompletedAlertAnalysisResult`, and `PartialAlertAnalysisResult` as usable results. Its semantic context admits only Metric and Alert Lens identities for this feature slice. The boundary rejects a context containing a Log Lens or any unsupported Lens type before applying the exact partition invariant, so usable Log evidence cannot be mislabeled as unavailable while Log integration is deferred.

Unavailable metadata reuses the accepted strict `StructuredReason` runtime contract: a required non-empty opaque `code`, optional `component`, and no extra or free-text diagnostic fields. It also carries a reasoning-owned `origin` discriminator. Caller-supplied failed/non-usable Metric and Alert metadata uses `origin=caller_unavailable`, preserves its exact producer code and component, and always projects to `missing_lens_evidence`; Reasoning does not introduce a closed reason-code enum. Only the deterministic input factory/projector may create `origin=completed_insufficient_metric`, requiring `code=insufficient_data` with no component and projecting to `insufficient_lens_evidence`. Reusing only this framework-neutral value contract does not bring persistence envelopes, repositories, or lifecycle behavior into the Reasoning validator.

The usable and unavailable collections must form an exact partition of the supported Metric and Alert Lens identities declared by the semantic context. The boundary rejects an empty usable set, correlation conflicts, duplicate type-local Lens identities, overlap, configured Lenses missing from both collections, Lens identities absent from the context, and duplicate Relationships before any model work.

Alternative considered: accept persistence `payload: dict` envelopes. Rejected because that would duplicate domain validation incompletely and allow malformed upstream artifacts into an LLM boundary.

Alternative considered: define a Reasoning-specific closed unavailable-reason vocabulary. Rejected because ADR-068 keeps the structured producer code extensible, and translating it would lose accepted upstream failure semantics. Alternative considered: admit Log Lenses as unavailable placeholders. Rejected because it could report usable Log evidence as missing and would silently approximate the deferred Log reasoning contract.

### 3. Build a transient catalog but persist structured evidence references

Use this final reference shape:

```yaml
source_type: metric_result | alert_result | relationship_evaluation
source_id: <lens-run UUID or relationship ID>
locator:
  - current_state
  - trend
  - direction
```

`locator` is a non-empty immutable sequence of non-empty string keys and non-negative integer indexes into the exact serialized validated source artifact. This avoids inventing a URI escaping grammar while retaining an unambiguous source and exact path. Resolution walks the immutable serialized artifact and rejects missing keys, invalid indexes, scalar traversal, and ambiguous source identity.

Catalog entries add a transient ID such as `evidence_0001`. IDs are assigned deterministically from supplied source order and fixed per-source projection order. The agent sees the full structured inputs plus entries that associate each transient ID with its structured reference. Phase one cites only transient IDs; the freeze boundary resolves and replaces them with structured references. The final result never stores transient catalog IDs.

Projection policy:

- Metric: admit leaves below `current_state` and `evidence.current`; each available reference comparison and paired reference evidence keyed by its array position; and leaves below `history` and `evidence.history` when present.
- Alert: admit each current `alerts[]` record as one concrete element; scalar leaves below deterministic activity/distribution/duration/provider-importance aggregates; each successful comparison as one element; each Lens-local finding as one element; and `overall_importance` as one element.
- Relationship: admit `applicability`, `state` when present, and each complete condition/expectation evidence item as one element.

Do not catalog identity, schema/status envelope, analysis windows by themselves, provenance, reasons, source references, configuration, unavailable metadata, or diagnostics. Alert record content remains part of the full accepted structured result and is treated as untrusted data in prompts; the catalog reference does not copy or promote its text into instructions.

Alternative considered: store `evidence_0001` in the final result. Rejected because ordinal identity is unstable outside the transient catalog. Alternative considered: define cross-domain URIs. Rejected because it would add escaping and per-domain grammar without improving resolution over a typed source plus path.

### 4. Derive the complete limitations collection before model work

Build limitations from one normalized availability view:

```text
origin=caller_unavailable          -> missing_lens_evidence
origin=completed_insufficient_metric -> insufficient_lens_evidence
partial usable Lens                -> partial_lens_analysis
```

Each limitation includes `lens_id`, `lens_type`, and only the partial reason's component when applicable. Order strictly by the semantic context's Lens order; the exact Lens-scope partition makes unmatched inputs invalid. Pass the immutable tuple to all three invocations and copy it into the final result. No agent completion contains a limitations field.

Alternative considered: let the model select limitations. Rejected by user decision because known evidence availability is a runtime fact; model selection could omit critical gaps and reduce replay determinism.

### 5. Coordinate a three-stage process with isolated model invocations under deterministic ownership

The application executor follows:

```text
validate correlated scope
  -> build evidence catalog
  -> derive limitations
  -> finding phase (no tools, exactly one model request)
  -> validate/resolve catalog IDs
  -> freeze exact findings
  -> hypothesis phase
       -> skip model work and use hypotheses=[] when findings=[]
       -> otherwise create exactly one BoundedRetrievalExecutor for the run
       -> 0..2 sequential retrieval calls
       -> return hypotheses only
  -> validate hypothesis references against frozen findings and returned knowledge
  -> overall-state phase (no retrieval, knowledge, hypotheses, or prior model history)
       -> receive Observation evidence + catalog + frozen findings + limitations
       -> return overall_state only
  -> build strict ObservationAnalysisResult 1.0
```

Use one framework-neutral `ObservationReasoningAgent` protocol with three explicit methods rather than a permissive combined completion. A fake can implement all methods; the production adapter uses the same configured model but constructs separate typed PydanticAI agents or equivalent invocations. The overall-state invocation occurs only after hypothesis reasoning succeeds but receives a freshly constructed knowledge-isolated request. It receives the full structured Observation evidence, deterministic catalog, frozen findings, and limitations, but no hypothesis completion, retrieved content or references, retrieval executor/ledger, or model history from the hypothesis invocation.

If finding formation returns no findings, hypothesis model work is skipped because the hypothesis contract cannot be satisfied without a finding anchor. The overall-state invocation still runs so the agent—not a deterministic classifier—owns the final assessment.

Alternative considered: one prompt with a `freeze_findings` tool. Rejected because it creates mutable tool-registration/state complexity, makes early retrieval attempts possible, and weakens the simple proof that finding formation had no knowledge channel. Alternative considered: let the retrieval-enabled hypothesis invocation also author overall state. Rejected because ADR-076 limits retrieved knowledge to hypotheses, and prompt instructions cannot prove that knowledge did not influence the assessment. Alternative considered: let finding formation also own final overall state. Rejected because the accepted reasoning sequence places overall assessment after optional hypothesis reasoning.

### 6. Reuse one bounded retrieval executor and add consumer-level refinement policy

Create exactly one `BoundedRetrievalExecutor` after non-empty findings are frozen, inject the production-ready `KnowledgeRetriever`, and retain that executor for the complete hypothesis invocation. The PydanticAI tool adapter translates model arguments into existing `KnowledgeRetrievalRequest` contracts and returns only typed outcomes.

The existing executor proves finding membership, two executed calls, sequential admission, structural refinement, cancellation-safe slot retention, and a metadata-only ledger. The Reasoning consumer adds only the semantics the foundation intentionally deferred:

- any returned item is candidate knowledge;
- returned references from either call are available for final validation;
- refinement is allowed only after execution one returned at least one item and requires a non-empty unresolved gap;
- after empty/failure/timeout, another attempt must be independent rather than marked refinement;
- failure/timeout is non-fatal and exposes no references;
- a rejected/model-policy-invalid call fails the reasoning phase instead of creating another executor or resetting budget.

The final builder compares exact KnowledgeReference values against the union of references from retrieved outcomes and permits only the subset actually cited by hypotheses. It does not persist the retrieval ledger or statements.

Alternative considered: copy the experiment's `success|insufficient|no_match` statuses. Rejected because the accepted foundation deliberately represents no-match as an empty retrieved batch and leaves usefulness to the consumer.

### 7. Fail closed at the Reasoning boundary

Return a strict success/failure union. Success contains the final ObservationAnalysisResult. Failure contains only one fixed code and component, including the distinct `overall_state_phase`. Normalize model/provider exceptions, timeouts, request-limit exhaustion, tool-policy violations, invalid invocation outputs, invalid references, and final build failures without exception or prompt leakage. Do not construct a partial ObservationAnalysisResult.

Retrieval `failed|timed_out|retrieved(items=[])` differs from Reasoning failure: it is a valid tool outcome from which the agent may complete with `hypotheses=[]`. Caller cancellation propagates unchanged. The later Observation execution change will map Reasoning failure to run lifecycle and HTTP behavior.

Alternative considered: preserve frozen findings after a later invocation failure as a partial result. Rejected by user decision because no architecture contract exists for a partial ObservationAnalysisResult and a fallback overall state would be fabricated.

### 8. Enforce model-request bounds outside prompts

Use application-observed request accounting around the injected PydanticAI model, following the existing Metrics adapter pattern:

- finding phase: exactly one model request;
- hypothesis phase: maximum three model requests (initial plus one continuation after each of two tool calls);
- overall-state phase: exactly one model request;
- framework tool/output retries: zero;
- a tool request in the final allowed model response terminates with policy failure and cannot trigger another response;
- at most one retrieval tool call is admitted per model response so the loop remains sequential.

Apply the configured 120-second default timeout and 12,288 default maximum completion tokens to every model request. Both are positive settings with no artificial range beyond positivity. A non-empty-finding run therefore permits at most five model requests; an empty-finding success uses one finding request plus one overall-state request. OpenRouter upstream routing/failover occurs inside one submitted request and does not alter application request accounting or retrieval state.

Alternative considered: rely on prompt instructions and PydanticAI defaults. Rejected because default retries or unobserved tool continuations can multiply requests and violate predictable cost/latency bounds.

### 9. Use native PydanticAI OpenRouter composition with one model default

Change the existing dependency declaration from `pydantic-ai-slim>=2,<3` to `pydantic-ai-slim[openrouter]>=2,<3` and update only the backend lockfile. This keeps the approved framework and adds its official OpenRouter integration; no second agent or routing framework is introduced.

Add private OpenRouter configuration/composition under `app.infrastructure.openrouter` and extend root settings with:

```text
OPENROUTER_API_KEY                         required at model composition, SecretStr
OBSERVATION_REASONING_MODEL                default openai/gpt-5.6-terra
OPENROUTER_REQUEST_TIMEOUT_SECONDS         default 120, positive
OBSERVATION_REASONING_MAX_OUTPUT_TOKENS    default 12288, positive integer
OPENROUTER_ALLOW_FALLBACKS                 default true
OPENROUTER_PROVIDER_ORDER                  default []
```

Keep the API key optional at general application-settings construction so unrelated APIs and tests can start without model configuration; fail safely when the Reasoning model resolver is actually requested. Parse the provider order as an ordered duplicate-free list of non-blank opaque provider slugs. When fallback is false, require exactly one provider and pass that order plus `allow_fallbacks=false`; when fallback is true, pass the optional order and allow OpenRouter routing/failover. Do not add presets, app attribution, provider-specific generation knobs, prompt caching, native web search, or a fallback model list.

Compose one `OpenRouterModel` with the configured model slug and provider. All three invocations use it through the injected-model Reasoning adapter. Natural-language prompts and serialization remain adapter-private, but tests assert the exact fields and tools visible to each invocation and the absence of hypothesis/retrieval data from overall-state determination.

Alternative considered: use OpenRouter only as an OpenAI-compatible base URL. Rejected because current PydanticAI provides a native OpenRouter model/provider and optional dependency group, which better expresses intent without extra custom client setup. Alternative considered: hard-code the model. Rejected because the user explicitly wants easy model experimentation.

### 10. Keep persistence and runtime integration for the execution feature

The executor returns an in-memory success/failure outcome. It does not open a database transaction, call the existing runtime repository, transition ObservationRun, detect strict JOIN, or generate a report. Tests may validate that a successful result can be wrapped by the existing `ObservationAnalysisResultInput`, but they must not add persistence behavior to this capability.

This matches the boundary already used by the Relationship evaluator and keeps the later `add-observation-execution` change responsible for the usable-results gate, correlation with stored artifacts, atomic persistence, terminal lifecycle, and HTTP error mapping.

## Risks / Trade-offs

- [Up to three isolated model invocations increase latency and token cost] -> Bound every invocation, skip hypothesis model work when findings are empty, use one model configuration, and prevent retries in exchange for mechanically enforced findings-before-knowledge and knowledge-isolated overall state.
- [Full structured results plus catalog metadata duplicate some prompt structure] -> Keep catalog entries reference-only and avoid copied evidence values; retain full results because ADR-064 requires them.
- [Array indexes in structured locators depend on the immutable serialized artifact] -> Persisted upstream artifacts are immutable and versioned; source identity plus exact path resolves against the artifact from the same run.
- [Provider-native Alert text can contain prompt injection] -> Serialize it strictly as untrusted data, keep invocation instructions separate, expose no tools during finding formation, and expose only the bounded retrieval tool during hypothesis formation.
- [A model switch may not support required structured output/tool behavior] -> Validate configuration shape early, fail closed at runtime, and document that configured models must support both; use deterministic adapter tests and a non-CI live smoke procedure.
- [OpenRouter provider failover may change model behavior or data path] -> Enable it by explicit default for availability, expose a strict single-provider pinning mode, and keep analytical validation invariant across providers.
- [No concrete retriever means production composition is incomplete today] -> Design and test against the accepted injected port as if ready; keep the separately requested retriever feature explicit and do not add an implicit stub/fallback corpus.
- [The hypothesis model may misuse candidate knowledge] -> Require exact reference membership and frozen finding linkage; unsupported explanations fail rather than becoming a partial result.
- [Fail-closed behavior discards valid frozen findings after a later failure] -> This is the selected MVP behavior and avoids defining an unapproved partial Observation result.
- [The OpenRouter optional extra changes the dependency graph] -> Keep the version range unchanged, update only the lockfile, and require explicit approval of these planning artifacts before implementation.

## Migration Plan

1. Update the PydanticAI dependency extra and backend lockfile.
2. Add strict Reasoning contracts, deterministic projection/catalog/limitation/building components, and fake-driven tests without wiring application startup.
3. Add the three-invocation PydanticAI adapter and model-request/isolation policy tests with injected test/function models.
4. Add OpenRouter settings, safe composition, `.env.example` documentation, and configuration tests; no real credential is committed.
5. Run focused checks and `make check`. A credentialed live smoke test may be run manually but is not required by normal CI.

Rollback removes the isolated Reasoning and OpenRouter modules and restores the prior dependency declaration/lockfile. There is no migration, persisted data rewrite, public API compatibility change, or external resource cleanup.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md` requires deterministic orchestration, full structured results without raw telemetry, findings-before-retrieval, bounded RAG, and a separate report stage. Decisions 2-8 enforce those boundaries.
- `docs/architecture/03_ADR_log.md`, ADR-050 through ADR-055 and ADR-064 through ADR-084 define role separation, degraded evidence, result semantics, finding/hypothesis grounding, retrieval budget, and overall-state ownership. Decisions 4-8 make them mechanical.
- `docs/architecture/03_ADR_log.md`, ADR-151 remains future-facing because Log integration is explicitly excluded; ADR-152 requires PydanticAI behind framework-neutral contracts, implemented by Decisions 2 and 9.
- `docs/architecture/04_pipeline_and_agent_concepts.md` keeps deterministic components, agents, and tools distinct; Decisions 1, 5, and 6 preserve that separation.
- `docs/architecture/05_relationship_evaluator_concept.md` and the accepted Relationship contract make evaluations self-contained downstream evidence; Decision 3 catalogs them without reconstructing definitions.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` defines the input/result shape and keeps persistence as a separate boundary; Decisions 2 and 10 conform.
- `docs/architecture/07_observation_reasoning_agent.md` and `08_observation_analysis_result_contract.md` are realized by the three-invocation executor and strict builder without adding excluded taxonomy or report behavior.
- `docs/architecture/10_open_decisions_and_backlog.md`, sections 5 and 9 list the exact choices resolved here through user clarification. Broader Observation-level history, concrete retriever/corpus, permissions, indexing, and retrieval operations remain open or separately scoped.
