# Implementation Plan — add-metrics-analysis-pipeline

**Status:** DRAFT
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-metrics-analysis-pipeline`
**Planning branch:** `feature/add-metrics-analysis-pipeline`
**Implementation candidate branch:** `experiment/codex-add-metrics-analysis-pipeline`

## Approval history and renewed gate

- The original implementation plan was approved for execution, and accepted execution
  history through VS-07 remains valid.
- Approved dependency scope for VS-08:
  `pydantic-ai-slim>=2,<3`
- Provider extras: not approved / must not be added.
- This records an already-made dependency approval; it does not create a new decision.
- This structural revision inserts VS-07R and revises downstream ownership. It is not
  approved for execution until an independent slice-plan review completes and the human
  explicitly reapproves the revised plan.

## Authority and constraints

This file describes how the approved change will be implemented. It does not redefine what must be implemented. Accepted ADRs/normative contracts and the approved OpenSpec remain authoritative.

Approved change sources:

- `openspec/changes/add-metrics-analysis-pipeline/proposal.md`
- `openspec/changes/add-metrics-analysis-pipeline/specs/metrics-analysis-pipeline/spec.md`
- `openspec/changes/add-metrics-analysis-pipeline/design.md`
- `openspec/changes/add-metrics-analysis-pipeline/tasks.md`

Architecture and accepted-contract sources:

- `docs/architecture/README.md`
- `docs/architecture/01_observation_lens_concept.md`
- `docs/architecture/02_architecture_principles_and_runtime.md`
- `docs/architecture/03_ADR_log.md`: ADR-003, ADR-015–041, ADR-043–049, ADR-059, ADR-068, ADR-133–135, and ADR-152–160
- `docs/architecture/04_pipeline_and_agent_concepts.md`
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`
- `docs/architecture/10_open_decisions_and_backlog.md`
- `docs/architecture/11_glossary_and_naming.md`
- `openspec/specs/observation-definition-api/spec.md`
- `openspec/specs/runtime-persistence/spec.md`

Repository constraints:

- Execute this plan only after independent re-review and explicit human approval.
- Do not use rejected experimental candidates as implementation references.
- Do not add a public endpoint, frontend behavior, database table, migration, Prometheus transport, production model/provider selection, or top-level Observation orchestration.
- Keep deterministic orchestration and domain contracts framework-neutral. PydanticAI belongs only in the infrastructure adapter.
- Use the existing runtime artifact aggregate and caller-owned async transaction.
- Human approval for `pydantic-ai-slim>=2,<3` without provider extras was already given during the approved Metrics planning process. Before VS-08 starts, the Coordinator verifies and records that existing approval in execution metadata; this is not a second approval decision. If the approval record cannot be verified, execution pauses for source reconciliation rather than re-deciding the dependency in this plan.
- Open prompt wording, provider/model choice, model-dependent budgets, request timeout, and Prometheus transport policy remain implementation-private or out of scope as stated in the approved design. They must not alter the typed contracts or deterministic budgets.
- OpenSpec tasks 1.2, 1.4, 2.1–2.3, 3.1–3.2, 7.3–7.5, 8.1–8.2, 9.1–9.3, 10.2, and 11.2 are intentionally fulfilled by explicitly named behavioral sub-parts across slices. A task checkbox is complete only when every listed owner has completed its sub-part; no later slice may silently absorb an earlier owner's behavior.

After renewed human approval, the revised slice structure is frozen. Only the Coordinator may update execution metadata. Further structural changes require re-planning, independent plan review, and human re-approval.

## Slice graph

```text
VS-01 -> VS-02 -> VS-03 -> VS-04 -------------------> VS-09
  |        |         |
  |        |         +-------> VS-06 ---------------> VS-09
  |        +-> VS-07 -> VS-07R -> VS-08 ------------> VS-09
  +-> VS-05 ----------> VS-06
```

VS-06 has both VS-03 and VS-05 as direct dependencies. VS-07R depends on VS-07,
and VS-08 depends on VS-07R. VS-09 has VS-04, VS-06, and VS-08 as direct
dependencies. Default execution remains sequential in the displayed order, with VS-07R
between VS-07 and VS-08. Graph edges express true prerequisites, not authorization to
execute independent slices concurrently. A slice starts only after its dependencies pass
their completion gates and any required independent high-risk review.

## Execution overview

| Slice | Goal | Depends on | Risk | Status | Commit | Handoff |
|---|---|---|---|---|---|---|
| VS-01 | Persist one representative completed-sufficient good-series Metric run end to end | none | high-risk | COMPLETE | 54fc2de | `implementation/VS-01-handoff.md` |
| VS-02 | Persist degraded and completed-insufficient current-quality behavior | VS-01 | high-risk | COMPLETE | dfcf909 | `implementation/VS-02-handoff.md` |
| VS-03 | Persist every mandatory current-failure outcome | VS-02 | high-risk | COMPLETE | 734ff07 | `implementation/VS-03-handoff.md` |
| VS-04 | Add independent reference comparison and reference-caused partial persistence | VS-03 | high-risk | COMPLETE | d65ff287 | `implementation/VS-04-handoff.md` |
| VS-05 | Add eligible persisted-result History behavior through the reader boundary | VS-01 | high-risk | COMPLETE | 442557e | `implementation/VS-05-handoff.md` |
| VS-06 | Implement PostgreSQL History selection and regress transaction ordering/atomicity for all result variants | VS-03 and VS-05 | high-risk | COMPLETE | ad59b9d + f6648d0 + 51b5236 | `implementation/VS-06-handoff.md` |
| VS-07 | Add deterministic optional tools, registered-execution ledger behavior, and tool-caused partial persistence | VS-02 | high-risk | COMPLETE | 9f598785 + 56a03b2 | `implementation/VS-07-handoff.md` |
| VS-07R | Add the framework-neutral rejection-capable request policy and persist protocol-caused partial outcomes | VS-07 | high-risk | PLANNED | - | - |
| VS-08 | Translate the accepted framework-neutral policy through PydanticAI and enforce framework request ceilings | VS-07R; existing dependency approval verified by Coordinator | high-risk | BLOCKED | d4d8e48 (unaccepted; revert before re-execution) | `implementation/VS-08-handoff.md` (unaccepted) |
| VS-09 | Verify cross-cause composition, document boundaries, and run full conformance | VS-04, VS-06, and VS-08 | high-risk | PLANNED | - | - |

## Slice definitions

### VS-01 — Representative persisted completed-sufficient walking skeleton

**Behavioral goal:** Given one already-created, already-running Metric LensRun with no configured references, one representative finite good series from a successful fake current provider, a successful framework-neutral fake Metrics Agent that requests no tools, and a successful History reader returning no eligible rows, calculate representative exact mandatory evidence/semantics and persist exactly one strict completed-sufficient MetricAnalysisResult while advancing the real LensRun to `completed` through the caller-owned transaction.

**OpenSpec coverage:** the representative completed-sufficient path of “Execute one immutable Metric Lens scope through a deterministic pipeline”; zero-reference and transport-free provider scenarios; one exact good-series preparation/statistics/mandatory-semantics path; the good usable-request projection and zero-tool fake-completion scenarios; completed-sufficient result construction; the successful transaction sub-part of persistence; tasks 1.1, good/current/available/usable/empty-History portions of 1.2–1.4, representative good-series portions of 2.1–2.3 and 3.1–3.2, completed-sufficient portions of 8.1–8.2, successful-current portion of 9.1, completed-sufficient portion of 10.2, and focused verification in 11.2.

**Dependencies:** none.

**Vertical boundary:** pre-transaction phase: existing already-running LensRun context -> fake current acquisition -> representative deterministic preparation/statistics/mandatory semantics -> exact framework-neutral good usable request -> zero-tool fake completion. Transaction-owned phase: caller opens the database transaction only after those stages finish -> successful empty History read -> strict completed-sufficient build -> real LensRun terminal transition -> artifact insertion/flush -> caller commit, with caller rollback ownership on transaction error -> retrieval.

**Expected code impact:** minimal `backend/src/app/metrics/` package with only the frozen current execution context, contracts/ports, good-series preparation/statistics/semantics, good usable-agent request and zero-tool completion, empty-success History boundary, completed-sufficient result builder, and pipeline behavior actually exercised here; focused unit/pipeline tests; one PostgreSQL-backed walking-skeleton integration test using the existing runtime repository. Do not add completed-insufficient, partial, failed, reference, non-empty History, optional-tool outcome, ledger, or adapter structural shells in this slice.

**Contracts consumed/changed:** consumes existing UUID/string definition primitives, `LensRunModel`, `LensAnalysisResultInput`, `LensRunStatus`, `StructuredReason`, and repository flush-without-commit behavior. Defines only contracts with first real use in this path: immutable execution context; current available/provider and prepared-good outcomes; representative mandatory evidence/semantics; exact good `MetricAgentUsableRequest` including the required fixed descriptors and opaque bound `dataset_ref`; strict zero-tool completion; minimal successful-empty History reader outcome; provider/agent/History ports needed by this execution; and the completed-sufficient result variant/nested models it uses. The fake agent cannot author provider scope or dataset selection.

**Non-goals:** non-finite degradation; exhaustive quality or ADR-153 threshold/constant boundaries; insufficient current behavior; mandatory failure mapping; optional tool execution/ledger; configured references; non-empty History analysis; other result variants; PydanticAI; PostgreSQL History selection; rollback fault injection; combined partial reasons; transport; or top-level run creation.

**Focused verification:** immutable scope and exact UTC `from/to`; one current request and zero reference requests; one representative good series with exact mean/population-std/min/max/elapsed-time OLS slope and exact representative trend/variability descriptors; exact strict good usable request with objectives, evidence, semantics, ordered descriptor tuple, and opaque dataset reference but no raw/provider/reference/History data; successful zero-tool fake completion; History reader actually invoked and empty History treated as normal; strict completed-sufficient payload; pipeline receives an already-running LensRun and creates no run. An ordered phase trace must prove provider acquisition, current preparation/statistics/semanticization, and agent execution all complete before the caller opens the database transaction; it must then prove the empty History read, LensRun transition, artifact insertion/flush, and caller commit occur inside that transaction. Retrieval must round-trip exact identity/window/provenance/current evidence. Import-boundary assertions remain framework/transport free.

**Context pack:** root `AGENTS.md`; approved requirements “Execute one immutable…”, “Acquire metric series…”, “Prepare samples…”, “Form mandatory trend…”, good usable-request and zero-call portions of “Invoke the Metrics Analysis Agent…”, completed-sufficient result/persistence portions; design decisions 1–4, 6, and 10–12; ADR-003, ADR-026–041, ADR-043–049, ADR-059, ADR-068, ADR-152–153, ADR-156; accepted runtime-persistence spec; current observation contracts, runtime contracts, repository/models, and persistence tests.

**Handoff expectations:** identify the pipeline entry point; contracts introduced because they are exercised; fake-port conventions; representative fixture/evidence; the exact pre-transaction versus transaction-owned phase trace; persisted walking-skeleton evidence; focused commands/results; explicitly deferred contracts/behaviors; and candidate shared knowledge with evidence.

**Risk:** high-risk

**Completion gate:** representative pure current analysis, fake-agent pipeline, and PostgreSQL-backed completed-sufficient walking-skeleton tests pass; the restored LensRun is `completed` with exactly one strict artifact; empty History is proven successful rather than skipped or treated as failure; the recorded order proves acquisition/current processing/agent execution precede transaction opening and History/transition/artifact flush/caller commit are transaction-owned; no future result/contract shell, run creation, transport, framework import, schema change, or new dependency appears; Ruff passes on changed files; independent high-risk review has no unresolved blocker/high finding; one atomic commit and handoff exist.

### VS-02 — Current-quality degradation and completed-insufficient behavior

**Behavioral goal:** Extend the persisted current-only pipeline across the remaining successfully assessed quality behavior: non-finite filtering produces a usable degraded result and exact degraded usable-agent request, exhaustive ADR-153 threshold/constant behavior remains deterministic, and fewer than three finite samples invoke the narrow fake-agent request while preserving `completed + insufficient` even when that fake invocation fails.

**OpenSpec coverage:** “Degrade after removing non-finite samples”; “Complete insufficient current data”; exhaustive trend/variability boundary and constant-series scenarios; degraded and insufficient framework-neutral projections; insufficient-agent resilience; strict degraded completed-sufficient and completed-insufficient results; tasks 1.2/1.4 degraded and insufficient contracts, remaining non-malformed quality/statistics portions of 2.1–2.3, exhaustive 3.1–3.2, degraded/insufficient portions of 8.1–8.2, completed-insufficient portion of 9.1, degraded/completed-insufficient portions of 10.2, and focused verification in 11.2.

**Dependencies:** VS-01.

**Vertical boundary:** existing running Metric LensRun -> successful fake current provider -> deterministic non-finite filtering/quality assessment and exhaustive mandatory semantics -> exact degraded usable or identity/window/quality-only insufficient fake-agent invocation -> unchanged degraded core or resilient insufficient determination -> strict completed-sufficient degraded or completed-insufficient result -> established transaction phase with successful empty History where applicable -> real terminal transition/artifact flush -> caller commit and retrieval.

**Expected code impact:** extend preparation/statistics/semantics and current-path contracts/builder/pipeline only for degraded and insufficient outcomes; table-driven semantic tests; focused fake-agent pipeline tests; PostgreSQL round trips for degraded completed-sufficient and completed-insufficient. No mandatory-failure, reference, non-empty History, optional-tool/ledger, or framework-adapter contracts are added.

**Contracts consumed/changed:** adds degraded preparation/quality behavior and the strict `MetricAgentInsufficientRequest` plus its operational failure outcome only when first invoked; adds the completed-insufficient result variant. Reuses the VS-01 good usable projection for degraded data without widening it. Insufficient has no objectives, tools, dataset, evidence, current state, reference, or History data.

**Non-goals:** current provider failure, duplicate/out-of-window terminal mapping, unexpected mandatory technical failure, configured references, optional-tool execution, History candidates, PydanticAI translation, combined reason precedence, or persistence fault injection.

**Focused verification:** every non-finite-removal and three-finite-sample quality boundary; exact statistics including irregular timestamps/constant values and finite-output safeguards; trend values immediately below/at/above `0.05/0.15/0.35`, variability values immediately below/at/above `0.05/0.15`, signed/near-zero/increasing/decreasing and constant-scale behavior; exact degraded good-shape request; exact identity/window/quality-only insufficient request and no analytical tools; insufficient fake-agent failure remains operational and does not fabricate completion/evidence or change `completed + insufficient`; strict forbidden-field and persisted round-trip assertions for both outcomes; established transaction ordering remains intact.

**Context pack:** VS-01 handoff; approved preparation, mandatory semantics, degraded/insufficient agent, strict-result, and persistence requirements; design decisions 3–4, 6, and 10–12; ADR-026–041, ADR-046, ADR-153, ADR-156; accepted runtime-persistence spec and VS-01 lifecycle/result correlation tests.

**Handoff expectations:** enumerate degraded/insufficient inputs, exact semantic tables, two projection shapes and fake-agent resilience, persisted outcomes, tests run, remaining current technical failures for VS-03, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** exhaustive current-quality/ADR-153 tests, focused fake-agent pipeline tests, and PostgreSQL round trips pass for degraded completed-sufficient and completed-insufficient; the insufficient request is narrow and resilient; status/artifact shape correlates exactly; no technical current failure or adapter behavior is silently claimed; established transaction ordering regresses green; Ruff passes; independent high-risk review has no unresolved blocker/high finding; one atomic commit and handoff exist.

### VS-03 — Mandatory current-failure terminal paths

**Behavioral goal:** Extend the current pipeline so current acquisition unavailable/failure/timeout, malformed duplicate/out-of-window current series, and unexpected mandatory statistics/semanticization/sufficient-result validation failures each build the exact minimal failed Metric result and atomically persist the matching failed LensRun without leaking diagnostics.

**OpenSpec coverage:** malformed current duplicate/out-of-window scenarios; all minimal-failed result/error/provenance/identity/window scenarios; current-role terminal mappings; tasks 1.2/1.4 mandatory-failure contracts, malformed portions of 2.1, failed portions of 8.1–8.2, failed-current portion of 9.1 and 9.3, failed portion of 10.2, and focused verification in 11.2.

**Dependencies:** VS-02.

**Vertical boundary:** existing running Metric LensRun -> fake current provider or injected mandatory-stage outcome -> role-aware technical failure mapping -> exact strict minimal failed result -> transaction opens only after the failed analytical outcome is known -> matching failed transition + artifact insertion/flush -> caller commit and retrieval.

**Expected code impact:** add only typed current acquisition/malformed/unexpected mandatory-failure outcomes, three fixed error variants, failed result construction, pipeline mapping, focused contract/pipeline tests, and PostgreSQL cases for all failed categories. No reference-role behavior, History candidates, optional tools, or framework contracts are added.

**Contracts consumed/changed:** adds unavailable/failure/timeout provider and malformed/unexpected mandatory outcomes with bounded operational diagnostics; adds the strict failed result variant and exact stable code/message mapping. Provenance comes from validated execution context and injected UTC clock even before provider success.

**Non-goals:** reference-specific malformed mapping, optional incompleteness, non-empty History, History repository errors, PydanticAI, combined reason precedence, or backend rollback hardening.

**Focused verification:** acquisition unavailable/failure/timeout, normalized duplicate timestamp, out-of-window sample, and unexpected statistics/semanticization/sufficient-result validation failures map to the exact public code/message pairs; provider/exception/query/rejected-sample details stay operational; failed payload forbids analytical/partial fields; context provenance is preserved before provider success; real failed lifecycle/artifact round trips correlate exactly; agent and History are not invoked when analytically inapplicable; analytical failure determination precedes the terminal-write transaction.

**Context pack:** VS-01/VS-02 handoffs; approved malformed-current, minimal-failed, pipeline, and persistence requirements; design decisions 3–4 and 10–12; ADR-035–041, ADR-059, ADR-068; accepted runtime-persistence spec and existing lifecycle/result code/tests.

**Handoff expectations:** enumerate all typed current technical failures, public mappings, diagnostic exclusions, provenance source/clock behavior, persisted failed evidence, tests run, reference-role reuse constraints, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** focused contract/pipeline tests and PostgreSQL round trips pass for every mandatory current failure category; LensRun status/reason and artifact status/error correlate exactly; no current technical failure is deferred to a later slice; established transaction ordering remains green; Ruff passes; independent high-risk review has no unresolved blocker/high finding; one atomic commit and handoff exist.

### VS-04 — Independent reference behavior and persisted partial outcomes

**Behavioral goal:** For one usable current run, independently acquire zero, one, or many configured references, preserve every successful ordered comparison, and persist a usable partial result with `reference_unavailable/reference_periods` whenever any configured comparison is unavailable, malformed, or insufficient.

**OpenSpec coverage:** one/multiple reference acquisition; valid ordered reference comparison; every missing-reference scenario; reference-specific result sections and terminal contribution; tasks 1.2/1.4 reference contracts, 5.1–5.4, reference portions of 8.1–8.2, reference contribution of 9.2, reference-role portion of 9.3, reference partial portion of 10.2, and focused verification in 11.2.

**Dependencies:** VS-03.

**Vertical boundary:** immutable configured offsets -> exact derived provider windows -> independent acquisition/preparation/mandatory semantics -> deterministic current-relative comparison -> strict paired reference semantic/evidence sections or per-offset operational diagnostic -> completed/partial builder contribution -> established transaction phase -> real correlated terminal transition/artifact persistence.

**Expected code impact:** `references.py`, reference-owned contracts, pipeline/builder integration, focused reference tests, and persisted completed/partial pipeline cases. No History candidate model or optional-tool outcome contract is introduced.

**Contracts consumed/changed:** consumes the provider port and role-neutral preparation/semantic kernel; adds only reference-window/outcome/comparison/diagnostic/result-section contracts and the first partial result variant with `reference_unavailable/reference_periods`. Successful offsets remain correlated by offset/window/order.

**Non-goals:** baseline/seasonality classification, definition schema changes, model access to reference data, History behavior, optional tools, PostgreSQL History query, or combined reference+History+optional verification.

**Focused verification:** exact zero/one/many request count and equal-duration shifted windows; configured-order preservation; all level/trend-rate/direction/variability relations and non-comparable cases; paired semantic/evidence correlation; acquisition failure/timeout, duplicate, out-of-window, and post-filter insufficiency; successful-offset preservation and no placeholder; malformed reference never fails current; current-insufficient exemption; real partial status/reason equality and artifact retrieval; established transaction phase/order regression.

**Context pack:** VS-01–VS-03 handoffs; approved provider/reference requirements and relevant result/persistence scenarios; design decisions 3–4, 8, and 10–12; ADR-133–135, ADR-157; accepted definition offset contract and current provider/runtime tests.

**Handoff expectations:** document offset/window derivation interface, per-offset diagnostics, strict paired output, reference-owned terminal contribution, persisted partial evidence, tests run, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** all reference unit/pipeline tests and persisted reference completed/partial cases pass; every configured offset is independently attributable; successful comparisons survive failed offsets; no placeholder/default/baseline behavior exists; reference-caused lifecycle/result reason correlation is complete in this slice; established transaction ordering remains green; Ruff passes; independent high-risk review has no unresolved blocker/high finding; one atomic commit and handoff exist.

### VS-05 — Eligible persisted-result History behavior

**Behavioral goal:** Expand the already-exercised History reader boundary from empty success to typed eligible prior Metric results, then produce strict History semantics/evidence, normal omission, accepted analytical unknown, or persisted `history_analysis_failed/history` without allowing reader/infrastructure failure to masquerade as no History.

**OpenSpec coverage:** History eligibility, policy, chronology, transition, direction, pattern, normal absence, analytical unknown, and deterministic-failure behavior; fake-reader repository-failure propagation; History-specific result sections and terminal contribution; tasks 1.2/1.3/1.4 History expansion, 6.1–6.3 except real PostgreSQL query proof, History portions of 8.1–8.2, History contribution of 9.2, reader-failure portion of 9.3 at the port boundary, and focused verification in 11.2.

**Dependencies:** VS-01.

**Vertical boundary:** transaction-owned fake History reader returning strict prior-result projections + current usable evidence + effective policy -> eligibility/total event-time order/lookback -> deterministic transitions/direction/pattern -> paired History result sections, normal omission, typed deterministic failure, or propagated infrastructure error -> terminal transition/artifact persistence where an analytical terminal result exists -> caller commit/rollback.

**Expected code impact:** `history.py`, History-owned candidate/stage/result contracts introduced with non-empty behavior, expansion of the minimal reader port, pipeline/builder integration, exhaustive pure/fake-reader tests, and persisted History completed/partial cases. ORM/JSON query implementation remains deferred to VS-06.

**Contracts consumed/changed:** consumes strict previously validated Metric result projections only; adds candidate validation, accepted History output/evidence, deterministic-failure outcome, and `history_analysis_failed/history` contribution. Reader/session failures remain typed infrastructure failures and produce no claimed terminal result.

**Non-goals:** SQLAlchemy query strategy, database ordering proof, new table/index/migration, raw telemetry/history serialization, transaction rollback fault injection, optional tools, or three-cause precedence verification.

**Focused verification:** accepted defaults/override inputs; failed/insufficient/current candidate exclusion; overlapping strict-earlier-end eligibility and full event-time tie order over typed candidates; newest lookback then oldest-first IDs; exact ADR-159 boundaries; ADR-023 direction; every ADR-160 sequence, unknown denominator, stable-neutral runs, direction changes, and priority; no-history omission; analytical unknown without partial; deterministic computation failure persists History partial; fake reader failure propagates with no transition/artifact; History access occurs only after the established transaction opens.

**Context pack:** VS-01 handoff; approved History/result/persistence requirements; design decisions 9–12; ADR-015–025, ADR-034, ADR-041, ADR-068, ADR-157–160; accepted runtime-persistence spec; strict current result projection.

**Handoff expectations:** document the expanded reader/candidate contract, analyzer interfaces, exact analytical versus infrastructure failure boundary, transaction-owned reader call, persisted History outcomes, exhaustive test evidence, real-reader requirements for VS-06, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** all normative History algorithm/sequence tests and fake-reader pipeline tests pass; normal absence and unknown remain non-partial; deterministic failure persists the exact History reason; reader failure leaves running state/artifact untouched in the test transaction; History access is transaction-owned; no ORM/raw JSON enters the analyzer; Ruff passes; independent high-risk review has no unresolved blocker/high finding; one atomic commit and handoff exist.

### VS-06 — PostgreSQL History reader and all-variant transaction ordering/atomicity

**Behavioral goal:** Implement the bounded eligible Metric History read over the existing PostgreSQL runtime aggregate, prove event-time selection against real rows, round-trip every result variant supplied by VS-01/VS-02/VS-03/VS-05, and regress that analytical work stays outside while History read plus terminal persistence stays inside the existing caller-owned transaction and fully rolls back on repository/flush/commit failure.

**OpenSpec coverage:** PostgreSQL-specific History overlap/order/repository-failure scenarios; full persistence requirement including all-variant round trip and rollback; transaction-phase ordering regression; repository/infrastructure behavior; tasks 10.1, infrastructure/atomicity completion of 10.2, 10.3, real-repository portion of 6.2–6.3 and 9.3, plus focused verification in 11.2.

**Dependencies:** VS-03 and VS-05. Through VS-03 this includes the VS-01 completed-sufficient and VS-02 completed-insufficient variants; VS-03 supplies the failed variant, and VS-05 supplies the History-caused partial variant/domain behavior needed by this slice.

**Vertical boundary:** pre-transaction provider/current/agent outcomes supplied by owning paths -> caller opens real PostgreSQL transaction -> bounded History filter/projection when applicable -> strict History candidate validation/order/lookback -> strict terminal result build -> real LensRun transition + artifact insertion/flush -> caller commit, or caller rollback of both writes on any repository/flush/commit error.

**Expected code impact:** bounded extension only to the existing runtime repository; real adapter from persistence rows to strict History projections; PostgreSQL query, all-variant round-trip, transaction-order, failure-propagation, and rollback tests. No persistence model, table, index, or migration is expected.

**Contracts consumed/changed:** implements the VS-05 `MetricHistoryReader` with the existing SQLAlchemy aggregate and reuses `advance_lens_run`/`persist_lens_analysis_result`. It consumes completed-sufficient, completed-insufficient, partial, and failed result variants already introduced by its dependencies; it does not create placeholder variants. If JSON timestamp ordering cannot be safely expressed, use only the approved bounded relational prefilter plus strict application validation/order strategy and document/test the bound.

**Non-goals:** new result behavior, raw telemetry, completion/persistence chronology as History chronology, a second repository, schema/index/migration, retry/recovery, database reset, top-level orchestration, or analytical reason fallback after backend failure.

**Focused verification:** same Observation definition through parent + same string Lens ID; metric completed/partial good/degraded eligibility; current/failed/insufficient exclusion; overlapping earlier windows; end/start/lexical-ID ordering; newest lookback and oldest-first IDs; late persistence independence; strict completed-sufficient/completed-insufficient/partial/failed round trips; exact LensRun/result status/reason correlation; History query/session failure propagation; forced flush and commit failure with both terminal state and artifact absent after rollback; no fabricated fallback result. An instrumented real-pipeline phase trace must regress, for every applicable variant, that provider acquisition, deterministic current processing, and agent execution finish before transaction opening; History read, LensRun terminal transition, artifact insertion/flush, and caller commit/rollback must be inside the transaction.

**Context pack:** VS-01/VS-02/VS-03/VS-05 handoffs; approved History/persistence requirements; design decisions 9 and 11–12; ADR-015–018, ADR-041, ADR-059, ADR-068, ADR-158; accepted runtime-persistence spec; repository/models/runtime contracts, migrations, unit tests, and PostgreSQL integration fixture.

**Handoff expectations:** record bounded query strategy and bound, strict row projection, exact phase trace and transaction owner/call order, all-variant round-trip and rollback evidence, exact PostgreSQL commands/results, unchanged schema confirmation, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** focused unit and PostgreSQL tests pass; query/filter/order/lookback is bounded and event-time correct; all four result variants from their owning slices round-trip; the pre-transaction versus transaction-owned order is regressed with real PostgreSQL; repository/transaction failures propagate; flush and commit failures roll back both writes; no schema/migration change exists; existing persistence tests remain green; Ruff passes; independent high-risk review has no unresolved blocker/high finding; one atomic commit and handoff exist.

### VS-07 — Deterministic optional-tool registry, registered executions, and persisted tool partials

**Behavioral goal:** Let the framework-neutral fake agent discover the exact deterministic registry and exercise exactly `spike`, `oscillation`, and `stuck_signal` once each over one opaque bound current dataset; record executed registered attempts and deterministic tool outcomes; project only successful optional semantics/evidence; and persist the exact tool-owned partial reason when deterministic optional execution fails or times out.

**OpenSpec coverage:** all exactly-three-tools algorithm scenarios; primary ownership of the deterministic allowed-tool registry projection and all-three-tools fake execution; executed registered-attempt order and tool-only component selection; successful/not-applicable/failed/timeout public projection matrix; tasks 1.2/1.4 registered-tool/ledger/result portions, registered-registry/outcome portions of 4.1 and 4.5, tasks 4.2–4.4, registered all-tools sub-parts of 7.3 and 7.5, tool-owned portions of 8.1–8.2 and 9.2, optional-tool partial portion of 10.2, and focused verification in 11.2. Rejected-request outcomes and their ledger/policy behavior are owned by VS-07R.

**Dependencies:** VS-02.

**Vertical boundary:** opaque run-scoped prepared-current binding + exact deterministic registry projected into the already-defined usable request + fake-agent registered request sequence -> executed-attempt ledger entries -> deterministic tool execution -> optional property/evidence projection or typed tool failure/timeout -> strict completed/partial result -> established transaction phase -> real terminal transition/artifact persistence.

**Expected code impact:** `tools.py`, registry/optional/ledger contracts introduced by this behavior, pipeline/builder integration, exhaustive tool tests, fake-agent registry/all-three pipeline tests, and persisted completed/partial cases.

**Contracts consumed/changed:** consumes the usable request/descriptors and opaque dataset reference introduced by VS-01; makes the registry the authoritative source of exactly those projected descriptors; adds typed success/not-applicable/failure/timeout outcomes, authoritative attempt ordering for executed registered tools, public optional evidence models, and earliest failed/timed-out registered-tool component selection when no agent/protocol violation exists. This completed slice's `MetricToolAttempt` represents executed registered-tool attempts only; VS-07R extends the framework-neutral ledger and request policy for rejected requests without changing these algorithms or successful outcome projections.

**Non-goals:** rejection-capable request policy; duplicate/unregistered/parallel/fourth request recording; PydanticAI translation/request mechanics; model limits/retries; natural-language prompt text; agent/protocol failure priority; references; History; or combined-cause precedence.

**Focused verification:** every Spike, Oscillation, and Stuck Signal rule/boundary and minimum-sample outcome; authoritative registry is exactly the fixed descriptors/order and the usable request projection cannot drift; immutable dataset binding; fake-agent all-three execution with one application-owned ordinal per attempt; successful present/absent/unknown co-occurrence; not evaluated/not-applicable omission; failure/timeout omission and partial contribution; earliest failed/timed-out tool by ordinal; not-applicable and successful unknown remain non-partial; transient series/reference/ledger/diagnostics absent from result; actual partial status/reason/artifact correlation; zero-tool behavior remains owned/regressed from VS-01 without being re-owned here.

**Context pack:** VS-01/VS-02 handoffs; approved optional-tool and framework-neutral registry/ledger/result requirements; design decisions 5, 6, 10, and 12; ADR-027, ADR-029, ADR-049, ADR-154–156; existing pipeline/builder and persistence tests.

**Handoff expectations:** list authoritative registry/tool interfaces, run-scoped catalog lifetime, registered outcome/public projection matrix, executed-attempt/component rules, all-three fake execution, persisted partial evidence, the framework-neutral gaps assigned to VS-07R, tests run, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** exhaustive tool and fake-agent registry/all-three pipeline tests pass; registry is exactly the three accepted tools and is the source of the usable descriptor projection; executed registered-attempt ordering and tool-only failure status/reason persistence are complete; no rejected-request or model-protocol behavior is claimed; no transient data is serialized; no PydanticAI import/dependency exists yet; established transaction ordering remains green; Ruff passes; independent high-risk review has no unresolved blocker/high finding; the accepted commits and handoff remain the execution record.

### VS-07R — Framework-neutral rejection ledger, request policy, and protocol partials

**Behavioral goal:** Extend the accepted VS-07 registry boundary with one application-owned, framework-neutral request policy that records every requested action needed by the approved three-slot/each-tool-once contract, rejects duplicate, unregistered, parallel, and over-budget requests before forbidden execution, retains earlier valid deterministic tool results, and persists `optional_analysis_failed/metrics_agent` for a usable run when a fake agent triggers a protocol rejection.

**OpenSpec coverage:** primary ownership of the framework-neutral rejection-capable ledger and request policy; the duplicate and fourth-request acceptance scenarios; unregistered and parallel rejection semantics from the bounded-agent requirement; agent/protocol priority over an earlier tool failure; scope enforcement at the deterministic request boundary; rejected-outcome portions of tasks 1.2, 1.4, 4.1, and 4.5; application-owned policy/rejection portions of 7.3–7.5; protocol-contribution portions of 8.1–8.2, 9.2, and 10.2; and focused verification in 11.2.

**Dependencies:** VS-07.

**Vertical boundary:** already-owned opaque dataset binding and deterministic registry + framework-neutral fake-agent request sequence -> application-owned request admission/rejection policy -> accepted registered execution or typed rejected attempt -> authoritative transient ledger and protocol outcome -> preservation of earlier successful projections -> deterministic optional reason selection -> strict partial result -> established transaction phase -> real terminal transition/artifact persistence.

**Expected code impact:** narrow extensions to framework-neutral contracts, ports, and `tools.py` for typed rejected attempts and request admission; pipeline/result-selection integration for a typed agent/protocol failure signal; focused fake-agent, contract, tool-policy, builder, pipeline, and PostgreSQL persistence tests. No dependency, PydanticAI import, adapter, prompt, provider, or deterministic tool-algorithm change belongs here.

**Contracts consumed/changed:** consumes the accepted VS-07 descriptors, deterministic evaluators, registered outcomes, successful projections, and executed-attempt ordering. Adds the approved framework-neutral rejected outcome with bounded rejection reason, a ledger entry capable of representing non-executed rejected requests (including an unregistered requested name), explicit slot-consumption/execution semantics, and an application-owned request policy that is the sole owner of each-tool-once, active-call/parallel, three-slot, and post-budget rejection decisions. Adds only the typed protocol-failure metadata needed for the deterministic pipeline to prefer `metrics_agent`; neither the model nor PydanticAI authors the ledger or terminal reason.

**Non-goals:** changing Spike, Oscillation, or Stuck Signal behavior; changing accepted VS-07 successful/not-applicable/failed/timeout projections; PydanticAI tool registration or message translation; framework validation retries; model-request counting/ceiling; production model/provider selection; prompt prose; references; History; cross-cause precedence; or reusing the rejected VS-08 candidate.

**Focused verification:** the first three requested actions each consume exactly one slot for success, not-applicable, failure, timeout, duplicate, unregistered, or parallel rejection; an already-used tool is not executed twice; an unregistered name never reaches a deterministic evaluator; a request made while another execution is active is rejected without parallel execution; a request after three consumed slots is recorded as over-budget without consuming or executing a fourth slot; ordinals and requested names remain deterministic; valid earlier tool results survive a later rejection; any rejection selects `optional_analysis_failed/metrics_agent` even after an earlier tool failure; tool failures without a protocol violation still select the earliest failed/timed-out tool; not-applicable and successful unknown remain non-partial; scope selectors cannot enter the policy call; ledger, rejection diagnostics, dataset references, and prepared samples remain absent from the public result; fake-agent pipeline and PostgreSQL tests prove real partial LensRun/result reason correlation.

**Context pack:** root `AGENTS.md`; VS-01/VS-02/VS-07 handoffs; complete approved bounded-agent and strict-result requirements; tasks 1.2, 1.4, 4.1, 4.5, 7.3–7.5, 8.1–8.2, 9.2, and 10.2; design decisions 5–6, 10, and 12; ADR-045–049 and ADR-152, ADR-154–156; current framework-neutral contracts/ports/tools/pipeline/result builder and focused tests. Do not read or reuse rejected experimental implementations.

**Handoff expectations:** record the request-policy interface, accepted/rejected outcome union, slot and ordinal accounting, active-call rule, agent/protocol metadata consumed by the pipeline, preservation of accepted VS-07 behavior and earlier successful projections, persisted rejection evidence, focused commands/results, exact adapter obligations left for VS-08, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** framework-neutral contract/policy, fake-agent pipeline, and PostgreSQL rejection-partial tests pass for duplicate, unregistered, parallel, and fourth requests; every request is recorded with exact consumption/execution behavior; forbidden execution is impossible through the policy; agent/protocol priority and earlier valid-result retention are proven; accepted VS-07 algorithms and tool-only component selection regress green; no PydanticAI/dependency/adapter change or public diagnostic leakage appears; established transaction ordering remains green; Ruff passes; independent high-risk review has no unresolved blocker/high finding; one atomic commit and handoff exist.

### VS-08 — Bounded PydanticAI translation and framework budget enforcement

**Behavioral goal:** Implement the injected PydanticAI adapter over the already-owned framework-neutral good/degraded/insufficient projections and VS-07R request policy, route framework-observable tool requests and violations through that policy, enforce zero validation retries and the hard model-request ceiling, and persist the correct usable partial result for adapter/model failure while preserving completed-insufficient resilience.

**OpenSpec coverage:** primary ownership of PydanticAI translation, zero framework validation retries, no model-retry hook, the four-model-request/no-fifth ceiling, usable adapter/model-failure translation, insufficient adapter resilience, and framework isolation; adapter-specific regression (not primary ownership) for exact good/degraded/insufficient projections, agentic scope rejection, zero/all-three calls, and every VS-07R request-policy rejection; tasks 7.1–7.2, framework-adapter/model-budget portions of 7.3–7.5, adapter/model portions of 1.2, 8.1–8.2, 9.2, and 10.2, and focused verification in 11.2.

**Dependencies:** VS-07R. Before dispatch, the Coordinator verifies that the already-given `pydantic-ai-slim>=2,<3` without-provider-extras approval remains recorded; no new dependency decision is requested.

**Vertical boundary:** exact already-owned framework-neutral request + VS-07R policy-bound tool closures + injected PydanticAI model -> adapter translation with zero validation retries and hard request ceiling -> framework events routed into accepted request-policy or typed adapter/model failure outcomes -> strict completion or failure translation -> existing deterministic result selection -> established transaction phase -> real correlated terminal transition/artifact persistence.

**Expected code impact:** approved `pydantic-ai-slim>=2,<3` dependency/lock update after the Coordinator records existing approval; one infrastructure adapter; deterministic model-double tests; narrow pipeline/persistence integration tests; import-boundary assertions.

**Contracts consumed/changed:** implements `MetricsAnalysisAgent` without widening the framework-neutral request, completion, rejection-policy, ledger, or protocol-outcome types owned by VS-01/VS-02/VS-07/VS-07R; uses no provider extra or model default. Framework-observable requests must pass through the VS-07R policy rather than an adapter-private duplicate/budget ledger. Adapter/model failure maps into the already-owned `optional_analysis_failed/metrics_agent` path and insufficient outcomes stay completed-insufficient.

**Non-goals:** re-owning framework-neutral projection, zero-tool behavior, request-slot semantics, rejection outcomes, protocol-component priority, insufficient-result semantics, registry, ledger, or tool algorithms; production provider/model/credentials; live calls; provider extras; token/cost/request-timeout policy; Prometheus transport; domain orchestration in PydanticAI; or reference/History data in agent context.

**Focused verification:** adapter translation exactly preserves the already-owned good/degraded and identity/window/quality-only insufficient requests with no scope selector/raw series/reference/History leak; exact descriptor literals/order regression; adapter zero and all-three call regression; every actual model request counts; duplicate/unregistered/parallel/fourth cases exercise the VS-07R policy and cannot bypass its ledger or execute forbidden work; zero tool/output validation retries and no retry hook; four-model-request/no-fifth ceiling; invalid tool/completion, request exhaustion, timeout, and model failure translation without corrective requests; prior successful tool result preservation; later adapter/model or policy rejection selects `metrics_agent` over earlier tool failure; adapter-specific insufficient failure regression; actual partial reason persistence; PydanticAI imports only in infrastructure.

**Context pack:** VS-01/VS-02/VS-07/VS-07R accepted handoffs; complete approved agent requirement; design decisions 5–7, 10, and 12; ADR-045–049, ADR-152, ADR-155–156; dependency policy and recorded existing approval; accepted framework-neutral policy/contracts and backend dependency files; installed official PydanticAI 2.x APIs needed for implementation. Do not read or reuse commit `d4d8e48` or its handoff as implementation reference.

**Handoff expectations:** record the verified pre-existing approval and resolved dependency version, adapter injection API, proof that all applicable calls use the VS-07R policy, budget/retry configuration, tested model doubles, exact adapter/model failure translations, persisted integration evidence, adapter regressions versus primary behavior owners, independence from `d4d8e48`, remaining implementation-private prompt choice, and candidate shared knowledge.

**Risk:** high-risk

**Completion gate:** the Coordinator's record confirms existing dependency approval before dependency edits; the unaccepted `d4d8e48` changes were first reverted and not reused; deterministic adapter and focused pipeline/persistence tests pass without network; no provider extra/default exists; every framework-specific request-budget/retry and adapter/model contribution is complete while VS-07R retains framework-neutral policy/rejection ownership; import-boundary and established transaction-order scans pass; Ruff passes; independent high-risk review has no unresolved blocker/high finding; one fresh atomic commit and handoff exist.

### VS-09 — Cross-cause conformance, documentation, and full verification

**Behavioral goal:** Verify that independently completed current, reference, History, optional-tool, adapter, and persistence behaviors interact according to the approved primary-reason/correlation rules; document stable injection boundaries; and run the complete change conformance/regression suite. This slice is conformance-only and owns no primary production behavior.

**OpenSpec coverage:** only genuinely cross-cause scenarios—reference + History + optional precedence, reference over optional, and History over optional—plus whole-change boundary/conformance verification; tasks 11.1, final full-suite portion of 11.2, 11.3, and cross-cause verification (not implementation ownership) for 8.2 and 9.2.

**Dependencies:** VS-04, VS-06, and VS-08.

**Vertical boundary:** already implemented typed stage contributions -> cross-cause pipeline executions -> strict one-reason result and matching persisted LensRun -> retrieval and diagnostic-exclusion assertions -> documentation/boundary audit -> full repository verification.

**Expected code impact:** cross-cause/regression tests and concise developer-facing documentation outside production modules for provider/model injection, accepted result ownership, and future transport composition. Existing production docstrings may be audited but not edited here. No production behavior/code edit is permitted in this slice. A demonstrated defect returns to its owning slice for a targeted fix and renewed gate; missing primary behavior or a widened contract triggers re-planning.

**Contracts consumed/changed:** consumes all prior contracts without widening them. Verifies fixed public precedence `reference_unavailable > history_analysis_failed > optional_analysis_failed`, exact component selection already implemented by owning slices, LensRun/result reason equality, and exclusion of secondary operational diagnostics.

**Non-goals:** any primary behavior or production fix; new terminal mapping, result field, failure semantic, redesign/refactor, transport/model/provider default, observability infrastructure, schema/migration, frontend, top-level orchestration, archive, push, PR, or merge.

**Focused verification:** reference + History + optional simultaneous incompleteness; reference + optional; History + optional; tool failure followed by agent/protocol failure; multiple failed tools by ordinal regression; duplicate/fourth component regression; non-failure tool outcomes; malformed current versus malformed reference regression; History repository and persistence failure escape; strict all-variant retrieval; pre-transaction/transaction-owned ordering; no secondary diagnostics/result leakage; complete 11/11 requirement, 72/72 scenario, and 37/37 task audit; boundary/import/dependency scan; focused backend suite; strict OpenSpec validation; full `make check`.

**Context pack:** all accepted slice handoffs; complete approved change; design Test Design and decisions 10–12; ADR-035–041, ADR-059, ADR-068, ADR-152, ADR-155–160; all changed modules/tests; `docs/development-workflow.md`; root `Makefile`.

**Handoff expectations:** provide final requirement/scenario/task audit totals, cross-cause evidence, transaction-order regression, documentation changes, all commands/results, unchanged scope/non-goals, remaining approved implementation-private choices, candidate shared knowledge, and readiness for official verification plus independent implementation review—not archive.

**Risk:** high-risk

**Completion gate:** no primary implementation behavior or production fix occurred here; every cross-cause test passes with exact persisted status/reason correlation and diagnostic exclusion; focused tests and `make check` pass; strict OpenSpec validation passes; coverage is confirmed at 11/11 requirements, 72/72 acceptance scenarios, and 37/37 implementation tasks; no prohibited dependency/provider/transport/schema/UI scope appears; independent high-risk review has no unresolved blocker/high finding; one atomic conformance/documentation commit and final handoff exist.

## Coverage matrix

Coverage audit target for this revised draft: **11/11 requirements, 72/72 acceptance scenarios, and 37/37 implementation tasks/sub-parts have an explicit primary owner and verification path.** Adapter and final-conformance regressions are identified as secondary verification and do not transfer primary ownership. Independent plan review must confirm this mapping before renewed human approval.

### Requirement-level ownership

| Exact OpenSpec requirement | Primary owning slice(s) |
|---|---|
| Execute one immutable Metric Lens scope through a deterministic pipeline | VS-01 owns the successful walking skeleton and transaction phase order; VS-02 owns remaining successful quality paths; VS-03 owns current technical-failure paths; VS-09 verifies cross-cause composition only |
| Acquire metric series only through the internal provider boundary | VS-01 owns current/zero-reference acquisition; VS-04 owns configured reference acquisition |
| Prepare samples and calculate mandatory evidence deterministically | VS-01 owns the representative good path; VS-02 owns degraded/insufficient and exhaustive quality/statistics behavior; VS-03 owns malformed current terminal behavior; VS-04 owns reference-role mapping |
| Form mandatory trend and variability using the fixed normalized policy | VS-01 owns representative use; VS-02 owns exhaustive ADR-153 behavior |
| Provide exactly three deterministic optional analytical tools | VS-07 owns the registry, algorithms, registered outcomes, and tool-only partials; VS-07R owns the framework-neutral rejected outcome and request-admission policy |
| Invoke the Metrics Analysis Agent through a bounded framework-neutral contract | VS-01 owns good usable projection and zero-tool fake completion; VS-02 owns degraded/insufficient projection and insufficient resilience; VS-07 owns deterministic registry/registered all-three fake execution; VS-07R owns the application rejection-capable ledger/policy and protocol partials; VS-08 owns PydanticAI translation, framework request ceilings/retries, adapter/model failures, and adapter regressions |
| Compare valid reference periods independently with ordered relations | VS-04 |
| Make missing configured reference analysis partial without placeholders | VS-04 |
| Analyze eligible persisted Metric History in event-time order | VS-05 owns domain behavior; VS-06 owns PostgreSQL selection/infrastructure behavior |
| Build the exact strict MetricAnalysisResult 1.0 contract | VS-01/VS-02/VS-03/VS-04/VS-05/VS-07/VS-07R own only the variants/sections/reasons first used by their behavior; VS-08 verifies adapter/model translation into those contracts; VS-09 verifies cross-cause combinations only |
| Persist terminal Metric outcome atomically through the existing repository | Every behavioral slice persists its own outcome; VS-01 owns initial phase ordering; VS-06 owns real PostgreSQL ordering regression, all-variant round trip, and rollback hardening |

### Requirements and acceptance scenarios

| OpenSpec requirement / acceptance scenarios | Primary owning slice | Verification |
|---|---|---|
| Execute immutable scope: “Execute a successful current-window analysis” | VS-01 | Already-running LensRun traverses fake provider/agent before transaction, then empty History/read-write transaction, caller commit, and retrieval |
| Execute immutable scope: “Reject agentic scope expansion” | VS-07R | Framework-neutral policy accepts only one bound tool name over the existing opaque dataset and rejects scope expansion; VS-08 regresses that the adapter cannot bypass it |
| Acquire through provider boundary: “Acquire zero configured references”; “Test without provider transport” | VS-01 | Fake provider sees only current; no transport/default reference exists |
| Acquire through provider boundary: “Acquire one configured reference”; “Acquire multiple references independently” | VS-04 | Exact per-offset requests/windows/order and isolated outcomes |
| Prepare/calculate mandatory evidence: “Calculate exact statistics” | VS-01 | Representative exact statistics own the scenario; VS-02 expands regression tables without changing ownership |
| Prepare/calculate mandatory evidence: “Degrade after removing non-finite samples”; “Complete insufficient current data” | VS-02 | End-to-end degraded and completed-insufficient fake-agent/persisted paths |
| Prepare/calculate mandatory evidence: “Fail a malformed current series with duplicate timestamps”; “Fail a malformed current series with an out-of-window sample” | VS-03 | End-to-end minimal-failed current cases |
| Mandatory trend/variability: “Classify trend threshold boundaries”; “Classify variability threshold boundaries”; “Semanticize a constant series” | VS-02 | Exact/adjacent boundary and constant-scale tables plus persisted quality paths |
| Exactly three tools: “Detect spike with non-zero MAD”; “Apply all zero-MAD spike outcomes”; “Skip inapplicable spike”; “Classify oscillation outcomes”; “Skip inapplicable oscillation”; “Classify exact stuck-signal outcomes”; “Skip inapplicable stuck signal” | VS-07 | Exhaustive deterministic registry/tool tables plus public projection and persistence tests |
| Bounded agent: “Project good current data into the usable request”; “Complete with zero tool calls” | VS-01 | Captured exact good framework-neutral request and zero-tool fake completion |
| Bounded agent: “Project degraded current data into the same usable request”; “Project insufficient current data into the narrow request”; “Preserve insufficient determination on agent failure” | VS-02 | Exact captured projections and fake-agent insufficient resilience |
| Bounded agent: “Project the deterministic allowed-tool registry”; “Use all three tools once” | VS-07 | Authoritative registry-to-request correlation and all-three fake execution with executed-attempt ledger entries |
| Bounded agent: “Reject a duplicate request”; “Reject a fourth request” | VS-07R | Framework-neutral fake-agent request-policy tests prove exact slot accounting, recorded rejection, forbidden-execution prevention, protocol partial persistence, and earlier-result retention |
| Bounded agent: “Enforce the hard model-request ceiling without validation retries” | VS-08 | Injected-model counters, zero-retry configuration, four-request ceiling, and no-corrective/no-fifth assertions |
| Bounded agent: “Preserve usable core on agent failure”; “Keep PydanticAI outside domain contracts” | VS-08 | Adapter-to-persisted-pipeline failure cases and import-boundary scan |
| Compare references: “Compare ordered reference descriptors”; “Preserve multiple independent comparisons” | VS-04 | Relation tables and paired configured-order output |
| Missing references: “Omit an acquisition-unavailable reference”; “Omit an analytically insufficient reference”; “Omit a reference with duplicate timestamps”; “Omit a reference with an out-of-window sample”; “Preserve successful references when another reference is malformed” | VS-04 | Per-cause end-to-end partial persistence with successful-offset preservation and no placeholders |
| History: “Omit History normally”; “Serialize analytical unknown without partial” | VS-05 | Fake-reader pipeline and strict paired omission/unknown result tests |
| History: “Include overlapping earlier History”; “Order History deterministically” | VS-06 | PostgreSQL event-time/tie/late-persistence selection tests |
| History: “Classify exact near-zero and zero boundaries”; “Classify inclusive relative-change boundaries”; “Classify sustained History patterns”; “Classify reversing History patterns”; “Classify oscillating History patterns”; “Classify a stable-neutral mixed pattern”; “Require two classifiable transitions for a pattern”; “Count public History direction changes from directional runs”; “Preserve oscillating and reversing priority over sustained” | VS-05 | Exact-boundary and every normative-sequence table |
| History: “Degrade on deterministic History failure” | VS-05 | Persisted partial History outcome |
| History: “Propagate History repository failure” | VS-06 | Real reader/transaction failure propagation with no artifact |
| Strict result: “Build completed sufficient result” | VS-01 | Strict builder plus persisted round trip |
| Strict result: “Build completed insufficient result” | VS-02 | Strict forbidden-field test plus persisted round trip |
| Strict result: “Build minimal failed Metric result”; “Map a failed Metric error without leaking diagnostics”; “Preserve provenance when current acquisition never succeeds”; “Preserve identity primitive compatibility”; “Preserve exact Metric window names” | VS-03 | Exact failure mapping/provenance/identity/window contract and persistence tests |
| Strict result: “Select the earliest failed tool attempt”; “Do not make non-failure tool outcomes partial” | VS-07 | Tool-owned ordinal and projection/result tests |
| Strict result: “Prefer the agent component after an earlier tool failure”; “Use the agent component for rejected duplicate and fourth requests” | VS-07R | Framework-neutral protocol-outcome priority and persisted component tests; VS-08 regresses adapter/model translation into the same accepted path |
| Strict result cross-cause: “Apply primary partial-reason precedence”; “Prefer reference component over optional failure”; “Prefer History component over optional failure” | VS-09 | Cross-cause verification over already implemented contributions; no new terminal logic |
| Persist terminal outcome: “Round-trip all Metric result variants”; “Roll back persistence failure” | VS-06 | PostgreSQL all-variant retrieval, phase-order regression, and forced flush/commit rollback |
| Persist terminal outcome: “Avoid transport, model, and framework coupling” | VS-09 | Whole-change import/dependency/scope audit; ownership enforced in VS-01, VS-07R, and VS-08 |

### Implementation task ownership

| OpenSpec task | Explicit owning slice/sub-part | Verification |
|---|---|---|
| 1.1 | VS-01 | Frozen execution context, primitive compatibility, order/uniqueness, strict UTC/window tests |
| 1.2 | VS-01 available/current-good/usable-agent/empty-History outcomes; VS-02 degraded/insufficient outcomes; VS-03 current-failure outcomes; VS-04 reference outcomes; VS-05 History candidate/stage outcomes; VS-07 registered-tool/executed-attempt outcomes; VS-07R rejected-attempt/policy/protocol outcomes; VS-08 adapter/model outcomes | Each contract is introduced with its first real behavioral path; task closes after VS-08 boundary audit |
| 1.3 | VS-01 provider/agent/minimal empty-History protocols; VS-05 History candidate expansion | Fake boundary/scope tests; no unused non-empty History structure in VS-01 |
| 1.4 | VS-01 completed-sufficient/common models actually used; VS-02 completed-insufficient; VS-03 failed/error; VS-04 first partial/reference sections; VS-05 History sections; VS-07 optional sections; VS-07R agent/protocol reason contribution | Per-variant/section strict tests; VS-08 only verifies framework translation and boundary isolation; task closes after VS-08 |
| 2.1 | VS-01 representative good preparation; VS-02 degraded/insufficient/non-finite behavior; VS-03 duplicate/out-of-window malformed behavior; VS-04 reference-role mapping | Pure role-neutral tables plus owning persisted paths |
| 2.2 | VS-01 representative exact evidence; VS-02 exhaustive irregular/constant/finite statistics | Exact formula tables and persisted current paths |
| 2.3 | VS-01 representative good classification; VS-02 exhaustive good/degraded/insufficient boundaries | Quality tables and degraded/insufficient persisted paths |
| 3.1, 3.2 | VS-01 representative semantic use; VS-02 exhaustive ADR-153 algorithm/boundary ownership | Exact threshold/constant/signed/near-zero tables |
| 4.1 | VS-07 registry and registered success/not-applicable/failure/timeout outcomes; VS-07R rejected outcome and request-admission policy | Exact registry/binding tests plus framework-neutral rejected-attempt and forbidden-execution tests |
| 4.2, 4.3, 4.4 | VS-07 | Complete Spike, Oscillation, and Stuck Signal algorithm/boundary tables |
| 4.5 | VS-07 successful/not-applicable/failed/timeout property/evidence matrix; VS-07R rejected-request omission and incompleteness path | Focused projection/result tests for every outcome, including persisted rejection partials |
| 5.1, 5.2, 5.3, 5.4 | VS-04 | Window/comparator/correlation/per-cause partial tests |
| 6.1 | VS-05 | Complete pure History algorithm tables |
| 6.2 | VS-05 typed candidate validation/order/lookback; VS-06 PostgreSQL query proof | Pure/fake selection then real database selection |
| 6.3 | VS-05 analytical/port outcomes; VS-06 repository/session implementation failure | Persisted deterministic failure and real infrastructure propagation |
| 7.1 | VS-08 after Coordinator records the already-given approval | Dependency/lock audit with no provider extra/default |
| 7.2 | VS-08 translation over projections owned by VS-01/VS-02, registry owned by VS-07, and policy owned by VS-07R | Adapter translation tests; no domain type widening |
| 7.3 | VS-07 owns registered all-tools execution; VS-07R owns the application rejection-capable ledger/policy for all outcome classes and slot/each-tool/parallel enforcement; VS-08 owns zero framework retries, no retry hook, hard model-request ceiling, and adapter routing through the policy | Fake policy/ledger/persistence tests precede injected-model request counters and adapter regressions |
| 7.4 | VS-02 owns framework-neutral insufficient resilience; VS-07R owns usable protocol-rejection mapping and earlier valid-result retention; VS-08 owns adapter/model failures and adapter-specific insufficient translation regression | Persisted fake-agent protocol cases plus adapter/model failure cases |
| 7.5 | VS-01 owns zero-tool fake behavior; VS-02 owns projection/insufficient fake behavior; VS-07 owns registry/all-three fake behavior; VS-07R owns fake duplicate/unregistered/parallel/fourth behavior; VS-08 owns deterministic PydanticAI regressions and framework-specific budget/retry cases | Primary framework-neutral behavior tests precede adapter regression; task closes after VS-08 |
| 8.1 | VS-01 completed-sufficient; VS-02 completed-insufficient/degraded; VS-03 failed; VS-04 reference partial; VS-05 History; VS-07 optional tool; VS-07R agent/protocol contribution | Builder grows only with first real use by each named owner; VS-08 consumes it unchanged |
| 8.2 | Same per-behavior owners as 8.1; VS-09 cross-cause-only regression | Exhaustive local builder tests plus final interaction verification |
| 9.1 | VS-01 completed-sufficient walking skeleton; VS-02 degraded/insufficient paths; VS-03 current-failed paths | Every current path executes through an already-running LensRun and real persistence |
| 9.2 | VS-04 reference contribution; VS-05 History contribution; VS-07 tool contribution/component; VS-07R agent/protocol contribution/component; VS-08 adapter/model translation regression; VS-09 cross-cause-only verification | Every terminal contribution is implemented with its primary behavior; adapter and final slices only regress/compose causes |
| 9.3 | VS-03 current failure roles; VS-04 reference role; VS-05 History port distinction; VS-06 real History repository/transaction infrastructure failure | Focused role-specific and real-infrastructure tests |
| 10.1 | VS-06 | Bounded PostgreSQL History query/filter/order/lookback integration tests |
| 10.2 | VS-01 completed-sufficient/order; VS-02 degraded/insufficient; VS-03 failed; VS-04 reference partial; VS-05 History partial; VS-07 tool partial; VS-07R protocol partial; VS-08 adapter/model partial regression; VS-06 all-variant/transaction-order/atomic hardening | Each primary behavior persists in its owning slice; VS-06 proves repository-wide ordering/invariants |
| 10.3 | VS-06 | Forced flush/commit failure and rollback tests |
| 11.1 | VS-09 | Concise provider/model/result/future-transport boundary documentation audit |
| 11.2 | Every slice for its focused tests; VS-09 for complete backend/change suite | Commands/results recorded per handoff and final conformance run |
| 11.3 | VS-09 | Strict OpenSpec validation and `make check` |

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements or redesign decisions here.

- Slice order defaults to VS-01 through VS-07, then VS-07R, VS-08, and VS-09 even where the graph permits independent work.
- VS-01 is the genuine persisted walking skeleton. Its test must enter through an already-running Metric LensRun, finish current acquisition/preparation/statistics/semantics and zero-tool fake-agent execution before opening the database transaction, then perform the successful empty History read, strict build, real terminal transition, artifact insertion/flush, and caller commit in that transaction.
- VS-06 must regress the same phase ordering with real PostgreSQL and own caller rollback verification: applicable provider/current/agent work is pre-transaction; applicable History loading, terminal transition, artifact insertion/flush, and caller commit/rollback are transaction-owned.
- No implementation resumes from this draft. First run an independent slice-plan review, resolve any accepted findings in the plan, and obtain explicit renewed human approval.
- After renewed approval and before dispatching VS-07R, the Coordinator must create a non-destructive revert of only commit `d4d8e48`, verify that its dependency, adapter, pipeline, tests, lockfile, and handoff changes are absent, and preserve all accepted slice commits plus the stop/replanning history. Do not rewrite branch history.
- Commit `d4d8e48` and `implementation/VS-08-handoff.md` are rejected execution evidence: they do not satisfy any task, coverage row, slice gate, or prerequisite, and no implementer may read, copy, cherry-pick, or otherwise reuse them as an implementation reference.
- After the revert, dispatch VS-07R to a fresh implementer and require its independent high-risk review and Coordinator acceptance before unblocking VS-08.
- Re-execute VS-08 from a fresh context and the accepted VS-07R handoff. Before dispatch, the Coordinator verifies and records the existing `pydantic-ai-slim>=2,<3` without-provider-extras approval. This is metadata verification, not a new approval request or decision.
- All slices are high-risk because each either introduces strict lifecycle/failure/persistence behavior or verifies the major integrated contract. Each requires independent slice review after implementer self-review and before acceptance/unblocking dependents.
- Each Slice Implementer works from a fresh context, reads its context pack plus predecessor handoffs, runs focused verification, self-reviews, creates one atomic commit, and writes a compact handoff using `openspec/templates/slice-handoff-template.md`.
- The Coordinator alone updates `Status`, `Commit`, and `Handoff` execution fields after accepting a slice. Planned goals, dependencies, boundaries, ownership, coverage, risks, and completion gates are frozen after renewed human approval.
- OpenSpec task checkboxes with split ownership remain unchecked until every listed sub-part has passed its owning slice gate. A later slice may integrate or regress an earlier behavior but may not become its implementation owner silently.
- If implementation exposes a source conflict, new behavior, missing architecture decision, unverifiable dependency-approval source, required migration/index, or other structural change, stop the affected slice and request re-planning/source reconciliation. Do not reinterpret an Open/Deferred item as permission.
- Shared-knowledge observations remain candidates in handoffs/`.agents/knowledge/candidates.md` until the Coordinator validates them against authoritative evidence. They are not requirements.
- VS-09 is conformance-only. Any production defect returns to the primary owning slice; missing behavior or contract change triggers re-planning.
- Coordinator stop record (2026-08-29): user directed execution to stop after VS-06. Superseded by the subsequent direction to execute VS-07 only.
- Coordinator pause record (2026-08-29): user directed execution to pause after VS-07 acceptance pending further confirmation. VS-08 and VS-09 remain unstarted.
- Coordinator execution record (2026-08-29): the approved plan's Human approval record for `pydantic-ai-slim>=2,<3` without provider extras was verified before VS-08 dependency work. By explicit user direction, the Coordinator is the VS-08 implementer; retain a fresh independent high-risk reviewer and pause after acceptance. This supersedes the prior pause record for VS-08 only.
- Coordinator stop record (2026-08-29): VS-08 is blocked by a source/plan conflict identified by independent review. The frozen VS-07 `MetricToolAttempt` contract permits only executed registered-tool attempts, but the approved VS-08 protocol requires recorded rejected duplicate, unregistered, parallel, and fourth requests. Reconciliation requires implementation-plan revision, independent slice-plan review, and human re-approval before implementation resumes. Commit `d4d8e48` is unaccepted and must not be treated as completion.
- Plan-revision disposition (2026-08-29): VS-01 through VS-07 acceptance records remain unchanged. VS-07R now owns the missing framework-neutral rejection ledger/policy and protocol-persistence prerequisite. VS-08 remains blocked until independent plan review, renewed human approval, a recorded revert of `d4d8e48`, and accepted VS-07R completion; it must then be re-executed by a fresh implementer without using the rejected commit or handoff. After those prerequisites are recorded, the Coordinator may reset the VS-08 execution row to `PLANNED` with empty commit/handoff fields before dispatch.
- Coordinator stop record (2026-08-30): execution could not begin after renewed approval because the required non-destructive `git revert d4d8e48` could not create `.git/index.lock` under the active filesystem policy. This session forbids escalation requests. No revert, code change, or VS-07R dispatch occurred; resume after Git write permission is available.
- Completion of VS-09 means ready for official change verification and independent implementation review. It does not authorize archive, push, PR creation, merge, or direct work on `main`.
