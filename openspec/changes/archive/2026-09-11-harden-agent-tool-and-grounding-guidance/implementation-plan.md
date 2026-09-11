# Implementation Plan — harden-agent-tool-and-grounding-guidance

**Status:** HUMAN_APPROVED — READY FOR EXECUTION
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `harden-agent-tool-and-grounding-guidance`
**Candidate branch:** `feature/harden-agent-tool-and-grounding-guidance`

## Authority and execution anchor

This plan describes execution only. The approved `proposal.md`, `design.md`, `tasks.md`,
and `specs/production-agent-composition/spec.md`; accepted architecture/contracts; and
root `AGENTS.md` remain authoritative. `.agents/PROJECT_KNOWLEDGE.md` was read as
advisory knowledge and has no entries.

The sole execution anchor is the approved planning baseline
`11e037f5548d80fc355e30d0cfa1822ddb225500` on this feature branch. Later sections use
the term *approved planning state* rather than duplicating raw commit identities.

Relevant sources are `docs/architecture/02_architecture_principles_and_runtime.md`
(sections 3 and 8), `04_pipeline_and_agent_concepts.md` (sections 4, 5, and 8),
`06_runtime_contracts_and_execution_semantics.md` (section 8),
`07_observation_reasoning_agent.md` (sections 2.5–7), and ADR-152, ADR-169, and ADR-171
in `03_ADR_log.md`.

The PydanticAI adapters remain infrastructure behind framework-neutral ports. This change
must preserve domain-owned sequential admission, budgets, grounding validation, failure
and partial-result mapping, plus the empty production `KnowledgeRetriever`. It authorizes
no dependency, API, persistence, model-default, timeout, token-limit, retry, or
architecture-document change.

## Preconditions and slice graph

Planning inspection found a clean candidate branch at the approved planning state. Before
dispatch, the Coordinator rechecks it and preserves any later unrelated worktree change.
`parallel_tool_calls` is available in the already approved PydanticAI 2.x range
(`pydantic-ai-slim[openrouter]>=2,<3`; currently locked at 2.36.0); no range changes.

```text
VS-01 Agent interaction steering and deterministic-boundary regression [high-risk]
  -> FINAL Whole-change conformance and independent implementation review [normal]
```

Execution is sequential. One slice is minimum sufficient: both role-owned prompts,
request-local provider steering, regression safety, private trace evidence, and the
manual procedure comprise one agent/tool boundary. A split would defer critical
integration proof.

| Slice | Increment | Depends on | Risk | Status | Commit | Handoff/review |
| --- | --- | --- | --- | --- | --- | --- |
| VS-01 | Tool-enabled Metric and hypothesis invocations receive server-owned guidance and non-parallel steering; deterministic policy remains unchanged. | approved planning state | high-risk | COMPLETE | `44c0122` | `implementation/VS-01-handoff.md`; high-risk review PASS |
| FINAL | Verify whole approved change without corrective work. | accepted VS-01 | normal | COMPLETE | coordinator metadata | `implementation/FINAL-handoff.md`; implementation review READY; IR-001 RESOLVED |

## Slice definitions

### VS-01 — Agent interaction steering and deterministic-boundary regression

**Behavioral goal:** Teach the existing Metric optional-analysis and Observation
hypothesis-retrieval protocols to the model and request provider-level sequential tool
behavior, while retaining application validation and outcome semantics as authority.

**OpenSpec coverage:** Both `production-agent-composition` requirements and all their
scenarios. Tasks 1.1–1.3, 2.1–2.3, and 3.1–3.3 are owned here; task 3.4 belongs to FINAL.

**Dependencies:** The approved planning state and current PydanticAI installation. The
manual smoke additionally requires an operator-controlled Home DEV Observation, valid
local OpenRouter/model routing, `APP_ENV=development`, and `AGENT_TRACE_ENABLED=true`;
it is deliberately not a CI dependency.

**Vertical boundary:** immutable serialized Metric/Observation input -> adapter-owned
instructions, tool descriptions, and request-local model settings -> PydanticAI/OpenRouter
function-tool request -> existing admission/grounding policy and typed result mapping ->
fake-model proof and optional correlated development trace.

**Ownership / expected code impact:**

- `backend/src/app/infrastructure/agents/pydantic_ai_metrics.py`: add one private,
  readable Metric instruction constant and a fixed capability-description mapping;
  register the existing `spike`, `oscillation`, and `stuck_signal` tools from that mapping;
  derive tool-enabled settings from existing timeout/token settings with
  `parallel_tool_calls=False`. Every continuation request in a usable tool-enabled run
  receives it. Insufficient Metric runs remain tool-free.
- `backend/src/app/infrastructure/agents/pydantic_ai_reasoning.py`: add one private,
  readable hypothesis instruction constant and `parallel_tool_calls=False` only for
  `form_hypotheses`; leave finding and overall-state settings/tool-free invocations alone.
- `backend/src/app/infrastructure/agents/tracing.py`, only if needed to make focused
  request-setting assertions via private trace metadata: allowlist this boolean setting.
  Do not broaden trace contents or expose traces publicly.
- `backend/tests/test_pydantic_ai_metrics_adapter.py` and
  `backend/tests/test_pydantic_ai_reasoning_adapter.py`: add failing-then-passing
  scripted-model tests for stable semantic clauses, descriptions, and settings; do not
  snapshot incidental prose/whole serialized requests.
- `backend/tests/test_reasoning_executor.py`, `test_production_agent_composition.py`, and
  `test_agent_tracing.py`: alter only focused regressions needed to prove unchanged
  executor/composition/trace behavior and safe metadata.
- `docs/development-guide.md`: add the opt-in Home DEV smoke procedure next to runtime
  diagnostics. It states local setup/restart, supported launch and `observation_run_id`
  correlation, the `tmp/agent-traces/<observation-run-id>/` convention, inspection steps,
  sensitive-data handling, and cleanup. No trace content enters Git.

Exact helper/test-fixture mechanics are implementation choices. Do not edit domain ports,
tool registry schemas/behavior, executors/builders, OpenRouter composition, settings
schemas, public contracts, or architecture docs unless a conflict requires escalation.

**Contracts consumed/changed:** consumes existing Metric request/completion/tool-executor,
Observation finding/hypothesis/retrieval, PydanticAI `ModelSettings`, and private trace
metadata contracts. No public/domain/persistence/provider-routing contract changes. Role
guidance remains fixed at adapter construction and cannot be selected, appended, or
weakened by Observation input, provider payload, retrieved content, or frontend input.

**Required boundary content:**

- Metric guidance covers immutable supplied scope, empty `{}` arguments, one call per
  response, wait-before-next, single use per registered tool, at most three attempts, and
  strict final completion. Descriptions distinguish the three existing deterministic
  capabilities without changing registry, scope, or schemas.
- Hypothesis guidance covers optional retrieval; frozen finding IDs; independent versus
  refinement retrieval; exact direct or preserved-upstream references; untrusted,
  non-evidentiary knowledge; and `hypotheses=[]` with no available reference, including
  after empty, failed, or timed-out retrieval.
- Preserved-upstream-reference coverage in this change is guidance-only: tests assert that
  the hypothesis instruction permits only exact invocation-available upstream references.
  They do not add or claim current functional upstream-reference support. Supplying,
  carrying, validating, or building that provenance through Log/reasoning contracts,
  executor, or builder remains a separate approved Log/reasoning change.
- Non-parallel steering applies to every request, including continuations, in a usable
  Metric tool run and every hypothesis invocation. Insufficient Metric, finding, and
  overall-state calls stay tool-free and do not acquire a setting merely to apply it.
- Ignored steering still reaches existing deterministic rejection: no inadmissible tool
  executes, no filtering/repair/retry appears, and type-specific outcomes remain unchanged.

**Non-goals:** Alert/finding/overall-state/report prompt refinement; prompt versioning;
real knowledge backend; model/default/provider-routing change; evaluation infrastructure;
repair retries; ungrounded-hypothesis filtering; UI/diagnostic expansion; schema,
migration, or dependency work; and a live provider call in tests or `make check`.

**Verification strategy:**

1. Establish the new adapter assertions as failures at the approved planning state, then
   assert required clauses rather than punctuation or complete prompt/request snapshots.
2. Verify usable Metric function tools/descriptions, server-only sequential guidance, and
   `parallel_tool_calls=False` on first and continuation requests. Verify insufficient
   Metric remains tool-free with no optional-analysis behavior/setting.
3. Verify the hypothesis retrieval tool, non-parallel setting, grounding/empty-output/
   untrusted-data guidance, and unchanged tool-free finding/overall phases. Assert only
   prompt-level future compatibility for exact preserved-upstream references; do not add
   functional upstream provenance fixtures or modify contracts, executor, or builder.
   Cover compliant empty completion after unavailable direct knowledge.
4. Re-run scripted parallel Metric/retrieval, duplicate, unregistered, invalid-input,
   over-budget, invented-reference, request-limit, failure/cancellation, and empty/failed/
   timed-out retrieval paths. Confirm rejection and partial/failure mappings do not change.
5. Run focused Metric, reasoning, executor, production-composition, and tracing modules;
   trace coverage must prove no secret or public-API expansion.
6. Compare the procedure to the runtime-observability guide. If optional prerequisites
   exist, perform Home DEV once. A smoke **PASS** requires all of the following: at least
   one admitted Metric optional-tool call, with every Metric model response containing at
   most one such call and empty arguments; frozen findings that cause a hypothesis
   invocation; and the no-knowledge condition under test (no preserved upstream reference
   and no direct retrieval reference available), followed by an empty hypothesis completion
   with no fabricated reference. Record only the run ID, PASS/FAIL/INCONCLUSIVE outcome,
   and which threshold conditions were or were not exercised.

   The smoke is **INCONCLUSIVE**, not PASS, if no Metric tool call occurs, no frozen
   findings/hypothesis invocation occurs, preserved upstream knowledge or a direct
   retrieval reference produces a different knowledge condition, or any other condition
   means either target behavior was not exercised. Record the run ID and the missing or
   different condition, keep task 3.3 unchecked, and require human disposition. A target
   model that emits parallel Metric calls or fabricated knowledge references when the
   no-knowledge condition was exercised is a **FAIL**: retain deterministic policy, do not
   copy trace payload to Git, and report it as a new model/default or evaluation change.

**Context pack:** root `AGENTS.md` sections 2–7, 9–10, 14–15, and 17; complete approved
change; architecture sources listed above; current Metric/reasoning/tracing/OpenRouter
composition files; focused adapter/executor/composition/tracing tests; and development
guide sections 8.3 and 20. A fresh implementer rereads this pack before editing.

**Handoff expectations:** `implementation/VS-01-handoff.md` contains changed paths,
observable behavior, semantic guidance/settings evidence, check results, regression
evidence, excluded scope, atomic commit, and `Shared knowledge candidates: none|...`.
It records manual-smoke run ID, PASS/FAIL/INCONCLUSIVE outcome, and only what was or was
not exercised (or exact missing prerequisites); never secrets or copied trace content.

**Risk:** high-risk because the delta affects provider request semantics and the model/tool
integration boundary. Fresh `ipo-high-risk-slice-reviewer` review is mandatory.

**Completion gate:** owned scenarios and focused checks pass; smoke instructions match
the existing trace guide; `git diff --check` passes; an available manual environment is
run and recorded against the explicit thresholds, otherwise its exact absence is recorded;
an INCONCLUSIVE smoke keeps task 3.3 unchecked pending human disposition; one atomic
commit/handoff exists; and high-risk review has no unresolved finding. Missing optional
credentials never authorizes a fabricated model result or relaxed policy.

### FINAL — Whole-change conformance and independent implementation review

**Behavioral goal:** Verify the complete approved implementation and repository
compatibility without correcting behavior.

**OpenSpec coverage:** all requirements/scenarios cumulatively and task 3.4. Reconcile
tasks 1.1–3.3 from VS-01; leave conditional task 3.3 open when local prerequisites were
unavailable, pending explicit operator/human disposition.

**Dependencies:** accepted VS-01; no active review/correction; clean candidate worktree;
and a runnable local `make check` environment.

**Vertical boundary:** cumulative feature delta -> repository checks and plan-versus-code
evidence -> independent whole-change review -> archive readiness or precise correction/
escalation route.

**Ownership:** Coordinator-owned verification metadata and task reconciliation only.

**Expected code impact:** none.

**Contracts consumed/changed:** verifies all approved sources and changes no contract.

**Non-goals:** implementation, opportunistic cleanup, archive, PR, push, merge, or
accepting unresolved findings.

**Verification strategy:** reconstruct Git/task/handoff state; inspect cumulative scope and
model-setting changes; run `make check`; verify focused-test and smoke-documentation/
handoff evidence; run official OpenSpec verification if installed; then run
`ipo-review-implementation`. Optional verifier absence is recorded, not proof/failure.
`make check` must not make a live provider call.

**Context pack:** complete approved OpenSpec, this plan, accepted VS-01 handoff/review,
cumulative Git history/diff, named architecture/code/tests, root governance, Makefile.

**Handoff expectations:** `implementation/FINAL-handoff.md` records scope/task
reconciliation, exact command results, smoke status/run ID if applicable, review verdict/
findings, and archive readiness or exact correction/escalation route.

**Risk:** normal for non-corrective verification; discovered corrections are classified
separately.

**Completion gate:** `make check` passes; scope/task reconciliation is correct; all reviews
complete; unresolved BLOCKER/HIGH/MEDIUM findings are routed under governance; FINAL
records archive readiness or exact non-terminal stop. The change cannot archive with an
incomplete task absent explicit human disposition.

## Coverage matrix — requirements and scenarios

| Requirement | Scenarios | Owning slice | Verification |
| --- | --- | --- | --- |
| Server-own admitted interaction guidance | Sequential Metric use; empty no-knowledge output; prompt-only future compatibility for preserved upstream references; empty output after unavailable retrieval; server ownership | VS-01 | Scripted semantic/settings tests, executor grounding/retrieval regressions, procedure review, optional trace smoke; no upstream-provenance implementation change |
| Non-parallel provider execution without weaker policy | Non-parallel Metric; non-parallel hypothesis; ignored-steering rejection; tool-free invocations | VS-01 | First/continuation request-setting tests and existing policy/result regressions |
| Complete-change compatibility | All approved scenarios | FINAL | `make check`, scope/task reconciliation, optional verifier, independent review |

## Coverage matrix — tasks

| Task | Owning slice | Completion evidence |
| --- | --- | --- |
| 1.1 | VS-01 | Failing-then-passing Metric guidance/settings/description tests |
| 1.2 | VS-01 | Insufficient Metric tool-free regression |
| 1.3 | VS-01 | Constants/settings and unchanged policy/partial mappings |
| 2.1 | VS-01 | Failing-then-passing hypothesis guidance/settings tests |
| 2.2 | VS-01 | Tool-free and parallel/invented-reference/budget regressions |
| 2.3 | VS-01 | Hypothesis constant/settings, prompt-only upstream-reference compatibility, and unavailable-retrieval empty completion tests |
| 3.1 | VS-01 | Guide procedure matches trace root/correlation controls |
| 3.2 | VS-01 | Focused module results in handoff |
| 3.3 | VS-01 | Run ID plus PASS/FAIL/INCONCLUSIVE threshold record; unavailable or inconclusive conditions keep task unchecked pending human disposition |
| 3.4 | FINAL | Successful `make check` before implementation review |

## Frozen structure and mutable execution state

After independent slice-plan review and explicit human approval, the graph, goals,
coverage, dependencies, boundaries, expected impact, contracts, non-goals, context packs,
risks, verification strategies, and gates are frozen. Changing them requires structural
re-planning, independent plan review, and renewed human approval.

Only the Implementation Coordinator may update mutable execution metadata: plan/slice
status, commit/handoff/review references, exact stop reason, bounded corrections, and task
checkboxes after all owning evidence is accepted. Normal statuses are
`PLANNED -> IN_PROGRESS -> COMPLETE`; `BLOCKED` records an exact stop.

## Execution notes

Mutable Coordinator-owned metadata only; do not add requirements or redesign decisions.

| Item | Current value |
| --- | --- |
| Coordinator status | IMPLEMENTATION COMPLETE — READY FOR ARCHIVE |
| Active assignment | none |
| Approved planning anchor | `11e037f5548d80fc355e30d0cfa1822ddb225500` |
| Last accepted slice | VS-01 (`44c0122`; high-risk review PASS) |
| Bounded correction | IR-001 handoff reconciliation accepted (`0473900`); verification RESOLVED |
| Stop/escalation reason | none |
| Home DEV smoke | PASS — run `b0ddf4df-f220-4955-8b87-36c3f10c8a4e`; both target paths exercised, no trace content recorded |
| Final local verification | PASS — `make check`; 974 backend passed, 84 skipped; 176 frontend passed; strict OpenSpec 21/21 |
