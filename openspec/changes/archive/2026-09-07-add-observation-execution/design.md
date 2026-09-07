## Context

See `proposal.md` for motivation. The backend currently has independently implemented capabilities for Observation Definition persistence/loading, forward-only runtime persistence, Metric and Alert analysis, deterministic Relationship Evaluation, bounded Observation Reasoning, and presentation-only report generation. Each analytical capability deliberately excludes top-level lifecycle and persistence coordination, so the missing piece is an application-level control plane.

The existing pipeline shapes constrain the design:

- Metric analysis performs provider/agent work before a caller-owned transaction, then reads History and atomically persists its terminal LensRun plus Metric artifact.
- Alert analysis returns a pre-transaction terminal outcome; the existing persistence helper atomically advances the LensRun and inserts an artifact only for a usable outcome.
- Relationship Evaluation, Observation Reasoning, and Report Generation are side-effect-free and expose strict in-memory outputs.
- `RuntimePersistenceRepository` flushes but never commits, making transaction ownership an orchestration concern.
- concurrent Lens work cannot share one SQLAlchemy `AsyncSession`.
- no public trigger, scheduler, Log definition/pipeline, or production knowledge retriever is part of this change.

The specifications for this change are `specs/observation-execution/spec.md` and `specs/runtime-persistence/spec.md`.

## Goals / Non-Goals

**Goals:**

- Add one small deterministic application service that owns the top-level stage graph and ObservationRun lifecycle.
- Reuse existing contracts/builders/executors without copying Metric, Alert, Relationship, reasoning, or reporting semantics into the orchestrator.
- Keep concurrent work bounded, ordered at admission/collection boundaries, independently transactional, and testable with deterministic fakes.
- Make every committed artifact and terminal status correlation-safe and preserve completed work across degradation, later-stage failure, and cancellation.
- Extend the existing runtime lifecycle with `cancelled` without changing the database schema.

**Non-Goals:**

- Add a FastAPI execution endpoint or expose an execution request/response publicly.
- Select trigger, scheduling, overlap, automatic retry, idempotency, replay, artifact reuse, process-crash recovery, or retention behavior.
- Add Logs, ad-hoc natural-language resolution, UI, notification, or new provider/agent functionality.
- Add dependencies, database migrations, a workflow framework, broker, queue service, distributed worker, or generalized plugin registry.

## Decisions

### 1. Put the control plane in a narrow `app.execution` application package

Add a small package containing strict framework-neutral execution values, snapshot/input projection, type-specific Lens adapters, and the top-level orchestrator. Definition ORM loading and runtime writes remain in the existing persistence layer; domain analytics remain in their existing packages. The orchestrator depends on narrow protocols/callables and an async session factory so unit tests can inject fakes without PostgreSQL or model/provider calls.

The package will expose a concise public orchestrator class and public request/policy/outcome values, each documented under repository rules. Its internal entry point returns a closed framework-neutral `ObservationExecutionOutcome` with required `kind` `completed`, `failed`, or `rejected`: `completed` carries the run ID and `completed` status with no reason; `failed` carries the run ID, `failed` status, and exact persisted structured parent reason; and pre-initialization `rejected` carries no run ID or runtime status and only `invalid_execution_request`, `observation_not_found`, `invalid_observation_definition`, `empty_lens_topology`, or `unsupported_lens_type` with component `execution_preparation`. Cancellation and persistence/infrastructure failures remain propagated control flow rather than outcome variants. Helper implementation details remain private. It will not be registered on FastAPI application state because no supported trigger consumes it yet; tests and a future trigger may compose it explicitly.

Alternative considered: place execution inside `app.observations.service`. Rejected because that service currently owns definition API behavior and would blur definition aggregate operations with runtime control-plane lifecycle.

Alternative considered: introduce generic workflow/stage abstractions. Rejected because the stage graph is fixed and one direct service is smaller and clearer for the MVP.

### 2. Validate a minimal execution request and detach one immutable definition snapshot

The execution request contains only `observation_id` and an exact UTC analysis window. A separate strict execution-policy value supplies positive `max_parallel_lens_runs` and per-Lens deadline seconds; these are injected by the caller rather than added to the persisted definition, API, or global settings in this change. This realizes the accepted behavior without choosing the still-open configuration location or defaults.

Preparation loads the existing aggregate with all owned Metric Lenses, Alert Lenses, and Relationships in one repository call and immediately projects it into immutable application values. The snapshot includes only fields required later and preserves Relationship order. Lens execution order is separately canonicalized to `(metric, lens_id)` then `(alert, lens_id)`, so definition collection order retains its accepted presentation-only meaning.

Alternative considered: re-query each Lens and Relationship before its stage. Rejected because it permits one run to observe multiple definition versions and increases transaction/I/O complexity.

Alternative considered: persist a copied definition payload in runtime JSON. Rejected because accepted runtime persistence forbids duplicating definition aggregates and there is currently no definition update API requiring a durable historical snapshot schema.

### 3. Initialize the full runtime graph in one transaction

Preparation opens one short transaction to load/validate the definition, create a pending ObservationRun, create every pending type-aware LensRun, and advance the parent to running. Nothing analytical begins until commit. Generated identities are application-owned UUIDs included in the detached snapshot-to-runtime mapping.

Keeping load and initialization together gives a coherent database snapshot today and leaves no partial runtime topology after integrity failure. The transaction contains no provider, agent, or other slow work.

Alternative considered: create LensRuns lazily as slots open. Rejected because strict JOIN and cancellation need a complete durable child set, and lazy creation could make omitted work indistinguishable from pending work.

### 4. Use a fixed-size in-process worker loop for work-conserving bounded fan-out

Build the canonical ordered Lens assignment list, then start `min(limit, lens_count)` asyncio workers. Each worker obtains the next unassigned item synchronously within the event loop, opens its own short session to transition that LensRun to running, executes only the adapter's pre-terminalization provider, agent, and deterministic analytical work under the supplied deadline, then opens the adapter-required terminal transaction. Metric History loading and any History analysis performed in that transaction are outside the deadline. When the terminal work finishes, the worker immediately obtains the next assignment. This is work-conserving and avoids relying on undocumented semaphore waiter fairness.

Queue delay and the durable pending-to-running admission write are outside the per-Lens deadline; timing begins immediately before the pre-terminalization analytical invocation and ends before Metric History or any terminal transaction begins. Every terminal transaction operation, including acquisition, History repository read, validation, artifact insertion, flush, commit, and rollback, remains deadline-exempt. Each worker/session is isolated because SQLAlchemy `AsyncSession` is not concurrency-safe. Returned outcomes are stored by canonical index, never by completion order.

The worker catches expiry and other non-cancellation, non-persistence exceptions from the deadline-covered analytical segment and delegates type-correct failed-outcome construction to the assigned Metric or Alert adapter. A Metric History repository failure and every terminal persistence exception escape, because retrying or normalizing an uncertain database boundary could create contradictory claims. Cancellation is never normalized inside a worker.

Alternative considered: `asyncio.gather` over one task per Lens guarded by a semaphore. Rejected because it creates an unbounded task set and makes deterministic admission/fairness less explicit.

Alternative considered: batch execution of `limit` Lenses at a time. Rejected because it is not work-conserving and conflicts with the architecture direction to fill a free slot immediately.

### 5. Keep type-specific outcome normalization behind two explicit adapters

`MetricLensExecutionAdapter` projects the frozen Metric definition/runtime identity into the existing `MetricLensExecutionContext`, runs the pipeline's pre-terminalization analytical work under the deadline, then performs the accepted History/read-and-write terminal transaction outside it. `AlertLensExecutionAdapter` resolves the injected Alert provider for the frozen source/scope, constructs `AlertLensExecutionContext`, invokes its pre-terminalization analysis under the deadline, and uses `persist_alert_terminal` inside a deadline-exempt terminal transaction.

Both adapters validate assigned identities before persistence. They also own construction of contract-compliant failure outcomes for wrapper deadline, unexpected execution error, and identity mismatch. This keeps the generic orchestrator unaware of the failed Metric artifact schema while preserving the existing distinction that failed Alert runs have no artifact. Safe structured reasons contain controlled codes/components only.

For Metric wrapper failures `timeout`, `analysis_failed`, and `identity_mismatch`, the Metric adapter keeps that exact code/component on the LensRun but calls the existing Metric-owned builder with the assigned immutable Metric context and its generic mandatory-analysis failure input. The resulting minimal artifact is the existing failed Metric 1.0 variant with `mandatory_metric_analysis_failed` and its fixed message, assigned identity/window, and builder-owned Prometheus provenance/generation time. The adapter never derives that artifact from a caught exception or a rejected producer artifact. This is an adapter composition rule, not a change to the canonical Metric public contract.

The adapter protocol returns a compact collected outcome containing the terminal status, optional validated persistence envelope, and identity; it does not expose raw telemetry or provider diagnostics to the orchestrator.

Alternative considered: make the orchestrator build failed Metric artifacts. Rejected because that would place Metric contract knowledge in the generic control plane and violate ADR-059.

### 6. Treat durable child terminalization as the strict JOIN signal

The fan-out stage returns only after every worker has either committed a normal `completed|partial|failed` Lens outcome or raised a top-level cancellation/persistence failure. No polling loop or second runtime load is needed for the normal in-process path, but the orchestrator verifies the collected identities/statuses against the initialized topology before advancing.

Usability classification reuses accepted strict result variants, not status alone: sufficient completed/partial Metrics and completed/partial Alerts are usable; completed-insufficient and failed Metrics are unavailable; failed Alerts are unavailable without artifacts. Canonical projection order is retained. A zero-usable set atomically fails the parent with `no_usable_lens_results` and stops.

Alternative considered: continue as soon as one usable result finishes. Rejected by strict JOIN semantics.

### 7. Persist each Observation-level stage at a deliberate commit boundary

Slow or probabilistic work is always outside database transactions. Writes use these boundaries:

| Boundary | Work committed atomically |
|---|---|
| Initialization | definition read snapshot, ObservationRun/LensRun creation, parent running transition |
| Lens admission | one pending LensRun to running |
| Lens terminal | one deadline-exempt terminal transaction: one terminal LensRun plus its eligible type-specific artifact; Metric includes History read and associated History analysis |
| Usable gate failure | parent failed transition |
| Relationships | the complete validated ordered evaluation batch |
| Reasoning success | one validated ObservationAnalysisResult |
| Reasoning/report/orchestration failure | parent failed transition after already committed artifacts |
| Final success | one ObservationReport plus parent completed transition |
| Cancellation | all unfinished LensRuns plus parent cancelled transition |

Relationship Evaluation receives the frozen ordered Relationships and the complete current-run artifact batch accepted by its existing input contract. Its complete output batch is validated, then persisted in one transaction. Reasoning input is constructed from the exact canonical Lens partition and committed relationship batch. A valid analysis is committed before report invocation so a report failure preserves analytical value. The final report insertion and completed transition are one transaction, preventing either a completed run without its report or a new report without completed status.

Alternative considered: one transaction around the entire Observation execution. Rejected because provider/model work can be long-running and concurrent, and holding locks/connections across it would be unsafe.

Alternative considered: commit all Observation-level artifacts only at the end. Rejected because it would discard valid Relationship and analysis artifacts when a later agent fails and would make the required report-failure behavior impossible.

### 8. Map downstream input and failures without weakening existing contracts

The post-JOIN projector builds exactly the current `ObservationReasoningInput`: compact semantic context, strict usable variants, `caller_unavailable` entries preserving producer reasons, the special completed-insufficient Metric projection, and the exact Relationship evaluations. It calls `validate_input` before invoking `ObservationReasoningExecutor`.

Typed reasoning and reporting failure codes/components pass unchanged into the parent structured reason. Relationship exceptions use `relationship_evaluation_failed/relationship_evaluator`; generic post-initialization orchestration exceptions use `execution_failed/<stage>` and unfinished LensRuns use `execution_aborted/<stage>`. Identity or cardinality inconsistencies fail closed before artifact persistence. Exception strings, payloads, prompts, credentials, and tracebacks never enter runtime reasons.

Persistence failure remains categorically different: roll back the failed transaction and propagate an infrastructure exception. The orchestrator must not claim a durable terminal state it could not write, nor recursively attempt arbitrary recovery through the same failing boundary. Process death and recovery of durable non-terminal rows remain outside this change.

Alternative considered: normalize every database failure to a failed ObservationRun. Rejected because the failed-state write itself cannot be guaranteed and could misrepresent durable state.

### 9. Extend lifecycle validators in place; add no migration

Add `CANCELLED` to the existing ObservationRunStatus and LensRunStatus enums and extend transition validation as specified. `pending|running -> cancelled` requires a structured reason; all terminal statuses reject further transition. Usability remains only completed/partial subject to analytical rules. Existing PostgreSQL status columns are unconstrained strings wide enough for `cancelled`, so no Alembic change is needed.

Repository methods remain caller-transaction-owned. Add one bounded operation that locks or conditionally updates the parent and unfinished children for cancellation, preserving terminal rows. For ordinary transitions, use guarded update/current-state validation so concurrent terminal attempts cannot silently overwrite status/reason/artifact truth. Unique artifact constraints remain a second enforcement layer.

Alternative considered: encode cancellation as failed. Rejected by ADR-165 and because it loses the distinction between analytical/operational failure and caller intent.

### 10. Make cancellation a shielded durable cleanup boundary, then re-raise

The orchestrator catches `asyncio.CancelledError` only at its outer execution boundary. It stops worker admission, requests cancellation for active worker tasks, waits only for their cancellation cleanup to settle, then runs cancellation terminalization in a separately created task protected with `asyncio.shield`. Shielding prevents the already-cancelled caller task from immediately interrupting the required database cleanup; the cleanup task must still be awaited to a definite commit/failure outcome and must not be left detached.

Cancellation terminalization reads/locks current child states in one transaction, updates only pending/running LensRuns to `cancelled/execution_cancelled`, and updates the running parent to the same terminal state. Terminal child states and all committed artifacts remain unchanged. Once cleanup commits, the original cancellation is re-raised. If cleanup cannot commit, the persistence failure is chained/raised so the caller can observe that durable cancellation is not guaranteed; no cancelled outcome is falsely returned.

Late cancellation follows the same rule: relationships or analysis already committed remain; the next stage is not started. Cancellation during the final success transaction resolves according to the transaction's actual commit result under guarded lifecycle validation, so the run cannot become both completed and cancelled.

Alternative considered: let cancellation propagate immediately. Rejected because it can leave a known cancelled operation durably running forever while ADR-164 prohibits resuming it.

Alternative considered: rewrite every child as cancelled. Rejected because it destroys already committed analytical truth and contradicts ADR-165.

### 11. Re-run only by invoking the full preparation path again

No resume method or stage entry point is exposed. Every explicit later execution request starts at definition loading and generates a fresh identity graph. Existing records are read-only except through their one forward execution lifecycle. Automatic retry and overlap acceptance are not implemented; a future trigger owns those decisions.

Alternative considered: resume from the latest persisted stage. Rejected because checkpoint validity, definition/version compatibility, artifact reuse, and idempotency are unresolved and the accepted lifecycle has no backward transition.

### 12. Verify deterministic composition at three levels

Framework-neutral unit tests cover request/policy validation, snapshot projection, canonical ordering, usability partitioning, reasoning/report input construction, failure mapping, and lifecycle guards. Orchestrator tests use controllable async fakes to prove the concurrency ceiling, work-conserving admission, the pre-terminalization-only timeout boundary, deadline-exempt Metric History/terminal persistence failure propagation, strict JOIN, completion-order independence, cancellation timing, and no downstream invocation after stop conditions.

PostgreSQL integration tests use the real repositories and existing schema to prove initialization rollback, per-Lens atomicity, complete relationship-batch rollback, analysis-before-report preservation, report-plus-completion atomicity, guarded duplicate terminalization, cancellation preservation, and retrieval of mixed/cancelled aggregates. Existing pipeline, evaluator, reasoning, and reporting suites remain the contract regression layer. No live provider or model call is required.

## Risks / Trade-offs

- [Process death can leave non-terminal durable rows] → Process-crash recovery is explicitly unresolved; this change handles observable in-process exceptions and caller cancellation only and never pretends such rows are resumable.
- [A cancellation-resistant child may delay cleanup] → Existing provider/model boundaries are cancellation-aware; the orchestrator cancels and settles owned tasks before one bounded database cleanup, with focused tests preventing detached task leakage.
- [Deterministic admission does not imply deterministic wall-clock completion] → Results are indexed and projected in canonical order; only physical completion timing may differ.
- [Multiple short transactions expose intermediate durable state] → Each boundary is internally atomic, retrieval is truthful, and only the orchestrator advances the parent; this is preferable to holding one transaction over external work.
- [A database failure can prevent promised terminalization] → Roll back and surface infrastructure failure explicitly; do not fabricate a terminal status or add unapproved retry behavior.
- [Adding an enum value can affect older application binaries] → Deploy the lifecycle reader/writer changes before any execution can persist `cancelled`; rollback is safe only when no cancelled rows exist, otherwise use a forward fix or an explicitly approved data-compatibility plan.
- [Canonical type/ID ordering may differ from UI order] → The definition contract already says collection order has no execution meaning; tests pin the independent canonical order.

## Migration Plan

1. Deploy the runtime enum/transition/repository changes and tests; no Alembic migration or dependency update is required.
2. Deploy the internal execution package and its composition tests. No HTTP route or automatic trigger activates it.
3. A later separately approved trigger may instantiate and call the orchestrator with explicit policy values and required injected provider/agent/retriever dependencies.
4. Roll back application code only before any `cancelled` row is written. If such rows exist, prefer a forward compatibility fix; any destructive data rewrite requires separate explicit approval.

## Open Questions

None within this change. Trigger type, trigger overlap, automatic retry initiation, configuration location/defaults, idempotency, replay/artifact reuse, process-crash recovery, observability, and retention remain intentionally outside scope and require later architecture decisions.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — the design instantiates definitions into separate runs, preserves type-aware Lens identity, and keeps configured collection order out of execution semantics.
- `docs/architecture/02_architecture_principles_and_runtime.md` — the orchestrator implements the accepted deterministic stage graph, bounded work-conserving fan-out, strict JOIN, usable gate, degradation, reasoning, reporting, and persistence sequence.
- `docs/architecture/03_ADR_log.md` — ADR-043..ADR-068 define orchestration and reasoning boundaries; ADR-085..ADR-088 define reporting and Metric-only Relationships; ADR-152 keeps PydanticAI behind ports; ADR-161..ADR-163 define mixed Definition ownership; ADR-164 and ADR-165 define fresh-run and cancellation semantics.
- `docs/architecture/04_pipeline_and_agent_concepts.md` — type-specific adapters preserve component responsibilities and keep domain reasoning out of the control plane.
- `docs/architecture/05_relationship_evaluator_concept.md` — the complete artifact collection and ordered definitions are passed to the evaluator without participant projection.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — status, usability, strict JOIN, reasoning/report inputs, failure propagation, and persistence ownership remain the contract basis.
- `docs/architecture/07_observation_reasoning_agent.md` and `08_observation_analysis_result_contract.md` — the design constructs the accepted reasoning boundary and persists its strict result without widening it.
- `docs/architecture/09_report_agent.md` — reporting stays presentation-only and is invoked only from a committed analysis result.
- `docs/architecture/10_open_decisions_and_backlog.md` — the design avoids choosing unresolved trigger, overlap, configuration-default, automatic retry, idempotency, replay, infrastructure, and retention policy.
