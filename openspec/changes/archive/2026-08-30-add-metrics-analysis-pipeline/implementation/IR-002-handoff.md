# IR-002 Handoff — terminal adapter behavior after policy rejection

**Status:** IMPLEMENTATION_COMPLETE
**Commit:** `HEAD`

## Implemented behavior

After the PydanticAI wrapper submits a framework-emitted tool-call batch to the
framework-neutral request policy, any recorded `MetricToolRejected` immediately
terminates the adapter run as an operational failure. The rejection remains in the
authoritative ledger, but PydanticAI receives neither a rejected tool response nor a
later completion/model request.

Earlier valid deterministic tool outcomes remain in the ledger and continue to
project into the usable partial result. The established protocol-failure priority
therefore remains `optional_analysis_failed/metrics_agent`.

## OpenSpec coverage

- Duplicate, unregistered, parallel, and over-budget policy rejections are all
  terminal after recording.
- Exact model-request counts are 2, 1, 1, and 4 respectively, proving that each
  scripted later completion is unreachable.
- PostgreSQL persistence coverage retains an earlier successful `spike` projection
  after a duplicate rejection and persists the existing `metrics_agent` partial
  reason.

## Important files and invariants

- `backend/src/app/infrastructure/agents/pydantic_ai_metrics.py` stops at the
  infrastructure boundary only after the VS-07R policy has recorded the rejection.
- `backend/tests/test_pydantic_ai_metrics_adapter.py` owns the rejection-kind
  request-count regression.
- `backend/tests/test_metric_analysis_pipeline.py` keeps the database-backed
  retention and partial-reason regression for a later protocol rejection.

## Verification

- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test PYTHONPATH=src UV_CACHE_DIR=/tmp/ipo-ir002-uv-cache uv run pytest tests/test_pydantic_ai_metrics_adapter.py tests/test_metric_analysis_pipeline.py -q` — 98 passed; one existing Alembic deprecation warning.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-ir002-uv-cache uv run ruff check src/app/infrastructure/agents/pydantic_ai_metrics.py tests/test_pydantic_ai_metrics_adapter.py tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-ir002-uv-cache uv run ruff format --check src/app/infrastructure/agents/pydantic_ai_metrics.py tests/test_pydantic_ai_metrics_adapter.py tests/test_metric_analysis_pipeline.py` — passed.
- `git diff --check` — passed.

## Known limitations within approved scope

none.

## Plan change requested

none.

## Shared knowledge candidates

none.
