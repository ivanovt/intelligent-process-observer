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
