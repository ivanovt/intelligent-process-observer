## Context

See [proposal.md](proposal.md). The completed but not yet archived `add-curated-knowledge-retrieval` change introduced `knowledge_scope` as one ordered service-ID set plus one optional scope-level version in Observation API and JSONB persistence. ADR-173 accepts that shape. The user now wants each service to have an independent optional version. The new change is stacked on that feature and cannot safely implement against the older canonical specs alone.

## Goals / Non-Goals

**Goals:** Make mixed service releases representable, retain exact behavior for existing persisted scopes, and keep per-run scope immutable and retriever-only.

**Non-Goals:** Change document upload versions or service-tag vocabulary; infer versions from suggestions; add version-range matching, service discovery, a new database column, or new retrieval budgets.

## Decisions

### Use one ordered entry per service in the canonical scope

The canonical public and domain shape is:

```json
{
  "knowledge_scope": {
    "services": [
      {"service_id": "mprm-server", "service_version": "1.0"},
      {"service_id": "gateway", "service_version": null}
    ]
  }
}
```

Require at least one entry, unique non-blank canonical IDs, optional non-blank opaque labels, and no unknown or mixed-shape fields. Preserve entry order for edit/review fidelity, but treat the set as OR alternatives for retrieval. The label `1.0` is an exact service-applicability value, not the immutable uploaded document version or a semantic-version range. A null/omitted label means all matching tags for that service are eligible. This is more explicit than parallel ID/version arrays and needs no new aggregate.

### Normalize legacy scope at the API and persistence read boundaries

An existing JSONB object such as `{"service_ids":["mprm-server","gateway"],"service_version":"1.0"}` maps to two canonical entries, each at `1.0`; null maps to no scope. The old request shape remains accepted for trusted-MVP clients, but its values are normalized before domain validation and newly persisted scope data always uses `services`. Canonical API responses always use the new shape. Reject mixed old/new fields instead of choosing precedence. No eager data rewrite is required, so existing persisted definitions and snapshots remain readable without a destructive migration. The new UI sends and hydrates only the canonical shape.

This changes the canonical response contract. Existing clients that parse `service_ids`/`service_version` from responses must update, even though their old write payloads remain accepted. A rollback to the previous application after new-format scope rows are written is unsafe: that version cannot represent independent versions. The deployment must keep the new application or restore a pre-change database snapshot; do not silently collapse unequal labels into one version. A targeted downgrade/conversion can be considered separately only if all affected service labels are equal. This limitation is explicit for human review.

### Apply each version filter only to its own service tag

Build the eligible approved chunk set before lexical/vector search as the existing global-document branch OR a match for any scoped service entry. For each entry, match its canonical service ID; if its version is absent, accept all tags for that service; if present, accept unversioned tags or tags containing the exact label. Preserve the approved-active-version gate, relevance admission, fixed passage/deadline budgets, and exact historical citation grammar. An Observation definition edit after run initialization cannot mutate the frozen per-service entries. `ObservationSemanticContext`, finding/overall-state model requests, and `KnowledgeRetrievalRequest` remain unchanged.

### Present each version beside its service in the Observation draft

Replace the shared version field with one optional input in each selected service row. Removing or changing a service affects only that row. The review step pairs each service with its own version or an explicit "all versions" state. The suggestion operation still returns catalog-backed service IDs only; accepting one adds an unversioned row and never overwrites an existing row's version. The current UI stack and aggregate submit boundary remain unchanged. This is a meaningful UI-direction change, so after explicit human approval update `docs/ui/README.md` and the living handoff to v1.10 with the per-service entry, review, and suggestion semantics; do not treat it as incidental copy adjustment.

### Supersede ADR-173 before production implementation

ADR-173 explicitly accepts one scope-level version. A new accepted ADR or user-approved architecture update must supersede only that part of ADR-173 and document the per-service optional shape, legacy meaning, and rollback limitation. Architecture documents remain read-only until the user approves that decision; OpenSpec planning alone does not override ADR-173.

## Risks / Trade-offs

- [Canonical response shape changes] → Keep legacy input acceptance, require clients to update response parsing, and cover both shapes in API tests.
- [Existing stored scopes lose meaning] → Normalize the shared label onto every listed service and test retrieval equivalence before/after.
- [Old application cannot read new per-service rows] → Do not assume code-only rollback after new writes; require snapshot restoration or an explicitly approved compatible conversion.
- [A version on one service filters another] → Test mixed-version and no-version scopes against real PostgreSQL eligibility before ranking.
- [Suggestion silently assigns a version] → Add only unversioned suggested rows and preserve operator-entered versions.

## Migration Plan

1. Obtain explicit approval of the superseding architecture decision and this OpenSpec change. Archive/synchronize the completed predecessor on its own feature branch and bring that canonical-spec update into this stacked branch before applying the follow-on. Verify strict validation no longer reports archive-refusal INFO for its `MODIFIED` headers.
2. Deploy the API/domain/UI and retrieval changes together; no new dependency or schema migration is proposed. Read legacy JSONB scopes and legacy request payloads, but write and return the canonical per-service shape.
3. Verify mixed-version retrieval, legacy semantic equivalence, run freezing, and public-contract compatibility on PostgreSQL; run `make check` and strict OpenSpec validation.
4. If rollback is needed after new-format writes, stop rather than run the old application against them. Restore a pre-change database snapshot or first obtain approval for a data conversion that can represent every affected scope without information loss.

## Architecture References

- `docs/architecture/03_ADR_log.md` (ADR-173): superseding decision required for scope-level version shape.
- `docs/architecture/02_architecture_principles_and_runtime.md` and `07_observation_reasoning_agent.md`: retain finding-before-knowledge and retriever-only frozen scope boundaries.
- `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md`: preserve Observation aggregate editing and knowledge/evidence distinction.
