## 1. Frontend Foundation

- [ ] 1.1 Start implementation on a clean `feature/add-observation-management-ui` branch based on `main` and verify that the unrelated `MVP_IMPLEMENTATION_ROADMAP.md` worktree change is not included.
- [ ] 1.2 Raise the frontend engine and documented development minimum to Node `>=24.15.0`, add the explicitly approved Tailwind 4, Base UI, Lucide, shadcn-support, React Router, Vitest, Testing Library, and jsdom dependencies at the proposal ranges, and update the npm lockfile without adding table, chart, form, cache, or global-state libraries.
- [ ] 1.3 Configure Tailwind through Vite, the same-origin `/api` development proxy, Vitest/jsdom setup, frontend test scripts, and root `make test`/`make check` coverage while preserving the existing lint and production-build gates.
- [ ] 1.4 Implement semantic CSS variables, Tailwind theme integration, responsive base styles, and the minimal project-owned Button/Input/Textarea/Select/Field/notice primitives needed by the management screens.
- [ ] 1.5 Implement the routed ObserveAI shell, active Observations navigation, page header patterns, create-route draft provider boundary, and safe direct/refresh fallback for nested editor routes.

## 2. Public Contract and Draft Core

- [ ] 2.1 Define narrow TypeScript representations of the current Observation summary/detail/create, Metric Lens, Alert Lens, Relationship, capabilities, and API error contracts without adding runtime, preflight, or UI-only fields to transport types.
- [ ] 2.2 Implement the relative-URL Observation API client for list, detail, capabilities, and aggregate create, including abort-safe loading and structured field/aggregate error handling; do not add preflight or child write methods.
- [ ] 2.3 Implement the route-scoped Observation draft reducer with opaque client child keys, ordered add/replace operations, and editor-local copy helpers that commit only on Apply; do not add an unspecified child-removal action.
- [ ] 2.4 Implement pure contract-aligned validators and the explicit `ObservationDraft` to `ObservationCreate` serializer, covering identifier/offset syntax, ordered duplicate rules, type-local IDs, Alert query preservation, and Relationship topology/vocabulary.
- [ ] 2.5 Add unit tests for reducer immutability, validation edge cases, exact ordered serialization, cross-type Lens ID allowance, Metric-only Relationship resolution, and exclusion of UI-only/unsupported fields.

## 3. Observation List and Read-Only Inspection

- [ ] 3.1 Implement the Observation definitions list from `GET /api/v1/observations` with project-owned rows, composition counts, case-insensitive name/description substring search, `New Observation`, and `Open`, omitting runtime columns/filters and Edit/Delete controls.
- [ ] 3.2 Implement distinct list loading, retryable error, collection-empty, populated, and successful-no-search-matches states whose copy does not imply analytical normality or absence when data failed to load; the no-match state must clear the search without using the collection-empty presentation.
- [ ] 3.3 Implement the lightweight read-only definition route from `GET /api/v1/observations/{id}` with metadata and ordered child summaries plus loading/not-found/error/retry behavior, without monitoring/run-analysis controls.
- [ ] 3.4 Add rendered tests for list loading/error/empty/search/no-match, exact searchable-field boundaries, supported row fields, absence of unsupported controls, and definition inspection success, loading, 404, retryable non-404 failure, retry of the same identity, and back-to-list behavior.

## 4. Aggregate Create Experience

- [ ] 4.1 Implement the Create Observation route with distinct name, optional description, and objective fields plus General, Metric lenses, Alert lenses, Relationships, and Review sections anchored to frozen frame 10.
- [ ] 4.2 Implement reusable `ConfigurationSection`, child summary/card, and `DefinitionSummary` components that preserve ordered draft composition and expose add/edit navigation without persisting children.
- [ ] 4.3 Implement top-level Cancel/discard behavior, invalid-draft review feedback, and neutral draft-loss handling for direct or refreshed nested editor routes.
- [ ] 4.4 Add rendered tests proving nested Cancel/browser-back preserves the aggregate draft, valid Apply performs exactly one ordered local mutation with no HTTP write, top-level Cancel clears a fully populated draft, returns to `/observations`, and leaves the next create flow neutral, and direct/refresh entry to every nested editor without a live draft redirects to `/observations/new` with neutral feedback, a neutral draft, and no HTTP write.

## 5. Lens Editors

- [ ] 5.1 Implement shared inline `AnalysisObjectivesField` and `ReferencePeriodsField` interactions with add/remove, stable order, blank/duplicate feedback, and no modal or tool-selection semantics.
- [ ] 5.2 Implement Metric capabilities pending, retryable-failure, empty-source, and supported-source states, then implement Metric Lens add/edit against the complete current API shape; prevent Metric Apply while capabilities are unavailable, never invent a source, keep Alert-only creation usable, restrict objectives to `spike | drift | oscillation`, support valid ordered reference offsets, omit preflight, and omit/disable history policy with a backend-dependency explanation.
- [ ] 5.3 Implement Alert Lens add/edit with exact supported source, owned-child semantics, ordered free-text objectives/offsets, and a selector field whose original opaque query is never trimmed, parsed, normalized, rewritten, or extended.
- [ ] 5.4 Add focused Metric/Alert editor tests for capabilities pending/failure/retry/empty/success and continued Alert-only creation, current shape mapping, ordered values, type-local ID rules, preflight and unsupported Metric objective/history exclusion, exact Alert selector preservation, Cancel/Apply behavior, and absence of standalone Lens requests.

## 6. Relationship Editor

- [ ] 6.1 Implement the Relationship identity and 2..N participant controls using only current draft Metric Lenses, including duplicate prevention and cross-type ambiguity avoidance.
- [ ] 6.2 Implement explicit When/Expect participant-property-value rows for only the accepted direction/rate/variability vocabulary, including empty When support, required Expect behavior, conjunctive descriptor mapping, and no generic DSL.
- [ ] 6.3 Add focused Relationship tests for conditional and always-applicable rules, participant usage, invalid Alert/unknown participants, duplicate assignments, accepted values, and exact Lens-keyed payload mapping.

## 7. Aggregate Submission and Production States

- [ ] 7.1 Wire final review validation and exactly one `POST /api/v1/observations` submission, ensuring nested Apply actions never call write endpoints and backend field paths are surfaced without client-side payload rewriting.
- [ ] 7.2 Implement pending/double-submit protection, retained draft and actionable feedback on transport/API failure, and success confirmation followed by draft clearing and read-only inspection of the returned definition.
- [ ] 7.3 Add end-to-end component tests for locally blocked invalid submission, exact successful aggregate payload/call count, server field and aggregate failures, retained retry state, and successful draft clearing/navigation.

## 8. Visual and Repository Verification

- [ ] 8.1 Compare the implemented shell, list, create flow, and three editors against MagicPath frames 09–13 at the reference desktop size and a narrower viewport; correct hierarchy, spacing, focus, keyboard, overflow, and semantic-token issues without adding out-of-scope screens or controls.
- [ ] 8.2 Update `docs/development-guide.md` and any affected README command/prerequisite text for Node `>=24.15.0`, the production frontend stack, same-origin Vite API proxy, frontend test command, and frontend coverage in `make test`/`make check`; leave architecture documentation unchanged.
- [ ] 8.3 Run the focused frontend test suite, frontend ESLint, and frontend production build; resolve failures and verify no backend production file, architecture document, unsupported endpoint, or unrelated dependency changed.
- [ ] 8.4 Run `make check` as the final local verification step and report any failure accurately before archive or pull-request preparation.
