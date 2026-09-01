## Context

See `proposal.md` for motivation and the two delta specs for required behavior. The current Observation Definition API stores only Metric Lenses in the public `lenses` field, validates Relationships against that collection, and exposes aggregate/list/owned-resource create-read surfaces. Its SQLAlchemy aggregate owns `metric_lens_definitions` and `observation_relationship_definitions`; repository reads eager-load both collections and preserve their `position` ordering.

Accepted ADR-161 through ADR-163 now fix the Alert definition contract and ownership model. They preserve `lenses` as the Metric collection, add `alert_lenses`, require type-local IDs and a dedicated owned table, and explicitly exclude new public update/delete endpoints. Runtime persistence already records `lens_type`, but its database uniqueness constraint currently permits only one `(observation_run_id, lens_id)`, which conflicts with accepted same-ID Metric and Alert definitions.

The existing `observation_runs.observation_id` foreign key uses `ON DELETE RESTRICT`. That retention constraint remains unchanged: parent-definition deletion is possible only when runtime dependents do not block it, and an allowed parent deletion must cascade to all owned definition rows.

## Goals / Non-Goals

**Goals:**

- Add the exact accepted Alert Lens create/read contract without changing existing Metric field names or shapes.
- Keep aggregate validation, persistence, and response construction atomic and deterministic for Metric-only, Alert-only, and mixed definitions.
- Preserve type-local Lens identity through both definition storage and runtime LensRun uniqueness.
- Make ordered round trips and parent ownership directly verifiable in PostgreSQL integration tests.

**Non-Goals:**

- Public Observation Definition update or delete routes, standalone Alert Lens CRUD, or Alert preflight/capability discovery.
- Alert provider transport, credentials, field mapping, retry/timeout policy, pipeline stages, analytical results, agents, tools, models, or RAG.
- A generic polymorphic Lens-definition model, changes to Metric Lens validation/storage, cross-type Relationships, Log Lens definitions, or frontend behavior.
- A `schema_version` bump: this is an additive API-v1 extension, and persisted definitions remain at schema version `1`.
- New dependencies or architecture-document edits.

## Decisions

### Keep separate public collections and owned-resource paths

`ObservationCreate`, summary, and detail projections gain `alert_lenses`; the existing `lenses` field remains Metric-only and is neither renamed nor aliased. Missing input collections use empty-list defaults, and aggregate validation requires at least one item across `lenses` and `alert_lenses`.

Compact list responses expose independent ordered references for `lenses` and `alert_lenses`. Existing Metric navigation remains `GET /api/v1/observations/{observation_id}/lenses/{lens_id}`. Alert navigation uses the owned child path `GET /api/v1/observations/{observation_id}/alert-lenses/{lens_id}`. Separate paths are necessary because accepted type-local identity permits the same ID in both collections; the Alert path remains nested under its parent and is not a standalone resource lifecycle.

Alternative considered: place Metric and Alert definitions in one discriminated `lenses` union. Rejected because ADR-161 preserves `lenses` as the existing Metric contract and requires a separate `alert_lenses` collection.

Alternative considered: omit an individual Alert read and expose Alert details only in aggregate responses. Rejected because the existing list contract provides navigable owned-resource links and the new collection needs an unambiguous target with the same navigation convention.

### Isolate Alert-specific validation and unknown-field tolerance

Add dedicated Alert input/response models and a selector model. Only these Alert-related input models use ignore-extra behavior; the rest of the API retains its existing forbid-extra policy. Serialization from typed models naturally drops ignored fields from persistence and canonical responses.

Validators check non-whitespace content with a non-mutating whitespace test and return the original string. Query, name, description, and objective strings are not trimmed or normalized. Duplicate objectives are detected by exact configured string equality. Reference periods reuse the existing string offset grammar and exact duplicate detection. Ordered values are retained as lists. `source` and `type` are exact literals, so no provider configuration or adapter call is needed during definition creation.

Alternative considered: loosen the global API model to ignore extras. Rejected because ADR-162 grants forward-compatible tolerance specifically to Alert definition input and does not change existing Metric, Relationship, or Observation validation.

Alternative considered: normalize opaque strings before validation/persistence. Rejected because exact query preservation is normative and no normalization semantics are accepted for Alert objectives.

### Validate topology by type-specific namespace

Aggregate validation checks Metric IDs only within `lenses`, Alert IDs only within `alert_lenses`, and Relationship IDs within `relationships`. It deliberately does not create a cross-type Lens-ID set. Relationship resolution continues to use only Metric IDs from `lenses`; an Alert-only ID is unknown to a Relationship, while a same-ID Alert Lens has no effect on a valid Metric participant.

Metric acquisition-source checks continue to iterate only over `lenses`. Alert source validity is contract validation against the accepted literal and does not imply that a Jira adapter or provider connection is configured.

### Add explicit Alert child storage without changing Metric storage

Add `AlertLensModel` mapped to `alert_lens_definitions` and an ordered `ObservationModel.alert_lenses` relationship with `all, delete-orphan` ownership. The table uses a surrogate UUID primary key, `observation_id` with `ON DELETE CASCADE`, `(observation_id, lens_id)` uniqueness, and a `position` column for collection order.

Persist stable values in explicit columns: `lens_id`, `lens_type` containing `alert`, `name`, `description`, `source`, and `selector_query`. Store `analysis_objectives` and `reference_periods` in the repository's existing JSON/JSONB type so list order is retained. The full Alert Lens is not stored as an opaque JSON payload.

Repository creation builds Metric, Alert, and Relationship children under one parent and one caller-owned transaction. List/get operations eager-load all three collections. Service projection reads from stored Alert rows and constructs canonical typed responses, which prevents ignored input fields from reappearing.

Alternative considered: add type and nullable Alert columns to `metric_lens_definitions`, or replace it with a generic `lens_definitions` table. Rejected by ADR-163 and because it would migrate stable Metric storage for no current requirement.

### Keep update/delete transport out of scope while enforcing ownership

No update or delete API/service/repository method is introduced. The ORM ownership and database foreign key implement the deletion invariant at the existing persistence boundary: when a parent deletion is allowed, Alert children are removed in the same transaction. The existing runtime `ON DELETE RESTRICT` foreign key continues to block deletion of definitions referenced by ObservationRuns.

Future aggregate update work must treat each submitted nested collection as a replacement snapshot, validate the complete resulting aggregate, and physically remove omitted Alert rows. This design records that accepted ownership constraint but does not pre-build update code or acceptance endpoints.

Alternative considered: add PUT/PATCH/DELETE routes to exercise replacement and deletion. Rejected because ADR-161 and ADR-163 explicitly reserve those public capabilities for a separate change.

### Make runtime LensRun uniqueness type-aware

Replace the current `lens_runs` uniqueness constraint on `(observation_run_id, lens_id)` with `(observation_run_id, lens_type, lens_id)`. The runtime contract and model already persist `lens_type`, so no new identity column or definition foreign key is needed. Existing rows remain valid, and same-ID Metric and Alert LensRuns become representable without weakening duplicate protection within a type.

Alternative considered: impose global Lens-ID uniqueness despite type-local definition IDs. Rejected because it contradicts ADR-161 and would make a valid mixed definition impossible to execute.

Alternative considered: add direct foreign keys from LensRuns to both type-specific definition tables. Rejected because the accepted runtime persistence model keeps immutable type-aware definition correlation without coupling runtime storage to one definition table.

### Use one forward Alembic migration and focused layered tests

Create one migration after the current head that adds `alert_lens_definitions`, drops the old LensRun unique constraint, and creates the type-aware constraint. No existing definition or runtime row needs transformation or backfill, and `schema_version` values remain unchanged.

Contract tests cover all Alert fields, defaults, non-whitespace rules, exact query preservation, duplicate lists, ignored extras, collection cardinality, type-local IDs, and Metric-only Relationship resolution. Repository/service/API tests cover atomic construction, compact/detail projections, type-specific hrefs, unknown reads, and Metric-only compatibility. PostgreSQL integration tests cover ordered Alert round trips, cascade behavior, the new uniqueness constraint, and migration upgrade/downgrade structure.

## Risks / Trade-offs

- [Additive `alert_lenses` output can affect clients that reject unknown response fields] → Preserve every existing field and API path, keep schema version `1`, and document the additive response contract; no dual-field or rename layer is introduced.
- [Ignoring unknown Alert input can hide client typos] → Limit ignore-extra behavior to Alert-related models and continue strict validation of every recognized field, as ADR-162 requires.
- [Opaque strings can differ only by whitespace] → Preserve and compare exact configured values; reject only strings with no non-whitespace content because normalization is not accepted behavior.
- [JSON/JSONB list storage provides weaker database-level element validation] → Keep semantic validation in the typed domain contract and prove exact ordered persistence with PostgreSQL round-trip tests.
- [Downgrading the runtime uniqueness constraint can fail after same-ID cross-type runs exist] → Roll back application code first and require an explicit pre-downgrade check for duplicate `(observation_run_id, lens_id)` pairs; the migration must fail rather than delete runtime data.
- [Dropping the Alert table on downgrade loses newly created Alert definitions] → Treat downgrade as destructive for the new feature and require backup/export or acceptance of data loss before executing it.

## Migration Plan

1. Apply the forward Alembic migration before deploying code that accepts Alert definitions or same-ID cross-type LensRuns.
2. Create `alert_lens_definitions` with no backfill; existing Metric-only definitions read with `alert_lenses: []` from an empty owned collection.
3. Replace the LensRun unique constraint in place; existing rows already satisfy the wider type-aware key.
4. Deploy the additive contracts, repository hydration, projections, route, and tests together.
5. For rollback, deploy the prior application first. Before database downgrade, verify that no ObservationRun contains duplicate `(observation_run_id, lens_id)` across types and preserve any Alert definitions that must survive. Downgrade then drops the type-aware constraint, restores the old constraint, and drops `alert_lens_definitions`.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — preserves `lenses`, adds `alert_lenses`, defines type-local identity, Metric-only Relationship resolution, and future snapshot semantics.
- `docs/architecture/02_architecture_principles_and_runtime.md` — keeps definition data separate from runtime artifacts and pipeline behavior.
- `docs/architecture/03_ADR_log.md` — ADR-088 and ADR-161 through ADR-163 are implemented directly; no alternative public schema or polymorphic storage is introduced.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — retains framework-neutral runtime correlations and definition/runtime separation.
- `docs/architecture/10_open_decisions_and_backlog.md` — leaves provider mapping, adapter, retry/timeout, analytical, model, and RAG decisions unresolved and out of scope.
- `docs/architecture/11_glossary_and_naming.md` — uses the canonical Observation Definition, Alert Lens, selector, source, and reference-period names.
- `docs/architecture/12_CHANGELOG.md` — follows the 6.4 compatibility and ownership clarifications.
- `docs/architecture/13_alert_lens_and_analysis_concept.md` — follows the accepted Alert serialized contract without implementing the Alerts Analysis Pipeline.

## Open Questions

None. The remaining Alert provider and analysis questions are intentionally outside this change and do not affect its contract, design, or task breakdown.
