# VS-07R Handoff — framework-neutral request admission and protocol partials

Implemented an application-owned request policy within the run-scoped optional-tool
registry. Every request receives a deterministic ordinal and ledger record. The first
three actions consume one slot whether executed or rejected; a subsequent request is
recorded as `over_budget` with `executed=false` and `consumed_slot=false`.

The policy rejects `duplicate`, `unregistered`, `parallel`, and `over_budget` requests
before deterministic evaluation. Rejected entries retain the raw requested name,
including unregistered names. Registered execution remains exactly once per name, and
the policy is the only path to the bound evaluators. Earlier successful tool outcomes
continue to project public semantic/evidence pairs after a later rejection.

The transient typed `MetricAgentProtocolFailure` is derived from rejected entries.
For usable current data it selects `optional_analysis_failed/metrics_agent`, including
after an earlier registered tool failure; without a rejection the existing earliest
failed/timed-out tool selection remains unchanged. Ledgers, rejection diagnostics,
dataset references, and prepared samples remain absent from result payloads.

Covered OpenSpec scenarios: duplicate and fourth-request rejection; unregistered and
parallel rejection; exact three-slot/each-tool-once accounting; valid result retention;
agent/protocol priority; no public transient-data leakage; and persisted terminal
partial reason correlation for all four rejection kinds.

Important files: `backend/src/app/metrics/contracts.py`, `tools.py`, `ports.py`, and
`pipeline.py`; focused policy and pipeline/PostgreSQL tests are in
`backend/tests/test_metric_tools.py` and `backend/tests/test_metric_analysis_pipeline.py`.

Verification:

- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07r-uv-cache uv run ruff check src/app/metrics tests/test_metric_analysis_pipeline.py tests/test_metric_tools.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07r-uv-cache uv run ruff format --check src/app/metrics tests/test_metric_analysis_pipeline.py tests/test_metric_tools.py` — passed.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-vs07r-uv-cache uv run pytest tests/test_metric_tools.py tests/test_metric_analysis_pipeline.py tests/test_metric_history.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py -q` — 152 passed; two existing Alembic `path_separator` deprecation warnings.
- `git diff --check` — passed.

Downstream adapter obligations: VS-08 must route every framework-observable tool
request through this executor/policy; it must not duplicate the ledger, bypass
admission, or alter rejection and component selection. Framework retry/model-request
budget and adapter/model failure behavior remain VS-08 scope.

Known limitations within approved scope: no PydanticAI, dependency, adapter, prompt,
model-request limit, transport, schema, reference/History behavior, or cross-cause
precedence work was added.

Commit SHA: `HEAD` (atomic VS-07R commit).

Plan change requested: none.

Shared knowledge candidates: none.
