# VS-07 Handoff — exhaustive Alert result invariants

**Status:** IMPLEMENTATION_COMPLETE

## Implemented behavior

The final Alert result boundary now revalidates serialized completed/partial artifacts,
correlates identity, window, timestamp, provenance, and configured comparison order to
the immutable execution context, and rejects non-UTC generated timestamps. Result
contracts recompute effective occurrences, status distribution, lifecycle durations,
duration statistics, provider-importance distribution, and comparison arithmetic from
the persisted records. Zero-record optional aggregates remain absent, and a zero-record
builder `ValueError` now maps through the pipeline to the approved artifact-free builder
failure outcome.

## Acceptance evidence

| Acceptance ID | Boundary / command | Observable assertion | Result |
| --- | --- | --- | --- |
| VS07-AC01 | `tests/test_alert_result_builder.py::test_builder_enforces_exact_envelope_identity_time_provenance_and_strict_fields` | Completed and both valid partial shapes validate; every identity member, envelope field, correlation/window boundary, provenance, invalid partial reason, and non-UTC generated-time mutation is isolated and rejected. | passed |
| VS07-AC02 | `tests/test_alert_result_builder.py::test_builder_enforces_exact_activity_status_lifecycle_duration_and_importance_invariants` | One-field count/status (including controlled `unknown`), lifecycle, negative/non-finite/per-record duration, each aggregate, provider-importance, and zero/non-zero section mutations reject. | passed |
| VS07-AC03 | `tests/test_alert_result_builder.py::test_builder_enforces_exact_comparison_optional_trace_and_status_sections` | Configured order (including an extra offset), each comparison arithmetic field/direction, success/not-applicable/extra optional trace, and missing findings reject; valid failed trace passes. | passed |
| VS07-AC04 | `tests/test_alert_analysis_pipeline.py::test_representative_builder_failures_map_exact_reason`; `tests/test_alert_analysis_pipeline.py::test_zero_record_builder_failure_maps_to_artifact_free_builder_failure`; `tests/test_runtime_persistence_integration.py::test_representative_builder_invariant_failures_persist_failed_run_without_artifact` | Correlation, aggregate, and zero-record builder failures become artifact-free `result_validation_failed/alert_result_builder`; malformed agent completion remains `agent_failed`; PostgreSQL restores all three failed runs without artifacts. | passed; PostgreSQL passed |

## Important changes / downstream invariants

- `CompletedAlertAnalysisResult` owns recomputation of all final deterministic record-derived aggregates; it does not trust preassembled nested evidence models.
- `AlertResultBuilder` owns execution-context correlation and exact configured-order comparison validation. Empty configuration continues to permit direct builder fixtures with comparison evidence, preserving the existing URI-resolution boundary.
- Both non-zero and zero-record result-build calls are guarded by the pipeline's builder-failure mapping; an Alert builder rejection never yields an artifact.
- Agent completion shape validation remains upstream in the pipeline; assembled-result validation alone maps to the builder failure reason.

## Plan guidance deviations

| Deviation | Evidence / rationale | Coordinator disposition |
| --- | --- | --- |
| none | No URI grammar, tool, adapter, dependency, persistence schema, or plan/task changes. | PENDING |

## Verification

- `cd backend && uv run pytest tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py -q` — 30 passed.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test uv run pytest tests/test_runtime_persistence_integration.py::test_representative_builder_invariant_failures_persist_failed_run_without_artifact -q` — 1 passed, including the zero-record failure proof (one existing Alembic configuration warning).
- `cd backend && uv run ruff check src/app/alerts tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.
- `cd backend && uv run ruff format --check src/app/alerts tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.

## Known limitations within approved scope

None. VS-08 adapter work remains out of scope.

Commit SHA: `HEAD` (atomic VS-07 correction commit)

Plan change requested: none.

Shared knowledge candidates: none.
