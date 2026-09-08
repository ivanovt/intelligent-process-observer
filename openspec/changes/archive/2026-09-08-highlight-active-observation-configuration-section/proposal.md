## Why

The sticky Create Observation configuration navigation does not communicate which part of the long aggregate form the user is currently viewing. Highlighting the active section will improve orientation during click navigation and manual scrolling.

## What Changes

- Add a distinct selected state for the active Create Observation configuration item.
- Select `General` when the page initially opens or is scrolled to the top.
- Update the selected item immediately when a configuration navigation link is activated.
- Update the selected item as the corresponding form section becomes current during scrolling, including selecting `Review` at the bottom of the form.
- Expose the active item to assistive technology while preserving the existing section anchors and aggregate behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-management-ui`: Add active-section feedback to the Create Observation aggregate configuration navigation.

## Impact

- Frontend-only changes in the Create Observation page and its focused component tests.
- No API, persistence, dependency, routing, Observation draft, or domain-contract changes.

## Architecture References

- `docs/architecture/`: N/A — the change is limited to local navigation feedback and does not alter Observation, Lens, Relationship, runtime, or persistence semantics.
- `docs/ui/ui_implementation_handoff_v1.md`: preserves the General, Metric lenses, Alert lenses, Relationships, and Review aggregate sections.
- `docs/ui/frontend_ui_stack_adr.md`: remains within the accepted React, Tailwind CSS, and project-owned component stack.
