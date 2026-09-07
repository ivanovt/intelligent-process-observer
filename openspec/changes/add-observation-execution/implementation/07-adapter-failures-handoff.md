# Adapter failures handoff

Tasks: approved implementation tasks 3.3 and 3.4 only.

Files changed:

- `backend/src/app/execution/adapters.py`
- `backend/tests/test_observation_execution_adapters.py`

Delivered mappings:

- Deadline expiry in the pre-terminalization adapter segment becomes
  `timeout/<metric|alert>`; other unexpected analysis-segment exceptions become
  `analysis_failed/<metric|alert>`; rejected/contradictory producer outcomes become
  `identity_mismatch/<metric|alert>`.
- Metric wrapper failures use `MetricResultBuilder.failed()` with the assigned immutable
  context and generic mandatory failure input. They persist a failed Metric artifact with
  `mandatory_metric_analysis_failed` while retaining the adapter wrapper reason on the
  LensRun.
- Alert wrapper failures persist only the failed LensRun and no Alert artifact.
- The analysis-only catch boundary excludes Metric History, terminal transaction load,
  write, commit, and rollback paths; those failures, and `asyncio.CancelledError`, propagate.

Verification:

- `cd backend && uv run ruff check src/app/execution/adapters.py tests/test_observation_execution_adapters.py` — passed.
- `cd backend && uv run ruff format --check src/app/execution/adapters.py tests/test_observation_execution_adapters.py` — passed.
- `cd backend && uv run pytest tests/test_observation_execution_adapters.py tests/test_metric_analysis_pipeline.py tests/test_alert_analysis_pipeline.py` — 110 passed, 28 skipped.
- PostgreSQL container status: running (`intelligent-process-observer-postgres-1`). No new PostgreSQL integration test was necessary: the focused tests prove adapter transaction boundary/rollback signaling with controllable sessions; existing PostgreSQL pipeline coverage remains skipped only where its suite marks those cases as optional.
- Self-review: no Metric/Alert pipeline, result builder, repository, provider, agent, dependency, migration, or OpenSpec task state was changed. The final commit SHA is recorded after commit.
