## Why

Generated Metric Lens, Alert Lens, and Relationship IDs currently occupy full read-only form controls even though users cannot edit them, which gives system metadata the same visual weight as user-authored identity fields. The generated values also do not identify their child type, making IDs less immediately understandable in drafts, persisted definitions, and runtime traceability.

## What Changes

- Generate new UI-owned child IDs in the form `<type>_<normalized-name>_<random-part>`, using the fixed type prefixes `metr`, `alrt`, and `rel` for Metric Lenses, Alert Lenses, and Relationships respectively.
- Keep each generated ID stable after its first generation, preserve the existing identifier grammar and 255-character limit, and keep collision handling within the accepted type-local or Relationship-local uniqueness scope.
- Remove the separate read-only ID input from each child editor and present the generated ID as secondary, non-editable identity text adjacent to the Name field, using wording such as `(id: metr_cooling_pressure_a1b2c3d4)` after generation.
- Preserve existing draft and persisted child IDs unchanged when reopening or displaying an existing child; the new typed format applies only when the UI generates a new ID.
- Advance the accepted UI direction to document this intentional identity-presentation and generation refinement.
- Do not tighten the backend API identifier grammar, migrate persisted data, alter aggregate ownership, or add standalone Lens or Relationship operations.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-management-ui`: Refine generated Observation-child ID composition and replace read-only ID controls with compact, accessible identity metadata beside the editable Name field.

## Impact

- Frontend Observation draft ID generation, Metric Lens editor, Alert Lens editor, Relationship editor, and their focused tests.
- Accepted UI direction and developer-facing UI documentation.
- No backend API, persistence schema, migration, dependency, runtime behavior, or existing persisted identity changes.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — aggregate-owned Lens/Relationship identity, type-local Lens uniqueness, and type-aware runtime identity.
- `docs/architecture/03_ADR_log.md` — ADR-167 authority order for intentional UI evolution.
