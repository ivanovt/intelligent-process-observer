# VS-02 Handoff

**Status:** IMPLEMENTATION_COMPLETE
**Commit:** `HEAD` (resolve on the implementation candidate branch)

## Implemented behavior

Current-series preparation now removes non-finite samples before quality assessment. Three or more remaining finite samples produce `good` or `degraded` prepared evidence; fewer than three produce the successful `insufficient` outcome. Good and degraded paths share the strict usable agent projection. Insufficient invokes the strict identity/window/quality-only projection once; an agent failure or invalid completion is retained only as an operational outcome and still persists `completed + insufficient`.

The result builder now creates strict completed-sufficient degraded artifacts and the strict completed-insufficient envelope. Usable paths retain the VS-01 History/read-write transaction ordering; insufficient does not read History or create analytical sections.

## OpenSpec coverage

- Non-finite filtering and `good` / `degraded` / `insufficient` classification, exact statistics, irregular timestamps, constant values, and finite public evidence.
- ADR-153 trend and variability boundaries, including positive and negative slopes, near-zero values, and zero scale.
- Exact degraded usable request and exact narrow insufficient request; insufficient fake-agent failure resilience.
- Strict degraded completed-sufficient and completed-insufficient payloads, lifecycle correlation, and PostgreSQL runtime-aggregate round trips.

## Important changes / downstream invariants

- `MetricAgentInsufficientRequest` has exactly identity, analysis window, and `data_quality=insufficient`; it exposes no objectives, tools, dataset reference, evidence, state, reference, or History data.
- The insufficient agent outcome is operational-only and never becomes public artifact content.
- Non-finite acquisition values are accepted only up to preparation; prepared samples, evidence, and residuals remain finite.
- Current provider/malformed/mandatory technical failure mapping remains unimplemented for VS-03. Reference, non-empty History, optional tools/ledger, and PydanticAI adapter behavior remain deferred.

## Verification

- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test uv run pytest tests/test_metric_analysis_pipeline.py -q` — 37 passed; one existing Alembic `path_separator` deprecation warning.
- `cd backend && uv run ruff check .` — passed.
- `cd backend && uv run ruff format --check .` — passed (35 files already formatted).

## Known limitations within approved scope

Current technical failures are intentionally deferred to VS-03. No reference comparisons, non-empty History, optional-tool/ledger behavior, framework adapter, provider transport, schema/migration, or top-level orchestration was added.

## Plan change requested

none

## Shared knowledge candidates

none
