## Why

Operators know process conditions and terminology that are not captured by an Observation's short description, analytical objective, or Lens definitions. An optional Observation-level note can help system-level reasoning and report presentation focus on the intended operational meaning while preserving evidence-grounded conclusions.

## What Changes

- Add optional `operational_context` free text to the Observation Definition create, replace, and canonical read surfaces. Existing definitions remain valid without it.
- Freeze the accepted text with each Observation Run and project it into the compact semantic inputs of Observation Reasoning and Report Generation only.
- Use the text as operator-supplied relevance and presentation context, never as observed evidence, trusted system instructions, a new knowledge source, or authority to change agent boundaries.
- Add a compact optional disclosure after Objective in Create/Edit Observation. Show a preview when populated and the complete value in definition review and read-only inspection.
- Keep Metric and Alert Lens agent inputs, the configuration-time Knowledge Scope Suggestion Agent, outputs, retrieval budgets, and report structure unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-definition-api`: validate, persist, replace, and read the optional aggregate field.
- `observation-execution`: freeze the field per run and project it only to the approved downstream agents.
- `observation-reasoning`: admit the field in compact semantic context without weakening evidence and knowledge grounding.
- `report-generation`: admit the field as presentation context without adding analytical claims or exposing raw operator text in the report.
- `observation-management-ui`: edit and review the optional field within the existing aggregate flow.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — Observation Definition ownership and meaning.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — compact reasoning and report input projections.
- `docs/architecture/07_observation_reasoning_agent.md` and ADR-065 in `docs/architecture/03_ADR_log.md` — semantic reasoning context and evidence boundaries.
- `docs/architecture/09_report_agent.md` and ADR-085/ADR-175 in `docs/architecture/03_ADR_log.md` — minimal report input and presentation-only role.
- `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` — accepted Observation Management UX and versioned UI direction.

## Impact

Observation API and persistence gain one nullable text field and migration; run snapshot and the two framework-neutral agent inputs gain one optional semantic field. The Create/Edit, Review, and definition inspection UI gain a small aggregate-owned control. No dependency change, new endpoint, Lens contract change, or new analytical result/report section is proposed.
