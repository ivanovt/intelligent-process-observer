## Context

See [proposal.md](proposal.md) for the problem and [the delta spec](specs/observation-runs-ui/spec.md) for acceptance behavior. The `/runs/{observationRunId}` page loads one strict durable `ObservationRunDetail` and keeps six top-level sections. The first implementation of this change introduced a Metric list/detail view, but initializes selection to the first Lens, gives the detail more width than the cards, and renders card semantics as compact text. `metricPresentation.tsx` already formats the accepted schema-1.0 evidence. The run-detail response does not contain a Lens display name, raw current samples, raw historical sequences, or operational logs; it does contain the frozen Metric reference and unit on a produced Metric artifact.

## Goals / Non-Goals

**Goals:** Make multiple Metric outcomes easy to scan and one outcome easy to inspect while reusing the current run response and status/quality semantics. Preserve the existing six-section Run Detail navigation and polling behavior.

**Non-Goals:** New retrieval paths, provider refetching, a separate Metric route, charts, diagnostic/log viewing, JSON inspection, or a separate Lens-level narrative analysis.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`, sections 6–7, and `docs/architecture/03_ADR_log.md`, ADR-031–041: current state, reference periods, and persisted History are independent; failed and insufficient results lack usable numerical/semantic evidence. The presentation will branch on the exact result variant before reading fields.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, section 3, and `openspec/specs/observation-run-api/spec.md`: Run Detail is one safe, coherent snapshot; the UI reads that snapshot only and does not join a mutable definition or expose undeclared data.
- `docs/architecture/03_ADR_log.md`, ADR-167 and ADR-171; `docs/ui/frontend_ui_stack_adr.md`; `docs/ui/ui_implementation_handoff_v1.md`, Run Detail v1.8: project-owned components/tokens govern presentation, and operational logs stay backend-only. The mock guides layout but does not override those boundaries.

## Decisions

### Keep the list and detail inside the existing Metrics section

Replace only the Metrics section's stacked-card composition. Keep the existing run header and top-level Summary/Metrics/Alerts/Relationships/Analysis/Report navigation. Before selection, the card list uses the available section width and the detail pane is absent. After explicit card selection, use a two-column list/detail layout where space permits, giving the card column approximately three-fifths to two-thirds of the width and the pane the remainder, with a stacked layout at narrow widths. The pane's own numerical and optional-analysis grids must remain readable at its narrower column width rather than relying only on viewport breakpoints. The selected detail is an in-page region, not a modal or new route, so the user retains run context. A separate Metric route would add URL and data-loading behavior without an approved contract need.

### Identify Lens items from immutable run data

Filter `lens_runs` by `lens_type=metric` in response order. Use the stable LensRun UUID for selection and keys. A produced Metric artifact supplies `identity.metric_ref`, `unit`, and `lens_id`; when there is no artifact, show the wrapper `lens_id`. Do not load the current Observation Definition to retrieve `name`: it can differ from the frozen run. Long provider references need wrapping or truncation with full text accessible. The list count describes Metric Lenses rather than asserting that all were analyzed.

### Open detail only by explicit card selection

Store the selected LensRun ID locally to the Metrics section and initialize it to no selection. A card button sets one ID and opens the pane; a close button clears it. Refresh keeps a selected ID only while it appears in the newest response, and clears it if absent. With no selection, refresh never opens the pane. This avoids index-based selection drift and meets the mock's closed-by-default interaction without an empty placeholder occupying the pane's width. The run identity still resets local selection.

### Build summaries by result variant, not visual color

The wrapper status is the execution-status source. A usable good/degraded result can supply quality, current trend/variability, and numerical evidence. A completed-insufficient result supplies quality but no mandatory current evidence. A failed result supplies frozen identity and safe error; a null result supplies only wrapper identity/status/reason. Partial status retains usable evidence and its structured limitation. Compose each wide card in the mock's order: identity/quality/status row, start/duration, semantic-state band with separately labelled direction/rate/variability, then a compact evidence strip ordered mean, min–max range, slope, returned reference availability, and persisted-History direction/pattern. The header reports zero/one selected without calling every Lens analyzed. For non-usable variants, the semantic band explicitly says unavailable and the card presents the supported reason instead of fabricated evidence. Use existing semantic tokens, textual badges, and a small consistent set of Lucide icons for a leading trend/failure cue plus inline trend/availability cues, all `aria-hidden` with adjacent text. Do not derive Observation analytical state from a Lens outcome. A generic placeholder card that renders missing fields as zero or `unknown` was rejected because it would invent analysis.

### Recompose existing Metric evidence without new interpretations

Reuse `formatMetricNumber` and the type-aware optional evidence rendering, while moving the existing distinct evidence groups into the selected detail. Reference rows are driven only by returned evidence/comparison pairs; a partial `reference_unavailable` reason can explain a gap, but the API does not identify the missing configured offset. Show the exact returned offset and window and label `relative_level_change` as symmetric relative change. History uses its aggregate descriptors, `run_ids.length`, and accepted transition counts; do not synthesize a historical series. Null optional sections remain merely unavailable in this result.

### Reuse the run refresh and Analysis section

The existing sequential polling hook remains the only run-detail loader. The Metrics “Last updated” label records the client time of the most recent successful response and remains unchanged on a failed refresh; it is not the analytical `generated_at`. The existing stale-data notice remains visible on refresh failure. `View Observation analysis` switches the parent section to Analysis for the same loaded run, preserving the distinction between Metric evidence and Observation-level findings/hypotheses. The mock's Time series and JSON tabs are excluded by user direction; Logs is excluded because ADR-171 and the current run API provide no browser-facing log source.

## Risks / Trade-offs

- [A dense list can become hard to scan with long metric references] → Give the frozen reference a bounded visual treatment and accessible full text; keep Lens ID visible for traceability.
- [More detail in wider cards could still crowd the selected split view] → Keep the card column wider than the pane and let semantic/evidence rows wrap at narrow widths without changing their reading order.
- [A partial result can be mistaken for failed acquisition] → Place execution status, data quality, current evidence, and the structured limitation in distinct, text-labelled positions.
- [Missing reference offsets cannot be named] → Show only returned comparisons and a general supported limitation, never a guessed offset or value.
- [Selection can drift during polling] → Track the LensRun UUID and derive the selected item from each coherent response.
- [A split view may crowd smaller screens] → Stack the list and selected detail without omitting evidence, and keep selection controls keyboard accessible.

## Migration Plan

Deploy as a frontend-only presentation change. Existing stored runs and the unchanged schema-1.0 API remain compatible. Roll back by restoring the previous Metrics section presentation; no data migration or cleanup is needed.
