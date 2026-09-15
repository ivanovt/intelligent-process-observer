## Why

The baseline Run Detail Metrics section stacks complete Metric results in long cards, making several Lens outcomes hard to compare. This change establishes the mock's scannable, selectable card layout. Its remaining responsive gap is that the selected detail scrolls away with the page at ordinary desktop widths where the current split layout has not yet activated.

## What Changes

- Replace the Metrics section's stacked cards with a responsive Metric Lens card list. The detail pane starts closed, opens only after explicit card selection, and closes when dismissed.
- Keep an open detail pane viewport-anchored beside the scrolling cards at usable desktop widths, including approximately 1200px windows; bound its height and allow its own evidence to scroll without stopping page/card-list scrolling.
- Make the cards substantially wider and scannable in the supplied mock's order: identity and execution status; start/duration; a distinct semantic-state band; then numerical and reference/History summary fields. Add meaning-aligned icons while keeping text as the source of meaning.
- Present the selected result's current state and numerical evidence, optional analyses, reference-period comparisons, and persisted History as distinct groups. Preserve the meanings and availability boundaries of the existing schema-1.0 result.
- Preserve the current run-detail refresh lifecycle and selected Lens across successful updates. Provide a clearly named link from the selected Lens to the existing Observation-level Analysis section.
- Exclude the mock's Time series and JSON tabs. Omit the Logs tab because operational logs have no approved browser-facing source and remain backend-only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-runs-ui`: Refine how the run-detail Metrics section selects, summarizes, and inspects Metric Lens results using only the existing durable run-detail response.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — Metric current, reference-period, and persisted-History perspectives.
- `docs/architecture/03_ADR_log.md` — ADR-031 through ADR-041 for structured Metric evidence and independent status/data quality; ADR-167 for UI authority; ADR-171 for backend-only operational logs.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — public run-detail projection and usable, partial, failed, and unavailable result boundaries.
- `docs/ui/frontend_ui_stack_adr.md` and `docs/ui/ui_implementation_handoff_v1.md` — accepted component stack and Run Detail presentation rules.

## Impact

- Frontend Run Detail Metrics presentation, selection/refresh behavior, responsive layout, and focused UI tests.
- No API, result schema, persistence, dependency, provider acquisition, logging, execution, or analytical-semantics change.
