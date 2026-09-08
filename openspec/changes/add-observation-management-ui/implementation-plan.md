# Implementation Plan — add-observation-management-ui

**Status:** APPROVED
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-observation-management-ui`
**Candidate branch:** `feature/add-observation-management-ui`

## Authority and constraints

This file describes how the human-approved OpenSpec change will be implemented. It does not redefine product behavior. Root `AGENTS.md`, accepted architecture/contracts, the approved OpenSpec artifacts, and frozen UI Direction v1.1 remain authoritative.

The approved dependency ranges and Node `>=24.15.0` baseline are included because the user explicitly approved the OpenSpec plan containing them. No other dependency, backend API, persistence, architecture, or domain-contract change is authorized.

The complete source set is:

- `openspec/changes/add-observation-management-ui/{proposal.md,design.md,tasks.md}` and `specs/observation-management-ui/spec.md`;
- `openspec/specs/observation-definition-api/spec.md`;
- `docs/architecture/01_observation_lens_concept.md`, `05_relationship_evaluator_concept.md`, `10_open_decisions_and_backlog.md`, and `13_alert_lens_and_analysis_concept.md`;
- `docs/ui/README.md`, `frontend_ui_stack_adr.md`, and `ui_implementation_handoff_v1.md`;
- frozen MagicPath project `447597481925181440`, especially `00 Design System` and frames `09`–`13`;
- root `AGENTS.md`, `docs/development-guide.md`, and `.agents/PROJECT_KNOWLEDGE.md` as advisory knowledge only.

## Repository and execution preconditions

Planning currently occurs on `chore/update-mvp-roadmap`, whose worktree contains a user-owned modification to `MVP_IMPLEMENTATION_ROADMAP.md` plus the untracked OpenSpec change. Before VS-01 dispatch, the Coordinator must ensure the approved change and this plan are established on a clean `feature/add-observation-management-ui` branch based on the current accepted `main`, without discarding, staging, or committing the unrelated roadmap edit into this feature. If a clean candidate branch cannot be established safely, execution stops for repository-state disposition.

The executing environment must provide Node `>=24.15.0` before the approved jsdom 30 dependency is installed or frontend checks are run. Updating the declared engine and documentation does not by itself upgrade the host runtime. If a compatible runtime is unavailable, execution stops for environment preparation; it does not weaken the approved engine or dependency ranges.

## Slice graph

```text
COORD-PREP
    -> VS-01 Read-only production walking skeleton [high-risk]
    -> VS-02 Alert-only aggregate create path       [high-risk]
    -> VS-03 Capability-driven Metric creation       [high-risk]
    -> VS-04 Relationships and mixed topology        [high-risk]
    -> FINAL whole-change conformance                 [normal]
```

Execution is sequential. VS-02 through VS-04 intentionally extend the same feature boundary after accepted predecessor commits; they must not run in parallel in the shared worktree.

## Execution overview

| Slice | Behavioral increment | Depends on | Risk | Status | Commit | Handoff/review |
|---|---|---|---|---|---|---|
| VS-01 | Browse, search, and inspect definitions in the production shell | COORD-PREP | high-risk | COMPLETE | 8409405 (+ accepted corrections) | No handoff (user-directed); high-risk review PASS |
| VS-02 | Create an Alert-only Observation through local draft semantics | VS-01 | high-risk | COMPLETE | 988aedd (+ accepted corrections) | No handoff (user-directed); high-risk review PASS |
| VS-03 | Create Metric-only Observations from live definition capabilities | VS-02 | high-risk | IN_PROGRESS | - | - |
| VS-04 | Add constrained Relationships and complete mixed aggregates | VS-03 | high-risk | PLANNED | - | - |
| FINAL | Verify the complete approved UI and repository compatibility | VS-04 | normal | PLANNED | - | - |

## Slice definitions

### VS-01 — Read-only production walking skeleton

**Behavioral goal:** Replace the bootstrap page with the smallest production ObserveAI application that lets a user enter the Observations product area, load/search the definition list, open a definition, and distinguish every approved loading/empty/no-match/not-found/error state using only supported read data.

**OpenSpec coverage:**

- Requirements `Place management in the Observations product area`, `List, search, and inspect supported definition data`, and `Provide explicit list loading, error, and empty states`, including every scenario under them.
- Tasks 1.1–1.4; task 1.5 shell/navigation portion; task 2.1 summary/detail/error types; task 2.2 list/detail client portion; tasks 3.1–3.4; task 8.1 for frames `00` and `09`; task 8.2; task 8.3 for this delta.

**Dependencies:** COORD-PREP has produced the clean candidate branch and a Node `>=24.15.0` runtime is available.

**Vertical boundary:** browser navigation to `/observations` or `/observations/:observationId` -> React Router and project-owned shell -> narrow relative-URL API client -> existing definition list/detail endpoints -> explicit read-only UI state and retry/back behavior.

**Ownership:**

- frontend dependency manifests/lockfile, Node engine, Vite/Tailwind/Vitest configuration, and frontend test setup;
- root `Makefile` test/check integration;
- global frontend entry, semantic tokens/styles, minimal shared primitives, shell/navigation/router;
- Observation read transport types/client, list/read-only feature components, pages, and focused tests;
- `docs/development-guide.md` and affected README prerequisite/command text required by task 8.2.

Expected implementation locations include `frontend/src` application/layout/UI primitives and an `observations` feature boundary. Exact filenames remain implementation choices; do not create a generic application framework or unused component catalog.

**Expected code impact:** `frontend/package.json`, npm lockfile, `frontend/vite.config.ts`, frontend TypeScript/config/test setup, `frontend/src/**`, root `Makefile`, and bounded contributor documentation. Backend source and architecture documents remain unchanged.

**Contracts consumed/changed:** consumes `ObservationSummary`, `ObservationResponse`, and the current API error envelope from `GET /api/v1/observations` and `GET /api/v1/observations/{id}`. Changes no backend/public/domain contract. Raises only the approved frontend/development Node minimum.

**Non-goals:** create flow, draft mutation, capability loading, Metric/Alert/Relationship editors, POST requests, monitoring/run-analysis UI, Edit/Delete, runtime status fields, TanStack Table, Recharts, or backend CORS changes.

**Focused verification:**

- tests for list pending/failure/retry/empty/populated, case-insensitive name/description-only search, distinct no-match clearing, row composition, and absence of runtime/Edit/Delete controls;
- tests for detail success/pending/404/non-404 retry of the same identity/back behavior and absence of monitoring controls;
- controllable-request tests proving navigation, unmount, or a superseding list/detail request aborts or invalidates abandoned work, ignores its late success/failure, and cannot replace the active view or surface a stale error;
- route/shell accessibility and active navigation tests where valuable;
- verify dependency and lockfile ranges, Node engine, relative `/api` proxying, test scripts, and updated contributor instructions;
- run focused Vitest, frontend ESLint, frontend production build, strict validation for the change, and `git diff --check`.

**Context pack:** root `AGENTS.md` sections 9–14; approved proposal dependency table and design decisions 2, 4–6, and 8; the three owned OpenSpec requirements; observation-definition API read/error contracts; backend observation contracts/API for exact shapes only; UI handoff sections 2–7 and 9; MagicPath `00 Design System` and `09 Observations Management`; current frontend, Makefile, README, and development-guide command/prerequisite sections.

**Handoff expectations:** `implementation/VS-01-handoff.md` records observable read behavior, dependency/Node changes, exact files changed, focused checks, visual comparison evidence for frame 09, limitations, commit identity, and `Shared knowledge candidates: none|...`.

**Risk:** high-risk because this slice introduces all approved dependencies, changes the supported Node/tooling baseline, and establishes the frontend HTTP/routing integration boundary. A fresh High-Risk Slice Reviewer is required before Coordinator acceptance.

**Completion gate:** the clean feature branch and compatible Node runtime are verified; approved dependency/configuration/doc changes are complete; `/observations` and `/observations/:id` satisfy all owned scenarios; abandoned or superseded list/detail requests cannot update the active view or surface stale errors; unsupported runtime and lifecycle controls are absent; focused tests, lint, build, strict OpenSpec validation, and diff checks pass; visual hierarchy matches frames 00/09 within approved API constraints; one atomic implementation commit and handoff are produced; fresh high-risk review passes.

### VS-02 — Alert-only aggregate create path

**Behavioral goal:** Deliver the first complete create workflow by allowing a user to build an Alert-only Observation in one local aggregate draft, cancel or apply nested edits with exact ownership semantics, validate it, submit exactly one aggregate POST, recover from failure, and inspect the successful result.

**OpenSpec coverage:**

- Requirement `Maintain one local Observation aggregate draft`, including its aggregate-wide, Alert editor, top-level Cancel, and draftless-route behavior; Metric and Relationship editor-specific Cancel/Apply behavior is completed in their owning slices.
- Requirement `Configure Alert Lenses as owned opaque-selector data`, including all three scenarios.
- Requirement `Validate the aggregate and submit exactly once`, covering its full request/failure/success behavior for the valid Alert-only topology and general/Alert invariants.
- `Place management in the Observations product area` as it applies to create and Alert editor routes.
- Task 1.5 create-provider and draftless nested-route portion; tasks 2.1, 2.2, 2.4, and 2.5 for general/Alert/draft/serialization behavior; task 2.3 base reducer and Alert child portion; tasks 4.1–4.3 and task 4.4 for aggregate/Alert/draftless-route behavior; task 5.1; task 5.3; task 5.4 Alert and draft-write portions; tasks 7.1–7.3 for Alert-only creation; task 8.1 for frames `10` and `13`; task 8.3 for this delta.

**Dependencies:** accepted VS-01 provides the shell, router, API/error boundary, primitives, tests, and read-only success destination.

**Vertical boundary:** `/observations/new` General/sections/review -> route-scoped aggregate draft -> editor-local Alert state -> Cancel or validated Apply with zero writes -> pure Alert/aggregate validation and serialization -> exactly one existing Observation create POST -> retained failure state or cleared draft plus read-only success view.

**Ownership:**

- create-route provider, base reducer/copy-helper contract, UI-only child-key handling, and Alert add/replace actions;
- general Create Observation view, section/summary/card components, and neutral draft-loss handling for all nested route patterns;
- shared inline objective/reference-period components at the behavior required by Alert configuration;
- Alert editor, Alert validation, base aggregate validation/serializer, aggregate create client method, submission states, and focused tests.

VS-02 may extend accepted VS-01 feature files but must preserve its read behavior. It must not implement speculative child removal; add/replace is the aggregate-child mutation surface.

**Expected code impact:** Observation feature draft/types/validators/serializer/API extension, create and Alert routes/components, shared configuration components, and focused tests. No new dependency, backend code, persistence, or architecture document.

**Contracts consumed/changed:** consumes the current `ObservationCreate`, `AlertLensCreate`, `ObservationResponse`, and API error contracts. It preserves `selector.query` exactly and uses only `source: jira_track_and_release`. Changes no contract and calls no standalone child endpoint.

**Non-goals:** Metric capability fetching/editor, Metric objectives/reference/history/preflight, Relationship editing, child removal, Observation update/delete, standalone Alert persistence, runtime time/status query rewriting, or final mixed-topology validation.

**Focused verification:**

- pure reducer/serializer tests for ordered Alert add/replace, UI-only field exclusion, empty-Lens rejection, Alert ID/objective/offset rules, and exact selector preservation;
- rendered Alert editor tests proving new-child addition, existing-child lookup by opaque client key and replacement at the same ordered position, Cancel/back non-mutation, and zero HTTP writes; plus top-level discard/navigation/fresh draft and direct/refresh entry to each nested route without a live draft;
- rendered create tests for local validation blocking, pending/double-submit protection, exactly one POST, backend field/aggregate errors, retained retry draft, and cleared successful draft/navigation;
- Alert-only API body/call-count assertions and explicit absence of child/preflight writes;
- focused regression tests for VS-01, frontend lint/build, strict OpenSpec validation, `git diff --check`, and visual comparison against frames 10/13.

**Context pack:** accepted VS-01 handoff; approved design decisions 1–3, 6, and 8; draft, Alert, and aggregate-submit requirements/scenarios; observation-definition API create and Alert requirements; architecture `01` sections 4.4/5.3 and `13` sections 3–4; UI handoff sections 6–7 and 9–11; MagicPath frames `10 Create Observation` and `13 Alert Lens Configuration`; current backend contract models as serialization evidence only.

**Handoff expectations:** `implementation/VS-02-handoff.md` records the Alert-only user flow, Alert new-add and same-position replacement by client key, exact selector and no-write evidence, Cancel/back behavior, request payload/call count, files changed, checks, visual comparison, commit identity, and shared-knowledge candidates.

**Risk:** high-risk because this slice introduces the external aggregate write path and must preserve opaque provider-native selector content and atomic aggregate ownership exactly. A fresh High-Risk Slice Reviewer is required before Coordinator acceptance.

**Completion gate:** every owned draft/Alert/Alert-only-submit scenario passes; the Alert editor adds a new child and replaces an existing child at the same ordered position via opaque client key; Cancel/back does not mutate and Apply never writes; final Create emits one exact supported payload and handles success/failure without data loss or implied partial persistence; draftless routes are safe; VS-01 remains green; focused tests, lint, build, strict validation, and diff checks pass; frames 10/13 are visually conformed within API constraints; one atomic commit/handoff and fresh high-risk review are accepted.

### VS-03 — Capability-driven Metric creation

**Behavioral goal:** Add the complete capability-driven Metric Lens path so a user can create a valid Metric-only Observation or a Metric-plus-Alert Observation without Relationships, while capability failure or absence leaves the already accepted Alert-only path usable.

**OpenSpec coverage:**

- Requirement `Resolve Metric capabilities without blocking Alert-only creation`, including all three scenarios.
- Requirement `Configure Metric Lenses against the current public contract`, including all three scenarios.
- Requirement `Maintain one local Observation aggregate draft` as it applies to Metric editor Cancel/back and validated Apply behavior.
- Requirement `Validate the aggregate and submit exactly once` for Metric-only and Relationship-free mixed aggregates, type-local Lens IDs, ordered Metric serialization, and existing success/failure behavior.
- `Place management in the Observations product area` for the Metric editor route.
- Metric/capability portions of tasks 2.1, 2.2, 2.4, and 2.5; task 2.3 Metric child portion; task 4.4 Metric editor portion; task 5.1 Metric variant reuse; task 5.2; task 5.4 Metric/capabilities portions; Metric-only and Relationship-free mixed portions of tasks 7.1–7.3; task 8.1 for frame `12`; task 8.3 for this delta.

**Dependencies:** accepted VS-02 provides the aggregate draft, Alert-only create path, shared fields, serializer/validation boundary, POST flow, and read-only destination.

**Vertical boundary:** Metric editor entry -> capability pending/failure/retry/empty/success -> one-metric configuration and validated local Apply -> Metric-only or Relationship-free mixed aggregate validation/serialization -> existing final POST -> successful read-only definition or retained failure state.

**Ownership:**

- capabilities transport/types/state within the create-route lifetime;
- Metric objective variant, source/query/unit/reference controls, Metric editor, validation, and tests;
- Metric reducer actions and editor-copy helpers for opaque-key lookup, ordered new-child addition, and same-position replacement, plus serializer/final-validation extensions for Metric collections and type-local Metric/Alert identity;
- frame 12 visual conformance and regressions for the accepted Alert-only path.

**Expected code impact:** Observation feature capability API/types/state, Metric editor/shared controls, aggregate validators/serializer, create/review summaries, and focused tests. No Relationship editor/descriptor mapping, dependency, backend, persistence, architecture, preflight, history-policy, or runtime-screen change.

**Contracts consumed/changed:** consumes `DefinitionCapabilities`, `MetricLensCreate`, and `ObservationCreate`. It changes no public/domain contract; `lenses` remains the Metric collection and the same ID may occur once in each Metric/Alert collection.

**Non-goals:** Relationship types/editing/topology, inventing a source or metric catalog, calling Metric preflight, arbitrary Metric objective strings, history controls, analyzer/tool toggles, child removal, or runtime behavior.

**Focused verification:**

- capability-state tests for pending, failure/retry, empty, success, exact source choices, disabled Metric Apply, and continued Alert-only creation;
- controllable-request tests proving navigation, unmount, or a superseding capability request aborts or invalidates abandoned work, ignores late success/failure, and cannot replace the active capability state or surface a stale error;
- Metric tests for exact current shape, one metric, enum objectives, ordered offsets, type-local duplicate allowance, and absence of preflight/history/tool fields;
- rendered Metric lifecycle tests proving new-child addition, existing-child lookup by opaque client key and replacement at the same ordered position, Cancel/browser-back non-mutation, and zero HTTP writes;
- serializer/submit tests for Metric-only, Alert-only regression, Relationship-free mixed cross-type same IDs, ordered collections, exact payload, one POST, and retained/success states;
- focused regression tests, frontend Vitest, ESLint, production build, strict OpenSpec validation, `git diff --check`, and visual comparison against frame 12.

**Context pack:** accepted VS-01/VS-02 handoffs; approved design decisions 2–4, 7, and 8; Metric-capability, Metric, and aggregate-submit requirements; observation-definition API capabilities/Metric/create requirements; architecture `01` sections 4.4–6; UI handoff sections 6–7 and 9–11; MagicPath frame `12 Metric Lens Configuration`; backend observation contracts/API for exact capability and Metric input shapes.

**Handoff expectations:** `implementation/VS-03-handoff.md` records capability states and abort safety, Metric new-add and same-position replacement by client key, Cancel/Apply/no-write evidence, Metric mapping, Metric-only/mixed-without-Relationship aggregate evidence, preserved Alert-only behavior, exclusions, checks, frame 12 comparison, files changed, commit identity, and shared-knowledge candidates.

**Risk:** high-risk because this slice adds asynchronous capability transport plus strict `MetricLensCreate` serialization and type-local identity to the external aggregate POST. A fresh High-Risk Slice Reviewer is required before Coordinator acceptance.

**Completion gate:** every capability and Metric scenario passes; the Metric editor adds a new child and replaces an existing child at the same ordered position via opaque client key; Metric Cancel/back and Apply satisfy non-mutation/mutation and no-write semantics; abandoned/superseded capability requests cannot change active state; capability failure/absence never blocks Alert-only creation; only supported Metric data reaches Metric-only and Relationship-free mixed payloads; all Alert/draft/read regressions remain green; focused tests, lint, build, strict validation, and diff checks pass; frame 12 is visually conformed; one atomic commit/handoff and fresh high-risk review are accepted.

### VS-04 — Relationships and mixed topology

**Behavioral goal:** Add the constrained Metric-only Relationship editor and complete full aggregate validation/serialization so supported Relationships can be included in Metric-only or mixed Observation creation without weakening any accepted Lens or submission behavior.

**OpenSpec coverage:**

- Requirement `Configure constrained Metric-only Relationships`, including all three scenarios.
- Requirement `Maintain one local Observation aggregate draft` as it applies to Relationship editor Cancel/back and validated Apply behavior.
- Requirement `Validate the aggregate and submit exactly once` for Relationship IDs, participant resolution/usage, descriptor vocabulary, ordered Relationship serialization, and complete mixed topology.
- Remaining `Place management in the Observations product area` behavior for the Relationship editor route.
- Relationship portions of tasks 2.1, 2.4, and 2.5; task 2.3 Relationship child portion; task 4.4 Relationship editor portion; tasks 6.1–6.3; remaining Relationship/mixed-topology portions of tasks 7.1–7.3; task 8.1 for frame `11` and whole-flow consistency across frames 09–13; task 8.3 for the complete frontend.

**Dependencies:** accepted VS-03 provides both valid Metric participants and the proven Metric/Alert aggregate create path.

**Vertical boundary:** Relationship editor entry -> Metric-only participant selection and explicit When/Expect rows -> validated local Apply -> Lens-keyed semantic descriptor maps -> complete aggregate validation/serialization -> existing final POST -> successful read-only definition or retained failure state.

**Ownership:**

- Relationship transport types, draft child representation, reducer actions, and editor-copy helpers for opaque-key lookup, ordered new-child addition, and same-position replacement;
- participant selector and explicit descriptor-row controls;
- descriptor-map conversion, Relationship/topology validation, serializer extension, create/review summary, and focused tests;
- frame 11 and final cross-screen visual/accessibility reconciliation limited to approved management UI.

**Expected code impact:** Observation feature Relationship types/state/editor, aggregate validators/serializer, create/review summaries, and focused tests. No dependency, capability transport, backend, persistence, architecture, generic DSL, cross-type Relationship, or runtime-screen change.

**Contracts consumed/changed:** consumes `RelationshipCreate`, `SemanticDescriptor`, the accepted property/value vocabulary, and complete `ObservationCreate`. It changes no public/domain contract; participants resolve only against `lenses`, every participant is used, conditions may be empty, and expectations are non-empty.

**Non-goals:** Alert/Log participants, runtime relationship discovery, numeric/temporal rules, generic expressions, child removal, new vocabulary, or changes to already accepted Metric/Alert acquisition and editor behavior.

**Focused verification:**

- Relationship tests for 2..N distinct Metric participants, every-participant usage, empty conditions, non-empty expectations, conjunctive descriptor mapping, duplicate assignment rejection, allowed property/value vocabulary, and Alert/unknown participant rejection;
- rendered Relationship lifecycle tests proving new-child addition, existing-child lookup by opaque client key and replacement at the same ordered position, Cancel/browser-back non-mutation, and zero HTTP writes;
- exact full-payload tests for conditional and always-applicable Relationships, unique/ordered Relationship IDs, Metric-only and mixed cross-type Lens IDs, one aggregate POST, server-error retention, and success navigation;
- complete read/draft/Alert/Metric/capabilities regression suite;
- full frontend Vitest, ESLint, production build, strict OpenSpec validation, `git diff --check`, and visual/accessibility comparison against frame 11 plus consistency across frames 09–13.

**Context pack:** accepted VS-01 through VS-03 handoffs; approved design decisions 2–4 and 8; Relationship and aggregate-submit requirements; observation-definition API Relationship/create requirements; architecture `01` sections 4.4–6 and `05` sections 1–6; UI handoff sections 6–7 and 9–11; MagicPath frame `11 Relationship Configuration`; backend observation contracts for exact Relationship/descriptor/topology shapes.

**Handoff expectations:** `implementation/VS-04-handoff.md` records Relationship new-add and same-position replacement by client key, Cancel/Apply/no-write evidence, Relationship mappings/topology, full mixed payload evidence, regression and visual results, exclusions, files changed, commit identity, and shared-knowledge candidates.

**Risk:** high-risk because this slice adds strict `RelationshipCreate` topology, constrained semantic descriptor mapping, and ordered Relationship data to the external aggregate POST. A fresh High-Risk Slice Reviewer is required before Coordinator acceptance.

**Completion gate:** all Relationship and remaining aggregate scenarios pass; the Relationship editor adds a new child and replaces an existing child at the same ordered position via opaque client key; Relationship Cancel/back and Apply satisfy non-mutation/mutation and no-write semantics; only accepted Metric participants/properties/values reach the payload; conditions/expectations and participant usage match the contract; all predecessor behavior remains green; full tests/lint/build, strict validation, and diff checks pass; frame 11 and the complete flow are visually/accessibly coherent; one atomic commit/handoff and fresh high-risk review are accepted.

### FINAL — Whole-change conformance and independent implementation review

**Behavioral goal:** Verify the cumulative implementation against the complete approved OpenSpec, frozen UI direction, repository governance, and current backend contracts without adding or correcting behavior inside FINAL.

**OpenSpec coverage:** every requirement and scenario; task 8.4; confirmation that tasks with split ownership are checked only after their last accepted portion.

**Dependencies:** accepted VS-04 with no slice awaiting review, correction, metadata acceptance, or handoff processing.

**Vertical boundary:** complete candidate-branch feature delta -> repository-standard verification and visual/contract inspection -> independent whole-change implementation review -> ready-for-human-triage result.

**Expected code impact:** none. FINAL is non-corrective. Any defect is routed through the Coordinator's bounded-correction or structural re-plan rules.

**Contracts consumed/changed:** verifies all approved sources; changes none.

**Non-goals:** implementation, opportunistic cleanup, archive, PR, push, merge, or accepting unresolved review findings.

**Focused verification:** reconstruct Git/task/handoff state; inspect the cumulative feature delta for scope; run `make check`; confirm strict OpenSpec validation; review visual conformance to MagicPath 09–13 and approved responsive/accessibility adjustments; invoke the repository's independent `ipo-review-implementation` whole-change gate. Use the optional official OpenSpec verify workflow only if it is installed and available; absence is reported, not treated as proof or failure.

**Context pack:** complete approved OpenSpec, this implementation plan, all accepted slice handoffs/reviews, cumulative Git diff/history, all referenced architecture/UI/API sources, MagicPath frames 00/09–13, root governance, and repository verification commands.

**Handoff expectations:** `implementation/FINAL-handoff.md` records cumulative scope, exact checks/results, visual conformance result, independent review verdict/findings, task reconciliation, and archive readiness or the exact correction/escalation route.

**Risk:** normal for a non-corrective verification step; discovered implementation deltas are classified separately before correction.

**Completion gate:** `make check` passes; cumulative scope and task reconciliation are correct; no agent or review remains active; independent implementation review has completed; unresolved findings are routed according to governance; FINAL records either archive readiness or an exact non-terminal correction/escalation state.

## Coverage matrix — requirements and scenarios

| OpenSpec requirement | Scenarios owned | Owning slice | Verification |
|---|---|---|---|
| Place management in the Observations product area | Enter Observation management; Keep later UI out of scope | VS-01 base shell/list; VS-02/03/04 route extensions | Route/navigation tests, absence assertions, MagicPath 09–13 comparison |
| List, search, and inspect supported definition data | Search loaded definitions; Search has no matches; Open a definition; Definition inspection is loading; Definition is not found; Definition inspection fails; Omit unsupported lifecycle and runtime controls | VS-01 | Rendered fetch/search/retry/absence tests |
| Provide explicit list loading, error, and empty states | Load an empty collection; Fail to load definitions | VS-01 | List state and retry tests |
| Maintain one local Observation aggregate draft | Cancel nested edits; Apply nested edits; Cancel the aggregate draft; Enter a nested editor without a live draft | VS-02 aggregate/Alert/draftless routes; VS-03 Metric editor; VS-04 Relationship editor | Reducer plus per-editor rendered route/navigation/mutation/no-write tests |
| Resolve Metric capabilities without blocking Alert-only creation | Load available Metric sources; Capabilities request fails; No Metric source is configured | VS-03 | Capability state/retry/Alert-only regression tests |
| Configure Metric Lenses against the current public contract | Apply a valid Metric Lens; Prevent unsupported Metric configuration; Preserve type-local Lens identity | VS-03 | Metric validation/serialization/rendered tests |
| Configure Alert Lenses as owned opaque-selector data | Preserve an opaque selector; Apply ordered Alert values; Keep Alert Lens aggregate-owned | VS-02 | Exact-value/order/no-child-write tests |
| Configure constrained Metric-only Relationships | Apply a conditional Relationship; Apply an always-applicable Relationship; Reject an Alert participant | VS-04 | Relationship mapping/topology/vocabulary tests |
| Validate the aggregate and submit exactly once | Block an invalid aggregate locally; Create successfully; Preserve draft after create failure | VS-02 Alert-only/base; VS-03 Metric and Relationship-free mixed; VS-04 Relationship topology | Exact payload/call-count/error/retention/success tests |

## Coverage matrix — tasks

| OpenSpec task | Owning slice | Completion evidence |
|---|---|---|
| 1.1 | COORD-PREP / VS-01 gate | clean candidate branch; unrelated roadmap edit absent |
| 1.2–1.4 | VS-01 | manifests/lock/config/tokens/primitives plus checks |
| 1.5 | VS-01 shell/navigation; VS-02 create provider/fallback | route and draftless-entry tests; checkbox after VS-02 |
| 2.1 | VS-01 read types; VS-02 general/Alert/create types; VS-03 Metric/capabilities types; VS-04 Relationship types | compile and exact boundary tests; checkbox after VS-04 |
| 2.2 | VS-01 list/detail; VS-02 create; VS-03 capabilities | client call and abort/stale-read tests; checkbox after VS-03 |
| 2.3 | VS-02 base/Alert; VS-03 Metric; VS-04 Relationship | per-child opaque-key add/same-position-replace/copy-helper tests; checkbox after VS-04 |
| 2.4–2.5 | VS-02 base/Alert; VS-03 Metric; VS-04 Relationship completion | pure validation/serialization suite; checkbox after VS-04 |
| 3.1–3.4 | VS-01 | list/detail rendered suite |
| 4.1–4.3 | VS-02 | create/draft route suite |
| 4.4 | VS-02 aggregate/Alert/draftless routes; VS-03 Metric editor; VS-04 Relationship editor | per-editor lifecycle/no-write tests; checkbox after VS-04 |
| 5.1 | VS-02 Alert field; VS-03 Metric constrained reuse | shared-field tests; checkbox after VS-03 |
| 5.2 | VS-03 | capabilities and Metric editor suite |
| 5.3 | VS-02 | Alert editor/opaque selector suite |
| 5.4 | VS-02 Alert portion; VS-03 Metric/capabilities portion | focused editor suites; checkbox after VS-03 |
| 6.1–6.3 | VS-04 | Relationship suite |
| 7.1–7.3 | VS-02 Alert-only/base; VS-03 Metric/Relationship-free mixed; VS-04 Relationship topology | exact aggregate POST suite; checkbox after VS-04 |
| 8.1 | VS-01 frames 00/09; VS-02 frames 10/13; VS-03 frame 12; VS-04 frame 11 and whole flow | per-slice visual/accessibility record; checkbox after VS-04 |
| 8.2 | VS-01 | reviewed contributor documentation diff |
| 8.3 | VS-01/02/03 focused; VS-04 complete frontend | test/lint/build results; checkbox after VS-04 |
| 8.4 | FINAL | successful `make check` |

## Frozen structure and mutable execution state

After independent slice-plan review and explicit human approval, the following are frozen: slice graph, behavioral goals, coverage ownership, dependencies, vertical boundaries, expected impact, contracts, non-goals, context packs, planned risk, verification strategies, and completion gates. Changing them requires structural re-planning, a new slice-plan review, and renewed human approval.

Only the Implementation Coordinator may update mutable execution metadata: plan status; per-slice status, commit, handoff/review reference, and exact stop reason; bounded-correction records; and `tasks.md` checkboxes after all owning portions pass. A task split across slices remains unchecked until its final owning portion is accepted.

Normal execution statuses are `PLANNED -> IN_PROGRESS -> COMPLETE`; `BLOCKED` records the exact structural, environmental, or repository-state stop. The Coordinator persists meaningful transitions according to its Git-backed metadata rules and restores a clean worktree before every delegation.

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements or redesign decisions here.

| Item | Current value |
|---|---|
| Coordinator status | EXECUTING |
| Active assignment | VS-03 |
| Last accepted slice | VS-02 |
| Bounded correction | none |
| Stop/escalation reason | none |
