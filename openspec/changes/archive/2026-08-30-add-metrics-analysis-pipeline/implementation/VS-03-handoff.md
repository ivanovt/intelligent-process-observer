# VS-03 Handoff — mandatory current-failure terminal paths

Implemented every mandatory current technical-failure terminal path. Typed provider
`unavailable`, `failure`, and `timeout` outcomes (and provider exceptions) map to
`current_metric_acquisition_failed`; duplicate normalized timestamps and out-of-window
samples map to `current_metric_series_malformed`; unexpected preparation/statistics,
semanticization, or sufficient-result validation failures map to
`mandatory_metric_analysis_failed`.

`MetricResultBuilder.failed()` is the sole minimal failed-result constructor. It emits
only identity, failed status/error, `analysis_window.from/to`, and context-derived
Prometheus provenance. Operational diagnostics are bounded on typed in-memory outcomes
and never enter the artifact. Failed provenance uses the injected clock and execution
context source even if acquisition produced no provider response.

The pipeline decides failed analytical outcomes before the caller opens the terminal
transaction. `persist_terminal()` advances the existing running LensRun to `failed`
with the matching public error code as its structured reason, then inserts exactly one
failed Metric artifact through the existing repository and caller-owned transaction.
History is not invoked for failed outcomes; current acquisition/malformed/semantic
failures also do not invoke the agent.

Covered OpenSpec scenarios: malformed duplicate/out-of-window current series; exact
minimal failed result and fixed error mappings; diagnostic exclusion; pre-provider
success provenance; failed lifecycle/artifact correlation and PostgreSQL retrieval.

Important files: `backend/src/app/metrics/contracts.py`, `ports.py`,
`preprocessing.py`, `result_builder.py`, `pipeline.py`, and
`backend/tests/test_metric_analysis_pipeline.py`.

Verification:

- `cd backend && uv run pytest tests/test_metric_analysis_pipeline.py -q` — 46 passed, 6 PostgreSQL tests skipped when no test database environment was active.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test uv run pytest tests/test_metric_analysis_pipeline.py -rs -q` — 52 passed; one existing Alembic configuration deprecation warning.
- `cd backend && uv run pytest tests/test_runtime_persistence.py -q` — 13 passed.
- `cd backend && uv run ruff check src/app/metrics tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && uv run ruff format --check src/app/metrics tests/test_metric_analysis_pipeline.py` — passed.
- `git diff --check` — passed.

Deferred within approved scope: reference-role mapping/reuse, non-empty History,
optional tools and agent adapter behavior, persistence rollback fault injection,
schema migration, and top-level orchestration.

Commit SHA: `HEAD` (resolve on the implementation candidate branch after the atomic VS-03 commit).

Plan change requested: none.

Shared knowledge candidates: none.
