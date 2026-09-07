# Fan-out and JOIN handoff

Tasks: approved implementation tasks 4.1 and 4.2 only.

Delivered behavior:

- `fan_out_lens_runs` starts exactly `min(max_parallel_lens_runs, assignment_count)`
  long-lived asyncio workers. Workers synchronously claim canonical indices, commit an
  isolated pending-to-running admission transaction, invoke the supplied type-specific
  adapter only after admission, and immediately reuse their slot. Collected outcomes are
  returned in assignment order, never completion order.
- The scheduler deliberately owns no timeout: adapters retain the approved analytical
  deadline and deadline-exempt History/terminal-persistence boundaries.
- `verify_and_partition_lens_outcomes` verifies exact initialized assignment order and
  cardinality, rejects mismatches/duplicates, and returns an immutable canonical
  usable/unavailable partition. It classifies Metric `good|degraded` completed/partial
  artifacts and completed/partial Alerts as usable; completed-insufficient/failed Metrics
  and failed Alerts as unavailable. Cancelled work has no normal JOIN representation.
- The zero-usable parent transition remains unimplemented for task 4.3.

Files changed:

- `backend/src/app/execution/fanout.py`
- `backend/src/app/execution/contracts.py`
- `backend/src/app/execution/__init__.py`
- `backend/tests/test_observation_execution_fanout.py`
- `openspec/changes/add-observation-execution/tasks.md` (4.1 and 4.2 only)

Verification:

- `cd backend && uv run pytest tests/test_observation_execution_fanout.py -q` — 3 passed.
- `cd backend && uv run pytest tests/test_observation_execution_contracts.py tests/test_observation_execution_adapters.py tests/test_metric_analysis_pipeline.py tests/test_alert_analysis_pipeline.py -q` — 142 passed, 28 skipped.
- Ruff check and format check for the changed execution files and focused test — passed.
- `git diff --check` — passed.

Self-review: the new code stays within the execution control-plane boundary. It adds no
adapter/pipeline/persistence/API/dependency/migration changes and no post-JOIN stage or
zero-usable transition. No source-of-truth conflict was encountered.
