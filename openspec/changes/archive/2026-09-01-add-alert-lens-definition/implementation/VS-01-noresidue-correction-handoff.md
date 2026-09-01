# VS-01 No-residue Correction Handoff

Corrected the PostgreSQL walking-skeleton test so its empty-aggregate proof now sends
real `POST /api/v1/observations` requests through the ASGI API boundary. It overrides
the API with a PostgreSQL-backed session dependency and the real
`ObservationDefinitionService`/`ObservationRepository`, submits both omitted and
explicitly empty Lens collections, asserts each request receives `422` validation, and
compares Observation, Metric, Alert, and Relationship table counts before and after.
This demonstrates validation rejection before repository persistence.

Changed files: `backend/tests/test_runtime_persistence_integration.py` and this handoff.
No production code, migration, future-slice behavior, or implementation plan changed.

Verification:

- `uv run pytest tests/test_observation_contracts.py tests/test_observation_api.py` — 20 passed.
- `uv run ruff check tests/test_runtime_persistence_integration.py` — passed.
- `uv run ruff format --check tests/test_runtime_persistence_integration.py` — passed.
- `IPO_TEST_DATABASE_URL=<local PostgreSQL URL> uv run pytest tests/test_runtime_persistence_integration.py::test_postgresql_alert_definition_walking_skeleton_and_empty_rejection` — not runnable locally: the available PostgreSQL container rejects its configured credentials against its pre-existing volume. A valid disposable `IPO_TEST_DATABASE_URL` is required to execute the PostgreSQL proof.

Commit SHA: `HEAD` (the atomic no-residue correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
