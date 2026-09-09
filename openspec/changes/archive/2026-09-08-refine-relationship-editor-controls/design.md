## Context

See `proposal.md` for motivation and `specs/observation-management-ui/spec.md` for observable behavior. The current Relationship editor places `Cancel` and `Apply changes` in the page header, rule guidance in a separate right-hand card, row removal in text-labeled ghost buttons, and add-row actions in link-like native buttons. The form can extend well below the viewport as descriptor rows are added.

The change must use the accepted React, Tailwind CSS 4, project-owned UI components, and Lucide React stack. It must preserve editor-local state, validation focus/error associations, Observation aggregate ownership, and the existing draft-only `Apply changes` behavior.

## Goals / Non-Goals

**Goals:**

- Create one coherent responsive action-and-guidance rail for Relationship editing.
- Keep the rail available during desktop form scrolling without covering editable content.
- Improve repeated row-action hierarchy while preserving keyboard and assistive-technology usability.
- Reuse the existing project-owned `Button` abstraction and installed Lucide icon set.

**Non-Goals:**

- Changing Relationship fields, validation rules, row defaults, ordering, or descriptor vocabulary.
- Changing `Cancel`, browser-back, `Apply changes`, or final Observation submission semantics.
- Applying the same layout to Metric Lens, Alert Lens, or other screens in this change.
- Adding a new primitive, dependency, persistence operation, or responsive navigation pattern.

## Decisions

### 1. Combine actions and semantics into the existing responsive side rail

Move the existing action group into the same rail as the Rule semantics card. In the wide two-column layout, make that rail self-starting and sticky beneath the shared application header. Keep the sticky behavior scoped to the rail and the existing desktop breakpoint so the primary form column continues to own document height and scroll.

On narrower layouts, render the rail near the editor heading in normal document flow. This avoids a viewport-fixed overlay, content occlusion, and extra bottom padding calculations. The two actions remain adjacent and keep their existing visual priority: secondary `Cancel`, primary `Apply changes`.

Alternative considered: a viewport-fixed panel or universal fixed bottom bar. This was rejected because it can obscure content, requires shell-height and safe-area coordination, and adds complexity outside the requested desktop form refinement.

### 2. Use Lucide icon-only removal controls with stable accessible names

Use an existing destructive/removal icon from Lucide React inside the project-owned ghost-style `Button`. Preserve the current section-specific `aria-label` (`Remove When — conditions row` or `Remove Expect — evaluated when applicable row`) and hide the decorative icon from assistive technology. Give the control a compact square hit area while retaining the `Button` component's focus-visible behavior.

Alternative considered: retaining visible `Remove` text beside an icon. This would not achieve the requested compact row layout and would continue to compete visually with the three select fields.

### 3. Render add-row actions through the project-owned Button component

Replace the link-like native add controls with compact secondary/outlined `Button` controls. Include a decorative plus icon while keeping the visible `Add condition` and `Add expectation` text and button semantics. The existing `onAdd` callbacks and row defaults remain unchanged.

Alternative considered: styling the native buttons directly. Reusing the project-owned component keeps hover, focus, sizing, and disabled-state behavior aligned with the rest of the accepted interface.

### 4. Verify behavior at component and responsive-presentation levels

Update component tests to assert the combined rail, action roles and accessible names, icon-only removal presentation, and unchanged add/remove/apply/cancel behavior. Because the current unit environment does not calculate browser sticky positioning, supplement automated tests with a focused manual check at wide and narrow viewport sizes; retain `make check` as the final repository verification.

## Risks / Trade-offs

- **[Sticky positioning conflicts with the shared shell header]** → Use a breakpoint-scoped top offset aligned with the shell and verify that the rail remains fully reachable while scrolling.
- **[The rail is taller than a short viewport]** → Keep the rail content compact and avoid nested scrolling; normal document scrolling still allows all rail content to be reached.
- **[Icon-only removal becomes ambiguous]** → Retain section-specific accessible names, visible focus treatment, and a conventional removal icon.
- **[Responsive source order places actions too late]** → Keep the rail near the heading on narrow layouts and use layout ordering only for the wide two-column arrangement.

## Migration Plan

No data or API migration is required. Deploy the frontend presentation change with its tests; rollback is a direct revert of the Relationship editor layout/control changes.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`: the design leaves Relationship ownership, participants, and rule semantics unchanged.
- `docs/architecture/05_relationship_evaluator_concept.md`: the design does not change deterministic descriptor behavior or introduce a rule DSL.
- `docs/architecture/03_ADR_log.md` (ADR-167): this approved OpenSpec delta records the intentional UI evolution without treating the MagicPath reference as an acceptance gate.
- `docs/ui/frontend_ui_stack_adr.md`: the design stays within the accepted visual stack and project-owned component boundary.
- `docs/ui/ui_implementation_handoff_v1.md`: the design preserves nested-editor draft semantics and the accepted Relationship Configuration structure.
