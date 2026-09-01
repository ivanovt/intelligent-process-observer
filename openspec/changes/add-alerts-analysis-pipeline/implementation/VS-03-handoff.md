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
| VS03-AC06 | `test_all_references_unavailable_remains_usable_partial` | All unavailable offsets yield usable partial `reference_unavailable/reference_periods`. | passed |
| VS03-AC07 | `test_successful_empty_reference_yields_zero_comparison` | Successful empty reference yields exact zero comparison without partial status. | passed |

Verification: `cd backend && uv run pytest tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py -q` (19 passed); focused Ruff check/format passed; PostgreSQL zero-record regression plus combined-cause partial correlation test passed (2 passed; existing Alembic deprecation warning). Remaining VS-03 PostgreSQL reference-specific proof cases are not implemented.

Important files: Alert contracts, normalization, analyzer, references, pipeline, result builder,
terminal persistence seam, focused service and PostgreSQL tests.

Downstream invariants: references are acquired before the zero gate; no reference records,
diagnostics, placeholders, or secondary partial reasons are serialized or given to the agent.

Deviation from change map: none (PENDING Coordinator disposition: none required).

Known limitations: all-invalid/current-acquisition and other mandatory failure behavior, tools,
adapter, URI validation, and the planned PostgreSQL reference-specific proof cases remain deferred/unimplemented.

Commit SHA: `HEAD` (resolve on the implementation candidate branch after the atomic commit).

Plan change requested: none.

Shared knowledge candidates: none.
