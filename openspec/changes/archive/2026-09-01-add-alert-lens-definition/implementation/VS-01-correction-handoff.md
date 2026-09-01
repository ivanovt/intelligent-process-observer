# VS-01 Correction Handoff — detail response materialization

Corrected `ObservationDefinitionService.observation_response` so it excludes the
summary's reference collections before supplying detail `lenses`, `alert_lenses`, and
`relationships` projections. This prevents Pydantic duplicate-keyword construction on
the Alert-only PostgreSQL create/read walking skeleton.

The PostgreSQL walking-skeleton regression now explicitly asserts the returned Alert
detail identity and type, in addition to its existing create/detail/nested-read checks.

Verification:

- `IPO_TEST_DATABASE_URL=<disposable PostgreSQL URL> uv run pytest tests/test_runtime_persistence_integration.py::test_postgresql_alert_definition_walking_skeleton_and_empty_rejection tests/test_observation_contracts.py tests/test_observation_api.py` — 21 passed.
- `uv run ruff check src/app/observations/service.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run ruff format --check src/app/observations/service.py tests/test_runtime_persistence_integration.py` — passed.

Scope remains VS-01 only; no future-slice behavior or migration changed.

Commit SHA: `HEAD` (the atomic correction commit containing this handoff).

Plan change requested: none.

Shared knowledge candidates: none.
