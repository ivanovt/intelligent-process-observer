## Purpose

Provide a resilient, read-only runtime feed for the Overview that preserves usable run information while explicitly representing records whose complete public run summary cannot be validated.

## ADDED Requirements

### Requirement: Expose a resilient Overview runtime feed

The system SHALL expose `GET /api/v1/overview-runtime` and return one newest-first non-paginated item for every persisted ObservationRun. Each item SHALL be exactly one of:

- `available`: the existing complete validated `ObservationRunSummary`; or
- `limited`: a safe minimal projection containing the run ID, Observation ID/name, created time, each independently valid lifecycle timestamp/status/duration field when available, `analytical_state=null`, and exact limitation code `runtime_projection_invalid`.

The endpoint SHALL attempt the complete existing summary projection for every record independently. One `RuntimeProjectionInvalid` SHALL produce a limited item only for that record and SHALL NOT suppress other available items. A limited item SHALL NOT expose the invalid analysis window, invalid analytical payload, raw execution context, validation details, internal exception, provider data, credentials, or fabricated replacement values.

#### Scenario: Return mixed available and limited runs

- **GIVEN** persisted history contains valid runs and a legacy run whose complete summary is invalid
- **WHEN** the Overview runtime feed is requested
- **THEN** valid runs are returned as available items and the invalid run as one limited item in durable newest-first order
- **AND** the response succeeds without hiding either kind

#### Scenario: Limit an invalid analysis window safely

- **GIVEN** a run has valid identity, Observation correlation, timestamps and execution status but lacks a valid analysis window
- **WHEN** it is projected for Overview
- **THEN** the limited item preserves the independently valid safe fields
- **AND** analytical state and analysis-window values remain unavailable rather than inferred

### Requirement: Report projection limitations explicitly

The response SHALL contain `limited_run_count`, equal to the number of limited items in that response. `limited_run_count=0` SHALL mean every returned item passed the complete summary projection; a positive count SHALL indicate incomplete Overview runtime coverage without classifying the underlying process state.

The endpoint SHALL still fail with the existing safe service error when the database query or response-level contract cannot be completed. It SHALL NOT turn infrastructure failure into an empty or partially invented feed.

#### Scenario: Count limited items

- **GIVEN** two of ten persisted runs cannot produce complete summaries
- **WHEN** the feed succeeds
- **THEN** it returns ten ordered items and `limited_run_count=2`

#### Scenario: Fail on unavailable persistence

- **WHEN** the runtime repository cannot complete the read
- **THEN** the endpoint returns a safe service failure
- **AND** it does not return an empty feed or reuse process-local state

### Requirement: Keep strict run APIs unchanged

The Overview runtime feed SHALL be a separate presentation projection. `GET /api/v1/observation-runs` and `GET /api/v1/observation-runs/{id}` SHALL retain their existing strict contracts and fail-closed behavior. Reading the Overview feed SHALL NOT start, resume, retry, cancel, repair, update, or delete any run or artifact.

#### Scenario: Preserve strict history behavior

- **GIVEN** one stored artifact violates the strict run contract
- **WHEN** a caller requests `GET /api/v1/observation-runs`
- **THEN** the existing endpoint continues to return `runtime_projection_invalid`
- **AND** the resilient behavior is available only through `GET /api/v1/overview-runtime`

#### Scenario: Keep the feed side-effect free

- **WHEN** the Overview feed is requested repeatedly
- **THEN** it performs no persistence or execution mutation
- **AND** later responses may reflect only independently committed durable progress
