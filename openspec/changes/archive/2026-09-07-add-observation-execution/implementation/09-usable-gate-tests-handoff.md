# Usable gate and orchestration tests handoff

Tasks: approved implementation tasks 4.3 and 4.4 only.

Delivered behavior:

- `enforce_usable_results_gate` accepts a verified JOIN partition and initialized parent
  identity in a caller-owned short transaction. An empty usable partition loads and
  correlates the running parent, then uses the existing guarded repository transition to
  persist `failed/no_usable_lens_results/usable_results_gate` and returns the strict
  failed execution outcome. Persistence failures propagate.
- A non-empty usable partition returns without loading or mutating the parent. The gate
  does not mutate collected Lens outcomes or their artifacts, and it starts no
  Observation-level stage.
- New controllable tests prove zero-usable STOP, exact parent reason, pass-through for
  degraded/nonzero usable partitions, persistence-error propagation, and no early
  continuation while a second admitted Lens worker is held. Existing accepted fan-out
  and adapter tests remain the focused evidence for the rest of the 4.4 matrix:
  concurrency ceiling, work-conserving admission, canonical completion collection,
  deadline scope, timeout isolation, and History/terminal persistence propagation.

Files changed:

- `backend/src/app/execution/gates.py`
- `backend/src/app/execution/__init__.py`
- `backend/tests/test_observation_execution_gate.py`
- `backend/tests/test_observation_execution_fanout.py`
- `openspec/changes/add-observation-execution/tasks.md` (4.3 and 4.4 only)

Checks:

- `cd backend && uv run pytest tests/test_observation_execution_gate.py tests/test_observation_execution_fanout.py tests/test_observation_execution_adapters.py -q` — 24 passed.
- Ruff lint and formatting checks for the changed execution files and focused tests — passed.
- `git diff --check` — passed.
- PostgreSQL: no new gate integration test was needed. The gate is a caller-owned
  composition over the existing guarded parent repository operation; focused fakes
  cover the gate boundary, while existing persistence integration tests cover that
  operation's database semantics.

Self-review: the slice adds no adapter, pipeline, repository, initialization,
persistence-schema, API, dependency, migration, or post-JOIN-stage behavior. The only
task-state edits are 4.3 and 4.4.

Final SHA: reported to the Coordinator after the atomic commit.
