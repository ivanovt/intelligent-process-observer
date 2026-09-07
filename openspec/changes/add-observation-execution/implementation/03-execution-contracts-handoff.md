# Execution contracts handoff

Tasks: 2.1 and 2.2.

Files:

- `backend/src/app/execution/__init__.py`
- `backend/src/app/execution/contracts.py`
- `backend/tests/test_observation_execution_contracts.py`

Delivered contracts:

- Frozen, framework-neutral request, policy, analysis-window, snapshot, assignment,
  collected-outcome, outcome, and adapter/definition-loader port values.
- The closed internal outcome union distinguishes initialized `completed`/`failed` from
  pre-initialization `rejected`; the rejection has no run ID or runtime status.
- One-shot aggregate projection copies Metric/Alert/Relationship data into immutable
  tuples, preserves definition relationship order, validates the input boundary, and
  returns only approved preparation rejection codes.

Verification:

- `cd backend && uv run ruff check src/app/execution tests/test_observation_execution_contracts.py`
- `cd backend && uv run ruff format --check src/app/execution tests/test_observation_execution_contracts.py`
- `cd backend && uv run pytest tests/test_observation_execution_contracts.py` (3 passed)
- `PYTHONPATH=backend/src uv run --project backend python -c 'import app.execution'`

Notes: no initialization, ordering, orchestration, persistence writes, adapters, API,
dependencies, migrations, or task-checkbox changes were made. Initial atomic commit:
`fed922d` (amended only to include this handoff reference; final commit is reported to
the Coordinator).
