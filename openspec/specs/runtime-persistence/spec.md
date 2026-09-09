# Runtime Persistence Specification

## Purpose

Provide the durable runtime record and artifact correlations that later execution stages require, while keeping Observation, Lens, and Relationship definitions separate from their executions.

## Requirements

### Requirement: Persist correlated runtime executions without duplicating definitions

The system SHALL persist an `ObservationRun` as a runtime instance correlated with its existing Observation definition, and SHALL persist each `LensRun` as a runtime instance correlated with exactly one ObservationRun. Runtime records SHALL retain stable run identities, the Observation and Lens identities needed to correlate the execution, Lens type where applicable, lifecycle status, timestamps, structured reason/failure metadata when present, and producer-supplied provenance/execution context.

Within one ObservationRun, LensRun definition identity SHALL be the type-aware pair `(lens_type, lens_id)`. The same `lens_id` SHALL be permitted for different Lens types in the same ObservationRun, while duplicate LensRuns with the same `lens_type` and `lens_id` SHALL be rejected.

ObservationRun status SHALL be one of `pending`, `running`, `completed`, `failed`, or `cancelled`. Its normal lifecycle direction SHALL be `pending -> running -> completed | failed | cancelled`. ObservationRun SHALL NOT have status `partial`; a partial LensRun SHALL NOT imply a partial ObservationRun. A terminal ObservationRun SHALL never return to `running`.

LensRun status SHALL be one of `pending`, `running`, `completed`, `partial`, `failed`, or `cancelled`. Its terminal statuses SHALL be exactly `completed`, `partial`, `failed`, and `cancelled`. Its normal analytical lifecycle direction SHALL be `pending -> running -> completed | partial | failed`; cancellation SHALL additionally permit `pending | running -> cancelled`. A terminal LensRun SHALL never return to `running`.

`failed`, `partial`, and `cancelled` transitions SHALL require a non-empty structured reason; `pending`, `running`, and `completed` SHALL not carry one. Definition objects (`Observation`, `Lens`, and `Relationship`) SHALL remain definition data and SHALL NOT be represented as runtime records or copied into runtime storage as new definition aggregates.

#### Scenario: Store an in-progress runtime execution

- **GIVEN** an existing Observation definition and runtime identity/lifecycle metadata for a new execution
- **WHEN** runtime persistence stores an ObservationRun and LensRun with status `pending`, then records them as `running`
- **THEN** both runs can be retrieved with their correlations and lifecycle metadata, without creating an analytical artifact or modifying the definition

#### Scenario: Store same-ID Metric and Alert LensRuns

- **GIVEN** a mixed Observation definition contains one Metric Lens and one Alert Lens with the same ID
- **WHEN** runtime persistence stores both LensRuns under one ObservationRun
- **THEN** both records are accepted and remain distinguishable by Lens type

#### Scenario: Reject a duplicate type-aware LensRun identity

- **GIVEN** an ObservationRun already contains a LensRun with a particular Lens type and Lens ID
- **WHEN** runtime persistence attempts to store another LensRun with the same type and ID under that ObservationRun
- **THEN** the duplicate is rejected without preventing a different Lens type from using the same ID

#### Scenario: Complete an ObservationRun after Lens processing

- **GIVEN** an ObservationRun is `running`
- **WHEN** runtime persistence records it as `completed`, `failed`, or `cancelled`
- **THEN** the persisted lifecycle follows the accepted forward transition and does not expose `created` or `partial` as an ObservationRun status

#### Scenario: Retrieve a terminal LensRun with failure metadata

- **GIVEN** a LensRun is persisted with terminal status `failed` and a structured failure reason
- **WHEN** its enclosing ObservationRun is retrieved
- **THEN** the LensRun exposes the failed status and failure metadata as unavailable runtime evidence, not as an empty usable result

#### Scenario: Cancel a pending LensRun

- **GIVEN** a LensRun is pending when top-level cancellation is observed
- **WHEN** runtime persistence records it as cancelled with an `execution_cancelled` reason
- **THEN** the LensRun is terminal without ever being recorded as running
- **AND** it has no analytical artifact

#### Scenario: Reject reopening a terminal run

- **GIVEN** an ObservationRun or LensRun is completed, partial where applicable, failed, or cancelled
- **WHEN** a caller attempts to transition it to running or another terminal state
- **THEN** persistence rejects the contradictory transition and preserves the original state

### Requirement: Preserve cancelled runtime state without fabricating or deleting artifacts

The system SHALL persist `cancelled` as a non-usable terminal runtime status. Cancelling an Observation execution SHALL transition only pending or running LensRuns and the running ObservationRun; already completed, partial, failed, or cancelled LensRuns SHALL remain unchanged with their reasons and artifacts intact. Every cancellation transition SHALL require structured reason code `execution_cancelled` and SHALL record a terminal timestamp.

A cancelled Metric, Alert, or Log LensRun SHALL have no newly created type-specific LensAnalysisResult. Persistence SHALL reject attaching a Lens analysis artifact whose status is cancelled. Existing artifacts belonging to LensRuns that reached another terminal status before parent cancellation SHALL remain retrievable. Observation-level artifacts committed before cancellation SHALL likewise remain retrievable; cancellation SHALL not fabricate a missing RelationshipEvaluation, ObservationAnalysisResult, or ObservationReport and SHALL not delete a committed one.

#### Scenario: Preserve completed children during parent cancellation

- **GIVEN** one LensRun completed with an artifact while sibling LensRuns remain pending or running
- **WHEN** cancellation terminalization is persisted
- **THEN** the completed LensRun and artifact remain unchanged
- **AND** only the unfinished siblings and parent ObservationRun become cancelled

#### Scenario: Reject an artifact for a cancelled LensRun

- **GIVEN** a LensRun has terminal status cancelled
- **WHEN** a caller attempts to attach a Metric, Alert, or Log analysis artifact
- **THEN** persistence rejects the artifact and retrieval continues to show no result for that LensRun

#### Scenario: Retrieve analysis preserved after report cancellation

- **GIVEN** an ObservationAnalysisResult committed before Report Generation was cancelled
- **WHEN** the cancelled ObservationRun is retrieved
- **THEN** the analysis result remains present and correlated
- **AND** no ObservationReport is fabricated

#### Scenario: Roll back cancellation atomically

- **GIVEN** a cancellation transaction updates multiple unfinished LensRuns and their parent ObservationRun
- **WHEN** any update or the transaction commit fails
- **THEN** the cancellation transaction rolls back as a unit
- **AND** persistence does not claim that only a subset was cancelled

### Requirement: Persist type-specific Lens analysis artifacts according to lifecycle

The system SHALL persist at most one type-specific Lens analysis artifact for an eligible LensRun, correlated with its producing LensRun and enclosing ObservationRun. Each persisted result SHALL retain its result type, complete payload, and the identity, provenance, and schema/version information defined by that result's accepted contract.

Persistence eligibility SHALL be type-specific:

- A MetricAnalysisResult SHALL be persisted for a Metric LensRun with status `completed`, `partial`, or `failed`; a failed result SHALL use the accepted minimal failed MetricAnalysisResult contract, including its required failure, identity, analysis-window, provenance, and traceability fields.
- An AlertAnalysisResult SHALL be persisted only for an Alert LensRun with status `completed` or `partial`.
- A LogAnalysisResult SHALL be persisted only for a Log LensRun with status `completed` or `partial`.

Completed and partial LensAnalysisResults SHALL be classified as usable downstream analytical evidence. A failed MetricAnalysisResult SHALL be preserved for traceability but SHALL NOT be classified as usable analytical evidence. Persisting any result SHALL NOT synthesize analytical payload fields, normalize absent optional sections into empty sections, or create raw telemetry/provider-payload storage.

#### Scenario: Persist a completed Metric result

- **GIVEN** a Metric LensRun has terminal status `completed` and a valid completed MetricAnalysisResult carrying the same runtime identity
- **WHEN** the result is persisted and the ObservationRun is retrieved
- **THEN** the result is correlated with the Metric LensRun and classified as usable analytical evidence

#### Scenario: Persist a partial Metric result

- **GIVEN** a Metric LensRun has terminal status `partial` and a valid partial MetricAnalysisResult carrying the same runtime identity and partial reason
- **WHEN** the result is persisted and the ObservationRun is retrieved
- **THEN** the result is correlated with the Metric LensRun and classified as usable analytical evidence

#### Scenario: Persist a failed Metric result

- **GIVEN** a Metric LensRun has terminal status `failed`
- **AND** a valid minimal failed MetricAnalysisResult exists with matching identity and failure metadata
- **WHEN** the result is persisted
- **THEN** the failed MetricAnalysisResult is preserved for traceability
- **AND** retrieval correlates it with the failed Metric LensRun
- **AND** the result is not classified as usable analytical evidence

#### Scenario: Persist and retrieve a partial Log result

- **GIVEN** a Log LensRun has terminal status `partial` and a valid versioned LogAnalysisResult carrying the same runtime identity
- **WHEN** the result artifact is persisted and the ObservationRun is retrieved
- **THEN** the result is returned as the Log LensRun's usable artifact with its contract-defined version, payload, provenance, and partial reason preserved

#### Scenario: Reject a mismatched Lens result

- **GIVEN** a Lens analysis artifact declares an identity, Lens type, or status inconsistent with its target LensRun
- **WHEN** the caller attempts to persist the artifact
- **THEN** the operation is rejected and no mismatched analytical artifact is stored

### Requirement: Preserve failed Alert and Log result absence

The system SHALL persist a failed Alert LensRun or failed Log LensRun with its terminal lifecycle and structured failure metadata, but SHALL NOT create an AlertAnalysisResult or LogAnalysisResult for that failed LensRun. The persistence contract SHALL reject attempts to attach either type-specific result to a failed LensRun.

The absence of the result artifact SHALL be observable on retrieval and SHALL NOT be encoded as a normal result, an empty result payload, or a generic placeholder analytical artifact.

#### Scenario: Persist a failed Alert LensRun

- **GIVEN** an Alert LensRun has failed before a usable analytical result exists
- **WHEN** the failure state and metadata are persisted
- **THEN** retrieval returns the failed Alert LensRun and no AlertAnalysisResult artifact

#### Scenario: Persist a failed Log LensRun

- **GIVEN** a Log LensRun has failed before a usable analytical result exists
- **WHEN** the failure state and metadata are persisted
- **THEN** retrieval returns the failed Log LensRun and no LogAnalysisResult artifact

#### Scenario: Reject a Log result for a failed LensRun

- **GIVEN** a Log LensRun has terminal status `failed`
- **WHEN** a caller attempts to persist a LogAnalysisResult for that run
- **THEN** the operation is rejected and retrieval continues to show no LogAnalysisResult artifact

### Requirement: Persist Observation-level analytical and presentation artifacts

The system SHALL persist zero or more self-contained RelationshipEvaluation artifacts, at most one ObservationAnalysisResult, and at most one ObservationReport for an ObservationRun in the MVP. Each artifact SHALL be correlated to the ObservationRun and SHALL preserve its identity, provenance, payload, or Markdown content as defined by its accepted contract. A persisted ObservationReport SHALL be correlated with the ObservationAnalysisResult from which it was generated.

The persisted ObservationAnalysisResult SHALL preserve its contract-defined schema version, findings, hypotheses, limitations, and traceability references. Each RelationshipEvaluation SHALL preserve its evaluated relationship identity and evidence without requiring a downstream consumer to reconstruct it from the current Relationship definition; this requirement SHALL NOT assign a new domain-level serialized schema version to RelationshipEvaluation. The persisted ObservationReport SHALL preserve its accepted minimum envelope: observation identity, ObservationRun identity, generated time, `markdown` format, and Markdown content; this requirement SHALL NOT assign a domain-level schema version to ObservationReport.

#### Scenario: Retrieve all Observation-level artifacts for an execution

- **GIVEN** an ObservationRun has persisted RelationshipEvaluation artifacts, one ObservationAnalysisResult, and one Markdown ObservationReport
- **WHEN** the runtime execution is retrieved
- **THEN** each artifact is returned with its ObservationRun correlation and its contract-defined identity, version information where defined, provenance, and preserved payload or content

#### Scenario: Preserve a self-contained RelationshipEvaluation

- **GIVEN** a RelationshipEvaluation includes relationship identity, evaluated expected/observed evidence, and an applicability outcome
- **WHEN** it is persisted and later retrieved
- **THEN** the retrieved artifact retains that self-contained evaluation information without depending on a second definition lookup or a newly invented domain schema version

#### Scenario: Retrieve a failed ObservationRun without downstream artifacts

- **GIVEN** an ObservationRun has failed before Observation Reasoning and Report Generation
- **WHEN** the runtime execution is retrieved
- **THEN** its persisted runtime state and available Lens artifacts are returned
- **AND** no ObservationAnalysisResult is fabricated
- **AND** no ObservationReport is fabricated

### Requirement: Provide coherent runtime execution retrieval

The system SHALL provide internal retrieval of a persisted ObservationRun by its stable run identity. The retrieved runtime record SHALL include its LensRuns and each correlated persisted Lens analysis, RelationshipEvaluation, ObservationAnalysisResult, and ObservationReport artifact where one exists.

Retrieval SHALL make the distinction between a missing artifact and an artifact with an empty optional section observable. It SHALL return no analytical artifact for failed Alert or Log LensRuns, retain failed MetricAnalysisResult traceability data for failed Metric LensRuns, and classify only completed and partial results as usable downstream evidence.

#### Scenario: Retrieve mixed completed, partial, and failed LensRuns

- **GIVEN** an ObservationRun contains completed and partial LensRuns with usable results, a failed Metric LensRun with a minimal failed MetricAnalysisResult, and failed Alert or Log LensRuns without result artifacts
- **WHEN** the runtime execution is retrieved
- **THEN** usable results are correlated only to completed or partial LensRuns
- **AND** the failed MetricAnalysisResult is retained but marked non-usable
- **AND** each failed Alert or Log LensRun is represented solely by its runtime failure state and metadata

### Requirement: Enforce one active ObservationRun per Observation

Runtime persistence SHALL prevent more than one ObservationRun whose status is `pending` or `running` from existing for the same `observation_id`, including when launch attempts race across transactions within the supported single-process application host. The enforcement SHALL NOT restrict concurrent active runs belonging to different Observations and SHALL NOT restrict the number of immutable terminal historical runs for one Observation. It SHALL NOT claim cross-process task ownership or make multi-process startup reconciliation safe.

#### Scenario: Race two active-run inserts

- **GIVEN** no active run exists for an Observation
- **WHEN** two transactions concurrently try to initialize a run for that Observation
- **THEN** at most one active ObservationRun commits
- **AND** the losing transaction leaves no parent, LensRun, or artifact residue

#### Scenario: Preserve terminal history

- **GIVEN** an Observation has multiple terminal historical runs
- **WHEN** a new run is initialized
- **THEN** the new active run can commit without modifying or deleting the terminal runs

### Requirement: Retrieve complete runtime history deterministically

Runtime persistence SHALL retrieve all ObservationRuns in descending creation order with stable run-identity tie-breaking and SHALL support resolving the Observation identity and display name needed by the public list projection. It SHALL retrieve one run by stable identity with its ordered LensRuns and all correlated persisted Lens analyses, RelationshipEvaluations, ObservationAnalysisResult, and ObservationReport artifacts where present.

One detail retrieval SHALL observe one coherent PostgreSQL database snapshot across every query needed to assemble the aggregate. A concurrent terminal lifecycle/artifact transaction SHALL therefore be visible either entirely before or entirely after the detail snapshot, never as a torn combination such as a stale LensRun status paired with its newly committed result. The full-history summary projection SHALL obtain each response from one statement-level durable snapshot.

Full-history retrieval SHALL return no pagination cursor or truncation. It SHALL distinguish an absent optional artifact from a present artifact whose collection fields are empty and SHALL preserve execution status independently from any available Observation analytical state.

#### Scenario: Retrieve newest-first history

- **GIVEN** runs exist for multiple Observations at different creation times
- **WHEN** complete runtime history is retrieved
- **THEN** every run is returned exactly once in newest-first order
- **AND** equal creation positions are ordered deterministically by run identity

#### Scenario: Retrieve an active run without analytical artifacts

- **GIVEN** an ObservationRun is pending or running and has not produced Observation analysis or a report
- **WHEN** its detail aggregate is retrieved
- **THEN** lifecycle, analysis-window, LensRun, and available artifact data are returned
- **AND** the missing ObservationAnalysisResult and ObservationReport remain explicitly absent

#### Scenario: Retrieve analysis from a failed run

- **GIVEN** a run persisted ObservationAnalysisResult but later failed during report generation
- **WHEN** list or detail data is retrieved
- **THEN** execution status remains `failed`
- **AND** the independently persisted analytical state remains available without being overwritten or inferred

#### Scenario: Interleave a terminal write with detail retrieval

- **GIVEN** detail retrieval has begun and a concurrent transaction atomically terminalizes a LensRun with its artifact
- **WHEN** the detail aggregate finishes loading
- **THEN** it contains either the pre-commit running LensRun without that artifact or the post-commit terminal LensRun with that artifact
- **AND** it never combines lifecycle and artifact values from different database snapshots

### Requirement: Reconcile active records left by process interruption

Before accepting public launches, runtime persistence SHALL atomically transition every recovered `pending` or `running` LensRun to `cancelled` with reason `execution_cancelled`, preserve every already terminal LensRun and committed artifact, and transition each recovered active ObservationRun to `cancelled` with the same reason. The same operation SHALL support recovery after a detached persistence failure by reconciling all active records owned by the sole supported process after its managed tasks have been quiesced.

Reconciliation SHALL be idempotent and SHALL NOT resume, delete, or fabricate artifacts for interrupted work. Runtime reconciliation SHALL begin only after the manager confirms every initializer and continuation from the fenced older generation has settled and closed its database transaction/session scope. An uncertain initializer SHALL never be retried. A reconciliation transaction failure SHALL propagate and SHALL NOT clear the manager's `recovery_required` state or startup readiness gate. Successful reconciliation SHALL be followed by durable verification that no `pending|running` ObservationRun remains before launch admission resumes.

#### Scenario: Reconcile after an ungraceful stop

- **GIVEN** persisted active runtime records have no owning execution task after process restart
- **WHEN** startup reconciliation runs
- **THEN** all unfinished records become durably cancelled in one coherent operation per ObservationRun
- **AND** the active-run uniqueness rule no longer blocks a fresh execution

#### Scenario: Repeat startup reconciliation

- **GIVEN** a previous startup already reconciled all orphaned active records
- **WHEN** reconciliation runs again
- **THEN** terminal records and artifacts remain byte-for-byte unchanged in their domain values

#### Scenario: Reconciliation cannot commit

- **GIVEN** active records require cancellation and persistence is unavailable
- **WHEN** reconciliation fails to commit
- **THEN** active records are not reported as durably terminalized
- **AND** launch admission and startup readiness remain blocked

#### Scenario: Defer reconciliation until initialization settles

- **GIVEN** an older-generation initializer has an indeterminate commit outcome and its session scope is still closing
- **WHEN** recovery is requested
- **THEN** persistence reconciliation waits until that admission settles
- **AND** its final active-state query cannot be followed by a late commit from that initializer

#### Scenario: Restore admission after verified reconciliation

- **GIVEN** the manager entered recovery after detached persistence uncertainty
- **WHEN** reconciliation commits and a durable verification read finds no active ObservationRun
- **THEN** the manager may return to `ready`
- **AND** later explicit launches create fresh runtime identities rather than retrying interrupted work

### Requirement: Persist RelationshipEvaluation definition order

Every RelationshipEvaluation persisted for an ObservationRun SHALL carry a zero-based non-negative ordinal equal to its Relationship's position in the frozen ordered definition snapshot. Ordinals SHALL be unique within one ObservationRun and SHALL form the exact contiguous range `0..N-1` for the atomically persisted evaluation batch. The ordinal is persistence ordering metadata and SHALL NOT add a field or schema version to the domain-owned RelationshipEvaluation payload.

Retrieval SHALL order RelationshipEvaluations by this persisted ordinal and SHALL NOT reconstruct order from UUID, timestamp, insertion accident, lexical Relationship ID, or the current mutable definition. Existing rows migrated by this change SHALL derive their ordinal by joining their ObservationRun to the current immutable MVP Relationship definition with the same `relationship_id`; migration SHALL abort without rewriting those artifacts if any row cannot resolve uniquely or would produce duplicate/non-contiguous order.

#### Scenario: Persist an ordered evaluation batch

- **GIVEN** a frozen Observation snapshot contains three Relationships in definition order
- **WHEN** their validated evaluation batch is persisted atomically
- **THEN** the rows receive unique ordinals `0`, `1`, and `2` matching that order
- **AND** their domain payloads remain unchanged

#### Scenario: Retrieve order independently of row metadata

- **GIVEN** RelationshipEvaluation row UUIDs, creation timestamps, or physical insertion order differ from definition order
- **WHEN** run detail is retrieved
- **THEN** evaluations are returned by persisted ordinal
- **AND** no current definition lookup is required to reconstruct their order

#### Scenario: Abort an unresolvable legacy backfill

- **GIVEN** an existing RelationshipEvaluation cannot map uniquely to a current Relationship definition position
- **WHEN** the ordinal migration runs
- **THEN** migration aborts with an actionable non-secret error
- **AND** it does not guess an ordinal, delete the row, or alter its analytical payload
