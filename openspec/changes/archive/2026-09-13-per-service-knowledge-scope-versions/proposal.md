## Why

An Observation can select several services but currently has only one optional service-version label. Those services may run different releases, so the shared label can exclude relevant approved knowledge or include knowledge for the wrong service release. Operators need to set or omit the version independently for each selected service.

## What Changes

- **BREAKING:** Replace the canonical Observation knowledge-scope shape (`service_ids` plus one `service_version`) with an ordered, duplicate-free collection of service entries, each with a canonical service ID and its own optional opaque version label.
- Let Create/Edit Observation operators add, remove, and review each service with its own optional version; keep scope-suggestion results service-ID-only and require the operator to enter any version.
- Match approved knowledge tags against each service's own optional version. A document is eligible when any service entry matches, or when it is globally applicable. Preserve unversioned-tag, no-version, approval, relevance, provenance, and bounded-retrieval behavior.
- Preserve the meaning of already-persisted shared-version scopes by interpreting the old label as applying to every service named in that legacy scope. Accept legacy request payloads during transition, while canonical reads and new writes use the per-service shape.
- Record the superseding architecture decision before implementation. This change does not alter document-version lifecycle, ingestion, embeddings, source references, or Observation evidence semantics.

## Capabilities

### New Capabilities

- `curated-knowledge-scope-filtering`: Define how the concrete curated retriever applies independently optional service-version labels. This is a narrow follow-on to the still-active `add-curated-knowledge-retrieval` change.

### Modified Capabilities

- `observation-definition-api`: Change the optional knowledge-scope request and canonical response contract while preserving existing persisted scopes.
- `observation-management-ui`: Edit and review a version beside each selected service rather than using one shared field.

## Impact

- Affected code: Observation API/domain contracts, JSONB scope serialization and legacy read compatibility, run-frozen scope projection, curated-retriever metadata filtering, Observation Create/Edit/review UI, and focused tests.
- Public contract: canonical `knowledge_scope` response changes; new clients send the per-service shape while legacy request payloads remain accepted and normalized. Existing persisted shared-scope records retain their prior retrieval meaning; rollback behavior is called out in the design for review.
- Dependencies and database schema: no new dependency or database column is proposed; existing JSONB scope data requires compatibility handling.
- This planning change is stacked on `feature/add-curated-knowledge-retrieval`. The predecessor must be archived/synced into canonical specs before this follow-on can be archived. Implementation also requires explicit approval of the superseding architecture decision.
- UI direction: a proposed v1.10 handoff update will replace the shared version control with per-service entries while retaining the existing Observation aggregate flow.

## Architecture References

- `docs/architecture/03_ADR_log.md` (ADR-173): currently specifies one optional scope-level version and therefore requires an explicit superseding decision.
- `docs/architecture/02_architecture_principles_and_runtime.md` and `07_observation_reasoning_agent.md`: preserve evidence-first, run-frozen, retriever-only knowledge scope.
- `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md`: preserve accepted Observation Management and knowledge/evidence UI boundaries.
