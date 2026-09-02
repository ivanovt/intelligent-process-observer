# VS-03 Handoff — Reference evidence and usable partial outcomes

Implemented independent same-duration Alert reference acquisition, valid-subset normalization,
duplicate-collision rejection, successful ordered occurrence comparisons, and strict usable
partial artifacts. The public primary reason is exactly `invalid_records/current_normalization`
or, when no current rejection exists, `reference_unavailable/reference_periods`. Reference
diagnostics and records remain transient.

## Acceptance evidence

| ID | Boundary / command | Observable assertion | Result |
| --- | --- | --- | --- |
| VS03-AC01 | `tests/test_alert_analysis_pipeline.py::test_references_are_independent_ordered_and_precede_zero_gate` | The configured `7d,1d,14d` windows are independently requested in that order. With current occurrences `3`, successful references `5` then `1` yield `decreased` then `increased` around the unavailable middle offset; a second empty-current run retains the successful comparisons and skips the agent. | passed |
| VS03-AC02 | `test_invalid_current_subset_selects_current_normalization_partial`; PostgreSQL `test_invalid_current_subset_persists_correlated_partial` | The service and persistence fixtures combine a valid record with missing ID, missing title, invalid `started_at`, malformed `ended_at`, and reversed lifecycle records. Every invalid record is absent; the valid evidence remains partial. | service passed; PostgreSQL node skipped (no local database URL) |
| VS03-AC03 | `test_duplicate_collision_rejects_every_member` | Both separated duplicate rows are rejected; only the unique record remains. | passed |
| VS03-AC04 | `tests/test_alert_analysis_pipeline.py::test_unavailable_and_duplicate_reference_sets_omit_only_their_offsets` | Ordered offsets exercise error, timeout, malformed/all-invalid, and separated duplicate-ID colliders plus one success. Only the successful offset yields a comparison; unavailable/reference records do not leak into the artifact. | passed |
| VS03-AC05 | PostgreSQL `test_current_incompleteness_precedes_reference_and_persists_once` | A usable invalid current subset and an actually requested unavailable reference produce only `invalid_records/current_normalization` on the LensRun and correlated result artifact; `reference_unavailable` is absent from the serialized artifact. | skipped (no local database URL) |
| VS03-AC06 | service `test_all_references_unavailable_remains_usable_partial`; PostgreSQL `test_all_references_unavailable_persists_usable_reference_partial` | Error, timeout, and malformed reference offsets retain usable current evidence, persist empty comparisons, and persist exactly `reference_unavailable/reference_periods`. | service passed; PostgreSQL test parameterized/skipped (no local URL supplied) |
| VS03-AC07 | service `test_successful_empty_reference_yields_zero_comparison`; PostgreSQL `test_successful_empty_reference_yields_zero_comparison_without_partial` | A successful empty reference persists its exact `current=3`, `reference=0`, `delta=3`, `increased` comparison on a completed LensRun/artifact with no reason. | service passed; PostgreSQL test parameterized/skipped (no local URL supplied) |

Verification: `cd backend && uv run pytest tests/test_runtime_persistence_integration.py::test_current_incompleteness_precedes_reference_and_persists_once -q` (collected and skipped because `IPO_TEST_DATABASE_URL` was unset); `cd backend && uv run ruff check tests/test_runtime_persistence_integration.py`; and `cd backend && uv run ruff format --check tests/test_runtime_persistence_integration.py` (both passed). No local Compose service or PostgreSQL test URL was available.

PostgreSQL proof command (not run successfully because `IPO_ALERTS_TEST_DATABASE_URL` was unset; no URL or credentials recorded):

`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest tests/test_runtime_persistence_integration.py::test_invalid_current_subset_persists_correlated_partial tests/test_runtime_persistence_integration.py::test_current_incompleteness_precedes_reference_and_persists_once tests/test_runtime_persistence_integration.py::test_all_references_unavailable_persists_usable_reference_partial tests/test_runtime_persistence_integration.py::test_successful_empty_reference_yields_zero_comparison_without_partial -q`

Important files: Alert contracts, normalization, analyzer, references, pipeline, result builder,
terminal persistence seam, focused service and PostgreSQL tests.

Downstream invariants: references are acquired before the zero gate; no reference records,
diagnostics, placeholders, or secondary partial reasons are serialized or given to the agent.

Deviation from change map: none (PENDING Coordinator disposition: none required).

Known limitations: all-invalid/current-acquisition and other mandatory failure behavior, tools,
adapter, and URI validation remain deferred/unimplemented.

Commit SHA: `HEAD` (this atomic correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
