## Why

Operators currently have separate Observation-definition and run-history views, but no single monitoring surface that summarizes the latest durable state of every Observation. The accepted UI direction calls for an Overview where users can quickly distinguish active work, significant findings, uncertainty, unavailable analysis, and execution failures without conflating those concepts.

## What Changes

- Activate a top-level Overview route as the application's monitoring entry point.
- Present a latest-state summary across all Observation definitions, including never-run Observations and independent analytical and execution state counts.
- Show a scan-oriented Observation list with definition context, latest run state, duration, and recent run-state history.
- Surface recent Observation-level findings with direct navigation to their source run.
- Visualize recent run activity without introducing severity, confidence, recommendation, or inferred health semantics.
- Keep the page current through manual refresh and polling while active runs exist, with explicit loading, empty, partial-data, and stale-data behavior.
- Add the already architecture-approved Recharts visualization dependency within this feature's explicit implementation scope.

## Capabilities

### New Capabilities

- `overview-monitoring-ui`: Defines the Overview route, its derived monitoring snapshot, summary cards, Observation rows, recent findings, run activity, navigation, refresh behavior, and honest unavailable states.

### Modified Capabilities

None.

## Impact

- Frontend routing and shell navigation will make `/overview` available and use it as the default application route.
- A new `features/overview` composition will reuse the existing Observation-definition list and Observation-run list/detail APIs and existing semantic status components.
- `frontend/package.json` and its lockfile will add Recharts with intended range `^3.10.1`; no alternative visual framework is introduced.
- The change does not alter backend contracts, persistence, execution behavior, or the trusted single-user/internal deployment boundary.

### Dependency Proposal

- **Dependency and range:** `recharts@^3.10.1`.
- **Why needed:** UI Direction v1.6 names `RunActivityChart`, and the accepted frontend stack requires project-owned charts to wrap Recharts.
- **Problem solved:** It supplies the accessible React chart primitives needed for the bounded Run Activity visualization while keeping chart-library details out of feature code.
- **Can this reasonably be implemented without it?** A custom HTML/CSS visualization is technically possible, but it would bypass the accepted chart stack and create project-owned chart mechanics unnecessarily. A plain list would not satisfy the accepted chart direction.
- **Stack impact:** This activates an already accepted part of the frontend visual stack; it does not replace React, Tailwind, shadcn/ui/Base UI, or any other dependency. The manifest and lockfile must not be changed until this dependency proposal is explicitly approved.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`
- `docs/architecture/08_observation_analysis_result_contract.md`
- `docs/architecture/03_ADR_log.md` — ADR-167 (UI authority), ADR-168 (on-demand execution/read semantics), and ADR-170 (trusted MVP access boundary)
- `docs/ui/frontend_ui_stack_adr.md`
- `docs/ui/ui_implementation_handoff_v1.md` — UI Direction v1.6, especially Overview, state, refresh, and component guidance
