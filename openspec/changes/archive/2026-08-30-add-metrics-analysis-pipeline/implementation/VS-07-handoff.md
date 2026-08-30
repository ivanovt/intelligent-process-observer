# VS-07 Handoff — deterministic optional-tool registry and tool partials

Implemented the exact framework-neutral optional registry: `spike`, `oscillation`, and
`stuck_signal`. A usable run creates one opaque `dataset_ref` bound to one immutable
prepared-current series in a transient registry. The fake-agent boundary can execute
only those bound tools; the registry records application-owned ordinal attempts and
typed success, not-applicable, failed, or timeout outcomes.

Successful `present|absent|unknown` outcomes project correlated optional
`current_state` and `evidence.current` fields. Not-applicable and unrequested tools
remain absent. Failed/timed-out tools project neither property nor evidence; the earliest
such registered attempt produces the usable partial reason
`optional_analysis_failed/<tool>`. Ledger entries, diagnostics, dataset references, and
prepared samples remain transient and are not serialized. The existing reference and
History primary paths retain their established behavior; this slice adds no cross-cause
cases.

Covered OpenSpec scenarios: exact ordered registry and usable projection; all three
fake-agent calls and ordinal ledger; every Spike rule including zero-MAD branches;
Oscillation present/absent/unknown/minimum cases; Stuck Signal threshold and earliest
longest-run tie; not-applicable omission; successful optional projection; earliest
failed/timeout tool selection; and PostgreSQL terminal partial persistence.

Important files: `backend/src/app/metrics/tools.py`, `contracts.py`, `ports.py`,
`pipeline.py`, `result_builder.py`, `backend/tests/test_metric_tools.py`, and focused
pipeline/History regressions.

Verification:

- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07-uv-cache uv run ruff check src/app/metrics tests/test_metric_analysis_pipeline.py tests/test_metric_tools.py tests/test_metric_history.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07-uv-cache uv run ruff format --check src/app/metrics tests/test_metric_analysis_pipeline.py tests/test_metric_tools.py tests/test_metric_history.py` — passed.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-vs07-uv-cache uv run pytest tests/test_metric_tools.py tests/test_metric_analysis_pipeline.py tests/test_metric_history.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py -q` — 133 passed; two existing Alembic configuration warnings.
- `git diff --check` — passed.

Corrective review evidence:

- Tool-caused partial construction now retains every already-successful paired
  Reference section/evidence and every successfully computed paired History
  section/evidence. Existing reference-then-History reason priority is unchanged;
  no cross-cause precedence behavior was added.
- The run-scoped `MetricToolRegistry` is constructed before the usable request, and
  `allowed_tools` is projected from `registry.descriptors`. A focused source
  regression protects that construction/projection order.
- Table-driven strict-boundary regressions cover Spike modified-z values immediately
  below, at, and immediately above `3.5`; Oscillation deadband equality and the next
  representable value above it; and sign-change ratios immediately below and exactly
  at `0.60`.
- The PostgreSQL-backed tool-partial regression now includes a successful configured
  reference and a successful History candidate, proving both semantic and evidence
  sections survive the persisted optional-tool partial result.

- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07-fix-uv-cache uv run pytest tests/test_metric_tools.py tests/test_metric_analysis_pipeline.py -q` — 68 passed, 15 skipped without PostgreSQL configuration.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07-fix-uv-cache IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test uv run pytest tests/test_metric_tools.py tests/test_metric_analysis_pipeline.py -q` — 83 passed; one existing Alembic `path_separator` deprecation warning.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07-fix-uv-cache uv run ruff check src/app/metrics/pipeline.py src/app/metrics/result_builder.py tests/test_metric_tools.py tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs07-fix-uv-cache uv run ruff format --check src/app/metrics/pipeline.py src/app/metrics/result_builder.py tests/test_metric_tools.py tests/test_metric_analysis_pipeline.py` — passed.
- `git diff --check` — passed.

Downstream adapter binding: VS-08 must bind PydanticAI tool closures to the supplied
`MetricToolExecutor`, retain this ledger as application-owned, and own all duplicate,
unregistered, parallel, fourth-call, model, and protocol behavior. It must not expand
registry membership or bypass the prepared-current binding.

Known limitations within approved scope: no PydanticAI or dependency change, provider
transport, agent/model protocol mapping, duplicate/fourth behavior, cross-cause tests,
or new Reference/History behavior.

Commit SHA: `HEAD` (atomic VS-07 correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
