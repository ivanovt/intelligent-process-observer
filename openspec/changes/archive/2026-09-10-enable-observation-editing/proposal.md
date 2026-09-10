## Why

Engineers can create and inspect Observation Definitions, but cannot adapt an existing definition when monitored metrics, alert selection, analytical objectives, or relationships change. Requiring a replacement Observation for every configuration adjustment fragments operational continuity and makes routine maintenance unnecessarily difficult.

## What Changes

- Add an aggregate update operation for an existing Observation Definition while preserving its stable Observation identity.
- Apply full snapshot/replacement semantics to Observation metadata, ordered Metric Lenses, ordered Alert Lenses, and ordered Relationships, with the same validation and atomicity guarantees as creation.
- Keep child resources aggregate-owned: editing, adding, reordering, or removing Lenses and Relationships occurs only through the parent Observation update, never standalone child CRUD.
- Add an Edit action and an aggregate edit flow that loads the persisted definition into a client draft, reuses the existing nested editors, and submits one final update request.
- Preserve existing child IDs while editing a child, generate IDs only for newly added children, and allow removal/re-addition when a new child identity and fresh identity-scoped history are intended.
- Make successful edits apply only to future Observation Runs; already initialized and historical runs retain their frozen runtime data and artifacts.
- Keep Observation deletion, Log Lens configuration, standalone Lens lifecycle, and unrelated monitoring/run-analysis changes out of scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-definition-api`: Add atomic full replacement of an existing Observation Definition aggregate and define its identity, validation, not-found, persistence, and run-isolation behavior.
- `observation-management-ui`: Add discoverable editing, persisted-draft initialization, nested child add/edit/remove behavior, final update submission, cancellation, validation, and success/error feedback.

## Impact

- Backend Observation contracts, FastAPI routes, service, repository persistence, and API/integration tests.
- Frontend Observation routes, API client/types, draft lifecycle, definition list/detail actions, shared create/edit form and nested editors, and UI tests.
- The public API gains an Observation aggregate update endpoint; existing create/read and run endpoints remain compatible.
- No dependency changes are required.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — Observation aggregate ownership and required snapshot/replacement semantics for future updates.
- `docs/architecture/03_ADR_log.md` — ADR-161 and ADR-163 define nested type-specific Lens ownership, atomic replacement, and physical removal of omitted Alert Lens rows.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — immutable runtime lifecycle and persistence boundaries.
- `openspec/specs/observation-execution/spec.md` — a run loads the definition once and remains isolated from later supported definition mutation.
