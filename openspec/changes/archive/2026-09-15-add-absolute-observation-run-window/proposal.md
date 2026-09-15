## Why

The Run Observation dialog can currently describe only windows relative to the launch instant, even though the run API already accepts any finite past-facing UTC interval. Operators need to analyze a fixed historical incident window, such as `2026-09-10 10:00:00 UTC` through `2026-09-10 17:00:00 UTC`, without calculating equivalent relative expressions at launch time.

## What Changes

- Add an `Absolute UTC` time-range mode alongside the existing relative-preset and expression modes in the Run Observation dialog.
- Let the operator enter exact UTC start and end date-times with second-level precision, clearly label the timezone, and preview the canonical UTC interval that will be submitted.
- Reject missing or invalid date-times, an empty or reversed interval, and an end later than the single captured validation instant before launch.
- Submit the resolved absolute interval through the existing `analysis_window.from` and `analysis_window.to` request fields; keep the public API contract, execution semantics, persistence model, and run projections unchanged.
- Preserve all existing relative presets and the closed `now | now-15m | now-1h` expression vocabulary.
- Advance the accepted UI Direction from v1.11 to v1.12 for this intentional Run Observation interaction change.
- Add no dependency and no browser-local-time or arbitrary-timezone interpretation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-runs-ui`: Extend the existing run-launch time-range interaction with explicit absolute UTC date-time entry, validation, preview, and submission behavior.

## Impact

- Frontend: update the run time-range input/resolution model, Run Observation dialog controls, and focused unit/component tests.
- UI documentation: update `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` to UI Direction v1.12.
- Public API: no change; `POST /api/v1/observation-runs` already accepts concrete aware UTC timestamps and continues to reject future-facing or non-forward windows.
- Backend and persistence: no production change or migration.
- Dependencies: none added, removed, or replaced.

## Architecture References

- `docs/architecture/03_ADR_log.md` — ADR-167 governs UI authority and intentional versioning; ADR-168 governs the on-demand run-launch boundary.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — frozen analysis-window propagation and Observation Run execution semantics remain unchanged.
- `docs/ui/frontend_ui_stack_adr.md` — accepted project-owned frontend component and interaction stack.
- `docs/ui/ui_implementation_handoff_v1.md` — current Runs History and Launch interaction, including concrete UTC submission and the existing two relative modes.
