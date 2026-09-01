# Implementation Plan — add-alert-lens-definition

**Status:** APPROVED
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-alert-lens-definition`
**Implementation branch:** `feature/add-alert-lens-definition`

## Approval state

The proposal, delta specs, design, tasks, and this revised implementation plan have human
approval. The plan passed independent slice-plan review before approval, and no slice had
begun at the approval point.

## Authority and constraints

This file describes how the approved change will be implemented. It does not redefine
what must be implemented. Accepted ADRs, normative architecture/contracts, and the
approved OpenSpec remain authoritative.

Approved change sources:

- `openspec/changes/add-alert-lens-definition/proposal.md`
- `openspec/changes/add-alert-lens-definition/specs/observation-definition-api/spec.md`
- `openspec/changes/add-alert-lens-definition/specs/runtime-persistence/spec.md`
- `openspec/changes/add-alert-lens-definition/design.md`
- `openspec/changes/add-alert-lens-definition/tasks.md`

Architecture and accepted-contract sources:

- `docs/architecture/README.md`
- `docs/architecture/01_observation_lens_concept.md`, especially sections 3, 4.4,
  5.3, 8.1, and 10
- `docs/architecture/02_architecture_principles_and_runtime.md`, especially definition
  versus runtime separation and persistence boundaries
- `docs/architecture/03_ADR_log.md`: ADR-088 and ADR-161 through ADR-163
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, especially
  persisted definition/runtime separation and LensRun correlation
- `docs/architecture/10_open_decisions_and_backlog.md`
- `docs/architecture/11_glossary_and_naming.md`
- `docs/architecture/12_CHANGELOG.md`, architecture package 6.4
- `docs/architecture/13_alert_lens_and_analysis_concept.md`, especially sections 3
  and 4
- `openspec/specs/observation-definition-api/spec.md`
- `openspec/specs/runtime-persistence/spec.md`

Advisory source:

- `.agents/PROJECT_KNOWLEDGE.md` (currently contains no validated entries)

Repository constraints:

- Preserve the public Metric `lenses` field, its existing models, owned-resource path,
  source validation, capabilities endpoint, and preflight behavior.
- Add `alert_lenses` only as the approved nested type-specific collection. Do not add a
  `metric_lenses` alias or a generic polymorphic definition table.
- Keep Relationships Metric-only and resolve participant IDs only against `lenses`.
- Keep schema version `1`; do not add dependencies, frontend behavior, provider access,
  Alert preflight/capability discovery, pipeline stages, analysis artifacts, agents,
  tools, models, RAG, public update/delete routes, or standalone Alert CRUD.
- Produce one final Alembic revision after `20260823_01` containing both the owned Alert
  table and the type-aware LensRun uniqueness change. Existing rows require no backfill.
- Keep repository writes in the caller-owned transaction and preserve the existing
  `observation_runs.observation_id` `ON DELETE RESTRICT` retention boundary.
- Do not treat any Open/Deferred Alert pipeline/provider decision as implementation
  scope.

The one unreleased revision is completed incrementally on the feature branch. VS-01 adds
only the Alert create/read storage required by its walking skeleton. VS-03 adds and proves
the final ownership/cascade declarations. VS-04 adds and proves the runtime uniqueness
replacement and guarded downgrade. No slice may introduce one of those high-risk
behaviors before its owning slice, and no intermediate revision state may be deployed or
used outside an isolated disposable test database. The completed branch contains one
final revision matching the approved design.

After implementation-plan approval, slice structure is frozen. Only the Coordinator may
update execution status, commit SHA, handoff path, verification result, stop reason, and
other explicitly mutable execution metadata. Any change to slice goals, dependencies,
boundaries, ownership, non-goals, risk, coverage, or completion gates requires re-planning,
independent slice-plan review, and renewed human approval.

## Slice graph

```text
VS-01 -> VS-02 -> VS-03 -> VS-04
```

This plan contains exactly four slices. Execution is sequential. A slice starts only
after its dependency has passed its completion gate, including independent high-risk
review and Coordinator acceptance.

## Execution overview

| Slice | Goal | Depends on | Risk | Status | Commit | Handoff |
|---|---|---|---|---|---|---|
| VS-01 | Create/retrieve one defaulted Alert-only Observation, reject an empty aggregate, and preserve Metric-only reads | none | high-risk | PLANNED | - | - |
| VS-02 | Complete exact Alert validation, mixed/type-local topology, ordering, navigation, and atomic aggregate creation | VS-01 | high-risk | PLANNED | - | - |
| VS-03 | Enforce and prove Alert-child ownership, parent cascade, and runtime deletion restriction | VS-02 | high-risk | PLANNED | - | - |
| VS-04 | Implement and prove type-aware LensRun uniqueness and safe migration upgrade/downgrade behavior | VS-03 | high-risk | PLANNED | - | - |

## Slice definitions

### VS-01 — Alert-only persisted API walking skeleton

**Behavioral goal:** A client can omit Metric and Relationship collections, submit one
valid Alert Lens with omitted optional fields, receive `201 Created`, and follow
list/detail/nested Alert links that return the persisted definition with
`analysis_objectives: []`, `reference_periods: []`, schema version `1`, and no runtime
objects. Alert-local unknown fields are ignored and absent from canonical reads. An
existing Metric-only payload that omits `alert_lenses` remains accepted and canonical
reads add `alert_lenses: []` without changing the Metric `lenses` representation. A
request that omits both Lens collections, or supplies both as empty, is rejected before
repository persistence and leaves no aggregate residue.

**OpenSpec coverage:** “Define supported Alert Lenses” scenarios “Apply optional Alert
defaults” and “Ignore unknown Alert input fields”; “Create an Alert-only definition” and
the Metric-only compatibility path in “Create a complete valid definition”; the first
create/read path for “Persist Alert Lenses as owned definition data”; “Follow an Alert
Lens link” and the Metric-link compatibility path; the no-Lens portion of “Reject an
invalid definition atomically”; tasks 1.1 required/default/extra-ignore portion, 1.2,
task 1.3 combined non-empty Lens invariant only, 2.1 create/read storage portion only,
2.3 Alert-table upgrade portion only, 2.4 first Alert child create/load path, 3.1 first
Alert projections and Metric-only source isolation, 3.2 first route/not-found path, 3.3
Metric-only canonical compatibility, 4.1 defaulted/extra-ignore and empty-aggregate cases,
4.2 Alert-only repository/service path, 4.3 Alert-only/Metric-only and empty-aggregate API
paths, empty-aggregate no-residue portion of 4.4, and 5.1 focused verification.

**Dependencies:** none.

**Vertical boundary:** HTTP `POST /api/v1/observations` -> default omitted `lenses`,
`alert_lenses`, and `relationships` -> combined aggregate cardinality validation -> either
pre-persistence rejection when both Lens collections are empty or, for one minimal Alert
Lens, Alert-local typed validation -> source checks over Metric `lenses` only ->
caller-owned transaction -> repository construction of one Alert child -> PostgreSQL Alert
row -> eager repository load -> typed summary/detail/Alert projections -> nested Alert
`GET`. The slice does not alter `LensRunModel`, the `lens_runs` constraint, or runtime
repository behavior, and it does not implement guarded uniqueness downgrade behavior.

**Expected code impact:** dedicated Alert selector/create/reference/response contracts,
additive collection defaults, and the combined non-empty Lens aggregate validator in
`backend/src/app/observations/contracts.py`; the minimum Alert child relationship/model and
explicit table fields needed for ordered create/read in
`backend/src/app/infrastructure/persistence/models.py`; the Alert-table portion of one new
revision under `backend/migrations/versions/`; Alert construct/load logic in
`backend/src/app/infrastructure/persistence/repository.py`; canonical projections and
nested read in `backend/src/app/observations/service.py` and `api.py`; focused
contract/API/repository tests and one PostgreSQL-backed walking-skeleton test that also
proves empty aggregate rejection leaves no rows. The final parent deletion
cascade/delete-orphan behavior belongs to VS-03 and the runtime constraint and downgrade
guard belong to VS-04.

**Contracts consumed/changed:** consumes the existing Observation aggregate transaction,
Metric contracts, relative-href conventions, `JSONType`, and schema-version behavior.
Adds only the approved Alert definition input/output needed by the valid Alert-only path,
`alert_lenses` projections, explicit Alert child storage, collection defaults, and the
approved invariant that at least one Lens exists across the two type-specific collections.
The selector query remains an unmodified string; no provider port or runtime Alert
contract is added.

**Non-goals:** exhaustive invalid-field behavior; multiple Alert ordering; mixed same-ID
topology; duplicate/type-local ID semantics; Relationship topology and edge cases; late
persistence-failure rollback proof; parent deletion/cascade or delete-orphan semantics;
runtime LensRun uniqueness; migration uniqueness replacement or guarded downgrade;
provider/capability/preflight behavior; pipeline execution; frontend or dependency changes.

**Focused verification:** validate minimal and defaulted Alert contracts, including
Alert-local unknown fields disappearing from output; prove omitted collections default to
empty, while omitting both Lens collections and explicitly supplying both as empty produce
a client-validation error before repository invocation; on a fresh PostgreSQL database,
assert those rejected requests leave no Observation, Metric, Alert, or Relationship row;
issue PostgreSQL-backed create/list/detail/nested-Alert reads and assert stable identity,
schema version `1`, empty optional lists, relative hrefs, and absent runtime fields; read a
Metric-only aggregate and assert unchanged Metric content plus `alert_lenses: []`; assert
the new revision follows `20260823_01`, creates only the required Alert-definition storage
for this slice, contains no backfill/schema-version rewrite, and does not touch `lens_runs`;
run existing Observation contract/API regressions and Ruff on changed files.

**Context pack:** root `AGENTS.md`; `.agents/PROJECT_KNOWLEDGE.md`; approved proposal;
observation-definition-api requirements “Define supported Alert Lenses,” “Persist Alert
Lenses as owned definition data,” “Create an atomic, versioned Observation definition,”
and “Read and navigate definitions”; design decisions “Keep separate public collections,”
“Isolate Alert-specific validation,” and “Add explicit Alert child storage”; ADR-161
through ADR-163; Observation concept section 4.4 and Alert concept section 3; current
Observation contracts/service/API, persistence models/repository, migrations, and
Observation tests.

**Handoff expectations:** identify exact new contract/model/projection names; record the
revision ID and Alert table/column names; show the minimal fixture and create/load path;
provide PostgreSQL walking-skeleton, empty-aggregate rejection/no-residue, and Metric
compatibility evidence; confirm duplicate/type-local ID and Relationship topology remain
for VS-02 and no runtime model/constraint/downgrade-guard change occurred; list focused
commands/results and candidate shared knowledge with evidence.

**Risk:** high-risk.

**Completion gate:** the minimal Alert-only request succeeds through PostgreSQL-backed
API/persistence and all linked reads; ignored Alert extras are absent; Metric-only
create/read is compatible with canonical empty `alert_lenses`; omitted or explicit empty
Lens collections are rejected before repository persistence and leave no aggregate rows;
migration and ORM agree on the create/read storage introduced in this slice and
`lens_runs` is unchanged; no provider/pipeline/update/delete/generalization scope is
present; focused tests and Ruff pass; independent high-risk review has no unresolved
BLOCKER/HIGH finding; one atomic commit and `implementation/VS-01-handoff.md` exist.

### VS-02 — Exact mixed topology, ordering, navigation, and atomic creation

**Behavioral goal:** Metric-only, Alert-only, and mixed Observations obey the complete
contract. Exact opaque Alert strings and independently ordered collections round-trip;
same-ID Metric and Alert definitions remain distinct through type-specific links;
Relationships and source enablement remain Metric-only; every VS-02-owned invalid member,
topology, or late aggregate write is rejected atomically with no parent or child residue,
while VS-01's empty-aggregate rejection remains intact.

**OpenSpec coverage:** “Create a valid Alert Lens with exact ordered values” and “Reject
invalid Alert configuration atomically”; “Round-trip ordered Alert children”; all
remaining “Create an atomic, versioned Observation definition” behavior after VS-01's
no-Lens rejection, including mixed type-local IDs and invalid-member/Relationship atomic
rejection; all “Define supported Metric Lenses” and “Define engineer-authored Metric
Relationships” scenarios; all remaining “Read and navigate definitions” scenarios; tasks
1.1 complete validation, task 1.3 duplicate/type-local ID and Metric-only Relationship
topology portions, 2.4 mixed/ordered and transaction behavior, 3.1 final
projections/source isolation, 3.2 equal-ID/not-found completion, 3.3 full public
compatibility, remaining portions of 4.1, 4.2, and 4.3, late-failure atomicity and
recognized-field/order portions of 4.4, and 5.1 focused verification.

**Dependencies:** VS-01.

**Vertical boundary:** Metric-only, Alert-only, and mixed HTTP inputs -> complete
type-specific validation namespaces -> Metric-only Relationship and source lookup -> one
aggregate transaction -> independently positioned Metric, Alert, and Relationship rows ->
list/detail/type-specific projections. Contract-invalid requests stop before repository
persistence; a deliberately late aggregate persistence failure rolls the caller-owned
transaction back; accepted same-ID mixed input can follow both hrefs to distinct resources.

**Expected code impact:** complete Alert and aggregate validators in
`backend/src/app/observations/contracts.py`; finish mixed projection/repository/service
behavior from VS-01; extend `backend/tests/test_observation_contracts.py` and
`backend/tests/test_observation_api.py`; add or extend PostgreSQL Observation-definition
integration coverage for atomic rollback, recognized-field round trips, and independent
collection order. No runtime model/constraint, migration downgrade, deletion ownership,
dependency, provider module, or generic Lens abstraction is added.

**Contracts consumed/changed:** consumes VS-01 Alert contracts/table/routes and existing
Metric/Relationship contracts. Finalizes non-mutating non-whitespace checks, exact-string
duplicate detection, direct offset strings, type-local ID sets, Metric-only participant
resolution, and Metric-only source validation. Existing Metric field names, response
shapes, capabilities, and preflight contracts remain unchanged.

**Non-goals:** parent deletion cascade/delete-orphan or runtime-dependent deletion
restriction; runtime LensRun cardinality; migration constraint replacement/downgrade;
provider query syntax checks or automatic predicates; Alert capability/preflight;
pipeline/agent/tool/result work; future replacement update.

**Focused verification:** table-driven tests cover every accepted/rejected Alert field,
exact whitespace-bearing opaque strings without trimming, duplicate versus distinct list
values, offset grammar/default/order, Alert-local extra-ignore while existing models stay
strict, duplicate IDs within a type, and same IDs across types; topology tests cover
Metric-only Relationships, same-ID positive resolution, Alert-only participant rejection,
and invalid structures; PostgreSQL-backed repository/API tests prove exact recognized-field
and independent-order round trips, equal-ID links, and Alert 404; atomic tests prove invalid
request members and a late persistence failure leave no Observation, Metric, Alert, or
Relationship row; regress VS-01's omitted/explicit-empty aggregate rejection, Metric
create/list/detail/Lens/Relationship, capability, and preflight behavior; assert no new
public update/delete route.

**Context pack:** VS-01 handoff; full approved observation-definition-api delta spec;
design decisions on validation, topology, paths, storage, and layered tests; ADR-088 and
ADR-161 through ADR-163; Observation concept sections 4.4, 5.3, 8.1, and 10; Alert concept
sections 3.2 through 4.2; canonical observation-definition-api spec; current Observation
contracts/service/API and all Observation tests; VS-01 model/repository/migration changes.

**Handoff expectations:** enumerate the accepted/rejected contract matrix; record exact
string/order/extra behavior; show same-ID definition and route evidence; show Metric-only
Relationship/source-resolution evidence; show both validation-time and transaction-time
no-residue evidence; list compatibility commands/results; confirm ownership and runtime
migration behavior remain for later slices; candidate shared knowledge with evidence.

**Risk:** high-risk.

**Completion gate:** every Observation-definition scenario except parent-deletion
ownership passes focused unit/API/PostgreSQL verification; VS-02-owned invalid-member,
topology, and late-failure paths leave no aggregate residue, while VS-01's empty-aggregate
rejection regresses green; ordered mixed same-ID definitions and links are unambiguous;
Metric contracts/capabilities/preflight are unchanged; no
ownership/runtime/migration-rollback or out-of-scope code appears; Ruff passes;
independent high-risk review has no unresolved BLOCKER/HIGH finding; one atomic commit and
`implementation/VS-02-handoff.md` exist.

### VS-03 — Alert-definition ownership and deletion integrity

**Behavioral goal:** Alert definition rows have no lifecycle outside their parent:
deleting an Observation Definition without runtime dependents removes all Alert children
in the same transaction with no orphan, while an existing ObservationRun retains the
current database restriction and blocks parent deletion without losing the parent or its
children.

**OpenSpec coverage:** “Persist Alert Lenses as owned definition data” scenario “Cascade
owned Alert rows on parent deletion”; ownership and runtime-deletion-restriction portions
of tasks 2.1, 2.3, 4.4, and 5.1.

**Dependencies:** VS-02.

**Vertical boundary:** final ORM parent/child ownership and final Alert foreign-key
declaration -> caller-owned PostgreSQL transaction -> either SQLAlchemy `AsyncSession`
deletion of a loaded parent or direct SQL/database parent deletion -> Alert-row cascade for
an unreferenced parent or existing ObservationRun `RESTRICT` failure -> commit/rollback ->
direct database verification of parent and child presence. No repository delete method is
introduced or exercised.

**Expected code impact:** complete the Alert relationship's `all, delete-orphan`
ownership and the Alert child `ON DELETE CASCADE` declaration in
`backend/src/app/infrastructure/persistence/models.py`; complete the matching ownership
portion of the single unreleased Alembic revision; add focused PostgreSQL integration tests
for ORM session deletion, direct SQL/database cascade, no-orphan outcome, and runtime
dependent restriction. No repository/service/API delete method, snapshot update, runtime
unique constraint, downgrade guard, or unrelated production seam is added.

**Contracts consumed/changed:** consumes the VS-01 Alert table/model and VS-02 final
aggregate behavior, existing caller-owned transaction semantics, and the existing
`observation_runs.observation_id` `ON DELETE RESTRICT` foreign key. Completes only the
approved parent ownership behavior; it does not create a public or independent lifecycle.

**Non-goals:** public Observation update/delete; standalone Alert CRUD; future snapshot
replacement implementation; runtime same-ID LensRuns; `lens_runs` constraint changes;
migration downgrade restoration/guard; a repository delete method; destructive cleanup;
provider/pipeline/frontend work.

**Focused verification:** on a fresh disposable PostgreSQL database upgraded with the
current revision, prove deleting a loaded parent through SQLAlchemy `AsyncSession.delete`
removes all ordered Alert children in the same committed transaction; prove a direct SQL
`DELETE` of the parent also cascades and leaves no orphan; create an ObservationRun and
prove each applicable parent-deletion path raises integrity failure and rollback retains
both parent and Alert children; inspect metadata and migrated foreign keys for exact
CASCADE/RESTRICT targets; assert no repository/service/API delete method or route was
added; regress VS-01/VS-02 create/read/order and atomicity tests; run Ruff on changed files.

**Context pack:** VS-01 and VS-02 handoffs; approved “Persist Alert Lenses as owned
definition data” requirement; design decisions “Add explicit Alert child storage” and
“Keep update/delete transport out of scope while enforcing ownership”; ADR-161 and
ADR-163; Observation concept section 4.4; Alert concept sections 3.3 and 3.4; current
models, migration, caller-owned session transaction behavior, runtime parent foreign key,
and Observation/runtime PostgreSQL fixtures.

**Handoff expectations:** record exact ORM cascade and foreign-key declarations; show
ORM-session and direct-database cascade evidence; show ObservationRun restriction and
rollback evidence; confirm no repository/service/API delete method or public lifecycle and
no runtime uniqueness change; list focused commands/results and candidate shared knowledge
with evidence.

**Risk:** high-risk.

**Completion gate:** ORM and database ownership declarations agree; unreferenced parent
deletion removes Alert children without orphans; runtime-dependent deletion is rejected
and preserves parent/children; all ownership tests pass on a fresh disposable PostgreSQL
database; earlier create/read/atomicity behavior regresses green; no repository/service/API
delete method, public lifecycle, runtime uniqueness, downgrade guard, or out-of-scope code
appears; Ruff passes;
independent high-risk review has no unresolved BLOCKER/HIGH finding; one atomic commit and
`implementation/VS-03-handoff.md` exist.

### VS-04 — Type-aware LensRun identity and guarded migration rollback

**Behavioral goal:** One ObservationRun accepts Metric and Alert LensRuns with the same
Lens ID, rejects duplicate LensRuns with the same type-aware identity, and retrieves the
distinct runs without changing existing lifecycle/failure semantics. The final migration
upgrades from `20260823_01` without backfill, exposes the approved table and constraints,
restores the old runtime key only when safe, and refuses unsafe downgrade before dropping
Alert data or runtime uniqueness protection.

**OpenSpec coverage:** all scenarios under runtime-persistence “Persist correlated runtime
executions without duplicating definitions”; tasks 2.2, final runtime-constraint and
guarded-downgrade portions of 2.3, runtime uniqueness and migration portions of 4.4, all of
4.5, 5.1 final focused verification, and 5.2.

**Dependencies:** VS-03.

**Vertical boundary:** existing Observation definition -> ObservationRun ->
`RuntimePersistenceRepository.create_lens_run` -> final ORM/database unique key
`(observation_run_id, lens_type, lens_id)` -> retrieval of distinct typed rows or atomic
integrity rejection. Migration boundary: clean `20260823_01` database -> final revision
upgrade -> schema/data assertions -> pre-downgrade duplicate query -> either explicit
refusal with all Alert/runtime data intact or safe restoration of the old key followed by
Alert table removal.

**Expected code impact:** change only `LensRunModel` uniqueness metadata and its stale
identity comment in `backend/src/app/infrastructure/persistence/models.py`; complete the
single unreleased migration with the old-key drop, type-aware-key creation, exact names,
and non-destructive pre-downgrade guard; extend runtime unit/integration tests for
cross-type acceptance, same-type rejection, typed retrieval, existing lifecycle/failure
regressions, upgrade structure, safe downgrade, and unsafe refusal. Production repository
changes are not expected because `lens_type` is already persisted and flush provides
integrity feedback.

**Contracts consumed/changed:** consumes `ObservationRunModel`, `LensRunModel`,
`LensType`, `LensRunInput`, runtime repository flush-without-commit behavior, and existing
lifecycle/retrieval contracts. Changes only the approved type-aware database identity and
the rollback safety mechanism; no new field, definition foreign key, lifecycle state, or
analytical artifact is introduced.

**Non-goals:** creating LensRuns automatically from definitions; executing an Alert Lens;
AlertAnalysisResult/provider/pipeline work; retention-policy changes; deletion ownership
changes already owned by VS-03; destructive cleanup to make downgrade pass; update/delete
API routes; frontend changes; archive, push, PR, or merge.

**Focused verification:** metadata and fresh PostgreSQL upgrade assertions prove the exact
type-aware key and absence of the old key, the final Alert table/FKs/ordered fields, no
backfill, and no schema-version rewrite; repository integration proves same-ID Metric and
Alert LensRuns coexist and retrieve with distinct types, while a duplicate same-type
insert raises integrity failure without preventing a different type; existing
pending/running/terminal/failure retrieval scenarios regress green; safe downgrade restores
the old key; unsafe downgrade detects cross-type duplicate IDs before any destructive
operation, raises, and preserves runtime rows, Alert definitions, and the upgraded
constraint. Run the focused backend suite with PostgreSQL tests enabled, `openspec validate
add-alert-lens-definition --strict`, `git diff --check`, and final `make check`.

**Context pack:** all accepted predecessor handoffs; approved runtime-persistence delta
spec; design decisions “Make runtime LensRun uniqueness type-aware” and “Use one forward
Alembic migration,” including migration risks and rollback plan; Observation concept
section 5.3; runtime contracts section 14; canonical runtime-persistence spec; current
models/repository/runtime contracts, both existing migrations, and runtime unit/integration
tests; completed Observation persistence tests and the in-progress final revision.

**Handoff expectations:** record exact old/new constraint names and final revision ID;
show cross-type acceptance, same-type rejection, and typed retrieval evidence; show fresh
upgrade, safe downgrade, and unsafe refusal/data-preservation evidence; list final focused
and whole-repository commands/results; report scope audit for dependencies, routes,
provider/pipeline/frontend code; candidate shared knowledge with evidence.

**Risk:** high-risk.

**Completion gate:** runtime uniqueness implementation and all behavioral proof land in
this slice; same-ID cross-type rows coexist, same-type duplicates fail, and existing
runtime lifecycle/retrieval remains green; the final revision matches ORM and approved
Alert ownership, refuses unsafe downgrade before data loss, and passes safe downgrade on
fresh disposable databases; all focused PostgreSQL tests, strict OpenSpec validation,
`git diff --check`, and database-enabled `make check` pass; every approved task is complete
without scope expansion; independent high-risk review has no unresolved BLOCKER/HIGH
finding; one atomic commit and `implementation/VS-04-handoff.md` exist.

## Coverage matrix

### Requirement and scenario ownership

| OpenSpec requirement/scenario | Owning slice | Verification |
|---|---|---|
| Define supported Alert Lenses — valid exact ordered values | VS-02 | Exact opaque-string/list contract and PostgreSQL/API ordered round trip |
| Define supported Alert Lenses — optional defaults | VS-01 | Defaulted Alert-only persisted API walking skeleton |
| Define supported Alert Lenses — ignore unknown Alert input fields | VS-01 | Alert/selector extra-ignore and canonical persisted/read omission |
| Define supported Alert Lenses — reject invalid Alert configuration atomically | VS-02 | Exhaustive rejection table and no-parent/no-child PostgreSQL assertions |
| Persist Alert Lenses — round-trip ordered Alert children | VS-02 | Multiple-child and ordered-list repository/API PostgreSQL round trip |
| Persist Alert Lenses — cascade owned Alert rows on parent deletion | VS-03 | ORM-session and direct-SQL/database cascade with no orphan |
| Create atomic versioned definition — complete valid Metric definition omitting `alert_lenses` | VS-01 | Existing Metric shape/order plus canonical `alert_lenses: []` |
| Create atomic versioned definition — Alert-only definition | VS-01 | PostgreSQL-backed API create/read/navigation path |
| Create atomic versioned definition — mixed type-local IDs | VS-02 | Same ID in independent collections with distinct links |
| Create atomic versioned definition — reject an empty definition atomically | VS-01 | Omitted/explicit-empty Lens collections reject before repository invocation and leave no rows |
| Create atomic versioned definition — reject invalid members or Relationships atomically | VS-02 | Validation and late transaction rollback residue checks |
| Define supported Metric Lenses — create Prometheus Metric Lens | VS-02 | Existing shape/order/source behavior regression in mixed-capable aggregate |
| Define supported Metric Lenses — reject unavailable acquisition | VS-02 | Existing source/adapter rejection remains Metric-only |
| Define Metric Relationships — conditional Relationship | VS-02 | Mixed aggregate with participants resolved only in `lenses` |
| Define Metric Relationships — always-applicable Relationship | VS-02 | Empty conditions and non-empty expected persistence regression |
| Define Metric Relationships — ignore same-ID Alert during resolution | VS-02 | Same-ID Metric/Alert positive topology test |
| Define Metric Relationships — reject Alert-only participant | VS-02 | Alert-only ID is absent from Metric lookup and aggregate is rejected |
| Define Metric Relationships — reject invalid structure | VS-02 | Existing and mixed-topology invalid tables plus no residue |
| Read/navigate — list compact Metric-only, Alert-only, mixed definitions | VS-02 | Creation order and independent href order |
| Read/navigate — follow Metric Lens link | VS-02 | Existing Metric nested route regression |
| Read/navigate — follow Alert Lens link | VS-01 | New nested Alert route round trip and 404 convention |
| Read/navigate — resolve equal IDs through type-specific links | VS-02 | Metric and Alert hrefs return distinct owned definitions |
| Runtime persistence — store in-progress execution | VS-04 | Existing lifecycle/retrieval regression under the final key |
| Runtime persistence — store same-ID Metric and Alert LensRuns | VS-04 | PostgreSQL cross-type acceptance and typed retrieval |
| Runtime persistence — reject duplicate type-aware LensRun identity | VS-04 | Same-type constraint failure with cross-type row retained |
| Runtime persistence — complete ObservationRun after Lens processing | VS-04 | Existing lifecycle direction/status regression |
| Runtime persistence — retrieve failed LensRun with failure metadata | VS-04 | Existing failure metadata/unavailable evidence regression |

### Implementation task ownership

| OpenSpec task | Explicit owner | Verification |
|---|---|---|
| 1.1 | VS-01 defaults/extra-ignore valid path; VS-02 exact validation completion | Persisted canonical output and full contract table |
| 1.2 | VS-01 | Metric-only and Alert-only create/summary/detail shapes, schema version `1` |
| 1.3 | VS-01 combined non-empty Lens invariant; VS-02 duplicate/type-local IDs and participant resolution | Empty-aggregate rejection first, then type-local identity and Relationship topology tests |
| 2.1 | VS-01 create/read storage; VS-03 final ownership semantics | Walking skeleton, then cascade/delete-orphan proof |
| 2.2 | VS-04 | ORM/database key plus cross-type/same-type PostgreSQL proof |
| 2.3 | VS-01 Alert-table upgrade; VS-03 final ownership FK; VS-04 runtime key and migration safety | One final revision, fresh upgrade, safe downgrade, unsafe refusal |
| 2.4 | VS-01 first create/load; VS-02 mixed/order/transaction completion | Repository round trips and atomic rollback |
| 3.1 | VS-01 first Alert projections; VS-02 exact mixed/order/source-isolation completion | Service/API projections and compatibility regressions |
| 3.2 | VS-01 nested route/not-found path; VS-02 equal-ID completion | Correct parent href, 404, distinct type paths |
| 3.3 | VS-01 Metric-only canonical path; VS-02 full compatibility; VS-04 whole-suite confirmation | Existing public tests and final `make check` |
| 4.1 | VS-01 default/extra valid cases and empty aggregate; VS-02 remaining exhaustive validation | Focused Pydantic/API tables |
| 4.2 | VS-01 Alert-only path; VS-02 mixed/order/atomic completion | Repository/service projections and rollback |
| 4.3 | VS-01 Alert-only/Metric-only and empty-rejection paths; VS-02 mixed/remaining-invalid/no-new-route completion | ASGI tests and route audit |
| 4.4 | VS-01 empty-aggregate no-residue; VS-02 late-failure atomicity/order; VS-03 cascade/RESTRICT; VS-04 runtime uniqueness | Each persistence behavior proven in its owning slice |
| 4.5 | VS-04 | Exact names, fresh upgrade, safe downgrade, unsafe refusal without deletion |
| 5.1 | Each slice for its owned behavior; VS-04 final focused regression | Commands/results in each handoff and final PostgreSQL run |
| 5.2 | VS-04 | Database-enabled `make check`, strict OpenSpec validation, diff check |

### High-risk behavior ownership audit

| Behavior | Implementation owner | Behavioral proof owner | Completion gate |
|---|---|---|---|
| Empty aggregate rejection | VS-01 | VS-01 | Omitted or explicit empty Lens collections reject before persistence and leave no rows |
| Invalid-member/topology and late-failure atomic rejection | VS-02 | VS-02 | No VS-02-owned invalid or late-failing write leaves parent or child residue |
| Alert child ownership and deletion | VS-03 | VS-03 | ORM-session/direct-database CASCADE, delete-orphan, and runtime RESTRICT behavior pass on PostgreSQL |
| Type-aware LensRun uniqueness | VS-04 | VS-04 | Cross-type acceptance and same-type rejection pass on PostgreSQL |
| Migration upgrade/downgrade safety | VS-04 | VS-04 | Fresh upgrade, safe downgrade, and pre-destructive unsafe refusal pass |

## Frozen plan and mutable execution state

Frozen after independent review and explicit human approval:

- implementation branch, slice count/order/graph, behavioral goals, dependencies, and
  vertical boundaries;
- OpenSpec ownership and coverage matrices;
- expected code impact, contracts, non-goals, risk, context packs, handoff expectations,
  focused verification, and completion gates.

Mutable only by the Coordinator after approval:

- plan and slice execution statuses;
- accepted commit SHAs and handoff paths;
- verification/review outcomes and knowledge-candidate disposition;
- exact stop/escalation records and other non-semantic execution notes.

Task checkboxes remain unchecked until every listed owner/sub-part has passed its slice
gate. A later slice may regress an earlier behavior but may not silently take ownership of
missing implementation. If implementation exposes a source conflict, new behavior,
missing decision, dependency need, schema change beyond the approved migration, or slice
structure problem, stop and re-plan rather than reinterpret the approved sources.

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements or
redesign decisions here.

- Planning record: the approved OpenSpec was independently reviewed and human-approved
  before this plan was created.
- Planning record: the first independent slice-plan review returned `CHANGES REQUIRED`;
  this revision co-locates each high-risk implementation with its proof, narrows VS-01,
  replaces the final persistence bucket with explicit behavior owners, and removes the
  experiment branch.
- Planning record: the latest independent slice-plan review returned `CHANGES REQUIRED`;
  this revision keeps exactly four slices, moves the combined non-empty Lens invariant and
  its no-residue proof into VS-01, and clarifies that VS-03 exercises ORM-session and direct
  SQL/database deletion without adding a repository delete method.
- All planning and implementation remain on `feature/add-alert-lens-definition`. The
  Coordinator verifies that exact branch and the expected clean/known starting state
  before every dispatch. No candidate or experiment branch is created.
- Default execution order is VS-01, VS-02, VS-03, VS-04. No concurrent dispatch.
- Every slice is high-risk because it changes a strict public contract, persistence
  transaction/ownership semantics, or runtime/migration integrity. Each requires a fresh
  independent high-risk slice review before Coordinator acceptance.
- Each implementer uses a fresh context, reads its context pack and accepted predecessor
  handoffs, runs focused verification and self-review, creates one atomic commit by
  default, and writes the repository-standard handoff.
- Because one unreleased revision is completed across slices, every migration-level test
  uses a newly created disposable database upgraded from the declared predecessor. Never
  reuse a database already stamped with an earlier intermediate form of that revision,
  and never use the developer's ordinary local database for upgrade/downgrade tests.
- VS-04 final verification requires PostgreSQL-backed tests to run rather than skip.
- Completion of VS-04 means ready for official change verification and independent final
  implementation review. It does not authorize archive, push, PR creation, merge, or work
  on `main`.
