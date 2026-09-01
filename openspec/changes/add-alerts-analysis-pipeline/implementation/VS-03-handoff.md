# VS-03 Handoff — Reference evidence and usable partial outcomes

Implemented independent same-duration Alert reference acquisition, valid-subset normalization,
duplicate-collision rejection, successful ordered occurrence comparisons, and strict usable
partial artifacts. The public primary reason is exactly `invalid_records/current_normalization`
or, when no current rejection exists, `reference_unavailable/reference_periods`. Reference
diagnostics and records remain transient.

## Acceptance evidence

| ID | Boundary / command | Observable assertion | Result |
| --- | --- | --- | --- |
| VS03-AC01 | `tests/test_alert_analysis_pipeline.py::test_references_are_independent_ordered_and_precede_zero_gate` | Requests `7d,1d,14d` independently; omits the failed middle offset, retains configured successful order, and zero current skips the agent. | passed |
| VS03-AC02 | `test_invalid_current_subset_selects_current_normalization_partial`; PostgreSQL `test_invalid_current_subset_persists_correlated_partial` | Malformed current input is absent while valid evidence persists as correlated partial. | passed |
| VS03-AC03 | `test_duplicate_collision_rejects_every_member` | Both separated duplicate rows are rejected; only the unique record remains. | passed |
| VS03-AC04 | `test_all_references_unavailable_remains_usable_partial` and AC01 | Error, timeout, and malformed reference offsets produce no placeholders and preserve usable current analysis. | passed |
| VS03-AC05 | service precedence test and PostgreSQL `test_invalid_current_subset_persists_correlated_partial` | Only `invalid_records/current_normalization` is serialized when both causes occur. | passed |
| VS03-AC06 | service `test_all_references_unavailable_remains_usable_partial`; PostgreSQL `test_all_references_unavailable_persists_usable_reference_partial` | Error, timeout, and malformed reference offsets retain usable current evidence, persist empty comparisons, and persist exactly `reference_unavailable/reference_periods`. | service passed; PostgreSQL test parameterized/skipped (no local URL supplied) |
| VS03-AC07 | service `test_successful_empty_reference_yields_zero_comparison`; PostgreSQL `test_successful_empty_reference_yields_zero_comparison_without_partial` | A successful empty reference persists its exact `current=3`, `reference=0`, `delta=3`, `increased` comparison on a completed LensRun/artifact with no reason. | service passed; PostgreSQL test parameterized/skipped (no local URL supplied) |

Verification: `cd backend && uv run pytest tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py -q` (19 passed); focused Ruff check/format passed. The two new PostgreSQL proof nodes were collected but skipped because `IPO_TEST_DATABASE_URL` was unset; no local Compose service was available.

PostgreSQL proof command (not run successfully because `IPO_ALERTS_TEST_DATABASE_URL` was unset; no URL or credentials recorded):

`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest tests/test_runtime_persistence_integration.py::test_invalid_current_subset_persists_correlated_partial tests/test_runtime_persistence_integration.py::test_current_incompleteness_precedes_reference_and_persists_once tests/test_runtime_persistence_integration.py::test_all_references_unavailable_persists_usable_reference_partial tests/test_runtime_persistence_integration.py::test_successful_empty_reference_yields_zero_comparison_without_partial -q`

Important files: Alert contracts, normalization, analyzer, references, pipeline, result builder,
terminal persistence seam, focused service and PostgreSQL tests.

Downstream invariants: references are acquired before the zero gate; no reference records,
diagnostics, placeholders, or secondary partial reasons are serialized or given to the agent.

Deviation from change map: none (PENDING Coordinator disposition: none required).

Known limitations: all-invalid/current-acquisition and other mandatory failure behavior, tools,
adapter, and URI validation remain deferred/unimplemented.

Commit SHA: `HEAD` (atomic correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
