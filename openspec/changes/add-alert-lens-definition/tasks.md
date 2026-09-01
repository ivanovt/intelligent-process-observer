## 1. Definition contracts and topology

- [ ] 1.1 Add dedicated Alert Lens and selector input/response contracts with exact literals, non-mutating non-whitespace validation, ordered duplicate-free objectives/reference periods, empty-list defaults, and Alert-local unknown-field tolerance.
- [ ] 1.2 Extend Observation create, summary, and detail contracts with additive `alert_lenses` collections while preserving the existing Metric `lenses` shape and schema version `1`.
- [ ] 1.3 Update aggregate validation to require at least one Lens across both collections, enforce type-local IDs, and resolve every Relationship participant exclusively against Metric `lenses`.

## 2. Persistence and migration

- [ ] 2.1 Add the owned ordered Alert Lens persistence model with explicit scalar fields, structured ordered-list fields, parent cascade/delete-orphan ownership, and Observation-local Alert ID uniqueness without changing Metric definition storage.
- [ ] 2.2 Update the LensRun model uniqueness declaration to `(observation_run_id, lens_type, lens_id)` so same-ID cross-type LensRuns are representable.
- [ ] 2.3 Add one forward Alembic migration that creates `alert_lens_definitions`, replaces the LensRun uniqueness constraint, performs no backfill or schema-version rewrite, and provides the documented guarded downgrade.
- [ ] 2.4 Extend Observation repository create/list/get behavior to write, eager-load, and restore ordered Alert children inside the existing aggregate transaction.

## 3. Service and API projections

- [ ] 3.1 Extend service summary/detail/reference projections for ordered Alert Lenses, ensure Metric source validation still applies only to `lenses`, and keep ignored Alert input fields out of persisted/read output.
- [ ] 3.2 Add the nested Alert Lens detail route at `/api/v1/observations/{observation_id}/alert-lenses/{lens_id}` with existing owned-resource href and not-found conventions.
- [ ] 3.3 Preserve all existing Metric-only create/list/detail/Lens/Relationship and Metric capability/preflight behavior while returning canonical `alert_lenses: []` when no Alert Lens exists.

## 4. Focused behavioral and persistence tests

- [ ] 4.1 Add contract tests for valid/defaulted Alert definitions, blank recognized strings, unsupported literals, exact query preservation, duplicate values, offset grammar, ignored extras, empty aggregate rejection, type-local IDs, and Metric-only Relationship resolution.
- [ ] 4.2 Add repository and service tests for atomic mixed construction, independently ordered collections, canonical projections, same-ID Metric/Alert links, and Alert not-found behavior.
- [ ] 4.3 Add API tests for Metric-only backward compatibility, Alert-only and mixed creation, compact/detail Alert projections, nested Alert navigation, validation errors, and absence of new public update/delete endpoints.
- [ ] 4.4 Add PostgreSQL integration tests for recognized-field round trips, list ordering, transactional rejection, parent cascade without orphans, runtime deletion restriction, same-ID cross-type LensRuns, and duplicate same-type LensRun rejection.
- [ ] 4.5 Add migration tests or structural assertions for upgrade/downgrade constraint names and confirm downgrade refuses unsafe runtime uniqueness restoration rather than deleting data.

## 5. Verification

- [ ] 5.1 Run focused backend contract, API, repository, migration, and PostgreSQL integration tests and resolve failures within the approved scope.
- [ ] 5.2 Run `make check` and resolve all reported failures before implementation review, archive, or pull-request preparation.
