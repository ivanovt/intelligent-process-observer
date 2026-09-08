## Why

Configuring every Lens and Relationship currently requires users to invent and manually validate a technical identifier in addition to entering its human-readable name. Generating these identifiers in the editor removes repetitive configuration work while preserving the existing public contract and stable aggregate references.

## What Changes

- Generate an ID for each new Metric Lens, Alert Lens, and Relationship after the user commits its initial non-empty name.
- Derive the ID from a normalized name plus a compact timestamp component so it remains readable and is unlikely to collide with another draft child.
- Present generated ID fields as read-only values and keep an ID stable after its first generation, including across later name edits.
- Preserve the existing ID unchanged when an already-applied draft child is reopened for editing.
- Evolve the frozen UI Direction from v1.1 to v1.2 for this approved Observation Management interaction and update its repository guidance during implementation.
- Bound every generated ID to the persistence-compatible maximum of 255 characters, including any collision discriminator.
- Retain current type-local Lens uniqueness, Relationship uniqueness, validation, aggregate ownership, and submission behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-management-ui`: Replace manual Lens and Relationship ID entry with one-time, name-triggered, read-only ID generation in the three nested Observation draft editors.

## Impact

- Affects the Observation draft helpers, Metric Lens editor, Alert Lens editor, Relationship editor, and their frontend tests.
- Updates `docs/ui/README.md`, `docs/ui/ui_implementation_handoff_v1.md`, `docs/ui/frontend_ui_stack_adr.md`, and current repository UI-direction guidance from v1.1 to v1.2 during implementation.
- Does not change backend APIs, persisted schemas, public identifier syntax, `docs/architecture/`, or dependencies.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`: preserves type-local Lens identity, stable Lens history correlation, and Metric-only Relationship references.
- `docs/architecture/05_relationship_evaluator_concept.md`: preserves Relationship identity and participant references.
- `docs/architecture/03_ADR_log.md` (ADR-161 and ADR-162): preserves type-aware Lens identity and the canonical Alert Lens ID primitive.
- `docs/ui/README.md`: requires an explicit UI version change for this meaningful Observation Management workflow change.
- `docs/ui/ui_implementation_handoff_v1.md`: governs the existing nested-editor identity fields and aggregate-draft interaction that UI Direction v1.2 will evolve.
- `docs/ui/frontend_ui_stack_adr.md`: contains normative current-direction declarations that must identify v1.2 while preserving the accepted frontend stack and historical v1.1 introduction context.
