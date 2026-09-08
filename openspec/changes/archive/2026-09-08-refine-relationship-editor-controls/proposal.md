## Why

The Relationship Configuration form can become long enough that its primary actions and supporting rule guidance scroll out of view, while its repeated row actions currently have weak visual hierarchy. Refining these controls will keep the editor efficient and understandable without changing Relationship semantics or Observation draft behavior.

## What Changes

- Keep the Relationship editor's desktop action-and-guidance rail visible while the form content scrolls, including `Cancel`, `Apply changes`, and the existing rule-semantics guidance.
- Preserve a responsive layout that does not obscure or compress form content when a sticky side rail is not appropriate.
- Replace each text `Remove` row action in the When and Expect sections with a compact icon-only action that retains an accessible name and usable focus/interaction states.
- Present `Add condition` and `Add expectation` as recognizable secondary buttons rather than link-like text while preserving their existing row-creation behavior.
- Preserve all current validation, draft ownership, navigation, and no-write-until-final-create semantics.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-management-ui`: Refine the visible and accessible interaction behavior of Relationship editor actions for long forms and repeated descriptor rows.

## Impact

- Frontend Relationship editor layout and controls under `frontend/src/features/observations/`.
- Relationship editor component tests and responsive/sticky presentation verification.
- No backend, public API, persistence, architecture, dependency, or database changes.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — Relationship aggregate ownership, Metric-only participation, and constrained current-state rule semantics.
- `docs/architecture/05_relationship_evaluator_concept.md` — deterministic Relationship rule boundaries and accepted descriptors.
- `docs/architecture/03_ADR_log.md` (ADR-167) — accepted UI authority model and approval requirement for intentional visual evolution.
- `docs/ui/frontend_ui_stack_adr.md` — accepted frontend visual stack and project-owned UI direction.
- `docs/ui/ui_implementation_handoff_v1.md` — accepted Observation Management nested-editor and Relationship Configuration behavior.
