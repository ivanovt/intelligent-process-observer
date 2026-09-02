# IR-002 Correction Handoff — Alert reference stage order

## Implemented behavior

- Restored Alert pipeline order to current normalization, configured reference acquisition and preparation, then mandatory deterministic analysis.
- Kept unavailable references supplementary: usable current analysis remains `partial` with `reference_unavailable` only where applicable.
- Kept deterministic analyzer exceptions terminal with exact `deterministic_analysis_failed` mapping.
- Moved reference comparison construction into the mandatory deterministic-analysis phase, after current evidence is available.

## Evidence

| Obligation | Proof |
|---|---|
| Reference acquisition/preparation precedes analysis | `tests/test_alert_analysis_pipeline.py::test_mandatory_analysis_failure_stops_agent_and_builder` asserts every configured provider call has completed before its injected analyzer raises. |
| Analyzer failure remains terminal | The same regression asserts `deterministic_analysis_failed` while fail-on-call agent and builder prove no downstream result construction. |
| Service phase ordering | `tests/test_alert_analysis_pipeline.py::test_pre_transaction_work_finishes_before_persistence_composition` asserts `reference_acquisition` precedes `mandatory_analysis`. |
| PostgreSQL phase ordering | Both persistence phase-order assertions were updated; `tests/test_runtime_persistence_integration.py::test_alert_pipeline_phase_order_keeps_long_work_outside_transaction` was collected but skipped without a configured PostgreSQL service. |

## Files changed

- `backend/src/app/alerts/pipeline.py`
- `backend/src/app/alerts/references.py`
- `backend/tests/test_alert_analysis_pipeline.py`
- `backend/tests/test_runtime_persistence_integration.py`

## Verification

- `cd backend && uv run pytest tests/test_alert_analysis_pipeline.py -q` — 27 passed.
- `cd backend && uv run pytest tests/test_runtime_persistence_integration.py::test_alert_pipeline_phase_order_keeps_long_work_outside_transaction -q` — 1 skipped (no PostgreSQL service configured).
- `cd backend && uv run ruff check src/app/alerts/pipeline.py src/app/alerts/references.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.
- `cd backend && uv run ruff format --check src/app/alerts/pipeline.py src/app/alerts/references.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.
- `git diff --check` — passed.

## Scope record

- Deviations from approved correction scope: none.
- Known limitations: PostgreSQL proof remains environment-skipped until a PostgreSQL test URL/service is configured.
- Plan change requested: none.
- Shared knowledge candidates: none.
- Commit SHA: `2ab06d5` (`fix: restore alert reference stage order`).
