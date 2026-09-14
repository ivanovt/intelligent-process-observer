## Why

The Run Detail Metrics section currently stacks complete Metric results in long cards. Comparing several Lens outcomes and finding the evidence for one selected Lens requires too much scanning, especially when some results are partial or failed. The supplied mock proposes a compact list with a focused detail pane; this change defines that UX against the existing public result contract.

## What Changes

- Replace the Metrics section's stacked cards with a responsive, single-selection Metric Lens list and an in-section detail pane.
- Make each list item scannable through frozen Metric identity, Lens execution status, data quality when available, current semantic state and numerical evidence when usable, and explicit limitations when evidence is unavailable.
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
