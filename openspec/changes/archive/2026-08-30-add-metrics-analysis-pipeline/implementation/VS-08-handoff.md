# VS-08 Handoff — bounded PydanticAI adapter and model-request ceiling

## Implemented behavior

Added the already approved `pydantic-ai-slim>=2,<3` dependency, resolved to
`2.36.0`, with no provider extra. `PydanticAIMetricsAnalysisAgent` is an
infrastructure-only, injected-`Model` implementation of `MetricsAnalysisAgent`;
it selects no provider, model name, credentials, or transport.

For usable requests, its model wrapper observes each framework function-tool
response, first validates that every tool input is an empty object, and only then
sends the complete valid batch through the supplied VS-07R `MetricToolExecutor`.
Malformed/non-empty input therefore becomes an adapter failure before executor
admission: no evaluator runs and no successful optional projection can leak. The
executor remains the sole ledger/admission owner for duplicate, unregistered,
parallel, and over-budget requests. Tool closures only return an already admitted
outcome. Insufficient requests expose no tools.

PydanticAI agent and tool retries are zero, no retry hook is registered, and
`UsageLimits(request_limit=4)` is paired with a wrapper guard so an underlying
model receives no fifth request. Adapter/model/validation/request-limit failures
return the existing operational outcome: usable pipeline paths persist partial
`optional_analysis_failed/metrics_agent`; insufficient paths remain
`completed + insufficient`.

## OpenSpec scenarios covered

- Exact good, degraded, and insufficient request projections without scope/raw/
  reference/History leakage.
- Zero and all-three serial tool calls, plus all VS-07R rejection kinds; a registered
  fourth call reaches four model requests, becomes over-budget, and cannot trigger a
  fifth request.
- Zero tool/output validation retries, four model requests/no fifth, model timeout,
  and usable/insufficient quality-specific failure handling.
- PostgreSQL runtime-artifact persistence for usable adapter failure
  (`metrics_agent` partial), insufficient adapter failure (completed-insufficient),
  prior successful tool output retained after later model/protocol failure, and the
  registered-fourth-call ceiling.

## Important files and invariants

- `backend/src/app/infrastructure/agents/pydantic_ai_metrics.py` is the only
  production PydanticAI import boundary.
- `backend/src/app/metrics/pipeline.py` treats a usable agent exception or invalid
  outcome as the existing agent partial path; it does not alter policy, registry,
  contracts, or deterministic tool algorithms.
- Only a fully input-valid framework batch calls `MetricToolExecutor.execute_batch()`
  before any PydanticAI tool closure returns, so malformed input and framework
  concurrency cannot bypass the VS-07R admission policy.

## Verification

- `cd backend && PYTHONPATH=src UV_CACHE_DIR=/tmp/ipo-vs08-fix-uv-cache uv run pytest tests/test_pydantic_ai_metrics_adapter.py tests/test_metric_analysis_pipeline.py -q` — 70 passed, 25 skipped.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test PYTHONPATH=src UV_CACHE_DIR=/tmp/ipo-vs08-fix-uv-cache uv run pytest tests/test_pydantic_ai_metrics_adapter.py tests/test_metric_analysis_pipeline.py tests/test_metric_tools.py tests/test_metric_history.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py -q` — 166 passed; two existing Alembic deprecation warnings.
- Focused Ruff check and format check for the adapter and changed tests — passed.
- `git diff --check` — passed.

## Scope and handoff

The Coordinator’s renewed-plan dispatch verified the pre-existing dependency
approval before this dependency edit. This implementation was completed
independently of rejected experimental work; no rejected implementation or handoff
was inspected or reused.

Remaining implementation-private choice: exact prompt wording. No provider/model,
timeout, token, cost, credentials, or transport policy was added.

Commit SHA: `HEAD` (atomic VS-08 commit).

Plan change requested: none.

Shared knowledge candidates: none.
