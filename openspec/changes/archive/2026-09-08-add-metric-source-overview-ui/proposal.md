## Why

Metric Lens configuration cannot proceed when the server has no configured Prometheus sources, while the existing `Data Sources` navigation is inactive and provides no explanation of the environment-managed setup. The MVP needs a safe place to show every configured Metric source and guide operators through environment configuration without moving credentials into application-managed storage.

## What Changes

- Activate the existing `Data Sources` navigation and add a `/data-sources` route within the ObserveAI shell.
- Add a read-only Metric Sources overview driven by the existing Observation-definition capabilities API.
- Show every configured Prometheus source using only its safe provider type, stable machine ID, and human-readable name.
- Provide explicit loading, retryable failure, empty, and configured-source states.
- In the empty state, explain the `PROMETHEUS_SOURCES` JSON-array contract, show placeholder-only Bearer and Basic-auth examples, and state that backend restart is required after environment changes.
- Confirm that multiple environment-configured Prometheus sources are supported and remain selectable in the existing Metric Lens editor.
- Keep source endpoints, credentials, health, and connection diagnostics out of public UI/API output.
- Add ADR-167 to supersede ADR-166's strict MagicPath authority: MagicPath becomes an informative visual reference, while accepted UI documentation and approved OpenSpec changes govern UI behavior and direction.
- Version the UI direction and living v1 handoff in place to v1.2 and reconcile architecture, repository, and UI guidance.

## Capabilities

### New Capabilities

- `metric-source-overview-ui`: Read-only visibility and environment-configuration guidance for the server-managed Prometheus source registry.

### Modified Capabilities

None.

## Impact

- Frontend shell navigation, routing, one new Data Sources feature page, the existing capabilities client/types, and focused tests.
- Architecture/UI documentation and repository instructions gain the new MVP screen, its read-only credential boundary, the approved non-binding MagicPath role, and consistent v1.2 authority language.
- Uses the existing `GET /api/v1/observation-definition-capabilities` response unchanged.
- No backend endpoint, database schema, dependency, dynamic reload, source CRUD, or secret-storage change.
- Planned on `feature/add-metric-source-overview-ui`, stacked on PR #18 until the Observation Management UI base is merged.

## Architecture References

- `docs/architecture/03_ADR_log.md`, ADR-166: the accepted frontend stack remains unchanged; ADR-167 will supersede only the strict v1.1/MagicPath source-of-truth clause.
- `docs/architecture/README.md` and `docs/architecture/12_CHANGELOG.md`: architecture package version/navigation and changelog will record ADR-167.
- `openspec/specs/prometheus-metric-provider/spec.md`: preserves server-managed source resolution and the environment-only secret boundary.
- `openspec/specs/observation-definition-api/spec.md`: consumes the existing safe capabilities projection without exposing endpoints or credentials.
- `docs/ui/frontend_ui_stack_adr.md`: uses the accepted React, Tailwind CSS, project-owned component, and Lucide stack.
- `docs/ui/ui_implementation_handoff_v1.md`: remains the living major-v1 handoff filename and is updated in place to v1.2 without changing accepted Observation Management semantics.
