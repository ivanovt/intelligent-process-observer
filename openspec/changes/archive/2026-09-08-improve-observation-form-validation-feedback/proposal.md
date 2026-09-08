## Why

Observation configuration errors are currently rendered mostly as small red text, making blocking problems easy to miss and causing aggregate conditions to appear as duplicated warning and error messages. A consistent validation-feedback hierarchy will make Create and nested Apply flows easier to scan, correct, and use with assistive technology.

## What Changes

- Visually distinguish invalid controls using an error border/focus treatment plus an icon-and-text field message while keeping persistent field guidance visible.
- Present one focused validation summary after an invalid Create or Apply attempt, with issue count and links to the affected fields or sections where navigation is available.
- Show blocking issue counts in the sticky Create Observation configuration navigation without conflating issue state with the currently selected section.
- Consolidate the sticky Definition Summary so an unmet Lens requirement is shown once as incomplete configuration before submission and once as a blocking validation state after an invalid submission, without duplicate raw messages.
- Standardize information, warning, error, and success notices with consistent Lucide icons, semantic colors, and accessible roles.
- Keep backend/transport failures prominent, retain the draft, and associate field-specific API errors with both their field and the validation summary.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-management-ui`: Improve validation, limitation, status, and failure feedback across Create Observation and the Metric Lens, Alert Lens, and Relationship Apply forms.

## Impact

- Frontend project-owned form and notice primitives, Create Observation composition, nested configuration editors, and focused tests.
- Builds on the completed active-section navigation from `highlight-active-observation-configuration-section` for section issue indicators.
- No backend API, persistence, domain contract, dependency, routing, or Observation lifecycle change.

## Architecture References

- `docs/architecture/`: N/A — the change only presents already-defined validation and transport outcomes; it does not alter Observation, Lens, Relationship, execution, or persistence semantics.
- `docs/ui/ui_implementation_handoff_v1.md`: preserves local validation, aggregate review, nested Apply behavior, and final aggregate Create behavior.
- `docs/ui/frontend_ui_stack_adr.md`: uses existing semantic tokens, project-owned primitives, and Lucide React without changing dependencies.
