## Context

The production backend currently has no Log Analysis Agent, Observation Reasoning Agent, or knowledge-retrieval module. Existing Metric and Alert features place strict Pydantic contracts and deterministic execution policy in domain/application modules, while framework and provider concerns remain behind ports and infrastructure adapters.

The accepted architecture fixes finding grounding, findings-before-retrieval, a maximum of two calls, optional second-query refinement, traceable knowledge references, and non-fatal retrieval failure. It deliberately leaves the corpus, permissions, backend, indexing, ranking, citation grammar, result-size limit, and timeout value open. The framework experiment is informative but its `success/insufficient/no_match` convention is not a production decision.

## Goals / Non-Goals

**Goals:**

- Provide strict reusable contracts for future Observation- and Log-level retrieval consumers.
- Put frozen-finding admission, sequential two-call budgeting, refinement validation, failure normalization, and attempt recording under deterministic application ownership.
- Make a concrete retrieval backend replaceable through one narrow asynchronous port.
- Preserve returned knowledge as external, untrusted candidate context with opaque provenance.

**Non-Goals:**

- Decide whether retrieved knowledge is sufficient to form a hypothesis or annotation.
- Build either consuming agent or expose retrieval as a public API.
- Select or implement a corpus, ingestion pipeline, embedding model, vector store, hybrid search, reranker, permissions model, or production provider.
- Define canonical knowledge-reference URI syntax, persisted retrieval history, or runtime artifact changes.
- Reuse experiment code as production code.

## Decisions

### 1. Add a small `app.knowledge` capability

Create a top-level backend package parallel to `app.metrics`, `app.alerts`, and `app.relationships`, with focused contract, port, and executor modules. Knowledge retrieval is shared future functionality rather than ownership of either consuming agent, so placing it inside a future Log or Observation package would create the wrong dependency direction.

Alternative considered: put retrieval directly in the first consuming agent. Rejected because the approved foundation scope explicitly precedes both consumers and the architecture defines equivalent bounded retrieval needs in each.

### 2. Use strict frozen Pydantic contracts without framework types

Represent requests, references, retrieved items, outcomes, and ledger entries as strict immutable Pydantic models, following current backend contract practice. `KnowledgeReference` contains non-empty opaque `source_id` and `reference` strings. The foundation preserves these values exactly but assigns no URI grammar or resolution semantics.

Alternative considered: use PydanticAI tool/result objects as the contract. Rejected by ADR-152 because agent-framework types must not own domain contracts. Defining a canonical citation URI now is also rejected because that architectural decision remains open.

### 3. Model no-match as a successful empty retrieval

The port returns a validated batch of zero or more retrieved items. The executor maps it to `retrieved`; zero items means no match. `failed`, `timed_out`, and `rejected` remain distinct operational outcomes.

The foundation deliberately has no `insufficient` status. Usefulness and sufficiency depend on a future consumer's frozen finding and intended hypothesis or annotation. This avoids promoting the experiment-local rule that partially useful knowledge may refine a query but cannot ground a hypothesis.

Alternative considered: copy all experiment statuses. Rejected because ADR-152 explicitly leaves the partially-useful/insufficient boundary for a future consuming feature.

### 4. Bind one stateful executor to one immutable finding set

Construct one executor per future agent run with a non-empty immutable set of already-frozen finding IDs and an injected retriever. Requests must cite a non-empty subset of that set. The executor never receives Lens data, raw telemetry, Observation configuration, or source-provider queries, so it cannot expand observational scope.

The executor exposes immutable ledger snapshots but owns a small amount of run-local mutable state: the next ordinal, consumed slots, active-call flag, and prior executed-call metadata. This is the minimum state needed to enforce the architectural loop.

The foundation can isolate state between executor instances but cannot prove how a future consumer composes them. Each consuming-agent change must therefore create exactly one executor for one agent run and must not reset the architectural two-call budget by constructing replacements during that run.

Alternative considered: a stateless helper taking a caller-maintained attempt count. Rejected because it would allow consumers to bypass the fixed budget and grounding rules.

### 5. Keep type-specific subject grounding with the consumer

The shared executor validates only that each query cites a subset of the session's frozen finding IDs. It intentionally has no generic `subject` field and does not infer whether query text names a concrete observed object.

A future Log consumer must resolve and validate its architecture-required template, error code, component-specific message, or log terminology against Log evidence before constructing the shared request. Observation Reasoning may have a different knowledge-need projection. Executor admission is therefore a shared safety floor, not proof that either consumer's complete grounding contract has been met.

Alternative considered: define one generic knowledge-subject union in the foundation. Rejected because it would prematurely generalize Log-specific semantics and constrain the not-yet-designed Observation consumer.

### 6. Admit only sequential calls and one structurally valid refinement

At most two calls execute. An executed empty, failed, or timed-out call consumes a slot. Rejected requests do not. Concurrent calls on one executor are rejected because the second query is defined relative to the first call and deterministic ordering is required.

After request-contract validation, admission uses one first-match order: `over_budget`, then `concurrent`, then `unknown_finding`, then `invalid_refinement`. Budget is checked first so an exhausted session exposes no further scope-validation result; concurrency is checked next so overlapping work cannot observe or alter in-flight session semantics; shared finding grounding precedes refinement because refinement is meaningful only for an otherwise grounded request.

The executor assigns a monotonically increasing `submission_ordinal` to each submitted request and an `execution_ordinal` of 1 or 2 when retriever invocation begins. Ledger entries preserve those identities for requests that produce typed outcomes. Rejected submissions have no execution ordinal and cannot become refinement targets; caller cancellation may later leave an intentional gap because reserved ordinals are never reused.

Optional refinement metadata provides a non-empty unresolved gap. When admitted as execution 2, the executor links it implicitly to execution ordinal 1 and records that link; callers do not provide a ledger ordinal or choose another target. Execution 2 may instead be an independent grounded query with no refinement metadata. The executor validates structure, not semantic usefulness; refined or independent query wording remains the future consumer's responsibility.

Alternative considered: automatically rewrite the second query. Rejected because query rewriting and retrieval strategy remain open and belong behind future consumer/provider boundaries.

### 7. Keep acquisition behind one asynchronous port

Define an asynchronous retriever protocol that accepts the framework-neutral request and returns a validated batch. The executor catches `TimeoutError`, other non-cancellation exceptions, and invalid results and maps them to typed outcomes with fixed application-owned diagnostic codes: `retriever_timed_out`, `retriever_failed`, and `invalid_retriever_result`. It never copies exception types/messages, tracebacks, query text, returned document content, credentials, or provider details into outcomes or ledger entries. This change does not impose a timeout duration; a future composition root or adapter may enforce an approved value and surface `TimeoutError` through the port.

Caller task cancellation is different from a retriever timeout or failure. The executor does not catch cancellation as a typed retrieval outcome: it propagates unchanged, retains the execution slot consumed when the retriever invocation started, and releases the active-call guard in cancellation-safe cleanup. This prevents session corruption and budget reset without choosing broader Observation/Lens cancellation, retry, idempotency, or replay policy. Because no typed outcome exists, the cancelled invocation is absent from the public ledger and its reserved submission/execution ordinals are not reused.

Alternative considered: implement an in-memory or filesystem retriever as production behavior. Rejected because it would silently select a corpus and retrieval strategy. Tests will use deterministic fakes only.

Alternative considered: preserve a truncated raw exception string, following some existing analytical-tool diagnostics. Rejected because retrieval exceptions may contain sensitive queries, documents, credentials, or provider internals and no current consumer needs free-text diagnostics.

### 8. Keep attempts transient and separate from analytical artifacts

The application-owned ledger records every request that returns a typed retrieval outcome, including rejected requests, and identifies execution and slot consumption explicitly. Caller-cancelled invocations are excluded and may leave ordinal gaps.

The ledger is a minimal projection rather than a stored request or result. Its exact fields are submission ordinal, optional execution ordinal, supported finding IDs, optional refinement target fixed to execution 1, execution/slot flags, outcome discriminator, optional controlled rejection reason, optional fixed diagnostic code, and knowledge references for retrieved outcomes. It never stores query text, unresolved-gap text, retrieved statements, exception data, document content, credentials, or provider details. This keeps the attempt record useful for deterministic verification and future operational telemetry without making it a second knowledge-content channel.

This capability performs no persistence and does not create findings, hypotheses, annotations, Lens results, or Observation results.

Alternative considered: persist retrieval traces through runtime persistence now. Rejected because retention and retrieval observability storage remain open and no consuming runtime exists in this scope.

## Risks / Trade-offs

- [The foundation has no production source and therefore retrieves nothing by itself] → Make this explicit in proposal, specs, and tests; a separately approved provider/corpus change will implement the port.
- [Opaque references defer canonical citation validation] → Require non-empty provenance now and preserve it losslessly; add grammar and resolution only when the knowledge source is selected.
- [A stateful run-scoped executor can be accidentally reused across runs] → Require construction with a frozen finding set and document one executor per consumer run; tests verify budget isolation between instances.
- [A future consumer could construct multiple executors and reset the per-run budget] → Require every consuming-agent change to own exactly one executor per run and verify that composition invariant at integration time.
- [Shared finding admission could be mistaken for the complete Log grounding contract] → State that Log-specific knowledge-subject resolution remains consumer-owned and test that the foundation exposes no claim of subject validation.
- [Concurrent callers could race admission] → Implement admission around a run-local async synchronization boundary or equivalent atomic state transition and test overlapping calls deterministically.
- [One request can violate multiple admission rules] → Apply and test the fixed first-match order `over_budget`, `concurrent`, `unknown_finding`, `invalid_refinement`.
- [Rejected submissions can make ledger order diverge from executed-call order] → Record separate submission and execution ordinals and link refinement only to executed-call ordinal 1.
- [Caller cancellation can strand the active guard or accidentally reset the call budget] → Propagate cancellation, release active state in cleanup, retain the consumed slot, omit the incomplete ledger entry, and never reuse its ordinals.
- [Generic retrieved text may contain prompt injection or unsafe content] → Treat statements as untrusted data and never execute or promote them to evidence; consuming-agent prompting and permissions remain required future work.
- [Retriever exceptions can contain sensitive content] → Expose only fixed diagnostic codes and test with sentinel query, document, credential, and provider values.
- [The transient ledger can become a second sensitive-content channel] → Use the exact metadata-only projection and test that queries, unresolved gaps, and retrieved statements are absent.
- [No `insufficient` outcome pushes usefulness evaluation downstream] → This is intentional until a consuming feature defines the hypothesis/annotation validation boundary approved by ADR-152.

## Migration Plan

Add the isolated backend package and tests without wiring it into application startup or persistence. Rollback consists of removing that unreferenced package and its tests; there is no database, API, configuration, or data migration.

## Future Production Adapter

This section is a non-normative handoff for a separate future OpenSpec change. It adds no requirement or implementation task to the current foundation. Production retrieval will remain unavailable until that later change implements the retriever port and, where necessary, receives explicit approval for decisions that are still Open in the architecture package.

### Intended runtime placement

The future path is expected to preserve this boundary:

```text
future consuming agent
  -> run-scoped bounded retrieval executor from this change
  -> framework-neutral retriever port from this change
  -> future concrete retrieval adapter
  -> approved knowledge index/search service
```

The adapter will acquire external domain documentation for interpretation of already-frozen findings. Operational Metric, Alert, or Log data from the current Observation remains observational evidence and must not be silently ingested or treated as the external knowledge corpus.

### Decisions the adapter change must make

1. **Knowledge sources and governance**
   - Identify the approved MVP sources, such as controlled manuals, runbooks, component/error catalogs, internal documentation, or incident knowledge.
   - Define source ownership, supported formats, trust level, version identity, freshness expectations, and which source is authoritative when documents conflict.
   - Define removal, replacement, stale-document, and source-unavailability behavior.

2. **Ingestion and update flow**
   - Define how documents are loaded, parsed, normalized, sanitized, divided into retrievable units, enriched with metadata, indexed, refreshed, and deleted.
   - Define idempotency, duplicate handling, partial-ingestion failure, re-indexing, and consistency between indexed content and source versions.
   - Preserve enough metadata to trace every returned statement to the exact approved source and relevant document section or chunk.

3. **Permissions and retrieval scope**
   - Define which documents each future consumer/run may search and where access checks are enforced.
   - Prevent query construction, refinement, or adapter behavior from escaping the approved corpus or observational scope.
   - Decide whether the foundation request contract needs a separately approved scope extension; do not anticipate that extension in the current change.

4. **Retriever and index strategy**
   - Select the minimum sufficient MVP backend and determine whether retrieval is keyword, vector, or hybrid.
   - Define chunking/indexing, embedding if any, ranking/reranking, filtering, and query-rewriting behavior.
   - Keep backend-specific request, score, document, and client types inside the infrastructure adapter and map results into the existing framework-neutral port.

5. **Provenance contract**
   - Define stable `source_id` and `reference` generation, resolution, canonical syntax, and behavior when a cited source version is replaced or removed.
   - Return only references that correspond to the content actually supplied by retrieval; future consumers remain responsible for retaining only references actually used by a hypothesis or knowledge annotation.

6. **Bounds and failure behavior**
   - Choose maximum returned items/chunks, per-item and total context size, timeout, and any backend retry policy without weakening the executor's fixed two-call budget.
   - Map empty search results, backend failures, timeouts, malformed results, truncation, and partial source availability into the foundation outcomes without inventing findings or analytical lifecycle transitions.
   - Resolve the partially useful/insufficient-knowledge boundary together with the first consuming-agent contract rather than embedding experiment-local semantics in the adapter.

7. **Security and content handling**
   - Treat documents, metadata, and returned statements as untrusted data; define sanitization and prompt-injection boundaries before exposing content to an agent.
   - Define secret, personal-data, and sensitive-operational-information handling for both ingestion and retrieval.
   - Ensure diagnostics do not disclose document content, credentials, queries, or backend internals beyond an approved bounded operational form.

8. **Operations and validation**
   - Define telemetry for ingestion and retrieval outcomes, latency, bounds, source/version identity, and permission decisions without persisting chain-of-thought.
   - Decide whether retrieval ledgers or corpus/index metadata require persistence and retention; the current foundation persists neither.
   - Verify the adapter with deterministic contract tests, representative approved documents, provenance resolution, permission isolation, refresh/deletion behavior, bounded results, and failure/timeout cases before connecting a consuming agent.

### Follow-up sequencing

The concrete adapter/corpus capability and the first consuming agent remain separate approval scopes. The adapter may be planned before or alongside a consumer, but it must not add Observation Reasoning or Log Analysis behavior implicitly. If adapter requirements need new scope, permission, citation, or result fields in the foundation contracts, a later OpenSpec change must modify the `knowledge-retrieval` capability explicitly.

## Open Questions

The decisions catalogued under Future Production Adapter remain intentionally deferred and do not change this foundation's contracts or task breakdown. Broader Observation/Lens cancellation, retry, idempotency, and replay semantics also remain Open; this foundation defines only cancellation-safe local executor cleanup and budget integrity.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md`: retrieval remains a bounded tool inside future agents and cannot change findings.
- `docs/architecture/04_pipeline_and_agent_concepts.md`: tools are narrow structured capabilities below agent stages.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, section 8: findings precede retrieval, maximum calls are two, refinement is optional, and failure permits an empty knowledge-derived result.
- `docs/architecture/07_observation_reasoning_agent.md`, sections 4-7: frozen Observation findings and hypothesis grounding boundaries.
- `docs/architecture/21_log_lens_and_analysis_concept.md`, sections 15-16; `docs/architecture/24_log_analysis_agent.md`, sections 7-9; and `docs/architecture/28_log_analytical_tools_and_knowledge_retrieval.md`, sections 6-9: Log-local retrieval shares the bounded foundation while annotations remain consumer-owned.
- `docs/architecture/03_ADR_log.md`: ADR-075 through ADR-081 and ADR-149 through ADR-152.
- `docs/architecture/10_open_decisions_and_backlog.md`, section 9: all concrete retriever and knowledge-layer choices listed there remain open.
