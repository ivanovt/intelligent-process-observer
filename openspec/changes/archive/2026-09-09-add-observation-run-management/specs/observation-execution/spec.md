## MODIFIED Requirements

### Requirement: Accept and freeze one predefined Observation execution scope

The system SHALL accept an internal execution request containing exactly an existing `observation_id` and one finite, forward UTC `analysis_window` with `from < to`. It SHALL load the complete predefined Observation Definition aggregate exactly once before creating runtime records and SHALL freeze an immutable run-scoped snapshot containing the definition identity and schema version, Observation semantic metadata, ordered Metric and Alert Lens definitions, and ordered Relationship definitions.

All downstream execution contexts SHALL be derived from that snapshot and the requested analysis window. The system SHALL NOT re-read definition members during the run, copy the definition into a new definition aggregate, or allow a later definition mutation to change the active run. Provider selectors and other technical configuration SHALL remain available only to the applicable Lens pipeline projection; reasoning and reporting SHALL receive only their already accepted semantic projections. Alert `analysis_timestamp` SHALL remain the analysis-window end required by the accepted Alert pipeline contract.

The framework-neutral internal entry point SHALL return exactly one closed `ObservationExecutionOutcome` variant when it handles the request normally. Its required `kind` discriminator SHALL be `completed`, `failed`, or `rejected`: `completed` contains `observation_run_id` and terminal status `completed` with no reason; `failed` contains `observation_run_id`, terminal status `failed`, and the exact persisted structured ObservationRun reason; and `rejected` contains no ObservationRun identity or runtime status and a preparation reason with component `execution_preparation` and exactly one controlled code: `invalid_execution_request`, `observation_not_found`, `invalid_observation_definition`, `empty_lens_topology`, or `unsupported_lens_type`. `rejected` is a pre-initialization result, not a runtime lifecycle status, and its code SHALL identify respectively malformed request/policy, absent definition, invalid stored aggregate, empty Lens topology, or a Log/other unsupported Lens type. No diagnostic, exception, raw definition, or provider detail SHALL be included in any outcome reason.

A missing Observation, malformed request, empty Lens topology, unsupported Lens type including Log, or invalid stored aggregate SHALL return the corresponding controlled `rejected` outcome before any ObservationRun or LensRun is created. Caller cancellation and persistence/infrastructure failures SHALL not be converted into an `ObservationExecutionOutcome`: cancellation SHALL follow the separate durable-cancellation path and propagate unchanged, and persistence/infrastructure failures SHALL propagate as infrastructure errors.

The internal entry point SHALL remain framework-neutral and non-HTTP. A public launch boundary MAY invoke it through the separately specified Observation Run API, but SHALL NOT expose execution policy, provider configuration, mutable runtime controls, or a second orchestration model.

#### Scenario: Freeze a mixed definition once

- **GIVEN** a valid predefined Observation contains Metric and Alert Lenses and Metric Relationships
- **WHEN** one valid execution request is accepted
- **THEN** the complete aggregate is loaded once and frozen for that execution
- **AND** every later stage derives its permitted input from the same snapshot and analysis window

#### Scenario: Isolate an active run from later definition changes

- **GIVEN** an execution has frozen its definition snapshot
- **WHEN** the persisted definition is changed by a future supported aggregate operation
- **THEN** the active execution continues with its frozen snapshot
- **AND** the runtime storage does not create a duplicate definition aggregate

#### Scenario: Reject before runtime creation

- **GIVEN** the requested definition is absent, invalid, empty, or contains a Log or unsupported Lens type
- **WHEN** execution preparation runs
- **THEN** the entry point returns the corresponding controlled `rejected` preparation outcome with no ObservationRun identity
- **AND** no ObservationRun, LensRun, analytical artifact, or report is persisted

#### Scenario: Adapt execution through one public launch boundary

- **GIVEN** the public Observation Run API accepts a valid launch request
- **WHEN** it invokes Observation execution
- **THEN** the same frozen snapshot, runtime graph, stage order, outcome, and cancellation semantics apply
- **AND** no HTTP concern or client-supplied execution policy enters the framework-neutral execution contracts

### Requirement: Dispatch Lens pipelines in deterministic bounded order

The system SHALL establish the canonical Lens dispatch order by ascending `(lens_type, lens_id)`, using the literal type order `metric`, then `alert`, and lexical Lens ID order within each type. Definition collection order SHALL remain presentation-only and SHALL NOT change dispatch order, result ordering, or reasoning input ordering.

Execution SHALL use a positive caller-supplied `max_parallel_lens_runs` policy and a positive caller-supplied per-Lens deadline. The public on-demand launch boundary SHALL construct that policy from backend-only positive settings with defaults `max_parallel_lens_runs=4` and `lens_deadline_seconds=300`; other internal callers MAY continue supplying their own positive policy. At most the configured number of Lens pipelines SHALL be active simultaneously. Admission SHALL be work-conserving: when a slot becomes free, the earliest not-yet-started Lens in canonical order SHALL start without waiting for a batch. Queue time before admission SHALL NOT consume the admitted Lens execution deadline.

The per-Lens deadline SHALL begin only after the assigned LensRun has durably transitioned to `running` and immediately before its adapter starts pre-terminalization provider, agent, and deterministic analytical work. It SHALL end when that pre-terminalization work returns or raises. It SHALL NOT enclose Metric History repository loading or History analysis performed in the caller-owned terminal transaction, nor any Lens terminal transaction work including transaction acquisition, validation, artifact insertion, flush, commit, or rollback. Those database-bound operations retain the accepted persistence semantics: a repository/transaction failure SHALL propagate as infrastructure failure and SHALL NOT be classified as an analytical `timeout` or converted to a failed Lens outcome.

Immediately before invoking a Lens pipeline, the system SHALL durably transition that LensRun from `pending` to `running`. A failure to persist that transition SHALL prevent the pipeline invocation. Physical completion order MAY vary, but all collected Lens outcomes and downstream Lens projections SHALL be restored to canonical order.

#### Scenario: Enforce the concurrency ceiling

- **GIVEN** more configured Lenses than the positive parallelism limit
- **WHEN** Lens fan-out runs
- **THEN** the number of active Lens pipelines never exceeds the limit
- **AND** every configured Lens is eventually admitted unless the top-level execution is cancelled

#### Scenario: Use public launch defaults

- **GIVEN** no backend execution-policy override is configured
- **WHEN** the public on-demand boundary launches an Observation
- **THEN** it supplies parallelism `4` and a per-Lens deadline of `300` seconds
- **AND** no client request field can alter either value

#### Scenario: Fill a newly available slot

- **GIVEN** the concurrency limit is full and queued Lenses remain
- **WHEN** any active Lens reaches its durable terminal outcome
- **THEN** the earliest queued Lens in canonical order starts without waiting for the other active Lenses

#### Scenario: Keep presentation order out of execution semantics

- **GIVEN** two equivalent definitions list their Metric or Alert Lenses in different presentation order
- **WHEN** each execution is dispatched
- **THEN** both use the same type-and-ID canonical dispatch and downstream ordering

#### Scenario: Start only a durably running Lens

- **GIVEN** a pending LensRun is next for admission
- **WHEN** its transition to running cannot be committed
- **THEN** its pipeline is not invoked
- **AND** the persistence error is not reported as a successful or terminal Lens outcome

### Requirement: Treat every retry, restart, and re-run as a fresh execution

Every explicit retry, restart, or re-run request SHALL follow normal preparation and create a new ObservationRun and new LensRun identities from a newly loaded definition snapshot. An existing pending, running, completed, failed, or cancelled ObservationRun SHALL never be resumed, reopened, reset, or transitioned back to running. Previous runtime records and artifacts SHALL remain immutable and MAY contribute only through already accepted history behavior.

This capability SHALL NOT automatically start another run after failure, cancellation, or process restart; deduplicate requests; define an idempotency key; reuse intermediate artifacts; or replay a stage. A public on-demand launch for an Observation that already has a `pending` or `running` run SHALL be rejected without creating another runtime aggregate. After the prior run is terminal, a later explicit launch SHALL create fresh identities. Startup reconciliation of an orphaned active run SHALL cancel that existing runtime aggregate and SHALL NOT itself create its replacement.

#### Scenario: Re-run a failed Observation

- **GIVEN** a prior ObservationRun is failed
- **WHEN** the same Observation Definition is explicitly executed again
- **THEN** a new ObservationRun and new LensRuns are created
- **AND** the failed run and its artifacts remain unchanged

#### Scenario: Re-run a cancelled Observation

- **GIVEN** a prior ObservationRun is cancelled
- **WHEN** another execution is explicitly requested
- **THEN** the new execution does not resume or reuse the cancelled runtime graph
- **AND** it creates fresh run identities

#### Scenario: Reject overlap without creating a retry

- **GIVEN** an ObservationRun is pending or running
- **WHEN** the same Observation is explicitly launched again
- **THEN** the second request is rejected without a new ObservationRun
- **AND** the active run continues unchanged

#### Scenario: Define no automatic retry

- **GIVEN** an ObservationRun becomes failed or cancelled
- **WHEN** no separate execution request is supplied
- **THEN** this capability creates no replacement run

### Requirement: Keep the MVP execution boundary intentionally small

The deterministic modular-monolith workflow SHALL remain composed with Python asynchronous execution and the existing framework-neutral ports. This change SHALL adapt that workflow through one public on-demand launch/read API, one single-process managed-task host, one active-run persistence invariant, and the Runs UI. It SHALL add no message broker, workflow engine, distributed worker, scheduler, new dependency, notification, Log pipeline, ad-hoc natural-language resolution, cross-type Relationship, recommendation, or autonomous observational scope expansion.

PydanticAI SHALL remain behind the existing Metric, Alert, Observation Reasoning, and Report Generation ports and SHALL NOT enter orchestration or persistence contracts. On-demand trigger policy, same-Observation overlap rejection, public-launch execution defaults, and orphan cancellation after process restart are fixed by this change and ADR-168. Automatic retry, public cancellation, idempotency, replay/artifact reuse, multi-process task ownership, system observability, retention, periodic/event-driven triggering, and scheduling remain unresolved or out of scope and SHALL NOT be silently selected.

#### Scenario: Execute without scope expansion

- **GIVEN** the public run-management capability is implemented
- **WHEN** its production and test dependencies are inspected
- **THEN** it reuses the existing supported Metric/Alert workflow and persistence through the approved API, single-process host, active-run invariant, and UI
- **AND** it introduces none of the remaining excluded infrastructure, trigger, deferred Lens, or analytical behavior

## ADDED Requirements

### Requirement: Separate durable initialization from detached continuation

The system SHALL permit the accepted Observation execution to expose a successful initialization handoff containing the fresh `observation_run_id` only after the complete runtime identity graph has committed and the parent ObservationRun is `running`. The remaining execution stages SHALL continue exactly once under a process-owned task after that handoff. Returning the handoff SHALL NOT represent analytical completion and SHALL NOT alter the final `completed`, `failed`, or `cancelled` outcome semantics.

Before its first persistence operation, every public launch initializer SHALL be registered as manager-owned admission work with the manager's current monotonic recovery generation. Registration and the initial `ready` check SHALL be atomic under the manager state lock. A known preparation rejection or transaction rollback SHALL remove the admission without forcing recovery. Caller cancellation, connection loss, commit failure, or another outcome that cannot prove rollback or commit status SHALL be treated as initialization commit uncertainty and SHALL enter `recovery_required`.

After a successful initialization commit, the initializer SHALL reacquire the manager state lock and compare its captured generation and manager state before registering continuation or releasing an accepted response. Only an unchanged generation in `ready` MAY atomically register the continuation and accepted initialization snapshot. If recovery or shutdown has begun, the initializer SHALL register no continuation, return no `202`, settle its admission, and leave the committed run for cancellation reconciliation.

Public managed execution SHALL support exactly one application process for the MVP. Multi-process or multi-worker task ownership and coordination SHALL remain unsupported and SHALL be documented as a deployment constraint; this change SHALL NOT claim that startup reconciliation can distinguish work owned by another live process.

If preparation is rejected or initialization fails, no background continuation SHALL start. If graceful application shutdown cancels a detached continuation, the existing durable cancellation path SHALL terminalize unfinished runtime records before shutdown reports completion. If that terminalization cannot commit, shutdown SHALL remain incomplete while the process is alive; an external hard stop MAY still terminate it, after which the next startup SHALL remain unready until reconciliation commits. An active record recovered after an ungraceful process interruption SHALL be terminalized as `cancelled` with the existing `execution_cancelled` reason before any new launch is accepted; it SHALL never be resumed.

If initialization commit becomes uncertain, any detached continuation propagates a persistence/infrastructure failure, or cancellation cannot durably terminalize, the single-process manager SHALL enter `recovery_required` atomically, increment its generation, and reject every new launch. It SHALL cancel and await every registered initializer and continuation from the older generation and SHALL wait until their transaction/session scopes are closed before starting reconciliation. It SHALL then retry only idempotent durable cancellation/reconciliation immediately and at five-second intervals. It SHALL NOT retry provider, analytical, reasoning, report, initialization, or other workflow work. The manager SHALL return to `ready` only after all older-generation work has settled, reconciliation commits, and durable retrieval confirms no `pending|running` ObservationRun remains.

#### Scenario: Return only after durable initialization

- **GIVEN** a valid public launch request
- **WHEN** the runtime graph commits and the ObservationRun becomes `running`
- **THEN** the launch boundary can return its stable run identity immediately
- **AND** the process-owned continuation performs the remaining stages exactly once

#### Scenario: Fence an initializer before persistence

- **GIVEN** the manager is ready at recovery generation N
- **WHEN** a public launch begins initialization
- **THEN** its admission is registered with generation N before its first database operation
- **AND** recovery can identify, cancel, and await it

#### Scenario: Recheck generation after initialization commit

- **GIVEN** initialization commits while recovery advances the manager beyond the initializer's captured generation
- **WHEN** the initializer reacquires the state lock
- **THEN** it registers no continuation and returns no accepted response
- **AND** reconciliation owns terminalization of the committed active run

#### Scenario: Continue after unchanged generation

- **GIVEN** initialization commits and the manager remains ready at the captured generation
- **WHEN** the initializer reacquires the state lock
- **THEN** it atomically registers exactly one continuation and accepted initialization snapshot
- **AND** only then settles its admission and permits the `202` response

#### Scenario: Do not detach rejected preparation

- **GIVEN** preparation rejects an invalid or unsupported execution request
- **WHEN** no runtime graph is committed
- **THEN** no continuation task starts
- **AND** the rejection remains a pre-initialization result without a run identity

#### Scenario: Cancel a task during graceful shutdown

- **GIVEN** a detached execution is active when graceful application shutdown begins
- **WHEN** the process cancels and awaits its managed task
- **THEN** unfinished LensRuns and the ObservationRun follow the accepted durable cancellation path
- **AND** already terminal records and committed artifacts remain unchanged

#### Scenario: Fail closed after a detached persistence failure

- **GIVEN** one managed continuation propagates a persistence/infrastructure failure after launch was accepted
- **WHEN** the manager observes the task failure
- **THEN** it stops accepting all new launches and quiesces its remaining managed tasks
- **AND** it retries only durable cancellation/reconciliation every five seconds until no active run remains

#### Scenario: Treat initialization commit uncertainty as recovery-required

- **GIVEN** a registered initializer is cancelled or loses its connection around commit and cannot prove the transaction outcome
- **WHEN** the manager observes that uncertainty
- **THEN** it advances the recovery generation and blocks every launch
- **AND** performs no initialization retry or accepted response

#### Scenario: Wait for older admissions before reconciliation

- **GIVEN** recovery begins while initializers or continuations from the prior generation are active
- **WHEN** the manager quiesces work
- **THEN** reconciliation does not inspect or clear active state until all prior-generation tasks and transaction scopes have settled
- **AND** none of those initializers can later register continuation or return `202`

#### Scenario: Do not complete shutdown without durable cancellation

- **GIVEN** graceful shutdown cannot commit cancellation terminalization
- **WHEN** the process remains alive
- **THEN** shutdown does not report completion and reconciliation retries continue
- **AND** no execution is reported terminal unless that state is durable

#### Scenario: Reconcile an interrupted active record

- **GIVEN** a previous process ended without terminalizing an active ObservationRun
- **WHEN** a new application process starts
- **THEN** that ObservationRun and its unfinished LensRuns become `cancelled` with `execution_cancelled`
- **AND** the interrupted run is not resumed or reported as successful

#### Scenario: Block startup readiness while reconciliation fails

- **GIVEN** orphaned active records exist and the database cannot commit reconciliation
- **WHEN** application startup runs
- **THEN** the public API does not become ready or accept launch traffic
- **AND** a later startup may succeed only after reconciliation can commit

#### Scenario: Keep managed execution single-process

- **WHEN** the public run capability is deployed for the MVP
- **THEN** one application process owns every detached execution task and startup reconciliation
- **AND** multi-process task claiming or ownership coordination is not implied

### Requirement: Prevent overlapping active runs for one Observation

The system SHALL accept at most one active ObservationRun in `pending` or `running` state for a given Observation. The single-process manager SHALL serialize launch admission per Observation, check durable active state, and complete initialization while holding that admission boundary so concurrent public callers cannot both pass the check. Active runs for different Observations SHALL remain independent. Once the prior run is `completed`, `failed`, or `cancelled`, a later request admitted after that terminal state SHALL create a fresh ObservationRun and LensRun identity graph under the existing re-run semantics.

#### Scenario: Reject a concurrent same-Observation launch

- **GIVEN** an Observation already has a pending or running ObservationRun
- **WHEN** another caller reaches the serialized admission check for that Observation
- **THEN** the second request is rejected without creating any runtime record or background task
- **AND** the existing active execution continues unchanged

#### Scenario: Admit after a concurrent predecessor finishes

- **GIVEN** one launch waited for the same-Observation admission boundary
- **WHEN** its predecessor is already terminal before the waiting request performs the durable active check
- **THEN** the waiting request may initialize a fresh run
- **AND** the terminal predecessor remains immutable

#### Scenario: Run different Observations concurrently

- **GIVEN** one Observation has an active run
- **WHEN** another Observation is launched
- **THEN** the second Observation may create and execute its own runtime graph

#### Scenario: Launch after terminal completion

- **GIVEN** an Observation's previous run is completed, failed, or cancelled
- **WHEN** the Observation is launched again
- **THEN** a new ObservationRun and new LensRuns are created
- **AND** the prior runtime aggregate remains immutable

### Requirement: Supply bounded server-owned public execution policy

Publicly launched Observation execution SHALL use server-owned positive settings with defaults `max_parallel_lens_runs=4` and `lens_deadline_seconds=300`. Clients SHALL NOT view or override these values through the launch request. These bounds SHALL retain the accepted work-conserving dispatch and per-Lens deadline semantics and SHALL NOT alter the independent model-request, tool-call, provider, transaction, or cancellation boundaries.

#### Scenario: Use default public execution bounds

- **GIVEN** no execution-policy environment override is configured
- **WHEN** an Observation is launched through the public API
- **THEN** at most four Lens pipelines are active concurrently
- **AND** each admitted Lens uses the accepted 300-second per-Lens deadline boundary

#### Scenario: Reject invalid execution policy configuration

- **WHEN** either server-owned execution setting is zero or negative
- **THEN** application settings validation rejects it before a public run can use it

#### Scenario: Ignore client execution policy

- **WHEN** a client attempts to submit a parallelism or Lens deadline field
- **THEN** strict public request validation rejects the undeclared field
- **AND** server execution policy remains unchanged
