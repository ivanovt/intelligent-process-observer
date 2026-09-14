## Context

See `proposal.md` for the usability problem and `specs/report-generation/spec.md` for behavior. Today the strict report request carries the analysis result plus minimal Observation context, while `ObservationExecutionSnapshot` already owns the immutable UTC analysis window. A single PydanticAI request returns source-keyed presentation prose; deterministic code validates exact source membership and renders the persisted Markdown. The browser displays that Markdown through the accepted safe subset and copies the exact persisted string.

## Goals / Non-Goals

**Goals:** Preserve the narrow analysis-to-presentation boundary while making the generated artifact useful for a quick objective-led read and an exact later traceability audit. Keep one model request and renderer-owned Markdown structure.

**Non-Goals:** Change Observation analysis, add an anomaly/severity/ranking model, create a baseline, query Lens results from reporting, add recommended actions, add report variants/export, render new Markdown constructs in the browser, or rewrite existing persisted reports.

## Architecture References

- `docs/architecture/08_observation_analysis_result_contract.md`: findings, hypotheses, limitations, and their references remain the only analytical source. No new analysis field is proposed.
- `docs/architecture/09_report_agent.md` and ADR-085/ADR-087/ADR-175 in `docs/architecture/03_ADR_log.md`: the agent stays presentation-only, without Lens results, retrieval, new reasoning, or recommendations. ADR-175 approves only the immutable UTC run-window addition alongside minimal semantic context; no other run metadata is admitted.
- ADR-086 in `docs/architecture/03_ADR_log.md`: output remains one Markdown artifact with the existing minimal envelope, not a structured report schema or engineer/operator variant.
- ADR-012 in `docs/architecture/03_ADR_log.md` and `docs/architecture/01_observation_lens_concept.md`: reference periods and persisted History are descriptive context, never expected baseline or normality thresholds.
- ADR-172 in `docs/architecture/03_ADR_log.md` and `docs/ui/ui_implementation_handoff_v1.md`: the browser remains a presentation-only safe-subset view and copies persisted Markdown exactly. New output uses only headings, paragraphs, blockquotes, flat unordered lists, and inline code; no links, raw HTML, tables, nested lists, or browser-side synthesis.
- `docs/architecture/10_open_decisions_and_backlog.md`: exact engineer/operator templates remain open. This design changes the current MVP renderer's reading hierarchy, not the public report schema or variant policy.

## Decisions

### 1. Add only immutable run-window metadata to the strict request

The execution projector will copy the snapshot's exact UTC `analysis_window` into a reporting-owned, immutable start/end value. Reporting will validate UTC awareness and `start < end` before the model call. The request keeps the same source Observation/run identity correlation and rejects undeclared fields. Reporting will not import execution contracts or fetch current Observation definitions; the projector translates at the boundary.

Alternative considered: derive the window from Lens results, the current Observation definition, or persistence during rendering. Rejected because it breaks the approved narrow input and can misstate the historical run. Alternative considered: show only `generated_at`. Rejected because it answers when the artifact was created, not when the process was observed.

**Architecture alignment:** ADR-175 now extends ADR-085 only for the immutable UTC run window, and `09_report_agent.md` reflects that boundary. Implementation must reject any broader run-snapshot or analytical input. The OpenSpec planning artifacts still require their separate human approval before production edits.

### 2. Keep the model's contribution source-keyed and presentational

Extend the strict presentation draft with a conditionally required neutral English objective summary and a short source-keyed heading for each finding. Require a summary when the admitted objective is non-blank; otherwise require its absence and use a deterministic generic header. The objective summary is intent context, never evidence or a claim that the objective succeeded or failed. The model may choose the order of its exact-key finding presentations to match objective relevance; deterministic validation checks one-to-one membership, uniqueness, required text, and no undeclared fields. The renderer enumerates that validated order and creates report-local finding numbers. A finding heading remains plain escaped text inside a renderer-owned heading line; the model cannot supply Markdown structure. Existing one-request, no-tool, no-retry policy remains unchanged.

The prompt/evaluation guidance will require objective evidence first, material auxiliary events second, concise current-observation-first finding prose, preservation of material conflicts, and source-only quantitative claims. It will not introduce a severity score, ranking field, anomaly category, or deterministic keyword classifier. Semantic faithfulness remains subject to representative adversarial evaluation rather than a claim of runtime proof.

Alternative considered: derive titles and relevance by parsing prose or fetching Lens data in the renderer. Rejected because parsing is unreliable and the latter violates the input boundary. Alternative considered: add structured relevance/severity fields to `ObservationAnalysisResult`. Rejected because this is a report-presentation change and the accepted analytical contract intentionally excludes those fields.

### 3. Render a layered but schema-flexible report

The current renderer will place a human-oriented header and evidence-only overall assessment first, then numbered findings, possible explanations, limitations, and a final technical appendix. These are deterministic layout choices for the current output; they do not define an engineer/operator variant or require one exact heading spelling in the public envelope. The header uses a neutral objective summary when supplied, exact unrounded UTC start/end (full dates on both sides), and an eight-hex-character Observation UUID prefix only as an orientation cue. Technical details retain full Observation/run IDs, exact source overall state, and generated time. The source overall state also gets a fixed English display label in the opening; execution status is not inferred from it.

The renderer derives a one-to-one map from displayed finding number to exact source finding ID. Hypothesis `supported_by` values become readable finding numbers beside the possible explanation; exact source IDs remain in the appendix. Each hypothesis remains a separate possible explanation. Empty hypotheses and limitations keep the existing careful meaning. The final appendix groups evidence under the owning finding and then exact `(source_type, source_id)` pair, lists every locator in source order including repeated entries, and keeps hypothesis knowledge references in separate groups. A source pair is repeated across different findings when both own references to it; ownership takes precedence over global deduplication.

Alternative considered: a global source-only index. Rejected because it makes the finding-to-evidence chain harder to follow. Alternative considered: interactive or linked cross-references. Rejected because the persisted Markdown/browser safe subset does not support active links or disclosures in report content. Alternative considered: labelled current/reference/history fields for every finding. Rejected because findings can come from different Lens and Relationship sources and the current source item is prose, not a uniform Metric fact schema.

### 4. Reduce visible escapes without ceding Markdown structure

Replace blanket punctuation escaping for ordinary presentation prose with context-sensitive encoding of only Markdown/HTML-active syntax. Continue normalizing structural whitespace and rejecting non-renderable controls. Renderer-owned block prefixes and code fences remain deterministic; opaque IDs and locators use the existing exact inert inline-code representation. Tests will check both the persisted raw string and the browser's safe-subset rendering, including hostile headings, lists, links, HTML-like text, backticks, and control characters. Some defensive escapes may remain for hostile syntax; normal metric names, decimals, timestamps, commas, parentheses, and internal hyphens should not acquire visible backslashes.

Alternative considered: strip escape characters in the browser or Copy action. Rejected because Copy must preserve exact persisted content and browser rewriting would create a second artifact. Alternative considered: allow model-authored Markdown or add a general Markdown dependency. Rejected because both expand the trust and rendering boundary.

## Risks / Trade-offs

- [The implementation admits more run context than ADR-175] → Keep the reporting-owned request to exact UTC window boundaries plus the existing semantic context and reject undeclared fields.
- [A model-created title or objective summary misstates source meaning] → Keep source-keyed strict fields, explicit prompt constraints, and representative adversarial tests; do not claim deterministic semantic proof or silently repair text.
- [Objective-led ordering appears to assign severity] → Use reading order only, no priority labels or source-state changes; validate complete exact-key coverage and retain material contrasts.
- [Appendix compaction loses a locator or source owner] → Build groups from immutable source references, preserve multiplicity and order, and test multi-source and repeated-reference cases.
- [Less escaping enables Markdown injection] → Keep renderer-owned structure and untrusted text inert in both copied Markdown and the safe browser view; test hostile content before changing the escape policy.
- [Persisted old reports differ visually from new ones] → Leave persisted strings untouched. The browser renderer continues to support its accepted subset for both generations.

## Migration Plan

No data migration or public API change is needed. After explicit OpenSpec approval, deploy the new report request/presentation and renderer together. New runs produce the new Markdown; old persisted reports retain their original content. Rollback restores the prior generator for future runs without rewriting old artifacts.
