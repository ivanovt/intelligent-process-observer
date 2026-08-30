# VS-04 Handoff — independent Metric reference comparisons

Implemented equal-duration reference windows for every configured offset. Each
usable current run now acquires, prepares, and semanticizes each reference independently,
then compares successful references against current data in configured order. The strict
paired `reference_periods` and `evidence.reference_periods` sections preserve matching
offset/window correlation and omit unsuccessful offsets.

Reference acquisition failures/timeouts, duplicate or out-of-window samples, and
post-filter insufficient reference data produce operational per-offset diagnostics and
the usable partial result/reason `reference_unavailable/reference_periods`. Successful
offsets remain serialized, and current insufficiency neither acquires comparisons nor
becomes partial. Terminal partial status, LensRun reason, and persisted artifact reason
are correlated through the existing caller-owned transaction.

Covered scenarios: zero/one/many configured windows; exact shifted-window arithmetic;
current-relative level/trend/variability comparisons; configured-order preservation;
every reference-unavailable cause; successful-offset preservation; current-insufficient
exemption; and PostgreSQL-backed completed/partial result persistence.

Important files: `backend/src/app/metrics/references.py`, `contracts.py`,
`pipeline.py`, `result_builder.py`, and `backend/tests/test_metric_analysis_pipeline.py`.

Verification:

- `cd backend && UV_CACHE_DIR=/tmp/ipo-uv-cache uv run ruff format --check src/app/metrics tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-uv-cache uv run ruff check src/app/metrics tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-uv-cache uv run pytest tests/test_metric_analysis_pipeline.py -rs -q` — 60 passed; one existing Alembic `path_separator` deprecation warning.
- `git diff --check` — passed.

Corrective review/fix evidence: the independent review HIGH finding for finite
extreme means is resolved. `compare_reference()` now normalizes both finite
means by their larger magnitude before evaluating the equivalent symmetric
relative-level expression, avoiding overflow to `NaN`. The added pipeline
regression uses positive and negative largest-finite means; it verifies the
reference remains comparable, produces `relative_level_change=2.0`, and ends
completed without a false `reference_unavailable` partial result.

- `cd backend && UV_CACHE_DIR=/tmp/ipo-uv-cache uv run ruff check src/app/metrics/references.py tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-uv-cache uv run ruff format --check src/app/metrics/references.py tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-uv-cache uv run pytest tests/test_metric_analysis_pipeline.py -q -k extreme_finite_reference_means` — 1 passed, 60 deselected.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-uv-cache uv run pytest tests/test_metric_analysis_pipeline.py -q` — 61 passed; one existing Alembic `path_separator` deprecation warning.

Downstream invariants: only successful `good|degraded` references enter paired non-empty
sections; paired semantic/evidence entries have identical offset/window/order; public
reference incompleteness always uses the one fixed reason and never serializes diagnostics
or placeholders. Reference acquisition/preparation/semanticization completes before the
agent stage; comparison follows it and all terminal writes remain transaction-owned.

Known limitations within approved scope: no History candidates/query, optional tools or
ledger, PydanticAI adapter, combined-cause precedence, schema/migration, transport, or
top-level orchestration.

Commit SHA: `HEAD` (the atomic VS-04 commit).

Plan change requested: none.

Shared knowledge candidates: none.
