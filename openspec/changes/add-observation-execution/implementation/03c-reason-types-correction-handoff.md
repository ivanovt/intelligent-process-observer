# Reason-type correction handoff

Finding: C8 (MEDIUM) — rejected outcomes accepted duck-typed reasons, and collected
partial/failed outcomes accepted raw or duck-typed reasons without preserving the
strict immutable boundary.

Changes:

- Rejected outcomes now require an exact `ExecutionReason` before controlled-code and
  component validation.
- Collected outcomes require a `LensExecutionAssignment`; `partial` and `failed`
  require an exact `ExecutionReason`, while `completed` continues to require none.
- Focused tests cover accepted terminal shapes plus assignment, raw-reason, and
  duck-typed-reason rejection.

Files changed:

- `backend/src/app/execution/contracts.py`
- `backend/tests/test_observation_execution_contracts.py`

Checks:

- `cd backend && uv run pytest tests/test_observation_execution_contracts.py -q` — 24 passed.
- `cd backend && uv run ruff check src/app/execution/contracts.py tests/test_observation_execution_contracts.py` — passed.
- `cd backend && uv run ruff format --check src/app/execution/contracts.py tests/test_observation_execution_contracts.py` — passed.
- `git diff --check` — passed.

Scope/normative concerns: none. No dependencies, migrations, OpenSpec task metadata, or
architecture artifacts changed.

Final SHA: reported directly to the Coordinator; including a commit's own SHA in this
tracked handoff would alter that commit.

Shared knowledge candidates: none.
