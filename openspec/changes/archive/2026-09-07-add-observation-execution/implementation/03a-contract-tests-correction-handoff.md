# Contract tests correction handoff

Finding: MEDIUM — contract coverage used stand-in aggregates and omitted material
execution-boundary cases.

Coverage: the projector now receives a mixed real `ObservationModel` aggregate with
real Metric Lens, Alert Lens, and Relationship ORM shapes. Focused cases cover strict
UTC forward windows; positive, finite, non-boolean policy deadlines; controlled empty
and invalid aggregate rejections; equal cross-type Lens IDs; and closed outcome shape
invariants, including the no-run rejection boundary.

Verification:

- `cd backend && uv run ruff check tests/test_observation_execution_contracts.py`
- `cd backend && uv run ruff format --check tests/test_observation_execution_contracts.py`
- `cd backend && uv run pytest tests/test_observation_execution_contracts.py` — 17 passed
- `git diff --check`

Scope/normative concerns: none. No production code, dependencies, migrations, task
checkboxes, or orchestration/initialization tests were changed.

Commit: final atomic correction commit; final SHA is reported directly to the
Coordinator because embedding a commit's own final object ID in its tracked content
would change that ID.

Shared knowledge candidates: none.
