## MODIFIED Requirements

### Requirement: Persist correlated runtime executions without duplicating definitions

The system SHALL persist an `ObservationRun` as a runtime instance correlated with its existing Observation definition, and SHALL persist each `LensRun` as a runtime instance correlated with exactly one ObservationRun. Runtime records SHALL retain stable run identities, the Observation and Lens identities needed to correlate the execution, Lens type where applicable, lifecycle status, timestamps, structured reason/failure metadata when present, and producer-supplied provenance/execution context.

Within one ObservationRun, LensRun definition identity SHALL be the type-aware pair `(lens_type, lens_id)`. The same `lens_id` SHALL be permitted for different Lens types in the same ObservationRun, while duplicate LensRuns with the same `lens_type` and `lens_id` SHALL be rejected.

ObservationRun status SHALL be one of `pending`, `running`, `completed`, or `failed`, and its valid lifecycle direction SHALL be `pending -> running -> completed | failed`. ObservationRun SHALL NOT have status `partial`; a partial LensRun SHALL NOT imply a partial ObservationRun.

LensRun status SHALL be one of `pending`, `running`, `completed`, `partial`, or `failed`. Its terminal statuses SHALL be exactly `completed`, `partial`, and `failed`; its lifecycle direction SHALL be `pending -> running -> completed | partial | failed`.

Definition objects (`Observation`, `Lens`, and `Relationship`) SHALL remain definition data and SHALL NOT be represented as runtime records or copied into runtime storage as new definition aggregates.

#### Scenario: Store an in-progress runtime execution

- **GIVEN** an existing Observation definition and runtime identity/lifecycle metadata for a new execution
- **WHEN** the runtime persistence contract stores an ObservationRun and LensRun with status `pending`, then records them as `running`
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
- **WHEN** runtime persistence records it as `completed` or `failed`
- **THEN** the persisted lifecycle follows `pending -> running -> completed | failed` and does not expose `created` or `partial` as an ObservationRun status

#### Scenario: Retrieve a terminal LensRun with failure metadata

- **GIVEN** a LensRun is persisted with terminal status `failed` and a structured failure reason
- **WHEN** its enclosing ObservationRun is retrieved
- **THEN** the LensRun exposes the failed status and failure metadata as unavailable runtime evidence, not as an empty usable result
