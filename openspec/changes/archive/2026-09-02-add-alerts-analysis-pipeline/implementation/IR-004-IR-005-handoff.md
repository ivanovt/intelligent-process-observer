# IR-004 / IR-005 Correction Handoff — Final builder correlation

## Implemented behavior

- The final Alert result model unconditionally rejects duplicate current Alert IDs, including when agent findings are empty; upstream normalization retains its existing duplicate-collision handling.
- The final builder accepts comparisons only as a unique ordered subsequence of immutable configured reference offsets. An empty configuration therefore requires empty comparisons.
- Contextual builder validation errors continue to produce artifact-free `result_validation_failed/alert_result_builder` pipeline outcomes.

## Evidence

| Obligation | Proof |
|---|---|
| Duplicate final current IDs are rejected independently of findings | `tests/test_alert_result_builder.py::test_builder_rejects_duplicate_current_ids_without_findings` |
| Empty, unconfigured, duplicate, and out-of-order comparison sets are rejected | `tests/test_alert_result_builder.py::test_builder_rejects_comparisons_without_configured_references`; `test_builder_rejects_unconfigured_duplicate_or_out_of_order_comparisons` |
| Ordered configured successful subset remains valid when other references are unavailable | `tests/test_alert_result_builder.py::test_builder_accepts_ordered_configured_comparison_subset_when_refs_unavailable` |
| Contextual builder rejection has the exact artifact-free terminal mapping | `tests/test_alert_analysis_pipeline.py::test_contextual_builder_comparison_failure_maps_to_artifact_free_terminal_outcome` |

## Files changed

- `backend/src/app/alerts/contracts.py`
- `backend/src/app/alerts/result_builder.py`
- `backend/tests/test_alert_result_builder.py`
- `backend/tests/test_alert_analysis_pipeline.py`

## Verification

- `cd backend && uv run pytest tests/test_alert_contracts.py tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py tests/test_alert_tools.py tests/test_pydantic_ai_alerts_adapter.py -q` — 58 passed.
- `cd backend && uv run ruff check src/app/alerts tests/test_alert_contracts.py tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py tests/test_alert_tools.py tests/test_pydantic_ai_alerts_adapter.py` — passed.
- `cd backend && uv run ruff format --check src/app/alerts tests/test_alert_contracts.py tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py tests/test_alert_tools.py tests/test_pydantic_ai_alerts_adapter.py` — passed.
- `git diff --check` — passed.

## Scope record

- Deviations from approved correction scope: none (`PENDING` Coordinator disposition).
- Known limitations: none within the authorized correction scope.
- Plan change requested: none.
- Shared knowledge candidates: none.
- Correction commit SHA: `68990e60663f751bf40ad076401c774708c91d8d` (`fix(alerts): enforce final builder correlation`).
