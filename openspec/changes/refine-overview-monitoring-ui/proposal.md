## Why

The first Overview implementation provides correct monitoring semantics, but its vertically stacked cards make high-volume Observation sets slow to scan and push Recent Findings and Run Activity below the fold. The page should use the available desktop workspace more effectively while retaining honest failure states and the accepted separation between analytical and execution semantics.

## What Changes

- Refine the Overview into a wider desktop monitoring workspace with compact header, state summary, and a persistent insights rail.
- Add compact latest-state counts for `no_significant_findings` and `uncertain` alongside the existing total, active, significant-findings, and failed-execution counts.
- Replace large per-Observation cards with a dense, responsive, accessible monitoring table/list that preserves the same durable fields and navigation.
- Add local Observation search over the already loaded definition set with a distinct no-match state and clear-search action.
- Present Recent Findings and Run Activity beside the Observation list on wide screens so they remain visible during scanning, while stacking them predictably on narrower screens.
- Refine recent-run markers, typography, spacing, dividers, hover/focus treatment, and state feedback using existing semantic tokens and components.
- Keep the supplied target screenshot as an informative visual reference rather than a parity or acceptance requirement.
- Explicitly exclude global time-range filtering, user/avatar identity, ObservationRun `partial`, non-finding status entries in Recent Findings, and local database cleanup or compatibility changes.

## Capabilities

### New Capabilities

- `overview-monitoring-refinement`: Defines the denser Overview presentation, supplemental analytical-state counts, local Observation search, responsive desktop/compact layout, and visual-semantic constraints layered on the approved Overview monitoring capability.

### Modified Capabilities

None. The existing `overview-monitoring-ui` behavior remains authoritative and is supplemented rather than weakened or replaced.

## Impact

- Refines `frontend/src/features/overview/OverviewPage.tsx`, its projections/view models, `RunActivityChart`, and focused tests.
- May add or extract small project-owned Overview presentation components, but does not introduce another design system or table abstraction.
- Uses existing React, Tailwind CSS, semantic tokens/components, Lucide React, and Recharts dependencies; no dependency changes are required.
- Does not change backend APIs, persistence, runtime execution, polling, finding acquisition bounds, trusted deployment assumptions, or architecture documents.
- Depends on the completed `add-overview-monitoring-ui` implementation and must be integrated only after that change is made canonical or otherwise retained as its approved base.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`
- `docs/architecture/08_observation_analysis_result_contract.md`
- `docs/architecture/03_ADR_log.md` — ADR-167 (UI authority and informative visual references), ADR-168 (durable run reads), and ADR-170 (trusted MVP access boundary)
- `docs/ui/frontend_ui_stack_adr.md`
- `docs/ui/ui_implementation_handoff_v1.md` — Overview purpose, required areas, semantic tokens, project-owned components, and responsive/accessibility rules
- Approved OpenSpec change `add-overview-monitoring-ui` — prerequisite monitoring behavior and failure-state contract
