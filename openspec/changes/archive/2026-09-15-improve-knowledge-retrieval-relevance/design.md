## Context

See `proposal.md` for the diagnosed failure. The current curated retriever applies service/version eligibility first, creates one query embedding, obtains strict `websearch_to_tsquery` lexical candidates and nearest semantic candidates, admits either signal against fixed thresholds, and rank-fuses admitted passages. Verbose model prose can make the strict lexical expression conjunctive across peripheral terms; the diagnosed relevant chunks then receive no lexical candidate position, while their semantic distance does not meet the current standalone ceiling.

The retrieval boundary must continue to treat returned passages as untrusted candidate knowledge, preserve exact provenance, and permit a valid empty result. Findings, overall state, the framework-neutral retrieval contract, the reasoning two-call budget, and public report behavior remain outside this design.

The exact retriever query-rewriting policy was listed as Open in `docs/architecture/10_open_decisions_and_backlog.md`. The user explicitly approved the deterministic retriever-owned strict-then-relaxed direction on 2026-09-15; this design makes that direction concrete without editing the architecture package.

## Goals / Non-Goals

**Goals:**

- Recover a relevant scoped passage when verbose peripheral wording defeats the strict lexical expression.
- Require corroborating lexical and semantic evidence for every fallback admission.
- Keep fallback execution deterministic, bounded, and internal to one retriever call.
- Make successful strict, relaxed, and empty decisions diagnosable using safe aggregate operational metadata.

**Non-Goals:**

- Guarantee a hypothesis or citation whenever an Observation has a knowledge scope.
- Change scope eligibility, document lifecycle, embeddings, provenance, reasoning prompts, retrieval-call budgets, public contracts, reports, or UI.
- Add model-based query rewriting, advanced reranking, another search service, dependency, setting, database schema, or migration.
- Expose query text, passages, scores, distances, embeddings, or source identities in normal operational logs.

## Decisions

### 1. Use strict-first fallback, not unconditional query expansion

The retriever will preserve the current strict lexical and semantic branches as the initial path. It will evaluate the relaxed lexical branch only when no initial candidate passes either existing admission rule. A strict-path result therefore retains its current candidate set and ordering.

The alternative of always merging relaxed candidates would broaden successful result sets and could silently change established relevance behavior even when the current strategy already works. Prompt-only guidance was also rejected because it is provider-dependent and does not make retrieval admission deterministic.

### 2. Derive the relaxed expression from database-normalized query lexemes

The relaxed branch will use the same PostgreSQL `simple` text-search normalization as retained chunk search vectors. It will obtain the distinct normalized lexemes from the original request and construct a disjunctive lexical expression from those lexemes. It will not invent synonyms, summarize the query, inspect finding text outside the request, or invoke another model/provider operation.

Using PostgreSQL normalization avoids a parallel Python tokenization vocabulary. Converting the full original prose to a second conjunctive expression was rejected because it preserves the diagnosed failure mode; model-authored rewritten queries were rejected because they add cost, nondeterminism, and another prompt boundary.

### 3. Admit relaxed candidates only through a two-signal gate

Each relaxed lexical candidate will carry its count of distinct query lexemes present, relaxed lexical rank, and the semantic distance computed from the call's existing query embedding. It is admitted only when:

1. at least two distinct normalized query lexemes are present;
2. relaxed lexical rank exceeds a fixed relaxed minimum; and
3. semantic distance is at or below a fixed relaxed ceiling.

The relaxed lexical and semantic thresholds remain private server-owned constants. They will be calibrated with a committed positive/negative regression matrix before final values are selected. The diagnosed document/query pair must pass, while unrelated passages, single-term coincidences, scope mismatches, and threshold boundaries must remain rejected. The fallback cannot be enabled by Observation configuration or model tool arguments.

Requiring both signals is intentionally stricter than merely lowering the existing standalone semantic ceiling or accepting an OR-query rank. Either single-signal alternative increases false-positive risk and conflicts with ADR-173's rule that nearest position or ranking alone is not relevance evidence.

### 4. Reuse the existing embedding and bounded selection pipeline

The relaxed branch will not issue another embedding request. It will query only the already filtered eligible-chunk relation, retain the existing per-branch candidate cap and deterministic tie-breakers, and pass admitted fallback candidates through the existing whole-passage/provenance serializer. Strict search, relaxed search when needed, ranking, and serialization remain inside the existing 30-second timeout.

An empty fallback remains `RetrievalSuccess(items=[])`. Timeout, database, embedding, and invalid-result handling remain unchanged.

### 5. Emit one retrieval-decision event from the concrete adapter

The concrete curated retriever needs both internal strategy/count data and run correlation. Its private construction path will therefore receive the existing operational emitter and optional ObservationRun identity; the internal retriever factory/orchestrator wiring may be narrowed accordingly without changing the framework-neutral `KnowledgeRetriever` protocol or request/outcome contracts.

After successful selection, the adapter will emit one `INFO` event with a controlled category (`strict_admitted`, `relaxed_admitted`, or `no_match`) and explicit bounded integer fields for strict candidates/admissions, relaxed candidates/admissions, and returned passages. A not-evaluated relaxed path will use a fixed representation selected consistently in implementation and tests. The diagnostic allowlist will be extended only for these controlled scalar fields. Existing emitter failure suppression keeps diagnostics non-authoritative.

Logging only the returned-item count in the executor was rejected because it cannot distinguish an eligibility/query/admission miss. Logging queries, source IDs, scores, or distances was rejected because normal operational logs are not the sensitive development trace.

## Risks / Trade-offs

- **[False positives from relaxed lexical matching]** → Require two or more distinct lexical matches plus a separately calibrated semantic ceiling, and include unrelated/single-term negative regressions.
- **[Overfitting thresholds to the reported run]** → Calibrate against a small matrix covering relevant paraphrases, unrelated eligible passages, scope exclusions, and exact boundary values rather than one fixture.
- **[Additional database work on empty searches]** → Run the relaxed branch only after empty initial admission, retain the candidate cap, reuse the embedding, and share the existing 30-second deadline.
- **[Operational-log volume]** → Emit exactly one compact informational event per completed curated retrieval call, with no per-candidate events or unbounded values.
- **[Diagnostic wiring leaks into domain contracts]** → Keep emitter/correlation injection in infrastructure composition and leave framework-neutral retrieval inputs, outputs, and ledgers unchanged.

## Migration Plan

No data migration or backfill is required. Deploy the code and tests together. Existing approved chunks and embeddings remain valid because indexing and vector dimensions do not change. Rollback restores the strict-only adapter; persisted analyses and knowledge references require no conversion.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md` sections 12.2-12.3 — findings remain frozen before bounded retrieval; retrieved knowledge may affect hypotheses only.
- `docs/architecture/07_observation_reasoning_agent.md` sections 5-7 — on-demand two-call retrieval and mandatory hypothesis grounding.
- `docs/architecture/03_ADR_log.md` ADR-171 — safe correlated backend diagnostics and content exclusions.
- `docs/architecture/03_ADR_log.md` ADR-173 — eligibility-first PostgreSQL lexical/pgvector retrieval, server-owned relevance admission, provenance, empty success, and fixed resource bounds.
- `docs/architecture/10_open_decisions_and_backlog.md` section 9 — the previously Open exact query-rewriting policy is resolved for this proposal by the explicitly approved deterministic strict-then-relaxed direction.
