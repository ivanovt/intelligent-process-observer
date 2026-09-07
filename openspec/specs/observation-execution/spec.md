# Observation Execution Specification

## Purpose

Provide deterministic, bounded, and durable top-level execution of one predefined Metric/Alert Observation by composing the accepted runtime, analytical, reasoning, and reporting capabilities without expanding their scopes.

## Requirements

### Requirement: Accept and freeze one predefined Observation execution scope

The system SHALL accept an internal execution request containing exactly an existing `observation_id` and one finite, forward UTC `analysis_window` with `from < to`. It SHALL load the complete predefined Observation Definition aggregate exactly once before creating runtime records and SHALL freeze an immutable run-scoped snapshot containing the definition identity and schema version, Observation semantic metadata, ordered Metric and Alert Lens definitions, and ordered Relationship definitions.

All downstream execution contexts SHALL be derived from that snapshot and the requested analysis window. The system SHALL NOT re-read definition members during the run, copy the definition into a new definition aggregate, or allow a later definition mutation to change the active run. Provider selectors and other technical configuration SHALL remain available only to the applicable Lens pipeline projection; reasoning and reporting SHALL receive only their already accepted semantic projections. Alert `analysis_timestamp` SHALL remain the analysis-window end required by the accepted Alert pipeline contract.

The framework-neutral internal entry point SHALL return exactly one closed `ObservationExecutionOutcome` variant when it handles the request normally. Its required `kind` discriminator SHALL be `completed`, `failed`, or `rejected`: `completed` contains `observation_run_id` and terminal status `completed` with no reason; `failed` contains `observation_run_id`, terminal status `failed`, and the exact persisted structured ObservationRun reason; and `rejected` contains no ObservationRun identity or runtime status and a preparation reason with component `execution_preparation` and exactly one controlled code: `invalid_execution_request`, `observation_not_found`, `invalid_observation_definition`, `empty_lens_topology`, or `unsupported_lens_type`. `rejected` is a pre-initialization result, not a runtime lifecycle status, and its code SHALL identify respectively malformed request/policy, absent definition, invalid stored aggregate, empty Lens topology, or a Log/other unsupported Lens type. No diagnostic, exception, raw definition, or provider detail SHALL be included in any outcome reason.

A missing Observation, malformed request, empty Lens topology, unsupported Lens type including Log, or invalid stored aggregate SHALL return the corresponding controlled `rejected` outcome before any ObservationRun or LensRun is created. Caller cancellation and persistence/infrastructure failures SHALL not be converted into an `ObservationExecutionOutcome`: cancellation SHALL follow the separate durable-cancellation path and propagate unchanged, and persistence/infrastructure failures SHALL propagate as infrastructure errors. This capability SHALL expose no public execution endpoint.

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

### Requirement: Create and correlate the complete runtime identity graph atomically

The system SHALL generate one fresh ObservationRun identity and one fresh LensRun identity for every Lens in the frozen snapshot. It SHALL create the ObservationRun, all LensRuns, and the ObservationRun transition from `pending` to `running` in one caller-owned transaction before starting any Lens pipeline. Each LensRun SHALL initially be `pending`, SHALL identify its parent ObservationRun and source Lens, and SHALL preserve type-aware identity so equal Metric and Alert `lens_id` values remain distinct.

The created runtime topology SHALL exactly partition the snapshot's Lens topology: no configured Lens may be omitted, duplicated, or supplemented. A creation, correlation, flush, or commit failure SHALL roll back the entire runtime graph and SHALL start no Lens pipeline. Runtime storage SHALL retain only the accepted execution context/provenance projection and SHALL not duplicate definition objects.

#### Scenario: Create a complete mixed runtime graph

- **GIVEN** the snapshot contains two Metric Lenses and one Alert Lens
- **WHEN** runtime initialization commits
- **THEN** one running ObservationRun and exactly three pending correlated LensRuns exist
- **AND** every generated run identity is unique

#### Scenario: Preserve type-aware equal Lens IDs

- **GIVEN** one Metric Lens and one Alert Lens share the same Lens ID
- **WHEN** runtime initialization creates their LensRuns
- **THEN** both LensRuns are created under the same ObservationRun
- **AND** their type-aware identities remain unambiguous

#### Scenario: Roll back incomplete initialization

- **GIVEN** persistence rejects any runtime record or the initialization commit fails
- **WHEN** the runtime graph is created
- **THEN** no partial ObservationRun or LensRun graph is committed
- **AND** no Lens pipeline starts

### Requirement: Dispatch Lens pipelines in deterministic bounded order

The system SHALL establish the canonical Lens dispatch order by ascending `(lens_type, lens_id)`, using the literal type order `metric`, then `alert`, and lexical Lens ID order within each type. Definition collection order SHALL remain presentation-only and SHALL not change dispatch order, result ordering, or reasoning input ordering.

Execution SHALL use a positive caller-supplied `max_parallel_lens_runs` policy and a positive caller-supplied per-Lens deadline. The exact configuration location, default hierarchy, and timeout values remain outside this contract. At most the configured number of Lens pipelines SHALL be active simultaneously. Admission SHALL be work-conserving: when a slot becomes free, the earliest not-yet-started Lens in canonical order SHALL start without waiting for a batch. Queue time before admission SHALL not consume the admitted Lens execution deadline.

The per-Lens deadline SHALL begin only after the assigned LensRun has durably transitioned to `running` and immediately before its adapter starts pre-terminalization provider, agent, and deterministic analytical work. It SHALL end when that pre-terminalization work returns or raises. It SHALL NOT enclose Metric History repository loading or History analysis performed in the caller-owned terminal transaction, nor any Lens terminal transaction work including transaction acquisition, validation, artifact insertion, flush, commit, or rollback. Those database-bound operations retain the accepted persistence semantics: a repository/transaction failure SHALL propagate as infrastructure failure and SHALL NOT be classified as an analytical `timeout` or converted to a failed Lens outcome.

Immediately before invoking a Lens pipeline, the system SHALL durably transition that LensRun from `pending` to `running`. A failure to persist that transition SHALL prevent the pipeline invocation. Physical completion order MAY vary, but all collected Lens outcomes and downstream Lens projections SHALL be restored to canonical order.

#### Scenario: Enforce the concurrency ceiling

- **GIVEN** more configured Lenses than the positive parallelism limit
- **WHEN** Lens fan-out runs
- **THEN** the number of active Lens pipelines never exceeds the limit
- **AND** every configured Lens is eventually admitted unless the top-level execution is cancelled

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

### Requirement: Invoke existing Metric and Alert pipelines through type-specific adapters

For each running Metric LensRun, the system SHALL invoke the accepted Metric Analysis Pipeline with an immutable context containing the exact Observation/Lens runtime identities, Metric provider scope, analysis window, analysis objectives, reference periods, and accepted History policy. For each running Alert LensRun, it SHALL invoke the accepted Alert Analysis Pipeline with the exact runtime identities, Alert provider scope, analysis window, semantic Lens fields, objectives, reference periods, and running status. The top-level orchestrator SHALL NOT inspect or reproduce the internal analytical stages of either pipeline.

Each type-specific execution adapter SHALL validate that the returned outcome belongs to the assigned ObservationRun and LensRun and satisfies the accepted type-specific result/lifecycle contract. Expiry of the deadline-covered pre-terminalization analytical work SHALL produce a failed LensRun with reason `timeout` and the Lens type as component. A Metric History repository failure, History-transaction failure, or any Lens terminal persistence failure SHALL instead propagate as infrastructure failure. Any other unexpected non-cancellation, non-persistence Lens execution exception SHALL produce a failed LensRun with reason `analysis_failed` and the Lens type as component. A mismatched or contradictory outcome SHALL be rejected, SHALL not be persisted as usable evidence, and SHALL produce a contract-compliant failed Lens outcome with reason `identity_mismatch`.

For a wrapper-level Metric Lens failure with LensRun reason `timeout`, `analysis_failed`, or `identity_mismatch`, the Metric adapter SHALL construct the required minimal failed MetricAnalysisResult through the existing Metric-owned result builder using the assigned immutable Metric execution context and its generic mandatory-analysis failure variant. The artifact SHALL therefore have failed status error code `mandatory_metric_analysis_failed` and its existing fixed public message, assigned Observation/ObservationRun/Lens/LensRun identity and analysis window, and Metric-owned `prometheus` provenance with builder-owned generation time. Its artifact error SHALL NOT be replaced by, or required to equal, the wrapper LensRun reason; the LensRun SHALL retain its exact wrapper code and component. The adapter SHALL never persist an untrusted mismatched producer artifact. A failed Alert execution SHALL continue to have no AlertAnalysisResult.

The Lens terminal transition and eligible type-specific artifact insertion SHALL commit atomically in one caller-owned transaction outside the per-Lens deadline. For Metric, that same deadline-exempt transaction SHALL perform the accepted History read and any associated History analysis before terminal persistence. One Lens failure SHALL not cancel or prevent other logically independent Lens executions.

#### Scenario: Invoke both supported pipelines

- **GIVEN** one running Metric LensRun and one running Alert LensRun
- **WHEN** their fan-out work executes
- **THEN** each receives only its accepted immutable type-specific context
- **AND** the orchestrator performs no Metric or Alert analysis itself

#### Scenario: Persist one usable outcome atomically

- **GIVEN** a pipeline returns a correlated completed or partial result
- **WHEN** its Lens outcome is persisted
- **THEN** the terminal LensRun transition and artifact insertion commit together
- **AND** a rollback leaves neither durable change

#### Scenario: Isolate a Lens timeout

- **GIVEN** one admitted Lens exceeds its supplied execution deadline while another Lens can finish
- **WHEN** the deadline expires
- **THEN** the timed-out Lens becomes failed with structured `timeout` reason
- **AND** a timed-out Metric Lens persists only the assigned-context minimal Metric artifact with error `mandatory_metric_analysis_failed`
- **AND** the other Lens continues independently

#### Scenario: Propagate a deadline-exempt Metric History or terminal persistence failure

- **GIVEN** a Metric Lens has completed its deadline-covered pre-terminalization analytical work
- **WHEN** its History repository read or caller-owned terminal transaction fails or cannot commit
- **THEN** the failure propagates as infrastructure/persistence failure rather than a `timeout` Lens outcome
- **AND** no fabricated terminal LensRun or Metric artifact is claimed

#### Scenario: Contain an unexpected Lens exception

- **GIVEN** one Lens execution raises an unexpected non-cancellation exception before returning an outcome
- **WHEN** its type-specific adapter handles the exception
- **THEN** it persists the accepted type-specific failed outcome with `analysis_failed`
- **AND** no exception text, traceback, credential, provider response, or raw input enters the structured reason

#### Scenario: Map a Metric wrapper failure without changing the LensRun reason

- **GIVEN** a Metric adapter normalizes `timeout`, `analysis_failed`, or `identity_mismatch` for its assigned running LensRun
- **WHEN** it persists that failed terminal outcome
- **THEN** the LensRun retains the exact wrapper reason code and component `metric`
- **AND** its sole minimal MetricAnalysisResult has failed error `mandatory_metric_analysis_failed` with the canonical fixed message
- **AND** the artifact identity, analysis window, source, and generated time are constructed from the assigned immutable Metric context and Metric-owned builder rather than from an exception or rejected producer artifact

#### Scenario: Reject a contradictory producer identity

- **GIVEN** a Lens pipeline outcome identifies another ObservationRun, Lens, LensRun, type, or status
- **WHEN** the adapter validates the outcome
- **THEN** the contradictory artifact is not persisted or admitted downstream
- **AND** the assigned LensRun reaches a contract-compliant failed `identity_mismatch` outcome with the Metric-specific replacement artifact when applicable

### Requirement: Enforce strict JOIN and classify the complete Lens outcome set

The system SHALL not begin the normal post-Lens workflow until every LensRun in the current ObservationRun has durably reached `completed`, `partial`, or `failed`. It SHALL not continue early because one or more usable results exist. A supplied deadline SHALL ensure an admitted straggler in deadline-covered analytical work reaches failed timeout rather than blocking JOIN indefinitely. `cancelled` SHALL be terminal for lifecycle retrieval but SHALL use the separate cancellation abort path and SHALL never satisfy a normal-continuation JOIN.

After JOIN, the system SHALL classify Lens outcomes in canonical Lens order. Usable results SHALL be exactly completed or partial Metric results with `data_quality=good|degraded` and completed or partial Alert results. A completed Metric result with `data_quality=insufficient`, every failed Metric result, and every failed Alert LensRun SHALL be unavailable. Failed Metric artifacts SHALL remain non-usable traceability inputs; failed Alert outcomes SHALL remain artifact-free.

If zero usable results exist, the system SHALL transition the ObservationRun to `failed` with reason `no_usable_lens_results` and component `usable_results_gate`, preserve all committed Lens outcomes, and stop without Relationship Evaluation, Observation Reasoning, ObservationAnalysisResult, Report Generation, or ObservationReport. If at least one usable result exists, failed or insufficient Lenses SHALL remain explicit unavailable evidence and SHALL not be interpreted as normal or empty results.

#### Scenario: Wait for the final Lens

- **GIVEN** at least one Lens is usable while another Lens remains running
- **WHEN** the usable-results threshold is already met
- **THEN** no Relationship Evaluation or reasoning starts
- **AND** normal execution waits until the remaining Lens reaches a durable terminal outcome

#### Scenario: Continue with degradation

- **GIVEN** JOIN contains one usable partial result, one completed-insufficient Metric result, and one failed Alert LensRun
- **WHEN** the usable-results gate runs
- **THEN** execution continues with the partial result as usable
- **AND** the insufficient Metric and failed Alert Lens are represented as unavailable

#### Scenario: Stop with no usable results

- **GIVEN** every Lens is failed or a completed Metric result is analytically insufficient
- **WHEN** the usable-results gate runs
- **THEN** the ObservationRun becomes failed with `no_usable_lens_results`
- **AND** no Observation-level analytical or report artifact is created

### Requirement: Evaluate and persist Relationships deterministically before reasoning

When the usable-results gate passes, the system SHALL invoke the existing Relationship Evaluator exactly once with all ordered Relationship definitions from the frozen snapshot and the complete canonical-order collection of type-specific LensAnalysisResult artifacts produced for the current ObservationRun. This collection SHALL include usable Metric and Alert artifacts, completed-insufficient Metric artifacts, and failed Metric traceability artifacts; it SHALL contain no fabricated artifact for a failed Alert LensRun. The evaluator SHALL remain responsible for participant resolution and SHALL ignore non-Metric results under its accepted contract.

The system SHALL preserve Relationship definition order and SHALL require exactly one validated self-contained evaluation per configured Relationship, or an empty batch when none are configured. It SHALL validate batch cardinality, order, unique relationship identity, and current-run correlation before persistence. All evaluations SHALL be inserted atomically in one caller-owned transaction. No Observation Reasoning invocation may start until that transaction commits.

An evaluator exception, invalid batch, identity mismatch, or persistence-independent contract failure SHALL fail the ObservationRun with reason `relationship_evaluation_failed` and component `relationship_evaluator`, preserve Lens outcomes, create no partial evaluation batch, and stop before reasoning.

#### Scenario: Evaluate after degraded JOIN

- **GIVEN** at least one usable Lens result and one failed participant Lens
- **WHEN** Relationship Evaluation runs
- **THEN** the evaluator receives the complete admissible artifact collection
- **AND** it produces the accepted unknown or uncertain evidence rather than the orchestrator projecting participant semantics

#### Scenario: Preserve empty Relationship topology

- **GIVEN** the frozen definition contains no Relationships and the usable-results gate passes
- **WHEN** Relationship Evaluation runs
- **THEN** an empty evaluation batch is accepted
- **AND** Observation Reasoning may start after the empty persistence boundary completes

#### Scenario: Reject a malformed evaluation batch

- **GIVEN** evaluator output has missing, duplicate, reordered, or unexpected Relationship identities
- **WHEN** the orchestration boundary validates it
- **THEN** no RelationshipEvaluation from the batch is committed
- **AND** the ObservationRun fails before reasoning

### Requirement: Construct, invoke, and persist Observation Reasoning from the exact run partition

After Relationship Evaluation commits, the system SHALL deterministically construct the existing strict ObservationReasoningInput from the frozen snapshot and current run. The semantic context, usable results, unavailable Lens metadata, and Relationship evaluations SHALL use canonical Lens order and persisted Relationship order as applicable. The usable and unavailable collections SHALL form the exact type-aware partition of all configured Lenses required by the accepted reasoning contract.

A completed-insufficient Metric SHALL be projected through the accepted deterministic `completed_insufficient_metric` origin with reason `insufficient_data`; failed Metric and Alert outcomes SHALL use `caller_unavailable` and preserve their persisted reason code and component exactly. Raw telemetry, provider queries, diagnostics, concurrency/deadline settings, persistence data, and definition technical fields SHALL not enter reasoning input.

The system SHALL invoke the existing Observation Reasoning capability exactly once and SHALL not alter its bounded multi-phase model/retrieval policy. A successful result SHALL match the current Observation and ObservationRun identity and SHALL be persisted in its own transaction before report generation begins. A typed reasoning failure SHALL fail the ObservationRun using the exact safe reasoning code and component, persist no ObservationAnalysisResult, preserve Lens and Relationship artifacts, and stop before report generation. Invalid input construction, identity mismatch, or invalid success output SHALL use `reasoning_result_invalid` with component `result_builder`.

#### Scenario: Build an exact degraded reasoning partition

- **GIVEN** usable completed and partial results plus failed and insufficient Lenses
- **WHEN** reasoning input is constructed
- **THEN** every configured Lens appears exactly once as usable or unavailable in canonical order
- **AND** producer reasons and the special insufficient-Metric projection follow the accepted reasoning contract

#### Scenario: Persist analysis before reporting

- **GIVEN** Observation Reasoning returns one valid correlated ObservationAnalysisResult
- **WHEN** the reasoning stage succeeds
- **THEN** the analysis result commits before Report Generation is invoked
- **AND** at most one analysis result exists for the ObservationRun

#### Scenario: Stop on typed reasoning failure

- **GIVEN** Observation Reasoning returns a safe typed failure
- **WHEN** the orchestrator handles it
- **THEN** the ObservationRun becomes failed with the same controlled code and component
- **AND** no analysis result or report is fabricated

#### Scenario: Reject a mismatched analysis identity

- **GIVEN** a purported reasoning success identifies another Observation or ObservationRun
- **WHEN** orchestration validates the result
- **THEN** the result is not persisted
- **AND** the ObservationRun fails with `reasoning_result_invalid` for `result_builder`

### Requirement: Generate and persist a faithful report before successful completion

Only after a valid ObservationAnalysisResult commits, the system SHALL construct the existing strict ReportGenerationRequest from that result and the minimal semantic context derived from the same frozen snapshot. It SHALL invoke the existing Report Generation capability exactly once and SHALL not expose Lens results, Relationship definitions/evaluations, raw evidence, provider configuration, execution policy, or a retrieval capability to reporting.

A successful ObservationReport SHALL match the source Observation and ObservationRun identities. The report insertion and ObservationRun transition from `running` to `completed` SHALL commit atomically in one caller-owned transaction. A completed ObservationRun SHALL therefore have its persisted ObservationAnalysisResult and exactly one persisted Markdown ObservationReport, while completed or partial Lens outcomes do not make the ObservationRun partial.

A typed report failure, invalid report identity, or invalid report output SHALL transition the ObservationRun to `failed` using the exact safe report code and component. The previously committed ObservationAnalysisResult and RelationshipEvaluations SHALL remain available, no partial or fallback report SHALL be persisted, and no completed status SHALL be claimed.

#### Scenario: Complete a degraded successful Observation

- **GIVEN** reasoning succeeds after a JOIN containing usable and unavailable Lenses
- **WHEN** report generation and its final transaction succeed
- **THEN** the report is persisted and the ObservationRun becomes completed atomically
- **AND** the degraded Lens outcomes and reasoning limitations remain unchanged

#### Scenario: Preserve analysis when report generation fails

- **GIVEN** a valid ObservationAnalysisResult has committed and Report Generation returns a typed failure
- **WHEN** the report failure is handled
- **THEN** the ObservationRun becomes failed with the report failure code and component
- **AND** the analysis result and prior artifacts remain persisted
- **AND** no ObservationReport or fallback report exists

#### Scenario: Roll back report and completion together

- **GIVEN** report insertion or the completed lifecycle transition cannot commit
- **WHEN** the final transaction rolls back
- **THEN** neither a new report nor a completed status is durable
- **AND** the system does not claim successful execution

### Requirement: Preserve forward-only, non-contradictory lifecycle ownership

Only the top-level Observation execution capability SHALL coordinate ObservationRun lifecycle. Lens execution adapters SHALL own only their assigned LensRun terminal outcome and eligible Lens artifact transaction. Relationship Evaluation, Observation Reasoning, and Report Generation SHALL remain side-effect free with respect to top-level lifecycle and persistence.

Every lifecycle transition SHALL use the accepted forward graph and compare the persisted current state before mutation. A terminal ObservationRun or LensRun SHALL reject a duplicate, backward, or contradictory transition; an artifact uniqueness or identity violation SHALL roll back its transaction. Concurrent or repeated terminalization attempts SHALL produce at most one committed terminal truth and SHALL not overwrite an existing terminal reason or artifact.

For non-persistence unexpected orchestration failures after runtime initialization, the system SHALL stop admitting new work, settle or internally stop outstanding Lens tasks, preserve already terminal LensRuns, transition each remaining pending/running LensRun to failed with reason `execution_aborted` and a controlled stage component, then transition the ObservationRun to failed with `execution_failed` and that component. Exception text and sensitive diagnostics SHALL not enter durable reasons. A database flush/commit/connection failure SHALL propagate as an infrastructure error because the system cannot truthfully claim durable terminalization through an unavailable persistence boundary; it SHALL not be converted into a fabricated successful or failed runtime state.

#### Scenario: Reject a duplicate terminal transition

- **GIVEN** a LensRun or ObservationRun already has a terminal status
- **WHEN** another completion, failure, or cancellation transition is attempted
- **THEN** persistence rejects the contradictory transition
- **AND** the original status, reason, and artifact remain unchanged

#### Scenario: Contain an unexpected orchestration failure

- **GIVEN** a non-persistence exception escapes a post-initialization orchestration stage
- **WHEN** the top-level failure boundary handles it
- **THEN** already terminal work is preserved and unfinished LensRuns become failed with `execution_aborted`
- **AND** the ObservationRun becomes failed with `execution_failed`
- **AND** no later stage starts

#### Scenario: Do not fabricate durability during database failure

- **GIVEN** a required runtime or artifact transaction cannot flush or commit
- **WHEN** persistence reports the infrastructure failure
- **THEN** the failed transaction is rolled back and the infrastructure error propagates
- **AND** the caller receives no false claim that the affected lifecycle or artifact write committed

### Requirement: Terminalize top-level cancellation without rewriting completed work

When caller cancellation reaches an initialized top-level execution, the system SHALL stop admitting new Lens work and request cancellation of active child work. In one cancellation-terminalization transaction, every `pending` or `running` LensRun SHALL transition to terminal `cancelled` with reason code `execution_cancelled` and no diagnostic detail, while every already `completed`, `partial`, `failed`, or `cancelled` LensRun and every committed artifact SHALL remain unchanged. The running ObservationRun SHALL transition to terminal `cancelled` with the same structured reason.

No usable-results gate, Relationship Evaluation, Observation Reasoning, or Report Generation stage not already started SHALL begin after cancellation is observed. If cancellation arrives during a later stage, that capability's accepted caller-cancellation behavior SHALL propagate without a typed artifact; previously committed Lens, Relationship, ObservationAnalysisResult, or ObservationReport artifacts SHALL remain unchanged, and no next artifact SHALL be created. After cancellation terminalization commits, the original cancellation SHALL propagate unchanged to the caller. Cancellation SHALL not be translated to failed, shall not create an automatic retry, and shall not rewrite terminal child outcomes.

If the cancellation-terminalization transaction itself fails, its transaction SHALL roll back and the persistence failure SHALL be observable alongside the inability to guarantee durable cancellation; the system SHALL not claim that cancellation state was persisted.

#### Scenario: Cancel during Lens fan-out

- **GIVEN** one LensRun is completed, one is running, and one remains pending
- **WHEN** caller cancellation reaches the orchestrator
- **THEN** the completed LensRun and its artifact remain unchanged
- **AND** the running and pending LensRuns become cancelled
- **AND** the ObservationRun becomes cancelled and no post-JOIN stage begins

#### Scenario: Cancel during Observation Reasoning

- **GIVEN** all Lens outcomes and RelationshipEvaluations are committed and reasoning is active
- **WHEN** caller cancellation propagates from reasoning
- **THEN** those committed artifacts remain unchanged
- **AND** the ObservationRun becomes cancelled
- **AND** no ObservationAnalysisResult or report is fabricated

#### Scenario: Cancel during Report Generation

- **GIVEN** an ObservationAnalysisResult is committed and Report Generation is active
- **WHEN** caller cancellation propagates from reporting
- **THEN** the analysis result remains persisted
- **AND** the ObservationRun becomes cancelled without an ObservationReport

#### Scenario: Propagate only after durable cancellation

- **GIVEN** cancellation terminalization can commit
- **WHEN** unfinished children and the parent are marked cancelled
- **THEN** the original caller cancellation is re-raised after the commit
- **AND** no typed success or failure outcome replaces it

### Requirement: Treat every retry, restart, and re-run as a fresh execution

Every retry, restart, or re-run request SHALL follow normal preparation and create a new ObservationRun and new LensRun identities from a newly loaded definition snapshot. An existing pending, running, completed, failed, or cancelled ObservationRun SHALL never be resumed, reopened, reset, or transitioned back to running. Previous runtime records and artifacts SHALL remain immutable and MAY contribute only through already accepted history behavior.

This capability SHALL NOT automatically start another run after failure or cancellation, deduplicate requests, define an idempotency key, reuse intermediate artifacts, replay a stage, or decide whether a new run may overlap an existing running run. Those trigger and overlap policies remain outside scope.

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

#### Scenario: Define no automatic retry

- **GIVEN** an ObservationRun becomes failed or cancelled
- **WHEN** no separate execution request is supplied
- **THEN** this capability creates no replacement run

### Requirement: Keep the MVP execution boundary intentionally small

The capability SHALL remain an internal deterministic modular-monolith workflow composed with Python asynchronous execution and the existing framework-neutral ports. It SHALL add no message broker, workflow engine, distributed worker, scheduler, dependency, database schema, public execution API, UI, notification, Log pipeline, ad-hoc natural-language resolution, cross-type Relationship, recommendation, or autonomous observational scope expansion.

PydanticAI SHALL remain behind the existing Metric, Alert, Observation Reasoning, and Report Generation ports and SHALL not enter orchestration or persistence contracts. Exact trigger policy, overlap policy, automatic retry policy, idempotency, replay/artifact reuse, process-crash recovery, system observability, and retention remain unresolved and SHALL not be silently selected by this change.

#### Scenario: Execute without scope expansion

- **GIVEN** the top-level workflow is implemented
- **WHEN** its production and test dependencies are inspected
- **THEN** it composes only the existing supported Metric/Alert capabilities and persistence
- **AND** it introduces none of the excluded infrastructure, public surfaces, or deferred Lens behavior
