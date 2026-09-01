# VS-02 Proof Correction Handoff

Implemented only the two unresolved VS-02 proof corrections. The PostgreSQL mixed
aggregate now submits Relationship IDs in deliberately reverse lexical order
(`zeta-first`, then `alpha-second`) and asserts that the persisted response retains that
exact submission order. An ID-ordered repository load would therefore fail the proof.

The same persisted PostgreSQL scenario now sends a real ASGI request for an unknown
Alert child through the application's session and service dependency overrides. It asserts
the `404 alert_lens_not_found` envelope, then compares the durable definition projection
and Observation/Metric/Alert/Relationship row counts before and after the request.

Changed file: `backend/tests/test_runtime_persistence_integration.py`. The existing stub
API test remains unit coverage only. No production code, migration, plan, or future-slice
behavior changed.

Verification:

- `uv run pytest tests/test_observation_api.py` — 12 passed.
- `IPO_TEST_DATABASE_URL=<disposable PostgreSQL URL> uv run pytest tests/test_runtime_persistence_integration.py::test_postgresql_mixed_definition_order_navigation_and_late_failure_are_atomic` — 1 passed (one Alembic deprecation warning).
- `uv run ruff check tests/test_observation_api.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run ruff format --check tests/test_observation_api.py tests/test_runtime_persistence_integration.py` — passed.
- `git diff --check` — passed.

Downstream constraints: VS-03 remains the owner of Alert-child deletion/cascade behavior;
VS-04 remains the owner of runtime uniqueness and migration behavior.

Commit SHA: `HEAD` (this atomic proof-correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
