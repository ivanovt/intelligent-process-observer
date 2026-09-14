## Context

See `proposal.md` for motivation and the delta specs for behavior. Observation Definitions currently store `name`, `description`, and `objective`; accepted runs use a detached immutable definition snapshot. The JOIN projects a compact semantic context to three isolated Observation Reasoning invocations, then a separate minimal context to Report Generation. Create/Edit already has General, Knowledge scope, Lens, Relationship, and Review sections; General contains Name, Description, and Objective. This change adds one optional field to those existing paths.

## Goals / Non-Goals

**Goals:** Keep the operator's note stable for one run; make its model-visible role explicit; preserve the small General form and existing aggregate draft lifecycle.

**Non-Goals:** Prompt-template editing, overriding agent policies, new Lens-local context, a report background section, direct disclosure of the raw note in generated Markdown, or a change to evidence, knowledge, and retrieval contracts.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`: the note belongs to the Observation Definition aggregate, not an individual Lens.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, `docs/architecture/07_observation_reasoning_agent.md`, and ADR-065: Reasoning receives a compact semantic projection, never the complete configuration. One bounded note extends that semantic projection without admitting execution settings or provider data.
- `docs/architecture/09_report_agent.md`, ADR-085, and ADR-175: Reporting continues to receive only the analysis result, minimal semantic context, and exact frozen window. The note is presentation guidance, not an analytical input or new report item.
- `docs/architecture/08_observation_analysis_result_contract.md`: the note adds no analytical result field or evidence reference.
- `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md`: the new control remains inside the existing General section and aggregate draft. Its visual change is part of this reviewed UI proposal.

## Decisions

### One nullable aggregate field with a bounded public contract

Use `operational_context` as a nullable top-level Observation Definition field, separate from Description (what is observed) and Objective (what to evaluate). Accept omitted or `null` as absent; reject non-null blank text and values over 4,000 Unicode code points. Preserve accepted text exactly, including paragraph breaks. The bounded size keeps repeated model input proportionate while allowing a useful operator note. A single nullable `TEXT` column and migration fit the existing persistence model; existing rows read as `null`. Create and replacement responses plus detail reads expose the field; compact list summaries omit it. Keep API schema version `1` because this is an optional compatible extension.

The browser must count Unicode code points rather than JavaScript UTF-16 code units, so the same visible text passes or fails at both validation boundaries.

Alternatives considered: reuse Description or Objective, which would obscure the note's purpose; allow unbounded text, which would make per-run model input unpredictable; include the full note in list summaries, which would undermine their compact role.

### Freeze once, then project selectively

Copy the accepted value into the detached `ObservationExecutionSnapshot` at initialization. Build `ObservationSemanticContext` and `ReportSemanticContext` from that snapshot. All three Reasoning phases can see the same note; Reporting sees it after analysis has committed. Metric and Alert Lens assignments, the Knowledge Scope Suggestion request, Relationship evaluation, evidence catalog, and persisted analytical artifacts do not gain the field. Replacing the definition while a run is active leaves that run's value unchanged.

Alternatives considered: reread the current definition at each stage, which would break frozen-run consistency; inject into every agent, which would widen strict Lens contracts with little value for numerical tool selection.

### Treat context as lower-trust semantic data

The PydanticAI adapters serialize the note as a declared field in their structured model-visible requests, under system-owned instructions that limit its use to relevance, terminology, and faithful presentation. Reasoning still requires catalog-backed findings and knowledge-referenced hypotheses. Overall state still follows admitted evidence and limitations. Reporting may use the note to order or word already supplied analysis items, but the structured presentation draft and deterministic Markdown renderer remain unchanged; the raw note is not quoted or independently summarized in the report. Keep existing model request limits and retrieval budgets.

Alternatives considered: append note text to system instructions, which would grant operator text false authority; add a report section for it, which would expand the presentation contract and create a path for unsupported claims.

### Use a small optional disclosure in General

Place an `Add operational context (optional)` disclosure after Objective without adding a navigation item. A new empty draft starts collapsed; a populated edit draft starts open; when collapsed with content, its header shows a short preview. The multiline field, helper text, validation, Review, and read-only inspection preserve the full text. Client-side draft state owns the field until final aggregate create or replacement. Errors open the disclosure and identify the control. Existing form primitives and accessible disclosure behavior suffice; no UI dependency is needed.

Because this intentionally extends accepted Observation Management UX, record it as the next version of the living `docs/ui/` direction/handoff when the change is approved. That documentation update is limited to this General-field behavior and does not authorize a broader redesign.

Alternatives considered: a third always-visible textarea, which increases General's initial height; a separate section or modal, which adds navigation and save semantics for one optional value.

## Risks / Trade-offs

- Operator text may contain instructions or unsupported claims → keep it in a typed data field, retain system-owned agent policy, and evaluate adversarial examples where the note conflicts with evidence or asks for a policy change.
- Long text consumes input tokens in multiple invocations → enforce the 4,000-code-point limit at API and UI boundaries and verify request construction without changing model budgets.
- The note is sent to the configured model provider and may appear in opt-in full traces → explain model use beside the field; rely on existing backend trace access and no-secrets guidance rather than presenting it as private report content.
- A collapsed optional field may be overlooked → use an explicit action label, preview populated content, and show it in Review and read-only inspection.

## Migration Plan

Add a nullable definition column with no data rewrite or default backfill. Existing definitions expose `null`, and old create clients remain valid. Rollback can remove the unused column only through an approved migration path; any stored notes would be lost, so deployment rollback must first preserve that data if it matters.
