## Why

The MVP has a production Observation Definition create/read API but only a bootstrap frontend, so users cannot yet find definitions or create a validated Observation aggregate through the frozen UI Direction v1.1 flow. This first production UI feature establishes only the shared frontend foundation needed to deliver Observation Management without pulling later monitoring and run-analysis screens into scope.

## What Changes

- Replace the bootstrap page with the frozen ObserveAI application shell and route Observation Management under the existing `Observations` product area.
- Add a production Observation definitions list with client-side search, loading/error/empty behavior, `New Observation`, and `Open`; show only definition composition supplied by the current list API, omitting unsupported latest-runtime columns and filters and all Edit/Delete actions.
- Add one local Observation draft flow with General, Metric lenses, Alert lenses, Relationships, and Review sections; nested Cancel leaves the draft unchanged, while `Apply changes` updates only the draft and performs no Lens or Relationship API write.
- Add Metric Lens configuration for the current public API shape, including one metric per Lens, source/query/unit data, the currently accepted `spike | drift | oscillation` objective vocabulary, and ordered reference periods. Free-text Metric objectives and persisted-history configuration remain explicit backend dependencies and are not submitted by this change.
- Load Metric adapter/source choices from the current definition-capabilities API with explicit loading, retryable failure, and no-configured-source states; an unavailable Metric path must not prevent Alert-only Observation creation.
- Add Alert Lens configuration as owned draft data, preserving opaque provider-native `selector.query` exactly and supporting ordered free-text objectives and ordered reference periods without introducing standalone lifecycle operations.
- Add constrained Relationship configuration over 2..N Metric Lens participants, with explicit When/Expect controls for only `trend.direction`, `trend.rate`, and `variability.state` and their accepted values.
- Map the validated aggregate explicitly to `POST /api/v1/observations`, keep the backend authoritative, and provide field/aggregate validation, create failure, successful-create, and nested-editor state behavior.
- Add the minimum reusable frontend primitives, semantic tokens, routing, API boundary, and focused component/unit tests required by this flow; do not add charts, an advanced table abstraction, monitoring/run-analysis screens, dark mode, or unrelated domain components.

## Capabilities

### New Capabilities

- `observation-management-ui`: Production UI behavior for listing, opening, drafting, validating, and creating Observation Definitions through aggregate-owned Metric Lens, Alert Lens, and Relationship editors.

### Modified Capabilities

None. The existing `observation-definition-api` contract is consumed without changing its requirements, fields, endpoints, or lifecycle semantics.

## Impact

- Replaces the current `frontend/src` bootstrap UI with a routed React feature, project-owned shell/configuration components, semantic CSS tokens, API client boundary, and focused tests; backend production code, persistence, migrations, and architecture documents are unchanged.
- Raises the frontend and documented development minimum from Node `>=24` to `>=24.15.0`, which is required by `jsdom@^30.0.0`; implementation must update `frontend/package.json` and contributor documentation consistently.
- Proposes the following dependency groups. Approval of these planning artifacts explicitly approves these additions and ranges; shadcn/ui components remain generated project-owned source rather than a runtime framework package.

| Group and ranges | Problem solved / why needed | Viable alternative and impact |
|---|---|---|
| Tailwind: `tailwindcss@^4.3.0`, `@tailwindcss/vite@^4.3.0` | Implements the accepted Tailwind 4 token and utility integration for the frozen design. | Hand-authored CSS is technically possible but would contradict the accepted visual stack and duplicate the token/utility foundation. |
| Accessible primitives and shadcn support: `@base-ui/react@^1.8.0`, `class-variance-authority@^0.7.0`, `clsx@^2.1.0`, `tailwind-merge@^3.6.0` | Supplies the accepted headless interaction layer and deterministic variant/class composition for project-owned shadcn-style components. | Bespoke controls/class merging are possible but add accessibility and styling risk; these packages stay below domain components and do not change domain contracts. |
| Icons: `lucide-react@^1.42.0` | Provides the single accepted application icon set. | Maintaining local SVG copies is possible but creates unnecessary ownership and consistency work; Lucide remains presentation-only. |
| Routing: `react-router-dom@^7.18.0` | Provides URL, navigation, and browser-back semantics for list, read, draft, and nested-editor views. | Local view flags or a custom History wrapper are possible but make nested Cancel/back behavior harder to isolate and test; no global state framework is introduced. |
| Testing: `vitest@^5.0.0`, `@testing-library/react@^16.3.0`, `@testing-library/user-event@^14.6.0`, `jsdom@^30.0.0` | Verifies the first meaningful frontend draft, routing, accessibility-oriented interaction, and request-boundary behavior. | Pure tests without a DOM cannot verify the required rendered interactions; a browser E2E framework would be heavier. These are development-only and require Node `>=24.15.0`. |

- Uses only current public definition APIs: `GET /api/v1/observations`, `GET /api/v1/observations/{id}`, `GET /api/v1/observation-definition-capabilities`, and final `POST /api/v1/observations`. Nested editors never call standalone Lens/Relationship write endpoints because none exist; Metric preflight is outside this change because no preflight UX is specified.
- Leaves latest Observation runtime status, free-text Metric objectives, persisted Metric history configuration, update/delete, standalone Lens CRUD, Log Lens configuration, and monitoring/run-analysis UI for separately approved backend or roadmap changes.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — Observation aggregate ownership, type-local Lens identity, one-metric Lens boundary, and Metric-only Relationships.
- `docs/architecture/05_relationship_evaluator_concept.md` — deterministic Relationship participant, property-vocabulary, condition, and expectation semantics.
- `docs/architecture/13_alert_lens_and_analysis_concept.md` — Alert Lens ownership, exact serialized definition, opaque selector, source, objective, reference-period, and scope-versus-time semantics.
- `openspec/specs/observation-definition-api/spec.md` — current public create/read shapes and validation rules consumed by the UI.
- `docs/ui/frontend_ui_stack_adr.md` and `docs/ui/ui_implementation_handoff_v1.md` — accepted frontend stack and frozen UI Direction v1.1 implementation contract.
