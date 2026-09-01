## Why

Alert analysis cannot be implemented against a stable configuration boundary until Alert Lens definitions have an accepted public contract and durable representation. Extending the existing Observation Definition aggregate now provides that boundary while preserving the established Metric-only API and keeping provider/runtime analysis concerns deferred.

## What Changes

- Add an optional `alert_lenses` collection to Observation Definition create and read representations while preserving the existing `lenses` field as the Metric Lens collection.
- Define the accepted Alert Lens fields, defaults, validation, unknown-field handling, type-local identity rules, and exact ordered round-trip behavior.
- Allow Metric-only, Alert-only, and mixed Observation definitions, while requiring at least one Lens across `lenses` and `alert_lenses`.
- Keep Relationships Metric-only and resolve their participants exclusively against `lenses`, including when an Alert Lens has the same ID.
- Persist Alert Lens definitions as ordered, owned rows in a dedicated `alert_lens_definitions` table with explicit scalar columns and structured ordered-list storage.
- Align runtime LensRun uniqueness with type-aware Lens identity so a mixed Observation may execute Metric and Alert Lenses that share an ID.
- Preserve parent-deletion cascade ownership at the repository/database boundary without adding public Observation update/delete routes or standalone Alert Lens endpoints.
- Add deterministic contract, repository, migration, API, and PostgreSQL integration coverage for validation, atomicity, ordering, round trips, compatibility, and cascade behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-definition-api`: Extend the existing Observation Definition aggregate contract and create/read behavior with owned Alert Lens definitions.
- `runtime-persistence`: Make LensRun identity and uniqueness type-aware so accepted same-ID Metric and Alert definitions can coexist in one ObservationRun.

## Impact

- Affected backend areas: Observation Definition Pydantic contracts, service projections, FastAPI create/read responses, SQLAlchemy definition models, repository hydration, Alembic migrations, and focused unit/API/PostgreSQL integration tests.
- The migration adds `alert_lens_definitions` and changes the `lens_runs` uniqueness constraint from `(observation_run_id, lens_id)` to `(observation_run_id, lens_type, lens_id)`; existing rows require no data backfill.
- Existing Metric Lens storage remains unchanged and is not generalized into a polymorphic Lens-definition table.
- Existing Metric-only request payloads remain valid when `alert_lenses` is omitted; canonical reads add `alert_lenses: []` and preserve `lenses` unchanged.
- No dependency, frontend, provider adapter, Alert analysis pipeline, agent/tool, model/provider, RAG, or public update/delete endpoint change is included.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — Observation Definition ownership, type-specific collections, type-aware identity, and Metric-only Relationships.
- `docs/architecture/02_architecture_principles_and_runtime.md` — definition/runtime separation and structured persistence boundary.
- `docs/architecture/03_ADR_log.md` — ADR-088 and accepted ADR-161 through ADR-163.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — definition/runtime separation and persisted LensRun identity.
- `docs/architecture/10_open_decisions_and_backlog.md` — provider/API and Alert analysis questions that remain outside this change.
- `docs/architecture/11_glossary_and_naming.md` — canonical Observation, Lens, Alert Lens, selector, and reference-period terminology.
- `docs/architecture/12_CHANGELOG.md` — architecture package 6.4 definition decisions.
- `docs/architecture/13_alert_lens_and_analysis_concept.md` — accepted serialized Alert Lens definition and ownership rules.
