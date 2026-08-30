# VS-09 Handoff — cross-cause conformance and boundary documentation

Implemented conformance-only coverage and documentation. No production module,
contract, dependency, schema, migration, or OpenSpec plan metadata changed.

`test_cross_cause_precedence_persists_one_public_reason_without_diagnostics`
persists all approved cross-cause combinations: reference + History + optional,
reference + optional, and History + optional. It proves the fixed public order
`reference_unavailable/reference_periods > history_analysis_failed/history >
optional_analysis_failed/metrics_agent`, exact persisted LensRun/result-reason
correlation, and exclusion of secondary diagnostics/ledger data.

`docs/metrics-analysis-developer-boundaries.md` documents the injected provider,
agent, History-reader, and repository composition; injected PydanticAI-model
boundary; strict result-builder ownership; and the future Prometheus provider
composition boundary. It does not duplicate or alter architecture documents.

Coverage audit: the approved change contains **11/11 requirements**, **72/72
acceptance scenarios**, and **37/37 implementation tasks/sub-parts**. The frozen
coverage matrix assigns every item a primary owner and verification path; VS-09
adds only final cross-cause regression/conformance coverage and does not transfer
ownership.

Verification:

- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs09-uv-cache uv run ruff check tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && UV_CACHE_DIR=/tmp/ipo-vs09-uv-cache uv run ruff format --check tests/test_metric_analysis_pipeline.py` — passed.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-vs09-uv-cache uv run pytest tests/test_metric_analysis_pipeline.py::test_cross_cause_precedence_persists_one_public_reason_without_diagnostics -q` — 3 passed (one existing Alembic configuration warning).
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-vs09-uv-cache uv run pytest -q` — 189 passed (two existing Alembic configuration warnings).
- `openspec validate add-metrics-analysis-pipeline --strict` — passed.
- `IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test UV_CACHE_DIR=/tmp/ipo-vs09-uv-cache make check` — passed: Ruff lint/format, 189 backend tests, frontend ESLint/build, and `openspec validate --all --strict`.
- Boundary audit — PydanticAI import is only in `backend/src/app/infrastructure/agents/pydantic_ai_metrics.py`; Metric domain has no PydanticAI/Prometheus import; no PydanticAI provider extra is installed.
- `git diff --check` — passed.

The transaction-order, all-variant retrieval, malformed-current/reference,
History-repository failure, terminal-persistence rollback, ordinal tool failure,
protocol rejection, non-failure tool, and adapter-ceiling regressions remain green
in the full suite under their established primary owners.

Remaining approved implementation-private choices: prompt wording, production
model/provider and credentials, model-dependent timeout/token/cost limits, and
Prometheus transport/authentication/retry mapping.

Ready for official change verification and independent implementation review; do
not archive, push, create a PR, or merge from this handoff.

Commit SHA: `HEAD` (atomic VS-09 conformance/documentation commit).

Plan change requested: none.

Shared knowledge candidates: none.
