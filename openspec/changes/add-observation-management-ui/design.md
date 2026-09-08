## Context

See `proposal.md` for motivation and `specs/observation-management-ui/spec.md` for observable behavior.

The frontend is currently a one-page React/TypeScript/Vite bootstrap with no routing, API boundary, Tailwind integration, component primitives, or test framework. The backend already owns a strict Observation Definition aggregate and exposes list, detail, capabilities, and aggregate-create endpoints. It exposes no Observation update/delete API, no child write API, no latest-runtime projection on definition summaries, no Metric free-text objective support, and no public Metric history-policy field. Although a Metric preflight endpoint exists, this change does not expose it because no preflight UX has been accepted for the frozen flow.

The frozen MagicPath frames 09–13 define the visual hierarchy for the list, create flow, and three editors. Where mock content assumes runtime fields or unsupported controls, the API and architecture boundaries win: runtime columns/filters and Metric history controls are omitted, while the list's `Open` action leads to a small read-only definition view rather than implementing frozen monitoring screen 02.

The change introduces concrete UI behavior, routing, interaction primitives, and tests, so the dependency additions listed in the proposal require explicit approval with these artifacts. No backend or architecture-document change is required.

## Goals / Non-Goals

**Goals:**

- Establish a reusable but small shell, token, primitive, routing, API, and testing foundation justified by Observation Management.
- Keep the aggregate draft as the only mutable configuration model until one final create request.
- Make request serialization and current-contract validation easy to inspect and test independently from rendering.
- Preserve the frozen layout language while providing accessible keyboard, focus, loading, empty, validation, and error behavior.

**Non-Goals:**

- Introduce global server-state/cache or form libraries, schema-code generation, offline draft persistence, or a generic workflow engine.
- Build runtime dashboards, charts, advanced tables, update/delete behavior, standalone child resources, Log configuration, or unsupported backend fields.
- Generalize configuration components beyond the reuse demonstrated by Metric and Alert objective/reference fields.

## Decisions

### 1. Use a small route tree with an Observation draft provider scoped to create routes

Use React Router's declarative browser router for these routes:

```text
/                                      -> redirect to /observations
/observations                          -> definitions list
/observations/:observationId           -> read-only definition inspection
/observations/new                      -> aggregate draft/review
/observations/new/metric-lenses/:key   -> Metric editor
/observations/new/alert-lenses/:key    -> Alert editor
/observations/new/relationships/:key   -> Relationship editor
```

`:key` is an opaque client-only child key (with a reserved `new` value), not a domain ID, so a user may edit the Lens/Relationship ID without invalidating the route. A provider above the create route branch owns a reducer-based `ObservationDraft`; nested editors clone one child into component-local state and dispatch a single add/replace action only after successful Apply validation. Cancel/back simply navigate without dispatching. Direct navigation or refresh into a nested route without a live draft redirects to `/observations/new` with a neutral draft-loss notice.

Alternative considered: one large component with view-state flags. It avoids a router dependency but loses URL/back-button semantics and makes nested cancel/apply behavior harder to isolate. A global state library is unnecessary for one route-scoped aggregate.

### 2. Keep API transport and domain-shaped draft types separate from view state

Create a narrow typed fetch client around relative `/api/v1` URLs for definition list, definition detail, definition capabilities, and aggregate create only. Development uses a Vite proxy to the existing local backend, avoiding a backend CORS change; production keeps same-origin relative requests. The client handles non-success responses, parses the existing `{code, message, field?}` error envelope when available, and preserves unknown transport failures as generic errors.

Domain-shaped types mirror the public contracts. UI-only state such as client keys, dirty flags, active section, pending submit state, and field errors remains outside them. A pure serializer removes UI-only data and constructs the final request:

| Draft/UI source | `ObservationCreate` target |
|---|---|
| General name | `name` |
| General description | `description` or `null`/omitted consistently |
| General objective | `objective` |
| Ordered Metric children | `lenses` |
| Ordered Alert children | `alert_lenses` |
| Ordered Relationship children | `relationships` |

The definitions list consumes `ObservationSummary`, computes only composition counts, and performs case-insensitive substring search against `name` and `description`. A successful non-empty collection with no matches has a dedicated clear-search state rather than reusing the collection-empty state. The read-only view consumes `ObservationResponse`. No runtime shape is added to either type.

Alternative considered: reuse form/view objects directly as request bodies. Explicit serialization is slightly more code but prevents client keys, display labels, disabled mock controls, or derived values from leaking into a strict request.

### 3. Validate for feedback with pure contract-aligned functions

Validation is implemented as small pure functions for Observation, Metric Lens, Alert Lens, Relationship, objective lists, and reference offsets. They mirror only invariants represented by the public contract and return stable field paths compatible with backend errors. The final aggregate validation runs again immediately before serialization and POST; backend rejection remains authoritative and never causes client-side payload rewriting.

Notable mappings and constraints:

- Metric objective values are restricted to the API enum despite the shared inline visual pattern. A compact dependency notice explains that arbitrary Metric intent text is unavailable; Alert objectives remain exact opaque strings.
- Empty Metric and Alert objective lists remain valid; any entered item must be valid and duplicate-free.
- Alert selector validation uses `trim()` only to test whether content exists; the original string is retained and serialized exactly.
- Reference offsets are validated with the current regex and exact duplicate comparison; values are never sorted or normalized.
- Relationship form rows are converted to conjunctive Lens-keyed `SemanticDescriptor` maps. Duplicate participant/property assignments are rejected rather than silently overwritten.
- Conditions may be empty (always applicable), expectations may not, participants are distinct and Metric-only, and every participant must appear on at least one side.
- Metric and Alert Lens uniqueness maps are independent; Relationship resolution uses only Metric IDs.

Alternative considered: introduce a client schema-validation dependency. The current contract is small enough that a second schema system would add weight and risk drift without eliminating the need for form-specific messages.

### 4. Adapt project-owned components and tokens to the frozen design

Tailwind CSS 4 is integrated through its Vite plugin and semantic CSS variables. The initial token set covers background, surface, text, border, focus, primary action, destructive/error feedback, and the analytical/execution/trace groups reserved by the frozen handoff. Management screens use only the tokens they need; unused monitoring components are not created.

Use a small shadcn-style project-owned primitive layer built on Base UI where an accessible interaction primitive is needed, plus Lucide icons. The feature-level component set is bounded to:

```text
AppShell, Sidebar, PageHeader
Button, Input, Textarea, Select, Field, InlineNotice
ObservationRow, DefinitionSummary, ConfigurationSection
AnalysisObjectivesField, ReferencePeriodsField, ParticipantSelector
MetricLensEditor, AlertLensEditor, RelationshipEditor
```

The definitions list remains semantic table/list markup with responsive overflow and no TanStack Table. No Recharts package is added because management has no chart requirement. Narrow layouts may collapse the sidebar and stack form regions for fit/accessibility, but desktop hierarchy, terminology, density, and section ordering remain anchored to MagicPath.

Alternative considered: copy one-off Tailwind markup into every screen. A small owned vocabulary keeps focus/error/token behavior consistent without creating a broad design system before it is needed.

### 5. Add only dependency groups justified by the first production UI

The proposal's dependency table is the approval surface. Implementation uses the groups as follows:

| Group | Approved ranges | Technical role and rejected lighter alternative |
|---|---|---|
| Tailwind integration | `tailwindcss@^4.3.0`, `@tailwindcss/vite@^4.3.0` | Required by the accepted visual stack and semantic-token utility approach; a parallel hand-authored CSS system would conflict with that decision. |
| Base UI/shadcn support | `@base-ui/react@^1.8.0`, `class-variance-authority@^0.7.0`, `clsx@^2.1.0`, `tailwind-merge@^3.6.0` | Supports accessible project-owned primitives and deterministic variants/class merging; bespoke equivalents would add accessibility and maintenance risk. |
| Icons | `lucide-react@^1.42.0` | Implements the accepted single icon vocabulary; copied SVG assets would add unnecessary local maintenance. |
| Routing | `react-router-dom@^7.18.0` | Owns URL and browser-history semantics; custom History code is avoidable infrastructure for this multi-view flow. |
| Component testing | `vitest@^5.0.0`, `@testing-library/react@^16.3.0`, `@testing-library/user-event@^14.6.0`, `jsdom@^30.0.0` | Exercises rendered route/form/network behavior without a heavier browser E2E framework; pure non-DOM tests cannot cover the accepted interaction semantics. |

No package introduces domain semantics or a second server-state/form/state framework. `jsdom@^30.0.0` requires Node `>=24.15.0` within the project's Node 24 line, so the frontend engine, developer prerequisite, and relevant contributor instructions are raised together. This is a development-baseline change, not a browser/runtime API change.

### 6. Treat read-only inspection as a management fallback, not a monitoring screen

Because `Open` is required but the frozen Observation Detail/run screens are outside this change, `/observations/:observationId` renders a restrained read-only configuration summary using the same `DefinitionSummary` and child cards as Create Observation. It fetches the complete definition, includes loading/not-found/error/retry states, and offers Back to Observations. It does not show run actions, latest status, analytical state, findings, charts, tabs, or Edit/Delete controls.

Alternative considered: route `Open` to an unimplemented monitoring view or disable the action. Both would fail the production list flow; the read-only definition projection uses an existing API and stays within the accepted inspect boundary.

### 7. Treat Metric capabilities as an editor-local availability dependency

Load definition capabilities before enabling Metric acquisition fields. Pending state disables Metric Apply; request failure shows retry; a successful empty Metric list explains that no source is configured. Neither failure nor emptiness mutates the draft, invents a source, or disables General, Alert Lens, Review, or final Alert-only creation. Capabilities may be held for the lifetime of the create route, but no general server-state cache is introduced.

Alternative considered: hard-code the current Prometheus source or block the whole create flow. The former violates the API source of truth; the latter rejects the contract's valid Alert-only aggregate.

### 8. Test interaction contracts at pure and rendered boundaries

Vitest with jsdom and Testing Library covers pure serialization/validation plus user-observable route and form behavior. Fetch is injected or mocked at the client boundary; tests assert request method/URL/body and call counts rather than component internals.

Focused coverage includes:

- reducer and editor-local state proving Cancel/back makes no draft mutation and Apply makes exactly one mutation;
- top-level Cancel proving a populated aggregate is cleared, navigation returns to the list, and a later create flow starts neutral;
- exact aggregate payload construction, ordered collections, type-local ID uniqueness, and supported Relationship vocabulary/topology;
- exact Alert selector preservation, ordered objectives/offsets, and Metric objective restriction;
- absence of child HTTP writes on Apply;
- list loading/error/empty/search/no-match and read-only Open behavior;
- Metric capabilities pending/failure/retry/empty/success behavior and continued Alert-only creation;
- locally blocked invalid submit, successful create, backend field/aggregate error display, retained draft on failure, and cleared draft on success.

Add a frontend `test` script and include it in root `make test`/`make check`, while retaining ESLint, production build, backend pytest, Ruff, and strict OpenSpec validation. Update `docs/development-guide.md` and any affected README command/prerequisite text so the Node minimum, API proxy, frontend test framework, and canonical command descriptions remain accurate.

## Risks / Trade-offs

- **[Risk] The UI concept supports free-text Metric objectives but the API enum does not.** → Use the shared field layout with only the three accepted values and a backend-dependency notice; do not serialize arbitrary text.
- **[Risk] Mock list runtime columns cannot be populated by the definition API.** → Omit both columns and related filters; never infer analytical or execution state from missing data.
- **[Risk] In-memory drafts are lost on full refresh or direct nested-route entry.** → Redirect safely to the create root with an explicit neutral notice; persistent drafts are a separate feature.
- **[Risk] Frontend contract types can drift from Pydantic models.** → Keep types/API client narrow, cover exact payloads in tests, and treat backend validation errors as authoritative; defer code generation until duplication justifies it.
- **[Risk] Adding routing, primitives, styling, and tests in the first feature increases the delta.** → Limit dependencies and owned components to those used by this flow; avoid data-cache, form, table, chart, and state libraries.
- **[Risk] jsdom 30 does not support the repository's previous broad Node `>=24` range.** → Raise and document the minimum to Node `>=24.15.0` in the same implementation slice and verify the actual runtime before installing.
- **[Risk] A read-only management view could be mistaken for frozen monitoring screen 02.** → Use configuration terminology and cards only, with no runtime actions, analytical status, findings, or run navigation.

## Migration Plan

1. Begin implementation from a clean `feature/add-observation-management-ui` branch based on `main`; do not carry the unrelated `MVP_IMPLEMENTATION_ROADMAP.md` worktree modification into this change.
2. Raise the frontend and documented Node minimum to `>=24.15.0`, add the approved frontend dependencies and lockfile updates, and configure Tailwind/Vite and the test scripts.
3. Establish semantic tokens, the minimal primitive layer, router, API client, capabilities states, and development proxy while preserving the existing frontend entry point.
4. Replace the bootstrap screen with the shell and Observation routes, then add the list/read-only views and aggregate draft/editors in independently testable increments.
5. Add focused tests, integrate frontend tests into the root verification commands, and update contributor documentation for the resulting workflow.
6. Run `make check`; rollback is a normal revert of the frontend/configuration/documentation commits because there is no backend, database, or persisted-data migration.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`: the draft and payload preserve Observation aggregate ownership, `lenses`/`alert_lenses` type-local identity, one-metric scope, and Metric-only Relationship resolution.
- `docs/architecture/05_relationship_evaluator_concept.md`: the explicit When/Expect UI is limited to current-state property vocabulary and deterministic rule semantics.
- `docs/architecture/13_alert_lens_and_analysis_concept.md`: the Alert editor preserves owned-child lifecycle, source, opaque query, ordered objectives/offsets, and selector-which versus runtime-when boundaries.
- `openspec/specs/observation-definition-api/spec.md`: request/response types, current endpoint surface, validation, and unsupported runtime/update/delete behavior are consumed unchanged.
- `docs/ui/frontend_ui_stack_adr.md`: dependencies remain inside the accepted visual stack; routing and test choices are deliberately minimal local implementation decisions.
- `docs/ui/ui_implementation_handoff_v1.md` and MagicPath project `447597481925181440`: shell, management hierarchy, form language, draft interaction, and visual density follow frozen UI Direction v1.1, with documented API-constrained omissions.
