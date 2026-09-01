# Implementation Plan — add-alerts-analysis-pipeline

**Status:** HUMAN_APPROVED
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-alerts-analysis-pipeline`
**Candidate branch:** `feature/add-alerts-analysis-pipeline`
**Planning-workflow baseline:** acceptance-evidence/change-map/optional-sketch revision 1

## Authority and constraints

This file describes how the approved change will be implemented. It does not redefine
what must be implemented. Accepted ADRs/normative contracts and the approved OpenSpec
remain authoritative.

Approved change sources:

- `openspec/changes/add-alerts-analysis-pipeline/proposal.md`
- `openspec/changes/add-alerts-analysis-pipeline/specs/alerts-analysis-pipeline/spec.md`
- `openspec/changes/add-alerts-analysis-pipeline/design.md`
- `openspec/changes/add-alerts-analysis-pipeline/tasks.md`

Architecture and accepted-contract sources:

- `docs/architecture/README.md`
- `docs/architecture/02_architecture_principles_and_runtime.md`
- `docs/architecture/03_ADR_log.md`: ADR-089 through ADR-132 and ADR-152
- `docs/architecture/04_pipeline_and_agent_concepts.md`
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`
- `docs/architecture/10_open_decisions_and_backlog.md`
- `docs/architecture/13_alert_lens_and_analysis_concept.md`
- `docs/architecture/14_alerts_analysis_pipeline_detailed.md`
- `docs/architecture/15_alert_analysis_result_contract.md`
- `docs/architecture/16_alert_analysis_agent.md`
- `docs/architecture/17_deterministic_alert_analyzer.md`
- `docs/architecture/18_alert_analysis_result_builder.md`
- `docs/architecture/19_alert_provider_adapter.md`
- `docs/architecture/20_alert_analytical_tools.md`
- `openspec/specs/observation-definition-api/spec.md`
- `openspec/specs/runtime-persistence/spec.md`

Repository constraints:

- Implement only one existing, already-running Alert LensRun; do not create top-level
  runtime objects or add orchestration, scheduling, retry, recovery, or idempotency.
- Keep Alert contracts, deterministic components, and provider/agent/tool ports
  framework- and provider-neutral. `app.alerts` has no direct SQLAlchemy, PydanticAI,
  Jira client, or provider SDK imports; one infrastructure composition function owns
  ORM/session interaction through the existing runtime repository.
- Reuse `RuntimePersistenceRepository`, `LensAnalysisResultInput`, the existing runtime
  artifact table, and caller-owned transaction; add no repository, table, or migration.
- Keep provider/agent/tool work outside the write transaction. Only terminal transition,
  optional artifact insertion, flush, and caller commit belong to that transaction.
- Add no dependency. Reuse the installed constrained `pydantic-ai-slim` dependency with
  an injected model and no production provider/model default or provider extra.
- Add no Jira endpoint, transport, credentials, concrete field mapping, pagination,
  retry/backoff, production model configuration, public API, frontend, preflight, RAG,
  cross-Lens analysis, or raw/transient data persistence.
- Unregistered, scope-expanding, and over-budget optional requests must be rejected
  before forbidden execution. The plan does not invent a new public terminal reason for
  a rejected request; public failure behavior remains limited to approved agent/error,
  timeout, completion-validation, and result-builder mappings.

After human approval, slice structure, acceptance IDs, and proof levels are frozen. Only
the Coordinator may update execution evidence/results and other explicitly mutable
metadata. Acceptance sources, GIVEN/WHEN/THEN assertions, counterexample guards, and
ownership are frozen with the IDs and proof levels. Adding, removing, merging,
renumbering, or changing them requires re-planning, independent slice-plan review, and
human re-approval. Acceptance IDs cite approved normative clauses/scenarios; task numbers
are supplementary traceability, and process-only tasks remain completion-gate conditions.

Execution uses `PLANNED -> READY -> IN_PROGRESS -> COMPLETE`; `BLOCKED` records a defined
stop/escalation. After human approval, the Coordinator marks VS-01 `READY` and commits
that initialization metadata. Before each delegation it commits `READY -> IN_PROGRESS`
and the active assignment so the Implementer starts clean. The Implementer creates the
atomic slice code/tests/handoff commit with deviation dispositions `PENDING`. The
Coordinator then commits `ACCEPT_LOCAL`/`N/A` dispositions before high-risk review;
`ESCALATE_STRUCTURAL` records the stop reason and stops execution. Reviews and corrections
operate on committed candidates. After acceptance, the Coordinator commits accepted
implementation/correction SHAs, task/status metadata, `IN_PROGRESS -> COMPLETE`, and any
newly dependency-satisfied `PLANNED -> READY` transitions. The tree must be clean at every
Implementer/Reviewer boundary.

## Slice graph

```text
VS-01 -> VS-02 -> VS-03 -> VS-04 -------------------------------> VS-09
                  |        |
                  |        +-> VS-06 -> VS-07 -> VS-08 ----------+
                  +-> VS-05 ----^                 ^
                           +-----------------------+
```

VS-06 depends on VS-04 and VS-05. VS-07 depends on VS-06. VS-08 depends on VS-05 and
VS-07. VS-09 depends on VS-03, VS-04, VS-07, and VS-08. Default execution remains
sequential in numerical order; graph edges express prerequisites, not authorization for
parallel implementation.

## Execution overview

| Slice | Goal | Depends on | Risk | Status | Commit | Handoff |
|---|---|---|---|---|---|---|
| VS-01 | Persist a zero-record completed Alert walking skeleton | none | high-risk | COMPLETE | d1dc5b3, 5933bb5, af65a93 | `implementation/VS-01-handoff.md` |
| VS-02 | Persist representative non-zero deterministic evidence and fake-agent findings | VS-01 | high-risk | READY | - | - |
| VS-03 | Add independent references, invalid subsets, partial precedence, and partial persistence | VS-02 | high-risk | PLANNED | - | - |
| VS-04 | Persist every mandatory failure with no Alert artifact | VS-03 | high-risk | PLANNED | - | - |
| VS-05 | Execute the bounded optional registry and retain only allowed failure traces | VS-03 | high-risk | PLANNED | - | - |
| VS-06 | Enforce canonical evidence references through persisted results | VS-04, VS-05 | high-risk | PLANNED | - | - |
| VS-07 | Enforce exhaustive result invariants and builder failure | VS-06 | high-risk | PLANNED | - | - |
| VS-08 | Translate the accepted boundary through injected PydanticAI | VS-05, VS-07 | high-risk | PLANNED | - | - |
| VS-09 | Prove transaction rollback, whole-change conformance, and documentation | VS-03, VS-04, VS-07, VS-08 | high-risk | PLANNED | - | - |

## Slice definitions

### VS-01 — Zero-record persisted walking skeleton

**Behavioral goal:** Given one existing running Alert LensRun with a frozen Alert Lens
context, no configured references, and a successful empty fake provider response, execute
the real pipeline without invoking an agent and atomically persist one strict completed
AlertAnalysisResult with zero activity, empty findings, `overall_importance=none`, and no
duration statistics.

**OpenSpec coverage:** representative and non-running scenarios under “Analyze only an
immutable existing Alert LensRun”; zero-record portions of current acquisition, mandatory
evidence, agent gating, strict result, fake-integration, and completed persistence;
tasks 1.1-1.2 foundations, empty/current-window portion of 1.3, zero-record portion of
2.1, zero-record/envelope portions of 5.1 and 5.4, walking-skeleton portions of 6.1-6.3,
and focused verification/docstrings in 7.1-7.2.

**Dependencies:** none.

**Vertical boundary:** immutable context derived from an existing running LensRun ->
provider-neutral fake current acquisition -> empty normalization -> mandatory zero
evidence -> zero-record gate -> strict builder and ORM-neutral terminal outcome ->
infrastructure persistence composer uses the existing repository inside the caller-owned
transaction -> real LensRun completed transition plus artifact insertion/flush -> commit
and retrieval.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/alerts/contracts.py` | add | Minimal strict context, provider, zero-evidence, zero-result, and pipeline outcome contracts exercised here |
| `backend/src/app/alerts/ports.py` | add | Framework-neutral provider and agent protocols used by the walking skeleton |
| `backend/src/app/alerts/normalization.py` | add | Current-window derivation and successful-empty normalization |
| `backend/src/app/alerts/analyzer.py` | add | Mandatory zero-record activity/status evidence |
| `backend/src/app/alerts/result_builder.py::AlertResultBuilder` | add | Sole zero-record completed-result constructor and persistence-envelope projection |
| `backend/src/app/alerts/pipeline.py::AlertAnalysisPipeline` | add | Validate context and produce one framework/provider/ORM-neutral terminal outcome after pre-transaction analysis |
| `backend/src/app/infrastructure/persistence/alert_runtime.py::persist_alert_terminal` | add | Production composition seam accepting session, ORM LensRun, terminal outcome, and existing repository; perform transition plus conditional artifact insertion without a new repository abstraction |
| `backend/src/app/infrastructure/persistence/repository.py::RuntimePersistenceRepository` | reuse | Existing transition/artifact methods remain the only repository operations |
| `backend/tests/test_alert_analysis_pipeline.py` | add | Pure/fake pipeline proof and phase-order trace |
| `backend/tests/test_runtime_persistence_integration.py` | modify | Real PostgreSQL zero-record completed round trip |

**Contracts consumed/changed:** consumes existing Alert Lens definition fields, UUID/string
runtime identity primitives, `LensAnalysisResultInput`, `LensRunStatus`,
`StructuredReason`, and repository transition/flush-without-commit behavior. Adds only the
strict Alert contracts and terminal outcome first exercised by the zero-record path. The
infrastructure composer, not `app.alerts`, supplies the existing ORM LensRun and session
to the unchanged runtime repository. The outcome is ORM-neutral but intentionally carries
the accepted runtime persistence envelope/status/reason contracts. The provider query
stays opaque and no runtime object is created.

**Non-goals:** non-zero records; invalid-record handling; configured references; partial
or failed outcomes; optional tools; PydanticAI; non-zero agent request/completion;
evidence-reference grammar beyond the empty-finding case; rollback fault injection;
provider transport; schema/API/frontend changes.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS01-AC01 | Analyze immutable run / “Analyze a prepared running Alert LensRun” | Existing running Alert LensRun and frozen context whose IDs/window/source/query differ from unrelated fixtures | Analyze once | Every provider/build/persistence correlation uses only that context; no ObservationRun or LensRun is created | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_running_context_is_the_only_pipeline_scope`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_alert_zero_record_walking_skeleton_persists_completed_result` |
| VS01-AC02 | Analyze immutable run / “Reject a non-running Alert LensRun” | Pending, completed, partial, and failed LensRun variants | Invoke before acquisition | Each is rejected; provider and agent call counts remain zero; no artifact or lifecycle mutation occurs | service | `backend/tests/test_alert_analysis_pipeline.py::test_alert_pipeline_rejects_every_non_running_status_before_acquisition` |
| VS01-AC03 | Mandatory evidence, zero gate, strict result / zero-record scenarios | Successful empty current response and an agent fake that fails if called | Execute through builder | Activity/status are zero, findings are `[]`, importance is `none`, duration/provider-importance sections are absent, agent count is zero | unit + service | unit: `backend/tests/test_alert_contracts.py::test_zero_record_result_has_exact_sections`; service: `backend/tests/test_alert_analysis_pipeline.py::test_zero_record_path_skips_agent_and_builds_strict_result` |
| VS01-AC04 | Atomic persistence / completed usable path | Existing running row and empty provider result | Execute and reload through real PostgreSQL | LensRun is completed with no reason; exactly one correlated version-1.0 Alert artifact round-trips; long-running phases precede transaction open | PostgreSQL | `backend/tests/test_runtime_persistence_integration.py::test_alert_zero_record_walking_skeleton_persists_completed_result` |

**Counterexample guards:** VS01-AC01 must fail a pipeline that manufactures another
LensRun or reads scope from the provider fake. VS01-AC03 uses a fail-on-call agent.
VS01-AC04 records phase order so opening the transaction before acquisition fails.

#### Technical verification

- Approved task 1.1 internal strict-model strategy: run
  `backend/tests/test_alert_contracts.py::test_foundational_alert_models_are_strict_and_preserve_runtime_identity`.
  This is implementation conformance, not a behavioral acceptance ID.

#### Implementation sketch (optional)

Illustrative and non-normative; it clarifies the transaction boundary:

```text
validate existing running context
current = await provider.acquire(source, opaque_query, current_window)
normalized = normalize(current)          # empty success
evidence = analyzer.analyze(normalized)  # mandatory zero evidence
result = builder.build_zero(context, evidence)

return terminal_outcome(completed, reason=None, artifact=result.persistence_envelope)

caller opens transaction:
  await infrastructure.persist_alert_terminal(session, lens_run, outcome, repository)
      -> repository.transition_lens_run(completed)
      -> repository.add_lens_result(result.persistence_envelope)
      -> flushes; never commits
caller commits
```

**Focused verification commands:** `cd backend && uv run pytest
tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py -q`; with
`IPO_ALERTS_TEST_DATABASE_URL` exported,
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_alert_zero_record_walking_skeleton_persists_completed_result
-q`; `cd backend && uv run ruff check src/app/alerts
src/app/infrastructure/persistence/alert_runtime.py tests/test_alert_contracts.py
tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`; `cd backend && uv run ruff format --check
src/app/alerts src/app/infrastructure/persistence/alert_runtime.py
tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`.

**Context pack:** root `AGENTS.md`; approved immutable-run, current-acquisition,
mandatory-evidence, zero-gate, strict-result, persistence, and fake-integration sections;
design decisions on package/persistence, stage order, deterministic components, strict
result, and test design; ADR-089-105, ADR-116-124; runtime-persistence spec; current
Metrics pipeline/result builder and runtime repository/contracts/models/tests.

**Handoff expectations:** evidence for VS01-AC01 through VS01-AC04; actual contract,
pipeline, builder, and test symbols; phase trace; PostgreSQL artifact projection; any
change-map deviation; explicitly deferred non-zero/partial/failed/tool/adapter behavior;
standard commit, limitations, plan-change, and shared-knowledge fields.

**Risk:** high-risk

**Completion gate:** all `VS01-AC*` obligations have passing evidence at their specified
levels; focused and PostgreSQL checks plus nearby runtime regressions pass; no future
contract shells or excluded integrations appear; task 1.1 technical verification and Ruff
pass; independent high-risk review returns `SLICE REVIEW PASS`; one atomic implementation
commit and handoff exist, followed by Coordinator acceptance metadata.

### VS-02 — Representative non-zero completed analysis

**Behavioral goal:** Extend the persisted pipeline for representative valid active and
resolved records so lifecycle-overlap filtering, canonical normalization, mandatory
activity/status/duration/provider-importance evidence, one strict bounded fake-agent
completion, resolvable findings, and a completed Alert result work end to end.

**OpenSpec coverage:** boundary-spanning current record; missing occurrence default and
record-based status scenario; non-zero record with zero occurrences; representative
non-zero agent request/completion and strict completed result; tasks 1.1-1.3 valid
non-zero portions, 2.1, valid projections in 4.1, completed/non-zero portions of 5.1 and
5.4, pipeline composition in 6.1-6.3, and focused verification in 7.2.

**Dependencies:** VS-01.

**Vertical boundary:** frozen running context -> successful fake provider records with
boundary-spanning lifecycle -> canonical normalization -> deterministic evidence ->
strict source-agnostic request -> valid fake-agent findings/importance -> strict builder
with simple same-result evidence references -> established transaction -> completed
LensRun/artifact persistence and retrieval.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/alerts/contracts.py` | modify | Canonical non-zero records, mandatory evidence, strict agent request/completion, findings, and non-zero result variants |
| `backend/src/app/alerts/normalization.py` | modify | Required-field validity, overlap filtering, normalized status, and canonical record projection |
| `backend/src/app/alerts/analyzer.py` | modify | Effective occurrences, record status, full-lifecycle duration, finite unrounded statistics, native importance grouping |
| `backend/src/app/alerts/result_builder.py` | modify | Completed non-zero assembly and basic exact-target reference resolution |
| `backend/src/app/alerts/pipeline.py` | modify | Mandatory non-zero fake-agent path |
| `backend/tests/test_alert_contracts.py` | add | Strict contract and excluded-field assertions |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Representative deterministic/fake-agent end-to-end evidence |
| `backend/tests/test_runtime_persistence_integration.py` | modify | Completed non-zero PostgreSQL round trip |

**Contracts consumed/changed:** extends only contracts exercised by valid non-zero data.
The agent sees Lens semantics, normalized current records, mandatory evidence, and
successful comparisons (empty here), but never query/provider payload/reference records,
Metrics/Logs/Relationship/RAG data. `overall_importance=none` remains impossible for
non-zero completion.

**Non-goals:** invalid/duplicate records; acquisition failures; configured references;
partial/failure precedence; optional tools; exhaustive evidence-URI grammar; contextual
builder failures; PydanticAI; persistence fault injection.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS02-AC01 | Current overlap / “Include an alert spanning the window boundary” | One active record starting before the window and one resolved record ending after window start | Normalize and analyze | Both remain; normalized statuses and full, unclipped durations use ended-at or analysis timestamp | unit | `backend/tests/test_alert_analysis_pipeline.py::test_overlap_normalization_and_full_lifecycle_durations` |
| VS02-AC02 | Mandatory evidence / missing occurrence scenario | Active record with missing count and resolved record with count 3, with different native importance values | Analyze | Record count 2, occurrence count 4, status counts 1/1/0, exact min/max/unrounded mean, native importance grouped without severity mapping | unit | `backend/tests/test_alert_analysis_pipeline.py::test_mandatory_evidence_uses_effective_occurrences_and_record_statuses` |
| VS02-AC03 | Agent gate and strict projection / “Do not skip records with zero occurrences” | Valid record with explicit occurrence 0, distinct Lens name/description, mandatory evidence, and a fail-if-skipped fake agent | Execute pipeline | Agent is invoked once and receives the exact Lens name/description, normalized current record, mandatory evidence, and empty successful-comparison list; query, raw payload, reference records, provider configuration, cross-Lens, and knowledge data are absent; completion cannot use `none`; completed artifact persists | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_nonzero_zero_occurrence_invokes_agent_with_exact_projection`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_nonzero_zero_occurrence_invokes_agent_with_exact_projection_and_persists` |
| VS02-AC04 | Strict non-zero result | Canonical record containing description, source status, native importance, occurrence count, and source reference plus one valid finding | Build and retrieve | Exact completed 1.0 envelope, canonical record fields, source-provider provenance, evidence, and finding round-trip; opaque query and raw provider payload are absent | unit + PostgreSQL | unit: `backend/tests/test_alert_contracts.py::test_representative_nonzero_alert_result_is_strict`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_representative_nonzero_alert_result_round_trips_strictly` |
| VS02-AC05 | Current lifecycle-overlap formula | Mixed valid in-scope records plus records with `started_at == window.end`, `ended_at == window.start`, wholly-before, wholly-after, and one just inside each strict boundary | Normalize and complete pipeline | Equality/outside records are scope exclusions, not invalid rejections: they are absent without creating `invalid_records`; just-inside records are retained, proving exact `<` and `>` operators | unit + service | unit: `backend/tests/test_alert_analysis_pipeline.py::test_lifecycle_overlap_uses_strict_window_boundaries`; service: `backend/tests/test_alert_analysis_pipeline.py::test_scope_exclusions_do_not_make_result_partial` |
| VS02-AC06 | Bounded-agent request/completion requirement clauses; tasks 1.1/4.1 trace | Strict agent request/completion fixtures with distinct required values plus raw-provider, reference-record, cross-Lens, knowledge, scope, unknown, or missing completion fields | Validate/project at the agent boundary | Required agent fields remain exact; prohibited observational/context fields are absent; unknown/missing completion fields are invalid; valid findings are unique and Lens-local | unit + service | unit: `backend/tests/test_alert_contracts.py::test_agent_request_and_completion_contracts_are_strict`; service: `backend/tests/test_alert_analysis_pipeline.py::test_agent_projection_is_exactly_bounded` |

**Counterexample guards:** VS02-AC01 must fail timestamp-inside-window filtering or
duration clipping. VS02-AC02 uses occurrence counts different from record cardinality.
VS02-AC03 uses `record_count=1, occurrence_count=0` so a gate based on occurrences fails
and sentinel values prove exact positive/negative projection. VS02-AC05 must fail
inclusive overlap operators or an implementation that misclassifies scope exclusions as
invalid-record incompleteness. The controlled `unknown` status remains accepted by strict
contracts/build validation, but no positive normalization trigger is invented because the
approved source reserves the value without defining such a provider-neutral input case.

#### Implementation sketch (optional)

N/A — the existing Metrics package and VS-01 establish the orchestration shape; this
slice adds deterministic calculations whose exact expectations live in proof fixtures.

**Focused verification commands:** `cd backend && uv run pytest
tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_nonzero_zero_occurrence_invokes_agent_with_exact_projection_and_persists
tests/test_runtime_persistence_integration.py::test_representative_nonzero_alert_result_round_trips_strictly
-q`; `cd backend && uv run ruff check src/app/alerts tests/test_alert_contracts.py
tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py`;
`cd backend && uv run ruff format --check src/app/alerts
tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`.

**Context pack:** VS-01 handoff; approved current acquisition, mandatory evidence,
agent-boundary, strict-result sections; design deterministic-components and strict-result
decisions; ADR-093-111, ADR-117-122; Alert contract/analyzer/agent documents; current
VS-01 Alert package and corresponding Metrics deterministic tests.

**Handoff expectations:** VS02-AC01 through VS02-AC06 evidence; canonical record and agent
projection shapes; exact fixtures/arithmetic; persistence result; any change-map
deviation; remaining invalid/reference/failure/tool/URI/adapter work.

**Risk:** high-risk

**Completion gate:** all `VS02-AC*` obligations pass; focused and completed-result
PostgreSQL regressions pass; forbidden agent/result fields and future behavior are absent;
Ruff passes; independent high-risk review returns `SLICE REVIEW PASS`; one atomic
implementation commit and handoff exist, followed by Coordinator acceptance metadata.

### VS-03 — Reference evidence and usable partial outcomes

**Behavioral goal:** Extend the usable pipeline so invalid current subsets and
independently unavailable/malformed/invalid reference offsets preserve usable evidence,
omit rejected data/placeholders, retain successful configured order, select the approved
single partial reason, and persist an exactly correlated partial LensRun/result.

**OpenSpec coverage:** usable current subset and duplicate-collision scenarios; both
reference scenarios; partial current/reference outcomes including all references
unavailable and precedence; partial persistence scenario; tasks 1.3 remaining
uniqueness/reference behavior, 2.2, usable and reference portions of 2.3, partial portions
of 5.1/5.3/5.4, 6.1-6.3 partial integration, and 7.2.

**Dependencies:** VS-02.

**Vertical boundary:** running context with ordered offsets -> independent provider calls
and same-duration backward windows -> per-window normalization/duplicate rejection ->
successful occurrence comparisons plus operational unavailable diagnostics -> usable
current deterministic/agent result -> primary-reason selection -> strict partial builder
-> established transaction -> matching partial LensRun/artifact retrieval.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/alerts/contracts.py` | modify | Invalid-record/reference outcomes, comparisons, and two approved partial reasons |
| `backend/src/app/alerts/normalization.py` | modify | Invalid subsets and reject-all duplicate collision sets for current/reference data |
| `backend/src/app/alerts/references.py` | add | Same-duration offset windows, independent preparation, comparison, and configured order |
| `backend/src/app/alerts/analyzer.py` | modify | Successful reference occurrence comparisons |
| `backend/src/app/alerts/result_builder.py` | modify | Strict partial variants and primary-reason precedence |
| `backend/src/app/alerts/pipeline.py` | modify | Independent reference acquisition and partial contribution composition |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Adversarial current/reference partial paths |
| `backend/tests/test_runtime_persistence_integration.py` | modify | Partial reason/status/artifact correlation |

**Contracts consumed/changed:** adds only the approved invalid-record and reference
unavailability outcomes, successful comparison projection, operational diagnostics, and
public primary reasons. Reference records and secondary diagnostics remain transient and
must not enter agent input or result.

**Non-goals:** all-invalid current failure; current error/timeout; deterministic/agent
failure; optional tools; PydanticAI; exhaustive evidence-reference validation; rollback
fault injection; provider retry/timeout values.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS03-AC01 | References / both scenarios | Offsets `7d,1d,14d`; middle unavailable; successful records deliberately produce decreased then increased; current is empty in a second case | Process references before zero gate | Same-duration windows are requested independently; comparisons retain configured successful order with no placeholder; zero current still keeps comparison and skips agent | service | `backend/tests/test_alert_analysis_pipeline.py::test_references_are_independent_ordered_and_precede_zero_gate` |
| VS03-AC02 | Current / “Continue with a usable subset” | Valid records mixed with missing ID, missing title, invalid `started_at`, malformed `ended_at`, and `ended_at < started_at` records | Normalize and persist | Every invalid record is absent; usable evidence remains; result and LensRun are partial with `invalid_records/current_normalization` | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_invalid_current_subset_selects_current_normalization_partial`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_invalid_current_subset_persists_correlated_partial` |
| VS03-AC03 | Current / duplicate collision scenario | Duplicate IDs plus one unique valid record, with duplicate rows positioned first/last | Normalize | Every colliding row is rejected, never first/last-wins or merged; unique record remains and follows partial behavior | unit | `backend/tests/test_alert_analysis_pipeline.py::test_duplicate_collision_rejects_every_member` |
| VS03-AC04 | Reference requirement and duplicate uniqueness | One error, one timeout, one malformed/all-invalid set, one duplicate-ID set with colliders separated in input, and one success across ordered offsets | Process references | Every duplicate collider is rejected; only the success yields a comparison; unavailable sets do not fail usable current or leak records; result becomes reference partial when no stronger cause exists | service | `backend/tests/test_alert_analysis_pipeline.py::test_unavailable_and_duplicate_reference_sets_omit_only_their_offsets` |
| VS03-AC05 | Primary reason + partial persistence scenarios | Usable invalid current subset and unavailable reference in same run | Build, persist, reload | Exactly `invalid_records/current_normalization` is public on both LensRun/result; reference cause remains operational only; no secondary reason leaks | PostgreSQL | `backend/tests/test_runtime_persistence_integration.py::test_current_incompleteness_precedes_reference_and_persists_once` |
| VS03-AC06 | Reference-unavailability requirement clause; task 2.3 trace | Usable current evidence and three configured offsets respectively erroring, timing out, and normalizing to no usable reference records | Execute and persist | Current analysis remains usable; comparisons are empty with no placeholders; LensRun/result are partial with `reference_unavailable/reference_periods` | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_all_references_unavailable_remains_usable_partial`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_all_references_unavailable_persists_usable_reference_partial` |
| VS03-AC07 | Successful empty reference response | Usable current evidence and one configured reference whose provider response is successfully empty | Process and persist | A real successful comparison is retained with `reference=0`, exact current/delta/direction, and no reference incompleteness reason | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_successful_empty_reference_yields_zero_comparison`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_successful_empty_reference_yields_zero_comparison_without_partial` |

**Counterexample guards:** VS03-AC01 uses non-lexical offset order and different directions
so sorting or placeholder insertion fails. VS03-AC03 places duplicate records on both
sides of a unique record so first/last-wins logic fails. VS03-AC05 asserts serialized
absence of secondary diagnostics.

#### Implementation sketch (optional)

```text
for offset in configured_offsets:  # preserve configured order
    window = shift_back_same_duration(current_window, offset)
    outcome = await provider.acquire(source, query, window)
    if usable after normalization:
        comparisons.append(compare(current_occurrences, reference_occurrences))
    else:
        reference_diagnostics.append(offset)  # never a placeholder comparison

primary_reason = invalid_records if current_rejected else reference_unavailable if diagnostics else none
```

**Focused verification commands:** `cd backend && uv run pytest
tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_invalid_current_subset_persists_correlated_partial
tests/test_runtime_persistence_integration.py::test_current_incompleteness_precedes_reference_and_persists_once
tests/test_runtime_persistence_integration.py::test_all_references_unavailable_persists_usable_reference_partial
tests/test_runtime_persistence_integration.py::test_successful_empty_reference_yields_zero_comparison_without_partial
-q`; `cd backend && uv run ruff check src/app/alerts tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`; `cd backend && uv run ruff format --check
src/app/alerts tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`.

**Context pack:** direct VS-02 handoff and its recorded inherited invariants; approved current/reference/partial/persistence
sections; design decisions on stage order, deterministic analysis, local contract
decisions, and strict result; ADR-093, ADR-102-104, ADR-112-115; Alert concept/pipeline/
analyzer/result docs; current Alert package and Metrics reference patterns.

**Handoff expectations:** evidence for VS03-AC01 through VS03-AC07; exact invalidity and
duplicate fixtures; offset/window/order traces; public-vs-operational reason evidence;
PostgreSQL correlation; deviations and remaining mandatory failures/tools/builder/adapter.

**Risk:** high-risk

**Completion gate:** all `VS03-AC*` obligations pass; partial PostgreSQL and predecessor
regressions pass; raw reference data/placeholders/secondary diagnostics are absent; Ruff
passes; independent high-risk review returns `SLICE REVIEW PASS`; one atomic
implementation commit and handoff exist, followed by Coordinator acceptance metadata.

### VS-04 — Mandatory terminal failures and Alert artifact absence

**Behavioral goal:** Extend the pipeline across every approved mandatory failure boundary:
current error/timeout, all-invalid current data, deterministic analysis failure, agent
error/timeout, and malformed/contract-invalid required completion each persist an exact
failed LensRun reason and never create an AlertAnalysisResult.

**OpenSpec coverage:** fail-all-invalid, non-empty/no-usable, and current-acquisition
failure paths; invalid agent completion and required-agent failure scenarios; failure
portions of selected reason/Alert absence; tasks 2.3 mandatory failures,
invalid/error/timeout portions of 4.1, failure mappings in 5.3, failed-artifact absence in
5.4, 6.1-6.3 failed integration, and 7.2.

**Dependencies:** VS-03.

**Vertical boundary:** running context -> typed provider/normalization/analyzer/agent
failure contribution -> no builder for upstream failure -> caller-owned transaction ->
failed LensRun transition without artifact insertion -> commit and retrieval.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/alerts/contracts.py` | modify | Typed current, mandatory-analysis, agent, and completion-validation failures |
| `backend/src/app/alerts/pipeline.py` | modify | Exact failure mapping, builder bypass, and failed-only persistence |
| `backend/src/app/alerts/result_builder.py` | modify | Explicitly reject failed construction/use; no failed Alert result variant |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Table-driven pre-transaction failure and call-order proof |
| `backend/tests/test_runtime_persistence_integration.py` | modify | Failed status/reason persistence with zero Alert artifacts |

**Contracts consumed/changed:** consumes runtime `StructuredReason` and failed transition
rules. Adds approved codes/components only; diagnostics remain operational. Malformed
agent completion is rejected before the builder as `agent_failed`; timeout remains
`agent_timeout`; infrastructure/persistence errors are not reclassified here.

**Non-goals:** evidence-reference/builder contextual failures (VS-06/VS-07); optional-tool
failure/timeout; adapter translation; transaction fault injection; recovery/retry.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS04-AC01 | Current / “Fail current acquisition distinctly” | Typed error, thrown error, typed timeout, and thrown timeout provider doubles | Execute each | Exact `current_query_failed` or `current_query_timeout`; later stages not called; no artifact | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_current_acquisition_failures_map_exact_reason_and_stop`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_current_acquisition_failures_persist_exact_reason_without_artifact` |
| VS04-AC02 | Current / “Fail when every returned current record is invalid” | Non-empty response containing several invalid kinds and a duplicate-only collision set | Normalize | Failed `invalid_records`; analyzer/agent/builder are not called; no artifact | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_all_invalid_current_stops_before_analysis`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_all_invalid_current_fails_without_artifact` |
| VS04-AC03 | Mandatory evidence requirement | Analyzer double raises after usable normalized current | Execute | Failed `deterministic_analysis_failed`; agent/builder not called; no artifact | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_mandatory_analysis_failure_stops_agent_and_builder`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_mandatory_analysis_failure_is_terminal_without_artifact` |
| VS04-AC04 | Agent scenarios | Agent error, timeout, `none`, invalid controlled value, unknown/missing completion field, malformed finding | Execute table | Error/malformed maps `agent_failed`, timeout maps `agent_timeout`; builder call count zero; no artifact | service | `backend/tests/test_alert_analysis_pipeline.py::test_required_agent_failures_are_rejected_before_builder` |
| VS04-AC05 | Failed Alert absence | Each VS04 failure from a running PostgreSQL row | Persist and reload | Exactly one failed transition with matching reason is durable and artifact count remains zero | PostgreSQL | `backend/tests/test_runtime_persistence_integration.py::test_every_mandatory_alert_failure_has_no_result_artifact` |
| VS04-AC06 | Current non-empty/no-usable distinction | Successful non-empty response containing only valid but out-of-window records, contrasted with VS-01 successful empty response | Execute pipeline | Non-empty/no-usable fails `invalid_records` with no artifact, while the empty-response regression remains completed zero-record; exclusions are not reported as a usable partial subset | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_nonempty_all_out_of_scope_differs_from_empty_success`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_nonempty_all_out_of_scope_fails_while_empty_response_completes` |

**Counterexample guards:** fail-on-call doubles prove later stages do not run. PostgreSQL
tests count artifacts rather than accepting an empty/placeholder JSON payload. Distinct
error/timeout fixtures make a single generic mapping fail.

#### Implementation sketch (optional)

N/A — the risk is exact table-driven mapping and stage bypass; acceptance fixtures are
clearer than duplicating routine branching code.

**Focused verification commands:** `cd backend && uv run pytest
tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_current_acquisition_failures_persist_exact_reason_without_artifact
tests/test_runtime_persistence_integration.py::test_all_invalid_current_fails_without_artifact
tests/test_runtime_persistence_integration.py::test_mandatory_analysis_failure_is_terminal_without_artifact
tests/test_runtime_persistence_integration.py::test_every_mandatory_alert_failure_has_no_result_artifact
tests/test_runtime_persistence_integration.py::test_nonempty_all_out_of_scope_fails_while_empty_response_completes
-q`; `cd backend && uv run ruff check src/app/alerts tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`; `cd backend && uv run ruff format --check
src/app/alerts tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`.

**Context pack:** direct VS-03 handoff and its recorded inherited invariants; approved failure/partial, agent completion, strict
result, persistence sections; design stage-order/failure decisions; ADR-113-121; runtime
failure/persistence contracts; current Alert pipeline/builder and runtime repository.

**Handoff expectations:** evidence for VS04-AC01 through VS04-AC06; full cause-to-reason
matrix and stage call trace; database artifact-count evidence; deviations; builder-specific
and adapter failures remaining.

**Risk:** high-risk

**Completion gate:** all `VS04-AC*` obligations pass; focused/PostgreSQL and predecessor
regressions pass; every failure has exact reason and zero artifacts; Ruff passes;
independent high-risk review returns `SLICE REVIEW PASS`; one atomic implementation commit
and handoff exist, followed by Coordinator acceptance metadata.

### VS-05 — Bounded optional tools and minimal unsuccessful trace

**Behavioral goal:** Allow a non-zero fake Alert agent to invoke exactly the three
run-local deterministic optional tools repeatedly within the ten-attempt budget, reject
forbidden requests before execution, continue after tool failure/timeout, and persist only
agent findings/importance plus the approved minimal failed/timeout trace.

**OpenSpec coverage:** optional timeout and undersized-duration scenarios; complete
optional registry/tool algorithms/budget behavior; tasks 3.1-3.4, optional execution
mapping portion of 4.1, optional trace/result portions of 5.1, pipeline integration in
6.1, and 7.2.

**Dependencies:** VS-03.

**Vertical boundary:** already-normalized immutable current/reference data -> run-local
registry/executor projected to fake agent -> accepted/rejected attempt ledger -> pure tool
outcomes -> agent continues to valid completion -> builder retains only minimal
unsuccessful trace -> established completed/partial persistence (status unchanged by tool
failure alone).

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/alerts/contracts.py` | modify | Tool descriptors, outcomes, attempts, minimal unsuccessful trace |
| `backend/src/app/alerts/ports.py` | modify | Framework-neutral optional-tool executor boundary |
| `backend/src/app/alerts/tools.py` | add | Exact registry, ten-attempt admission, immutable binding, and three deterministic algorithms |
| `backend/src/app/alerts/pipeline.py` | modify | Run-local executor injection and non-fatal optional contribution |
| `backend/src/app/alerts/result_builder.py` | modify | Failed/timeout trace projection and successful/not-applicable omission |
| `backend/tests/test_alert_tools.py` | add | Exhaustive algorithms, budget, repeat, and rejection tests |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Fake-agent tool continuation and persisted-result behavior |

**Contracts consumed/changed:** adds exactly three accepted names and empty-object request
shape, all-outcome attempt accounting, repeat support, and minimal failed/timeout trace.
Unknown/scope-expanding/over-budget requests are rejected before execution; no new public
terminal reason is introduced. Successful/not-applicable outputs and the full ledger stay
transient.

**Non-goals:** PydanticAI translation; production tool serialization/prompt; per-tool
timeout values; new tools; scope expansion; successful tool output sections; new partial
reason; evidence-ref grammar for transient-derived findings (VS-06).

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS05-AC01 | Optional-analysis scope/budget requirement clauses; task 3.1 trace | Scripted sequence with repeated allowed names, all four outcome kinds, unknown name, scope payload, call 10 and call 11 | Submit through one run-local executor | Every first-ten attempt consumes one ordinal; repeats are allowed; forbidden requests execute nothing; no attempt beyond budget executes; immutable dataset scope is unchanged | unit | `backend/tests/test_alert_tools.py::test_optional_registry_enforces_scope_repeats_and_ten_attempt_budget` |
| VS05-AC02 | Recurrence tool | Missing occurrence counts, zero total, and tied top records in reverse lexical input order | Analyze recurrence | Defaults apply; zero total is not-applicable; all tied IDs return lexical order and exact share | unit | `backend/tests/test_alert_tools.py::test_recurrence_concentration_defaults_zero_and_ties` |
| VS05-AC03 | Duration tool / undersized scenario | Seven durations; eight values requiring interpolation; one value exactly at and one above high bound | Analyze outliers | Seven is not-applicable; `(n-1)*p` quartiles are exact; threshold equality is not an outlier and strict greater-than is | unit | `backend/tests/test_alert_tools.py::test_duration_outlier_minimum_interpolation_and_strict_threshold` |
| VS05-AC04 | Reference-pattern tool | Fewer than two comparisons, unique majority, and tied directions in non-grouped order | Analyze pattern | Below minimum is not-applicable; unique winner is returned; tie is `mixed` | unit | `backend/tests/test_alert_tools.py::test_reference_pattern_applicability_dominance_and_tie` |
| VS05-AC05 | “Continue after an optional timeout” | Agent invokes success, not-applicable, failed, and timeout tools then returns valid completion | Execute and persist | Agent continues; status is not changed by tool outcomes alone; only failed/timeout `tool` and `status` appear in result; ordinal remains internal and data/results/diagnostics do not leak | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_optional_failure_timeout_continue_with_minimal_trace`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_optional_failures_continue_and_persist_only_minimal_trace` |

**Counterexample guards:** VS05-AC01 mixes repeats and every outcome so counting only
successful executions fails. VS05-AC02 reverses tied IDs so input-order output fails.
VS05-AC03 contains exact-threshold and just-over-threshold values. VS05-AC05 asserts the
serialized result recursively excludes successful outputs and executor internals.

#### Technical verification

- Approved task 1.1 internal strict-tool-model strategy: run
  `backend/tests/test_alert_tools.py::test_optional_tool_contracts_reject_unknown_and_internal_fields`.
  This verifies implementation shape while the behavioral IDs own scope, budget, and
  public trace semantics.

#### Implementation sketch (optional)

```text
request(name, arguments):
    if attempts == 10: reject_without_execution(over_budget)
    record next ordinal
    if name not registered or arguments != {}: reject_without_execution
    outcome = execute_against_bound_run_data(name)
    record outcome  # success/not_applicable/failed/timeout all consume budget
    return outcome

public_trace = only failed|timeout tool/status  # ordinal stays internal
```

**Focused verification commands:** `cd backend && uv run pytest tests/test_alert_tools.py
tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_optional_failures_continue_and_persist_only_minimal_trace
-q`; `cd backend && uv run ruff check src/app/alerts tests/test_alert_tools.py
tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py`;
`cd backend && uv run ruff format --check src/app/alerts tests/test_alert_tools.py
tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py`.

**Context pack:** direct VS-03 handoff and its recorded inherited invariants; approved agent/optional-tool/result requirements;
design registry/ledger decision; ADR-123-132; Alert agent/tools/builder docs; existing
Metrics registry/adapter as structural reference without importing Metric semantics.

**Handoff expectations:** evidence for VS05-AC01 through VS05-AC05; registry names and
executor API; exact algorithms/fixtures; attempt ledger versus public trace; database
evidence; deviations; adapter and URI work remaining.

**Risk:** high-risk

**Completion gate:** all `VS05-AC*` obligations pass; focused/PostgreSQL and predecessor
regressions pass; exactly three tools and ten all-outcome attempts are enforced; no
forbidden execution or transient-output leak occurs; task 1.1 technical verification and
Ruff pass; independent high-risk review returns `SLICE REVIEW PASS`; one atomic
implementation commit and handoff exist, followed by Coordinator acceptance metadata.

### VS-06 — Canonical evidence references through persisted results

**Behavioral goal:** Extend the strict builder with the exact canonical `alert://`
grammar and exact-one final-target resolution so valid reserved/Unicode references persist
in completed/partial results while malformed, non-canonical, ambiguous, or non-resolving
references fail the LensRun with no artifact.

**OpenSpec coverage:** the three evidence-reference scenarios under “Build a strict
usable AlertAnalysisResult”; task 5.2, evidence-reference portions of 5.1 and 5.4,
builder-failure mapping portion of 5.3, 6.1/6.3 integration, and 7.2.

**Dependencies:** VS-04 and VS-05.

**Vertical boundary:** valid upstream deterministic/agent data -> canonical URI parse and
decode -> exact target resolution against assembled final sections -> either a strict
completed/partial envelope persisted through the established transaction or a failed
LensRun persisted without artifact.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/alerts/evidence_refs.py` | add | Canonical encoding/parsing, exact path grammar, UTF-8 validation, and target resolution |
| `backend/src/app/alerts/result_builder.py` | modify | Resolve every finding reference against the assembled final result and reject URI failures |
| `backend/src/app/alerts/pipeline.py` | modify | Map evidence-reference builder rejection to the approved builder-failure outcome |
| `backend/tests/test_alert_result_builder.py` | add | Canonical URI and exact-target matrix |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Reference-derived builder rejection bypasses artifact persistence |
| `backend/tests/test_runtime_persistence_integration.py` | modify | Valid encoded-reference round trip and invalid-reference no-artifact proof |

**Contracts consumed/changed:** extends the existing valid result variants without
changing agent completion ownership. Dynamic URI segments decode to exact existing final
current, aggregate, provider-importance, or comparison targets; optional-derived findings
may cite only persisted records/aggregates/comparisons. Agent shape errors remain VS-04
`agent_failed`; URI/target rejection maps to the builder reason.

**Non-goals:** new evidence targets; optional output persistence; agent repair; provider
mapping; PydanticAI; public schema/database changes.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS06-AC01 | Strict result / encoded reserved and Unicode scenario | Current IDs, importance type/value, and offsets containing space, slash, percent, and Unicode plus every static aggregate reference form | Encode, resolve, persist, and reload | Every canonical URI is ASCII, uses uppercase escapes, resolves to exactly its intended final current/aggregate/importance/comparison target, and round-trips unchanged | unit + PostgreSQL | unit: `backend/tests/test_alert_result_builder.py::test_all_canonical_evidence_target_forms_resolve`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_all_canonical_evidence_target_forms_round_trip` |
| VS06-AC02 | Strict result / malformed URI scenario | Raw Unicode, raw space, representative ASCII control/DEL and other non-unreserved bytes, and reserved bytes; uppercase/mixed-case scheme or static authority/path literals; userinfo; port; lowercase/incomplete/malformed escapes; encoded unreserved bytes; invalid UTF-8; empty dynamic segment; query; fragment; missing/extra/wrong path segments | Validate through pipeline | Every form is rejected without permissive URL normalization; LensRun fails `result_validation_failed/alert_result_builder` and no artifact persists | unit + PostgreSQL | unit: `backend/tests/test_alert_result_builder.py::test_evidence_refs_reject_every_noncanonical_grammar_case`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_noncanonical_evidence_refs_fail_without_artifact` |
| VS06-AC03 | Strict result / non-resolving scenario | Missing current/comparison target, absent duration/importance section target, duplicate/ambiguous assembled target, and transient-tool-derived reference without persisted backing | Resolve during build | Builder rejects every dangling, unavailable, transient-only, or ambiguous reference and no artifact is created | unit + service | unit: `backend/tests/test_alert_result_builder.py::test_builder_rejects_unavailable_unresolved_transient_or_ambiguous_targets`; service: `backend/tests/test_alert_analysis_pipeline.py::test_unresolvable_finding_reference_stops_before_persistence` |

**Counterexample guards:** URI cases include forms standard URL libraries commonly
normalize. VS06-AC01 exercises every static authority/path alternative, not only current
IDs. VS06-AC03 uses both missing and deliberately duplicate targets.

#### Implementation sketch (optional)

```text
parse ASCII URI without normalization
validate exact lowercase authority/static path shape
for each dynamic segment:
    reject raw reserved/non-ASCII and non-uppercase/noncanonical escapes
    decode bytes as strict UTF-8
    require encode(decoded) == original segment
resolve decoded identity against final assembled target index
require exactly one match and required target section present
```

**Focused verification commands:** `cd backend && uv run pytest
tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_all_canonical_evidence_target_forms_round_trip
tests/test_runtime_persistence_integration.py::test_noncanonical_evidence_refs_fail_without_artifact
-q`; `cd backend && uv run ruff check src/app/alerts tests/test_alert_result_builder.py
tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py`;
`cd backend && uv run ruff format --check src/app/alerts
tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`.

**Context pack:** direct VS-04 and VS-05 handoffs; approved strict-result evidence-reference
clauses/scenarios; design evidence-reference decision; ADR-111, ADR-116-120, ADR-132;
Alert result contract sections for evidence references and optional traces; current Alert
builder/evidence-ref code and its focused unit/persistence tests.

**Handoff expectations:** evidence for VS06-AC01 through VS06-AC03; canonical grammar and
target-index rules; valid round-trip and failure/no-artifact evidence; deviations;
remaining result-invariant and adapter work.

**Risk:** high-risk

**Completion gate:** all `VS06-AC*` obligations pass; URI, pipeline, PostgreSQL, and
predecessor regressions pass; no permissive URI normalization or invalid-reference
artifact exists; Ruff passes; independent high-risk review returns `SLICE REVIEW PASS`;
one atomic implementation commit and handoff exist, followed by Coordinator acceptance
metadata.

### VS-07 — Exhaustive Alert result invariants and builder failure

**Behavioral goal:** Complete the AlertResultBuilder as the sole completed/partial
contract owner by enforcing envelope, identity/time/provenance, section omission,
count/status/duration/comparison, controlled-value, and unknown-field invariants; every
contextual/final-result rejection fails the LensRun with the approved builder reason and
no artifact.

**OpenSpec coverage:** remaining strict-result and zero-record validation behavior,
contextual builder-failure mapping, and exhaustive result validation; tasks 5.1 remaining
validation, builder portions of 5.3, 5.4, 6.1/6.3 builder integration, and 7.2.

**Dependencies:** VS-06.

**Vertical boundary:** valid upstream data with already-resolved finding references ->
strict final envelope and cross-field validation -> either completed/partial result through
the established transaction or failed LensRun without an artifact.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/alerts/contracts.py` | modify | Final strict completed/partial variants and controlled values |
| `backend/src/app/alerts/result_builder.py` | modify | Exhaustive envelope/section/correlation/invariant validation |
| `backend/src/app/alerts/pipeline.py` | modify | Map contextual/final invariant rejection to approved builder failure |
| `backend/tests/test_alert_result_builder.py` | modify | One-field-at-a-time invariant matrix |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Builder rejection and upstream-agent boundary regression |
| `backend/tests/test_runtime_persistence_integration.py` | modify | Builder-failed LensRun/no-artifact proof |

**Contracts consumed/changed:** completes result version 1.0 without widening agent
completion or evidence-target contracts. Agent shape errors remain `agent_failed`; only
identity/provenance/assembled-result invariant failure maps to
`result_validation_failed/alert_result_builder`.

**Non-goals:** URI grammar changes; new evidence targets; optional output persistence;
agent repair; provider mapping; PydanticAI; public schema/database changes.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS07-AC01 | Strict result envelope | Known-valid completed and partial fixtures mutated one field at a time: each identity member differs from context, schema version differs from `1.0`, lens type differs from `alert`, analysis window/timestamp or generated-at is non-UTC or differs from context, source provider differs from context, completed has a reason, partial lacks/exchanges its reason, or an unknown field is added | Build | Every exact mismatch/unknown is rejected while unchanged completed and partial fixtures validate | unit | `backend/tests/test_alert_result_builder.py::test_builder_enforces_exact_envelope_identity_time_provenance_and_strict_fields` |
| VS07-AC02 | Mandatory result invariants | Known-valid fixtures mutated for `record_count != len(alerts)`, occurrence sum mismatch, each active/resolved/unknown count inconsistent with actual record statuses, status total mismatch, malformed or `ended_at < started_at`, normalized lifecycle inconsistent with timestamps, negative/non-finite duration, per-record duration unequal to `ended_at-started_at` or `analysis_timestamp-started_at`, min/max/average mismatch, provider-importance counts inconsistent with records, zero-record optional sections present, or non-zero importance `none` | Build | Every exact inconsistency is rejected; valid zero/non-zero boundary fixtures and the reserved `unknown` controlled value in contract/result validation pass without inventing a normalization trigger | unit | `backend/tests/test_alert_result_builder.py::test_builder_enforces_exact_activity_status_lifecycle_duration_and_importance_invariants` |
| VS07-AC03 | Reference/result-section invariants | Known-valid fixtures mutated for configured comparison order, current/reference/delta arithmetic, strict direction, failed/timeout trace containing an extra field or a success/not-applicable call, missing findings list, and completed/partial reason presence | Build | Every exact invalid projection is rejected; valid configured-order completed/partial fixtures pass | unit | `backend/tests/test_alert_result_builder.py::test_builder_enforces_exact_comparison_optional_trace_and_status_sections` |
| VS07-AC04 | Representative builder failure mapping | One identity-correlation mismatch and one activity/count invariant mismatch, each with otherwise structurally valid agent output against separate running PostgreSQL LensRuns | Execute and persist terminal outcome | Each becomes failed `result_validation_failed/alert_result_builder` with no artifact; one malformed agent completion regression still maps upstream to `agent_failed` | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_representative_builder_failures_map_exact_reason`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_representative_builder_invariant_failures_persist_failed_run_without_artifact` |

**Counterexample guards:** VS07-AC01 through VS07-AC03 mutate one field from a known-valid
fixture so an unrelated earlier validation cannot mask missing checks. VS07-AC04 keeps
the database proof representative—one correlation and one aggregate failure—while
comparing builder and agent ownership in the same durable-state matrix.

#### Implementation sketch (optional)

N/A — the slice is best specified as a one-field-at-a-time invariant matrix; duplicating
the validator would pre-write routine production code.

**Focused verification commands:** `cd backend && uv run pytest
tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_representative_builder_invariant_failures_persist_failed_run_without_artifact
-q`; `cd backend && uv run ruff check src/app/alerts tests/test_alert_result_builder.py
tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py`;
`cd backend && uv run ruff format --check src/app/alerts
tests/test_alert_result_builder.py tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`.

**Context pack:** direct VS-06 handoff; approved strict-result invariant and failure
clauses/scenarios; design strict-result ownership; ADR-108, ADR-110, ADR-116-120, ADR-132;
Alert result-contract invariant sections, Alert builder contract, runtime failure
contracts, and current Alert builder/pipeline/persistence tests.

**Handoff expectations:** evidence for VS07-AC01 through VS07-AC04; full invariant matrix;
builder-vs-agent failure boundary; PostgreSQL absence evidence; deviations; adapter work
remaining.

**Risk:** high-risk

**Completion gate:** all `VS07-AC*` obligations pass; exhaustive builder, pipeline,
PostgreSQL, and predecessor regressions pass; no invalid artifact exists; Ruff passes;
independent high-risk review returns `SLICE REVIEW PASS`; one atomic implementation commit
and handoff exist, followed by Coordinator acceptance metadata.

### VS-08 — Injected PydanticAI Alert adapter

**Behavioral goal:** Implement `PydanticAIAlertAnalysisAgent` as the sole framework
adapter over the already-complete framework-neutral request/executor boundary, using an
injected model, no corrective retries, no live integration, and domain-owned ten-call
enforcement while preserving exact completion/error/timeout behavior through persistence.

**OpenSpec coverage:** provider/model isolation scenario; adapter-specific optional and
completion behavior; tasks 4.2-4.3, adapter verification of 4.1 and task 3.1 boundaries,
6.1 integration, and 7.2.

**Dependencies:** VS-05 and VS-07.

**Vertical boundary:** strict domain request plus application-owned tool executor ->
injected PydanticAI model/agent -> framework tool calls translated through the same
domain executor -> strict domain completion or approved agent error/timeout -> existing
builder/transaction -> correlated completed/failed persistence.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/infrastructure/agents/pydantic_ai_alerts.py::PydanticAIAlertAnalysisAgent` | add | Injected-model translation only; no domain policy ownership |
| `backend/src/app/infrastructure/agents/__init__.py` | modify if needed | Infrastructure-local export only |
| `backend/tests/test_pydantic_ai_alerts_adapter.py` | add | Deterministic function/model doubles for calls, budgets, completions, errors, and retries |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Narrow adapter-to-persisted-result integration |

**Contracts consumed/changed:** implements the existing `AlertAnalysisAgent` port without
widening its request, completion, executor, ledger, or result types. No provider/model
default, production settings, prompt contract, retry hook, live call, or framework import
is added to `app.alerts`.

**Non-goals:** changing domain tool algorithms/admission; defining public behavior for a
forbidden request beyond rejection-before-execution; production composition/model/provider;
Jira; token/cost/time budget; agent-owned persistence/orchestration.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS08-AC01 | Provider/model-isolation requirement and fake-integration scenario; task 4.3 trace | Injected deterministic model returning valid strict completion with no tool calls | Run adapter | Exact domain request is translated; valid completion returns; no network/provider/default/model settings or forbidden fields are used | adapter | `backend/tests/test_pydantic_ai_alerts_adapter.py::test_valid_zero_call_completion_is_injected_and_bounded` |
| VS08-AC02 | Ten-call/repeat rules | Model double requests a permitted tool repeatedly through call 10 then completes | Run adapter | All ten calls pass through the application executor with exact ordinals; no adapter-private budget replaces it; completion is accepted | adapter | `backend/tests/test_pydantic_ai_alerts_adapter.py::test_repeated_calls_through_tenth_use_domain_executor` |
| VS08-AC03 | Optional-tool scope/budget clauses and ADR-125/ADR-130 | Separate model doubles request an unregistered tool, a permitted tool with non-empty/scope-expanding input, and an eleventh call; evaluators fail if forbidden execution occurs; the eleventh-call script then returns a valid completion on its next ordinary reasoning turn | Run request handling | Unknown/scope-expanding and eleventh calls are rejected before execution and recorded by the domain boundary; after the budget rejection the agent finishes with earlier available evidence and returns the valid completion; no new public reason is fabricated | adapter | `backend/tests/test_pydantic_ai_alerts_adapter.py::test_forbidden_requests_are_rejected_and_budget_rejection_then_completes` |
| VS08-AC04 | Strict completion/agent failure rules | `none`, invalid controlled value, unknown/missing fields, malformed finding, model error, and timeout doubles | Run adapter/pipeline | Malformed/error maps `agent_failed`, timeout maps `agent_timeout`; builder is bypassed and no artifact persists | adapter + PostgreSQL | adapter: `backend/tests/test_pydantic_ai_alerts_adapter.py::test_invalid_completion_error_and_timeout_map_exactly`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_pydantic_ai_alerts_invalid_completion_error_and_timeout_are_terminal` |
| VS08-AC05 | Optional timeout continuation | Tool closure times out before call ten and model then returns valid completion | Run adapter/pipeline | Model may continue with remaining evidence; minimal timeout trace persists; LensRun status is unaffected by timeout alone | adapter + PostgreSQL | adapter: `backend/tests/test_pydantic_ai_alerts_adapter.py::test_optional_timeout_continues_to_valid_completion`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_pydantic_ai_alerts_optional_timeout_continues_to_valid_result` |
| VS08-AC06 | Lens-local descriptive agent boundary | Capturing model double receives the adapter instructions and returns already-deduplicated findings | Inspect semantic instruction categories and completion | Instructions require deduplicated/merged Lens-local descriptive findings and prohibit causal/root-cause, recommendation/prescriptive, semantic-clustering, cross-Lens, RAG/external-knowledge, missing-data inference, and scope expansion; assertion is category-based, not exact prompt text | adapter | `backend/tests/test_pydantic_ai_alerts_adapter.py::test_instructions_preserve_lens_local_descriptive_boundary` |

**Counterexample guards:** VS08-AC02 compares domain ledger ordinals to framework requests
so an adapter-private budget fails. VS08-AC03 uses fail-if-called evaluators and requires
the ordinary post-budget completion turn. VS08-AC04 distinguishes malformed/error from
timeout mapping. Technical verification owns model-request counts. Import scans reject
PydanticAI under `app.alerts`.

#### Technical verification

- Approved design/task 4.2 no-corrective-retry configuration: scripted unknown and
  non-empty/scope-expanding requests use exactly 2 model requests (request plus ordinary
  completion), and the eleventh-call script uses exactly 12 (ten accepted calls,
  rejected eleventh request, then ordinary completion), with no additional framework
  validation/model retry. Run
  `backend/tests/test_pydantic_ai_alerts_adapter.py::test_forbidden_request_model_counts_have_no_corrective_retry`.
- Malformed completion/error/timeout scripts likewise use their exact single terminal
  model-attempt counts with no corrective retry. Run
  `backend/tests/test_pydantic_ai_alerts_adapter.py::test_invalid_completion_failure_counts_have_no_corrective_retry`.

#### Implementation sketch (optional)

```text
PydanticAI adapter owns: framework message/tool translation
domain executor owns: allowed names, immutable data, attempts 1..10, rejection
domain completion model owns: strict finding/importance validation
pipeline owns: agent_failed/agent_timeout mapping
builder owns: final AlertAnalysisResult validation
repository owns: generic terminal/artifact persistence
```

**Focused verification commands:** `cd backend && uv run pytest
tests/test_pydantic_ai_alerts_adapter.py tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_pydantic_ai_alerts_invalid_completion_error_and_timeout_are_terminal
tests/test_runtime_persistence_integration.py::test_pydantic_ai_alerts_optional_timeout_continues_to_valid_result
-q`; `cd /home/teodor/workspace/projects/intelligent-process-observer && test -d
backend/src/app/alerts && ! rg -n -e pydantic_ai -e sqlalchemy backend/src/app/alerts`;
`cd backend && uv run ruff check src/app/alerts
src/app/infrastructure/agents/pydantic_ai_alerts.py
tests/test_pydantic_ai_alerts_adapter.py tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`; `cd backend && uv run ruff format --check
src/app/alerts src/app/infrastructure/agents/pydantic_ai_alerts.py
tests/test_pydantic_ai_alerts_adapter.py tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py`.

**Context pack:** VS-05/VS-07 handoffs; approved agent/tool/isolation requirements;
design PydanticAI and registry decisions; ADR-106-110, ADR-123-132, ADR-152; Alert agent
and analytical-tools docs; official installed PydanticAI APIs; current
`pydantic_ai_metrics.py` and its tests as framework integration patterns only.

**Handoff expectations:** evidence for VS08-AC01 through VS08-AC06; injection API and
model doubles; retry/model-request counts; proof all tool calls use domain executor;
import scan and database results; deviations; remaining whole-change rollback/docs.

**Risk:** high-risk

**Completion gate:** all `VS08-AC*` obligations pass; adapter/pipeline/PostgreSQL and
predecessor regressions pass without network; no new dependency/provider extra/default or
framework import outside infrastructure exists; approved retry-configuration technical
checks and Ruff pass; independent high-risk review returns `SLICE REVIEW PASS`; one atomic
implementation commit and handoff exist, followed by Coordinator acceptance metadata.

### VS-09 — Transaction rollback and whole-change conformance

**Behavioral goal:** Complete the change by proving caller-owned transaction ordering and
rollback for terminal Alert writes, documenting stable injection/composition boundaries,
auditing every approved requirement/scenario/task, and running full repository checks
without adding new primary analytical behavior.

**OpenSpec coverage:** rollback terminal-write scenario; final whole-change verification
of partial status/reason correlation, mismatched artifact rejection, and fake integration;
task 6.3 rollback/mismatch portions, tasks 7.1-7.3, and final verification of all tasks.

**Dependencies:** VS-03, VS-04, VS-07, and VS-08.

**Vertical boundary:** already-validated completed/partial/failed pre-transaction outcome
-> caller opens transaction -> terminal transition plus conditional artifact flush ->
injected flush/commit failure -> caller rollback -> direct durable-state verification;
then documentation, scope audit, strict OpenSpec validation, and full repository checks.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/tests/test_runtime_persistence_integration.py` | modify | Flush/commit rollback and final completed/partial/failed correlation matrix |
| `backend/tests/test_alert_analysis_pipeline.py` | modify | Cross-cause and phase-order conformance regressions |
| `docs/development-guide.md` or nearest existing developer document | modify if needed | Concise provider/model injection and future composition boundaries only |
| `backend/src/app/alerts/*.py` public classes/interfaces | audit | Required concise public docstrings; no new primary behavior |

**Contracts consumed/changed:** consumes all completed contracts unchanged. Production
defects discovered here return to their owning slice for targeted correction and renewed
review; missing or changed behavior triggers re-planning rather than being silently added
to conformance work.

**Non-goals:** new production behavior, result fields, failure codes, refactors,
dependencies, schema/migration, public API/frontend, Jira/model/provider defaults,
archive, push, PR, or merge.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS09-AC01 | Persistence / “Roll back a failed terminal write” | Known running row plus valid result; distinct failures injected at transition flush, artifact-insertion flush, and caller commit | Attempt terminal persistence for each failure point | Neither terminal state nor artifact is durable after caller rollback in a fresh session; infrastructure failure escapes without fabricated terminal output | PostgreSQL | `backend/tests/test_runtime_persistence_integration.py::test_alert_transition_flush_artifact_flush_and_commit_failures_roll_back_all_writes` |
| VS09-AC02 | Persistence / partial correlation | Completed, current-partial, reference-partial, and each failed cause fixtures | Execute/reload matrix | Usable status/reason matches exactly between LensRun/artifact; completed has no reason; failed has no artifact | PostgreSQL | `backend/tests/test_runtime_persistence_integration.py::test_alert_terminal_outcome_correlation_matrix` |
| VS09-AC03 | Stage-order and integration constraints | Provider/agent/tool phase recorder plus transaction/session recorder | Execute representative adapter-backed usable run | All provider acquisition, normalization, reference analysis, deterministic analysis, optional tools, agent work, and result building finish before transaction open; the transaction may contain required repository correlation/duplicate reads plus transition, conditional artifact insertion, flush, and commit | service + PostgreSQL | service: `backend/tests/test_alert_analysis_pipeline.py::test_pre_transaction_work_finishes_before_persistence_composition`; PostgreSQL: `backend/tests/test_runtime_persistence_integration.py::test_alert_pipeline_phase_order_keeps_long_work_outside_transaction` |
| VS09-AC04 | Provider/model isolation / fake integration | Clean test environment with no Jira/model credentials or network | Run focused Alert suite and inspect the committed feature diff from its merge base | All pipeline behavior executes with fakes/injected models; audit finds no prohibited provider/API/schema scope or Python/npm dependency manifest in committed, staged, modified, or untracked changes | repository checks | suite: `cd /home/teodor/workspace/projects/intelligent-process-observer && uv run --project backend pytest backend/tests/test_alert_contracts.py backend/tests/test_alert_tools.py backend/tests/test_alert_result_builder.py backend/tests/test_pydantic_ai_alerts_adapter.py backend/tests/test_alert_analysis_pipeline.py -q`; committed/clean-tree scan: `cd /home/teodor/workspace/projects/intelligent-process-observer && IPO_FEATURE_BASE="$(git merge-base main HEAD)" && test -d backend/src/app/alerts && ! rg -n -e pydantic_ai -e sqlalchemy -e '^from fastapi' -e '^import fastapi' -e APIRouter -e 'FastAPI\(' backend/src/app/alerts && test -z "$(git diff --name-only "$IPO_FEATURE_BASE"..HEAD -- ':(glob)**/pyproject.toml' ':(glob)**/uv.lock' ':(glob)**/requirements*.txt' ':(glob)**/requirements*.in' ':(glob)**/constraints*.txt' ':(glob)**/constraints*.in' ':(glob)**/poetry.lock' ':(glob)**/Pipfile' ':(glob)**/Pipfile.lock' ':(glob)**/pdm.lock' ':(glob)**/setup.py' ':(glob)**/setup.cfg' ':(glob)**/package.json' ':(glob)**/package-lock.json' ':(glob)**/npm-shrinkwrap.json' ':(glob)**/pnpm-lock.yaml' ':(glob)**/yarn.lock')" && git diff --quiet "$IPO_FEATURE_BASE"..HEAD -- frontend backend/alembic backend/src/app/main.py backend/src/app/observations backend/src/app/infrastructure/persistence/models.py backend/src/app/infrastructure/persistence/repository.py backend/src/app/infrastructure/persistence/runtime_contracts.py ':(glob)backend/src/app/alerts/**/*api*.py' ':(glob)backend/src/app/alerts/**/*route*.py' && test -z "$(git diff "$IPO_FEATURE_BASE"..HEAD -- backend/src/app/infrastructure/persistence ':(exclude)backend/src/app/infrastructure/persistence/alert_runtime.py' ':(exclude)backend/src/app/infrastructure/persistence/__init__.py')" && ! rg -n -e '^from httpx' -e '^import httpx' -e '^from requests' -e '^import requests' -e '^from aiohttp' -e '^import aiohttp' -e '^from jira' -e '^import jira' -e OpenAIModel -e AnthropicModel -e GoogleModel backend/src/app/alerts backend/src/app/infrastructure/agents/pydantic_ai_alerts.py backend/src/app/infrastructure/persistence/alert_runtime.py && test -z "$(git status --porcelain=v1 --untracked-files=all)"` |
| VS09-AC06 | Accepted runtime-persistence mismatch-rejection contract; task 6.3 trace | Running Alert LensRuns paired one at a time with wrong result type, status, identity, and partial-reason correlation envelopes | Submit through the production persistence composer inside caller-owned transactions | Every mismatch raises before durable commit; fresh-session LensRun remains running and no artifact exists | PostgreSQL | `backend/tests/test_runtime_persistence_integration.py::test_alert_persistence_composer_rejects_every_mismatched_artifact_atomically` |

**Counterexample guards:** VS09-AC01 distinguishes both repository flush sites and commit,
then checks durable state in a fresh session rather than only observing an exception.
VS09-AC03 records both sides of transaction open/commit. VS09-AC04 scans the actual diff
and imports rather than relying on fake tests alone. VS09-AC06 mutates one correlation
dimension at a time so one validation cannot mask another.

#### Implementation sketch (optional)

```text
pre_transaction_outcome = await analyze_with_provider_tools_agent_builder()

try:
    async with caller_owned_transaction:
        transition running -> terminal
        insert artifact only for completed|partial
        flush
except infrastructure_error:
    rollback
    re-raise unchanged

fresh_session.assert_original_running_state_and_no_artifact()
```

**Focused verification commands:** `cd backend && uv run pytest
tests/test_alert_contracts.py tests/test_alert_tools.py tests/test_alert_result_builder.py
tests/test_pydantic_ai_alerts_adapter.py tests/test_alert_analysis_pipeline.py -q`;
`cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest
tests/test_runtime_persistence_integration.py::test_alert_transition_flush_artifact_flush_and_commit_failures_roll_back_all_writes
tests/test_runtime_persistence_integration.py::test_alert_terminal_outcome_correlation_matrix
tests/test_runtime_persistence_integration.py::test_alert_pipeline_phase_order_keeps_long_work_outside_transaction
tests/test_runtime_persistence_integration.py::test_alert_persistence_composer_rejects_every_mismatched_artifact_atomically
-q`; from repository root, `openspec validate add-alerts-analysis-pipeline --strict`;
`git diff --check`; `test -z "$(git status --porcelain=v1 --untracked-files=all)"`;
`make check`.

**Context pack:** direct VS-03, VS-04, VS-07, and VS-08 handoffs; accepted execution table
and coverage matrix; approved persistence rollback/mismatch and provider/model-isolation
clauses; design stage-order and test-strategy sections; ADR-105, ADR-114-121, ADR-131-132,
and ADR-152; runtime-persistence correlation contracts; current Alert pipeline,
persistence composer, PydanticAI adapter, focused integration tests, root `Makefile`, and
the developer document receiving injection/composition guidance.

**Handoff expectations:** evidence for VS09-AC01 through VS09-AC04 and VS09-AC06;
fresh-session
rollback evidence; final 9-requirement/25-scenario/23-task audit; all verification
commands/results; dependency/import/scope audit; documentation changes; deviations and
readiness for official verification plus independent implementation review.

**Risk:** high-risk

**Completion gate:** all `VS09-AC*` obligations pass; all earlier acceptance IDs regress
green; every approved requirement/scenario/task is reconciled; public class/interface
docstrings and injection/composition documentation are audited; strict validation,
`git diff --check`, merge-base feature-diff scope/dependency-manifest scans, clean-tree
check `test -z "$(git status --porcelain=v1 --untracked-files=all)"`, and `make check`
pass; no primary behavior or prohibited scope is
introduced in conformance work; independent high-risk review returns
`SLICE REVIEW PASS`; one atomic implementation commit and final handoff exist, followed
by Coordinator acceptance metadata.

## Coverage matrix

Coverage target: **9 requirements, 25 acceptance scenarios, and 23 tasks**. A task shared
across slices is complete only after every listed owner has passed its completion gate.

### Requirement and scenario ownership

| OpenSpec requirement/scenario | Owning slice | Verification |
|---|---|---|
| Analyze only an immutable existing Alert LensRun | VS-01 | VS01-AC01, VS01-AC02 |
| Analyze a prepared running Alert LensRun | VS-01 | VS01-AC01 |
| Reject a non-running Alert LensRun | VS-01 | VS01-AC02 |
| Acquire and validate current records with lifecycle overlap | VS-02, VS-03, VS-04 | VS02-AC01/05; VS03-AC02/03; VS04-AC01/02/06 |
| Include an alert spanning the window boundary | VS-02 | VS02-AC01, VS02-AC05 |
| Continue with a usable subset | VS-03 | VS03-AC02 |
| Fail when every returned current record is invalid | VS-04 | VS04-AC02, with non-empty/no-usable distinction in VS04-AC06 |
| Reject every duplicate current ID in its collision set | VS-03 | VS03-AC03 |
| Fail current acquisition distinctly | VS-04 | VS04-AC01 |
| Derive independent reference evidence without exposing records | VS-03 | VS03-AC01, VS03-AC04, VS03-AC06/07 |
| Retain successful comparisons around a failed offset | VS-03 | VS03-AC01, VS03-AC04 |
| Keep zero-record current analysis reference-aware | VS-03 | VS03-AC01 |
| Produce mandatory deterministic alert evidence | VS-01, VS-02, VS-04 | VS01-AC03; VS02-AC01/02; VS04-AC03 |
| Apply the missing occurrence default without changing status counts | VS-02 | VS02-AC02 |
| Omit duration statistics for zero records | VS-01 | VS01-AC03 |
| Constrain Alert Agent and optional analysis | VS-02, VS-04, VS-05, VS-08 | VS02-AC03/04/06; VS04-AC04; VS05-AC01-05; VS08-AC01-06 |
| Skip the agent only for zero records | VS-01 | VS01-AC03 |
| Do not skip records with zero occurrences | VS-02 | VS02-AC03 |
| Reject an invalid agent completion before result building | VS-04, VS-08 | VS04-AC04, VS08-AC04 |
| Continue after an optional timeout | VS-05, VS-08 | VS05-AC05, VS08-AC05 |
| Treat an undersized duration sample as normal non-applicability | VS-05 | VS05-AC03 |
| Build a strict usable AlertAnalysisResult | VS-01, VS-02, VS-03, VS-05, VS-06, VS-07 | VS01-AC03/04; VS02-AC04; VS03-AC05; VS05-AC05; VS06-AC01-03; VS07-AC01-04 |
| Validate zero-record output | VS-01 | VS01-AC03, VS01-AC04 |
| Resolve encoded reserved and Unicode current IDs canonically | VS-06 | VS06-AC01 |
| Reject a non-canonical or malformed evidence-reference URI | VS-06 | VS06-AC02 |
| Reject a non-resolving finding reference | VS-06 | VS06-AC03 |
| Select one public reason and preserve Alert failure absence | VS-03, VS-04, VS-06, VS-07 | VS03-AC05; VS04-AC01-05; VS06-AC02/03; VS07-AC04 |
| Select current-subset incompleteness over reference unavailability | VS-03 | VS03-AC05 |
| Fail a non-zero run when the required agent fails | VS-04, VS-08 | VS04-AC04/05, VS08-AC04 |
| Persist terminal outcome atomically through runtime persistence | VS-01, VS-03, VS-04, VS-06, VS-07, VS-09 | VS01-AC04; VS03-AC05/06; VS04-AC05/06; VS06-AC01/02; VS07-AC04; VS09-AC01-03/06 |
| Persist a partial result with its matching LensRun reason | VS-03, VS-09 | VS03-AC05, VS09-AC02 |
| Roll back a failed terminal write | VS-09 | VS09-AC01 |
| Keep provider transport and production model selection outside | VS-01, VS-02, VS-08, VS-09 | VS01-AC01; VS02-AC03/06; VS08-AC01/03/06; VS09-AC04 |
| Exercise the pipeline without live integrations | VS-01, VS-08, VS-09 | VS01-AC01-04; VS08-AC01-05; VS09-AC04 |

### Task ownership

| OpenSpec task | Owning slice(s) | Verification |
|---|---|---|
| 1.1 Strict Alert contracts | VS-01, VS-02, VS-03, VS-04, VS-05, VS-06, VS-07 | VS-01/VS-05 technical verification; VS02-AC06; VS03-AC02-04; VS04-AC01-04; VS06-AC01-03; VS07-AC01-03 |
| 1.2 Framework-neutral provider/agent/tool ports | VS-01, VS-02, VS-05 | VS01-AC01-03; VS02-AC03; VS05-AC01/05 |
| 1.3 Windows, overlap, validity, uniqueness, acquisition outcomes | VS-01, VS-02, VS-03, VS-04 | VS01-AC01; VS02-AC01/05; VS03-AC01-04; VS04-AC01/02/06 |
| 2.1 Deterministic current analyzer | VS-01, VS-02 | VS01-AC03; VS02-AC01/02 |
| 2.2 Independent references and comparison | VS-03 | VS03-AC01, VS03-AC04, VS03-AC07 |
| 2.3 Current/reference failure and incompleteness | VS-03, VS-04 | VS03-AC02-07; VS04-AC01-03/06 |
| 3.1 Optional registry and ten-attempt ledger | VS-05, adapter regression VS-08 | VS05-AC01; VS08-AC02/03 |
| 3.2 Recurrence concentration | VS-05 | VS05-AC02 |
| 3.3 Duration outlier analysis | VS-05 | VS05-AC03 |
| 3.4 Reference-pattern analysis | VS-05 | VS05-AC04 |
| 4.1 Strict agent projection and application executor mapping | VS-02, VS-04, VS-05 | VS02-AC03/04/06; VS04-AC04; VS05-AC01/05 |
| 4.2 Injected PydanticAI adapter | VS-08 | VS08-AC01-06 plus no-retry technical verification |
| 4.3 Deterministic adapter tests | VS-08 | VS08-AC01-06 plus no-retry technical verification |
| 5.1 Sole strict result builder | VS-01, VS-02, VS-03, VS-05, VS-06, VS-07 | Result acceptance IDs in each owner |
| 5.2 Canonical `alert://` grammar and resolution | VS-06 | VS06-AC01-03 |
| 5.3 Terminal reason mapping | VS-03, VS-04, VS-06, VS-07 | VS03-AC05; VS04-AC01-05; VS06-AC02/03; VS07-AC04 |
| 5.4 Exhaustive builder tests and failed absence | VS-01, VS-02, VS-04, VS-06, VS-07 | VS01-AC03/04; VS02-AC04; VS04-AC05; VS06-AC01-03; VS07-AC01-04 |
| 6.1 Alerts Analysis Pipeline stage order | VS-01 primary; VS-02-VS-08 increments; VS-09 conformance | Every service acceptance ID; VS09-AC03 |
| 6.2 Existing runtime transaction/artifact integration | VS-01, VS-03 | VS01-AC04; VS03-AC05-07 |
| 6.3 Completed/partial/failed/rollback/mismatch persistence tests | VS-01, VS-03, VS-04, VS-06, VS-07, VS-09 | VS01-AC04; VS03-AC05/06; VS04-AC05/06; VS06-AC01/02; VS07-AC04; VS09-AC01/02/06 |
| 7.1 Docstrings and injection/composition documentation | VS-01-VS-08 public symbols; VS-09 final audit/docs | Slice scope audits and VS-09 completion gate |
| 7.2 Focused backend and PostgreSQL verification | Every slice; VS-09 final focused suite | Each slice completion gate and VS09-AC04 boundary audit |
| 7.3 Strict OpenSpec validation and `make check` | VS-09 | VS-09 completion gate |

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements,
acceptance obligations, proof-level changes, dependency changes, or redesign decisions
here.

- 2026-09-01 — Execution stopped before readiness initialization. `git status
  --porcelain=v1 --untracked-files=all` is non-empty: unrelated modified skill/template
  files are present and the approved change artifacts, including this plan, are untracked.
  The Coordinator clean-boundary protocol prohibits dispatching VS-01 until the user
  reconciles or explicitly directs handling of that pre-existing working-tree state.
- 2026-09-01 — Stop condition resolved: the approved change and prior working-tree
  updates are committed, and the clean-boundary check passes. VS-01 is `READY`.
- 2026-09-01 — VS-01 assigned to a fresh Slice Implementer. Active assignment:
  `/root/vs01_implementer`; baseline commit: `79c9570`.
- 2026-09-01 — VS-01 candidate implementation commit: `d1dc5b3`; handoff:
  `implementation/VS-01-handoff.md`. Coordinator independently reran the required
  PostgreSQL proof with the existing local test service (`1 passed`), alongside the
  Implementer's recorded focused, nearby-regression, full-backend, and Ruff evidence.
  Change-map deviation disposition was `N/A` (none reported or observed). The required
  high-risk review returned `SLICE CHANGES REQUIRED`: a correctable in-scope strict
  zero-result projection defect and an evidence-recording inconsistency require a
  focused correction before a new deviation disposition and re-review.
- 2026-09-01 — VS-01 corrective assignment: `/root/vs01_correction`; baseline commit:
  `4c6940d`. VS-01 remains `IN_PROGRESS`.
- 2026-09-01 — Corrective commits `5933bb5` (strict zero-result projection and proof)
  and `af65a93` (handoff provenance correction) address the first high-risk review.
  Coordinator independently verified focused unit/service (`5 passed`), PostgreSQL
  (`1 passed`), and Ruff checks. Change-map deviation disposition: `N/A` (no map
  deviation; correction restores an approved VS-01 obligation). Candidate is ready for
  bounded re-review of the two reported findings.
- 2026-09-01 — VS-01 accepted after bounded findings verification: both reported
  findings are `RESOLVED`, with no new regressions. Accepted implementation/correction
  commits: `d1dc5b3`, `5933bb5`, `af65a93`; handoff:
  `implementation/VS-01-handoff.md`. All VS01-AC obligations and the high-risk gate
  passed. Approved tasks remain unchecked because every task portion touched by VS-01
  continues in later slices. VS-02 is now `READY`.
