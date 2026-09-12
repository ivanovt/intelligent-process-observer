## Why

The first successful end-to-end Observation run proved that durable results and reports are available, but it also exposed presentation defects that make them difficult to use: raw Markdown escapes and typed identifiers are shown directly, nested Metric evidence can render as `[object Object]`, numerical values are unformatted, and traceability references repeat internal IDs without explaining the referenced field or value. The run-detail experience should make the existing evidence understandable without changing analytical meaning.

## What Changes

- Refine deterministic Markdown rendering so report headings, identities, finding labels, references, and locator text are safe but human-readable instead of exposing reversible type encodings and pervasive escape characters.
- Preserve Copy Markdown while presenting the persisted report as a safe, formatted document view rather than raw Markdown inside a preformatted text block.
- Resolve the open MVP browser-rendering decision by adopting a dependency-free, safe renderer for the deterministic Markdown subset, with unsupported constructs retained as inert text.
- Replace generic Metric evidence enumeration with explicit semantic fields for numerical evidence and optional spike, oscillation, and stuck-signal results, including honest absent, unknown, and not-run states.
- Format numbers consistently for scanning, show relative level change as a dimensionless symmetric change rather than an ordinary percentage, and display comparison means alongside it.
- Improve Lens identity using information already present in the run result, with compact internal IDs retained as secondary traceability rather than the primary label.
- Make Evidence and Relationship references expandable or otherwise inspectable with their locator paths and resolved source values when those values are already present in the run-detail response.
- Replace persistence-oriented empty copy such as “No hypotheses were persisted” with meaning-oriented language that preserves absence semantics.
- Update the accepted UI Direction from v1.7 to v1.8 for this intentional run-detail and report presentation refinement.
- Do not add a Markdown dependency, new API field, new analytical state, severity, confidence, recommendation, inference, or backend execution behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `report-generation`: Make the existing Markdown artifact safely human-readable while preserving complete analysis membership, traceability, and presentation-only boundaries.
- `observation-runs-ui`: Refine Metric, Analysis, and Report sections into semantic, formatted, progressively disclosed views of the existing run-detail contract.

## Impact

- Affected backend areas: deterministic report Markdown rendering and its focused tests; no report-agent contract or model behavior change.
- Affected frontend areas: Run Detail Metric/Analysis/Report presentation, project-owned traceability components, formatting helpers, and tests.
- Architecture documentation: add the accepted browser-rendering decision to `docs/architecture/03_ADR_log.md`, close the corresponding renderer item in `docs/architecture/10_open_decisions_and_backlog.md`, and update the architecture README/changelog package metadata.
- UI documentation: `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` advance to UI Direction v1.8.
- Public API payloads, persisted schemas, execution/reasoning semantics, dependencies, routes, and Observation configuration remain unchanged.
- This change should land before `improve-observation-synthesis-quality` so the later prompt/evaluation work is assessed through the refined presentation surface.

## Architecture References

- `docs/architecture/08_observation_analysis_result_contract.md` — structured findings, hypotheses, limitations, and traceability remain authoritative.
- `docs/architecture/09_report_agent.md` — the report remains a human-readable Markdown presentation artifact with no new analysis.
- `docs/architecture/03_ADR_log.md` — ADR-086/087 preserve Markdown and the presentation-only Report Agent; ADR-167 governs UI authority and intentional versioning.
- `docs/architecture/10_open_decisions_and_backlog.md` — the currently open rendering-adapter item is explicitly resolved for the MVP browser Report view by this approved change.
- `docs/ui/frontend_ui_stack_adr.md` — project-owned components and the accepted dependency stack.
- `docs/ui/ui_implementation_handoff_v1.md` — current v1.7 run-detail, analysis, traceability, Metric evidence, and Report contracts.
