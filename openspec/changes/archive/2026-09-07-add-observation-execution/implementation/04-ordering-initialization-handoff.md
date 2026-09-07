# Ordering and initialization handoff

Tasks: 2.3 and 2.4.

Implemented behavior:

- Canonical Lens ordering is literal `metric`, then `alert`, with lexical Lens ID order
  within each type; frozen Relationship ordering remains unchanged.
- One short transaction loads once, validates/projects once, creates a fresh pending
  ObservationRun and exact pending type-aware LensRun topology, then advances the parent
  to `running` before commit. Runtime execution contexts retain only schema/window data,
  not provider configuration.
- Controlled preparation rejections write no runtime records. Creation/flush/transition
  failures escape the transaction and roll back the whole graph.

Files:

- `backend/src/app/execution/contracts.py`
- `backend/src/app/execution/ordering.py`
- `backend/src/app/execution/initialization.py`
- `backend/src/app/execution/__init__.py`
- `backend/tests/test_observation_execution_initialization.py`

Verification:

- `cd backend && uv run ruff check src/app/execution tests/test_observation_execution_initialization.py`
- `cd backend && uv run ruff format --check src/app/execution tests/test_observation_execution_initialization.py`
- `cd backend && uv run pytest tests/test_observation_execution_contracts.py tests/test_observation_execution_initialization.py -q` — 28 passed.
- `PYTHONPATH=src uv run python -c 'import app.execution'`
- `git diff --check`

Notes: no pipeline, API, resume/retry surface, dependency, migration, or task metadata
changes. No scope or normative concerns remain. The final atomic commit SHA is reported
directly to the Coordinator because embedding it in this tracked handoff would alter it.

Shared knowledge candidates: none.
