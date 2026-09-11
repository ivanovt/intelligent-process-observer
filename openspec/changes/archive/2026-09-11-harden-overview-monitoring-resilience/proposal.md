## Why

The refined Overview is closer to the target density, but its desktop column minimums overflow the primary panel and its current color/icon treatment remains heavier and less scannable than the accepted visual direction. More importantly, one invalid legacy ObservationRun makes the strict history endpoint fail as a whole, leaving every runtime-dependent Overview section unavailable even when other definitions and runs are usable.

## What Changes

- Add a dedicated read-only Overview runtime projection that returns each persisted run as either a validated summary or an explicit safe limited placeholder for client-side joining with configured Observations.
- Preserve the existing strict `GET /api/v1/observation-runs` and run-detail fail-closed contracts unchanged.
- Let invalid or incomplete runtime records degrade only the affected Overview row/marker and report aggregate limitations instead of hiding every valid monitoring result.
- Keep analytical and execution counts limited to validated latest-run values; add an explicit unavailable-runtime count so excluded state is visible rather than silently omitted.
- Continue showing definitions, valid runs, valid findings, and valid activity when other runtime records are unavailable or inconsistent.
- Correct the desktop grid so headers and rows share one non-overflowing column definition, remove the redundant Action heading, and use an icon-only row affordance with an accessible label.
- Move summary cards toward the supplied reference: neutral surfaces, semantic value/icon accents, and restrained unavailable styling instead of full-card success/warning/error fills.
- Add safe composition-derived Observation icons (`metric`, `alert`, `mixed`, or unavailable/legacy) without inventing domain categories or health meaning.
- Retain exact supported ObservationRun states; do not add `partial`, global time filtering, user identity, fabricated findings, or local data mutation.

## Capabilities

### New Capabilities

- `overview-runtime-projection`: Defines a safe, resilient, read-only public projection for Overview monitoring with per-record availability and aggregate limitations.

### Modified Capabilities

- `overview-monitoring-ui`: Changes Overview data loading and partial-result behavior so validated monitoring data remains usable when other runtime records are invalid.
- `overview-monitoring-refinement`: Corrects desktop column geometry and refines icons, surfaces, and semantic color application to match the intended monitoring hierarchy.

## Impact

- Adds one backend read contract, repository projection, service, and `GET /api/v1/overview-runtime` endpoint with focused unit/API/integration coverage.
- Updates the Overview frontend API/types, projections, coordinator, visual components, and tests to consume the resilient contract.
- Leaves the strict run list/detail APIs, persistence schema, stored records, execution lifecycle, and failure semantics unchanged.
- Requires no migration and does not delete, rewrite, or synthesize legacy runtime data.
- Requires no new dependency; existing React, Tailwind, Lucide, and Recharts foundations remain.
- The change is based on the current PR branch and should update PR #26 only after approval and implementation review.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`
- `docs/architecture/08_observation_analysis_result_contract.md`
- `docs/architecture/03_ADR_log.md` — ADR-167, ADR-168, and ADR-170
- `docs/ui/frontend_ui_stack_adr.md`
- `docs/ui/ui_implementation_handoff_v1.md`
- `openspec/specs/observation-run-api/spec.md`
- `openspec/specs/overview-monitoring-ui/spec.md`
- `openspec/specs/overview-monitoring-refinement/spec.md`
