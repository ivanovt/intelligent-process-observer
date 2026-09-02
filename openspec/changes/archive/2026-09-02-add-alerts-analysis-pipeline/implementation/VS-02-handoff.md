# VS-02 Handoff — Representative non-zero completed analysis

Implemented valid non-zero Alert analysis: strict lifecycle-overlap normalization,
full-lifecycle durations, deterministic current evidence, an exact bounded fake-agent
request/completion, strict completed artifact assembly, and existing transaction-seam
persistence coverage. No migration, transport, adapter, references, partial/failed path,
tools, or PydanticAI behavior was added.

## Acceptance evidence

| ID | Boundary and command | Observable assertion / counterexample guard | Result |
|---|---|---|---|
| VS02-AC01 | Unit: `cd backend && uv run pytest tests/test_alert_analysis_pipeline.py::test_overlap_normalization_and_full_lifecycle_durations -q` | A boundary-spanning active and resolved record remain; durations are 7200 and 3600 seconds, proving full lifecycle rather than timestamp-inside filtering or clipping. | passed |
| VS02-AC02 | Unit: `cd backend && uv run pytest tests/test_alert_analysis_pipeline.py::test_mandatory_evidence_uses_effective_occurrences_and_record_statuses -q` | Missing occurrence defaults to 1; explicit 3 gives total 4 while status remains 1/1/0; exact duration statistics and native priority values are asserted. | passed |
| VS02-AC03 | Service/PostgreSQL: `cd backend && uv run pytest tests/test_alert_analysis_pipeline.py::test_nonzero_zero_occurrence_invokes_agent_with_exact_projection -q`; parameterized PostgreSQL command below | One record with occurrence 0 invokes the agent exactly once; exact name/description, canonical record, mandatory evidence and empty comparisons are asserted, and excluded fields cannot appear in the strict request. | service passed; PostgreSQL blocked (no parameter supplied) |
| VS02-AC04 | Unit/PostgreSQL: `cd backend && uv run pytest tests/test_alert_contracts.py::test_representative_nonzero_alert_result_is_strict -q`; parameterized PostgreSQL command below | Exact 1.0 envelope, canonical fields, provenance, evidence and finding are asserted; opaque query is absent. | unit passed; PostgreSQL blocked (no parameter supplied) |
| VS02-AC05 | Unit/service: `cd backend && uv run pytest tests/test_alert_analysis_pipeline.py::test_lifecycle_overlap_uses_strict_window_boundaries tests/test_alert_analysis_pipeline.py::test_scope_exclusions_do_not_make_result_partial -q` | Equality/outside lifecycle cases exclude; just-inside records remain; scope exclusion completes without invalid-record behavior. | passed |
| VS02-AC06 | Unit/service: `cd backend && uv run pytest tests/test_alert_contracts.py::test_agent_request_and_completion_contracts_are_strict tests/test_alert_analysis_pipeline.py::test_agent_projection_is_exactly_bounded -q` | Strict models reject unknown/missing completion values and `none`; request contains only the permitted five fields and findings require unique Lens-local IDs. | passed |

PostgreSQL proof command (not run successfully because `IPO_ALERTS_TEST_DATABASE_URL` was unset; no URL or credentials recorded):

`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest tests/test_runtime_persistence_integration.py::test_nonzero_zero_occurrence_invokes_agent_with_exact_projection_and_persists tests/test_runtime_persistence_integration.py::test_representative_nonzero_alert_result_round_trips_strictly -q`

The same tests were run without that parameter and skipped (`2 skipped`), confirming the
test fixture does not select an uncontrolled database target.

Verification: focused unit/service suite passed (`13 passed`); focused Ruff check and
format check passed. The PostgreSQL prerequisite above is the remaining completion-gate
blocker.

Important files: Alert contracts, normalization, deterministic analyzer, bounded port,
pipeline, result builder, and focused unit/service/PostgreSQL tests.

Downstream invariants: only `record_count == 0` skips the agent; occurrence zero does
not. Scope exclusions are not invalid records. Full durations are never overlap-clipped.
The agent sees no query/raw payload/provider configuration/reference records/cross-Lens
or knowledge context. Result evidence refs resolve only to this persisted result's basic
current evidence in this slice.

Deviation from change map: none (PENDING Coordinator disposition: none required).

Known limitations: invalid/duplicate data, configured references/comparisons, partial or
failed terminal paths, optional tools, exhaustive URI grammar, PydanticAI, and provider
transport remain deferred. Mixed provider-importance types are not a valid VS-02 fixture.

Commit SHA: pending commit.

Plan change requested: none.

Shared knowledge candidates: none.
