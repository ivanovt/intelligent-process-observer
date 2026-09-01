# VS-03 Handoff — Alert definition ownership and deletion integrity

Implemented the final owned-child declarations only: `ObservationModel.alert_lenses`
uses `cascade="all, delete-orphan"`; `AlertLensModel.observation_id` and the matching
foreign key in unreleased revision `20260901_01` use `ON DELETE CASCADE`. The existing
`ObservationRunModel.observation_id` declaration remains `ON DELETE RESTRICT`.

PostgreSQL integration coverage adds one focused ownership test that checks ORM metadata
and migrated foreign keys, deletes an AsyncSession-loaded parent and verifies its ordered
Alert children are gone, deletes another parent with direct SQL and verifies no orphan,
and exercises both paths with an ObservationRun dependent. Each restricted delete raises
`IntegrityError`; rollback retains the parent and both Alert rows.

No repository/service/API delete method or route was added. No runtime LensRun uniqueness
change, migration downgrade guard, or other VS-04 behavior was added.

Verification:

- `uv run pytest tests/test_observation_contracts.py tests/test_observation_api.py tests/test_runtime_persistence_integration.py -q` — 41 passed, 5 skipped (the PostgreSQL integration module requires `IPO_TEST_DATABASE_URL`).
- `uv run ruff check src/app/infrastructure/persistence/models.py migrations/versions/20260901_01_add_alert_lens_definitions.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run ruff format --check src/app/infrastructure/persistence/models.py migrations/versions/20260901_01_add_alert_lens_definitions.py tests/test_runtime_persistence_integration.py` — passed.
- `PYTHONPATH=src uv run python -c '…ownership and FK declaration assertions…'` — passed.
- `git diff --check` — passed.

The local Compose container could not provide the required disposable URL: its database is
not reachable through the workspace host PostgreSQL endpoint, which rejected container
credentials and a newly created container-local test role. Run the added PostgreSQL test
with a valid disposable `IPO_TEST_DATABASE_URL` during Coordinator verification.

Commit SHA: `HEAD` (the atomic VS-03 commit containing this handoff).

Plan change requested: none.

Shared knowledge candidates: none.
