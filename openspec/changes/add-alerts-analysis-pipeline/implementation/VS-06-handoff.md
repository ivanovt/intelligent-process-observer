# VS-06 Handoff — canonical evidence references through persisted results

**Status:** IMPLEMENTATION_COMPLETE

## Implemented behavior

`AlertResultBuilder` now validates every finding reference as an exact, ASCII-only
`alert://` URI. Dynamic segments use UTF-8 with only RFC 3986 unreserved literals and
uppercase percent escapes. The resolver accepts the six approved path families and
requires exactly one final current record, aggregate field, provider-importance value,
or comparison target. It rejects malformed/case-normalized URI forms, absent optional
sections, missing targets, duplicate targets, and transient-only paths. Builder
rejection maps in the pipeline to the artifact-free failed terminal reason
`result_validation_failed/alert_result_builder`.

## Acceptance evidence

| Acceptance ID | Boundary / command | Observable assertion | Result |
| --- | --- | --- | --- |
| VS06-AC01 | `tests/test_alert_result_builder.py::test_all_canonical_evidence_target_forms_resolve`; `tests/test_runtime_persistence_integration.py::test_all_canonical_evidence_target_forms_round_trip` | All static target forms plus encoded space, slash, percent, and Unicode dynamic values resolve and persisted refs round-trip unchanged. | passed; PostgreSQL passed |
| VS06-AC02 | `tests/test_alert_result_builder.py::test_evidence_refs_reject_every_noncanonical_grammar_case`; `tests/test_runtime_persistence_integration.py::test_noncanonical_evidence_refs_fail_without_artifact` | Raw/non-canonical and malformed URI cases fail; failure reason is exact and the persisted LensRun has no result artifact. | passed; PostgreSQL passed |
| VS06-AC03 | `tests/test_alert_result_builder.py::test_builder_rejects_unavailable_unresolved_transient_or_ambiguous_targets`; `tests/test_alert_analysis_pipeline.py::test_unresolvable_finding_reference_stops_before_persistence` | Missing, unavailable, duplicate, and transient-only targets are rejected before an artifact can be created. | passed |

## Important changes / downstream invariants

- `backend/src/app/alerts/evidence_refs.py` owns canonical encoding, parsing, and
  exact-one final-target resolution without a URL-library normalization path.
- Existing finding payloads now retain canonical URI strings, not the former internal
  symbolic references.
- Optional-tool outputs remain transient; they cannot be evidence-reference targets.

## Plan guidance deviations

| Deviation | Evidence / rationale | Coordinator disposition |
| --- | --- | --- |
| none | The comparison URI persistence fixture builds its deliberately Unicode/reserved offset directly through the builder, because configured pipeline offsets remain intentionally constrained to `m|h|d|w`; this exercises the approved final-result URI contract without changing reference-acquisition semantics. | PENDING |

## Verification

- `cd backend && uv run pytest tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py -q` — 25 passed.
- `cd backend && IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55432/ipo_test uv run pytest tests/test_runtime_persistence_integration.py::test_all_canonical_evidence_target_forms_round_trip tests/test_runtime_persistence_integration.py::test_noncanonical_evidence_refs_fail_without_artifact -q` — 2 passed (one existing Alembic configuration warning).
- `cd backend && uv run ruff check src/app/alerts tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.
- `cd backend && uv run ruff format --check src/app/alerts tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.

The broad runtime-persistence file was additionally run with local PostgreSQL: the two
VS-06 nodes passed, while three pre-existing migration/constraint tests failed against
the branch's existing database/migration mismatch (unrelated to VS-06 paths).

## Known limitations within approved scope

VS-07 remains responsible for exhaustive result-envelope invariants; no adapter or
optional-output persistence was added.

Commit SHA: `HEAD` (atomic VS-06 implementation commit)

Plan change requested: none.

Shared knowledge candidates: none.
