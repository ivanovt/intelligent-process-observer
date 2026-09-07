## MODIFIED Requirements

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

## ADDED Requirements

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
