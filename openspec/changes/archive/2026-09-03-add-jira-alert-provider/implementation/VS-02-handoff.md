# VS-02 Handoff — Jira lifecycle mapping through current and reference behavior

## Implemented behavior

- The Jira adapter now retains terminal-page issues and projects usable issues into
  `AlertProviderRecord` values using created/resolution lifecycle fields, native status
  and priority, and canonical site-root browse references.
- Jira JQL continues to preserve the opaque selector and uses floor-start/ceil-end
  candidate bounds; the existing Alert normalizer remains the strict overlap owner.
- Malformed individual issues become compact canonical-mappable dictionaries, allowing
  existing `invalid_records` handling to retain usable records in the same acquisition.
- A present malformed `fields.priority` now remains a compact invalid
  `provider_importance` input for application normalization; only a truly absent optional
  priority is omitted.
- Current and reference acquisitions continue to use the unchanged pipeline outcome
  semantics. Jira query errors therefore fail current acquisition and make a reference
  unavailable; successful empty or stale pages remain successful.

## OpenSpec scenarios covered

VS02-AC01 through VS02-AC08.

## Important files/contracts

- `backend/src/app/infrastructure/jira/adapter.py`: terminal envelope projection only;
  no Alert pipeline, result, or provider-port contract change.
- `backend/tests/test_jira_alert_provider.py`: JQL/overlap, mapping, malformed record,
  canonical source-ref, current/reference, query-error, stale-success, and boundary
  isolation coverage.

## Verification

Correction verification:

`cd backend && uv run pytest tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py tests/test_alert_contracts.py -q` — 46 passed.

`cd backend && uv run ruff check src/app/infrastructure/jira tests/test_jira_alert_provider.py` — passed.

`cd backend && uv run ruff format --check src/app/infrastructure/jira tests/test_jira_alert_provider.py` — passed.

`git diff --check` — passed.

## Downstream invariants

Jira-side bounds are deliberately a candidate superset; do not move exact overlap into
the adapter. `source_ref` is the required canonical record field, not raw transport
leakage. Reference records retain latest returned resolution values but remain outside
agent/result record projections.

## Known limitations within approved scope

This slice accepts one terminal page only. Cursor continuation/volume cap, hard
deadlines, and retry behavior remain deferred to VS-03 through VS-05.

Commit SHA: `bc2f6eadc68fd06118cd7b9cedf2639df910d175` (the original VS-02 slice commit).

Correction commit SHA: `HEAD` (the atomic correction commit containing this evidence).

Plan change requested: none.

Shared knowledge candidates: none.
