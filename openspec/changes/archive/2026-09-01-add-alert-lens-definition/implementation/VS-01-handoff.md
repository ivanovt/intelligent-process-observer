# VS-01 Handoff — Alert-only persisted API walking skeleton

Implemented behavior: Alert-only Observation create/read walking skeleton with defaulted
`lenses`, `alert_lenses`, and `relationships`; a combined non-empty Lens invariant;
Alert-local ignored extras; canonical Alert summary/detail projections; and nested Alert
read at `/api/v1/observations/{observation_id}/alert-lenses/{lens_id}`. Metric reads keep
their existing `lenses` representation and now canonically include `alert_lenses: []`.

Contracts and storage: `AlertSelectorCreate`, `AlertLensCreate`, `AlertLensReference`,
and `AlertLensResponse`; `AlertLensModel`; repository Alert child construction/loading;
service/API Alert projections. Revision `20260901_01` creates
`alert_lens_definitions` with `id`, `observation_id`, `lens_id`, `lens_type`, `name`,
`description`, `source`, `selector_query`, `analysis_objectives`, `reference_periods`, and
`position`.

Scenarios/evidence: focused contract/API tests prove Alert defaults and ignored extras,
Alert-only create/nested read, Metric-compatible empty Alert collection, and rejection of
omitted or explicitly empty Lens collections before service/repository invocation. The
PostgreSQL integration test covers create/load projections and asserts all definition-table
counts are unchanged after empty-aggregate validation. It runs when `IPO_TEST_DATABASE_URL`
is supplied.

Verification:

- `uv run pytest tests/test_observation_contracts.py tests/test_observation_api.py tests/test_runtime_persistence_integration.py` — 20 passed, 3 skipped (PostgreSQL URL absent).
- `uv run ruff check src/app/observations src/app/infrastructure/persistence tests/test_observation_contracts.py tests/test_observation_api.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run alembic -c alembic.ini heads` / `history` — `20260901_01` is the single head after `20260823_01`.

Known scope limits: duplicate/type-local Alert identity and Relationship topology remain
VS-02. Alert parent cascade/delete-orphan remains VS-03. `LensRunModel`, its constraint,
and migration downgrade guard are unchanged for VS-04. No provider, preflight, runtime,
pipeline, update, or delete behavior was added.

Commit SHA: `HEAD` (the atomic VS-01 commit containing this handoff).

Plan change requested: none.

Shared knowledge candidates: none.
