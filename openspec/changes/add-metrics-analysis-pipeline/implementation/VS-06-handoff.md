# VS-06 Handoff — PostgreSQL History reader and terminal transaction atomicity

Implemented `RuntimePersistenceRepository.load()` as the concrete `MetricHistoryReader`.
It joins the existing runtime aggregate by parent Observation identity and string Lens ID,
accepts only usable Metric `completed|partial` artifacts with `good|degraded` quality,
requires a strictly earlier JSON-serialized UTC window end, orders by end/start/lexical
LensRun ID, limits to the newest configured lookback, validates the narrow rows as strict
History candidates, and returns them oldest-first. No model, table, index, or migration
changed.

Covered scenarios: overlapping earlier windows; event-time tie ordering independent of
persistence order; failed, insufficient, and equal-current-end exclusions; bounded
lookback; strict candidate projection; real reader phase ordering; and forced artifact
flush/transaction-commit failures that propagate and roll back both the terminal LensRun
transition and analysis artifact. Existing focused PostgreSQL coverage jointly verifies
completed-sufficient, completed-insufficient, partial, and failed result round trips.

Corrective test evidence closes the three implementation-review gaps without production
scope changes: eligible-looking rows from another Observation or Lens are excluded from
the aggregate-scoped History query; a forced real `AsyncSession.execute` failure during
History loading propagates, leaves the LensRun running, and leaves no artifact after the
caller rollback; and phase traces now cover completed, degraded, insufficient, failed,
reference-partial, and History-partial terminal paths. The real repository is used for
each applicable History-loading path.

Verification:

- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-vs06-uv-cache uv run pytest tests/test_metric_history.py tests/test_metric_analysis_pipeline.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py -q` — 125 passed (two existing Alembic configuration warnings).
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs06-uv-cache uv run ruff check src/app/metrics src/app/infrastructure/persistence tests/test_metric_history.py tests/test_metric_analysis_pipeline.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs06-uv-cache uv run ruff format --check src/app/metrics src/app/infrastructure/persistence tests/test_metric_history.py tests/test_metric_analysis_pipeline.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.
- `git diff --check` — passed.

Downstream invariants: the SQL ordering is safe because Metric result timestamps are
strictly normalized UTC strings; the query selects only the bounded lookback and then
reverses it for the analyzer's oldest-to-newest input. The caller continues to own both
commit and rollback; reader/session failures are not converted to History absence or a
fallback terminal result.

Commit SHA: `HEAD` (the atomic VS-06 corrective test commit).

Plan change requested: none.

Shared knowledge candidates: none.
