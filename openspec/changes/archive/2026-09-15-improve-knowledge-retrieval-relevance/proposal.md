## Why

The production curated-knowledge retriever can reject an explicitly relevant, scope-compatible passage when a finding-grounded model query contains verbose peripheral wording: the strict lexical path over-constrains the query and the fixed semantic admission path may also reject the candidate. This produced a successful empty retrieval for run `f2b654e2-2a78-46e7-8f05-fed15354448f`, preventing a knowledge-grounded hypothesis even though the approved document directly described the observed condition.

## What Changes

- Add a deterministic, retriever-owned relaxed lexical fallback when the existing strict lexical strategy yields no admitted passage.
- Require relaxed lexical admission to remain hybrid and relevance-gated: a passage must satisfy both bounded multi-term lexical evidence and a separately calibrated semantic-distance ceiling, rather than being returned merely because it is the nearest candidate or shares one term.
- Keep the fallback inside the existing retrieval call, scope filter, 30-second deadline, four-passage/8-KiB result bounds, and two-call reasoning budget.
- Add positive regression cases for verbose finding-grounded queries over relevant scoped knowledge and negative/boundary cases for unrelated, single-term, out-of-scope, and below-admission candidates.
- Emit safe aggregate retrieval-decision diagnostics identifying the applied strategy and bounded candidate/admission counts, without recording query text, passage text, embeddings, distances, or source identifiers.
- Preserve empty successful retrieval when no strict or relaxed candidate satisfies the server-owned relevance rules.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `curated-knowledge-retriever`: Add deterministic relaxed hybrid admission for verbose queries while preserving eligibility, provenance, trust, failure, and resource boundaries.
- `runtime-observability`: Add safe aggregate diagnostics for completed curated-knowledge retrieval decisions without weakening content or secret exclusions.

## Impact

- Affected backend areas: PostgreSQL lexical/vector candidate search and admission, knowledge-retrieval logging, and focused retrieval/integration tests.
- Public APIs, persistence schemas, knowledge-reference formats, Observation reasoning outputs, report/UI behavior, and lifecycle semantics remain unchanged.
- No dependency, embedding provider/model, migration, frontend, or architecture-package edit is included.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md` — Observation Reasoning and bounded hybrid knowledge retrieval.
- `docs/architecture/07_observation_reasoning_agent.md` — findings-first reasoning, bounded retrieval, and hypothesis grounding.
- `docs/architecture/03_ADR_log.md` — ADR-171 diagnostic boundaries and ADR-173 curated PostgreSQL/pgvector retriever boundaries.
- `docs/architecture/10_open_decisions_and_backlog.md` — exact retriever query-rewriting policy was Open; the user explicitly approved the deterministic retriever-owned strict-then-relaxed direction for this proposal on 2026-09-15.
