# VS-05 Handoff — eligible persisted-result History behavior

Implemented the framework-neutral History reader expansion and pure deterministic
History analysis. The reader returns either normal empty success or strict prior-result
projections; pure selection excludes current, failed, insufficient, and non-earlier
projections, orders by event time with the required tie-breaks, takes newest lookback,
then analyzes oldest-to-newest with current evidence appended. No ORM, JSON query, or
raw telemetry enters the analyzer.

Completed/partial Metric results now serialize paired `history` and
`evidence.history` sections when analysis succeeds. No History and accepted unknown
History remain completed. An unexpected pure History computation failure produces the
strict `history_analysis_failed/history` partial result. Reader/session failures
propagate before a LensRun transition or artifact insertion.

The History read remains inside the caller-owned terminal transaction; the PostgreSQL
candidate query/adapter is intentionally not implemented and remains VS-06 work.

Verification:

- `cd backend && uv run pytest tests/test_metric_history.py tests/test_metric_analysis_pipeline.py -q` — 76 passed, 9 skipped without PostgreSQL configuration.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test uv run pytest tests/test_metric_history.py tests/test_metric_analysis_pipeline.py tests/test_runtime_persistence.py -q` — 98 passed; one existing Alembic configuration deprecation warning.
- `cd backend && uv run ruff check src/app/metrics tests/test_metric_history.py tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && uv run ruff format --check src/app/metrics tests/test_metric_history.py tests/test_metric_analysis_pipeline.py` — passed.
- `git diff --check` — passed.

Corrective review evidence:

- `MetricHistoryCandidate` now accepts only strict persisted Metric result variants:
  usable `completed|partial` with `good|degraded` and a finite mean,
  `completed + insufficient` without a mean, or `failed` without data quality or
  a mean. The focused rejection matrix covers every invalid combination.
- Focused History tests now explicitly prove the strict current-end cutoff, lexical
  `lens_run_id` ordering when both event-time fields tie, and ADR-160 removal of an
  unknown transition between opposing directions before reversal detection.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs05-uv-cache uv run pytest tests/test_metric_history.py -q` — 43 passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs05-uv-cache uv run ruff check src/app/metrics/contracts.py tests/test_metric_history.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs05-uv-cache uv run ruff format --check src/app/metrics/contracts.py tests/test_metric_history.py` — passed.
- `git diff --check` — passed.

Downstream invariant: VS-06 must adapt only bounded, same-observation/same-lens
persisted Metric projections to `MetricHistoryRead` and must let reader/query failures
propagate unchanged. It must not replace the domain event-time ordering, lookback, or
analysis logic.

Known limitations within approved scope: no PostgreSQL History query, repository
extension, transaction rollback fault injection, raw History serialization, optional
tools, or combined-cause precedence verification.

Commit SHA: `HEAD` (the atomic VS-05 corrective commit containing this handoff).

Plan change requested: none.

Shared knowledge candidates: none.
