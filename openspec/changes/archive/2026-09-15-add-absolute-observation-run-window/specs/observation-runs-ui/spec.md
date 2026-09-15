## MODIFIED Requirements

### Requirement: Launch a run from a Grafana-inspired time-range dialog

The Runs screen SHALL provide a `Run Observation` action that opens an accessible dialog and independently requests current Observation Definitions from `GET /api/v1/observations`; it SHALL NOT derive launch choices only from run history. The dialog SHALL distinguish definition loading, retryable definition-request failure, successful empty definitions, and successful non-empty definitions. Confirmation SHALL remain disabled until definitions load successfully and the user selects one eligible definition. Failure SHALL offer Retry without presenting an empty collection. A successful empty collection SHALL explain that no Observation is available and offer navigation to `New Observation`.

Every returned definition SHALL appear exactly once in deterministic API order, including an Observation with no prior run. Current run history SHALL only annotate/disable definitions known to have `pending|running` runs; stale or racing history remains subject to authoritative server conflict handling. Closing the dialog SHALL abort an in-flight definition request and SHALL NOT launch or mutate a run.

The dialog SHALL contain an Observation selector and three mutually exclusive time-range modes. `Relative range` SHALL include `Last 5 minutes`, `Last 15 minutes`, `Last 30 minutes`, `Last 1 hour`, `Last 3 hours`, `Last 6 hours`, `Last 12 hours`, `Last 24 hours`, `Last 2 days`, and `Last 7 days`. `Expressions` SHALL contain `From` and `To` fields and support exactly `now`, `now-15m`, and `now-1h`. `Absolute UTC` SHALL contain explicitly UTC-labeled `From` and `To` date-time fields that accept valid calendar values with second-level precision and do not interpret them in the browser's local timezone. The initial mode SHALL remain `Relative range` with `Last 15 minutes`, equivalent at confirmation to `now-15m` through `now`.

The client SHALL resolve the selected mode against one captured current instant per validation or confirmation attempt, produce aware UTC timestamps, require `from < to` and a non-future end, show the concrete UTC range for review, and submit only those concrete timestamps to `POST /api/v1/observation-runs`. It SHALL reject an absent or invalid absolute endpoint and unsupported Grafana expressions rather than partially parse, normalize, or guess them. Switching among modes SHALL NOT reinterpret an absolute wall-clock value as browser-local time.

Observation choices SHALL identify any currently active Observation and disable it with explanatory text. The server SHALL remain authoritative: a race returning `409 Conflict` SHALL update the feedback with the existing active run and SHALL NOT be treated as successful duplicate execution.

#### Scenario: Launch from a relative preset

- **WHEN** a user selects an eligible Observation and `Last 1 hour` and confirms
- **THEN** the UI resolves one UTC window ending at the captured current instant and beginning exactly one hour earlier
- **AND** submits one launch request with concrete timestamps

#### Scenario: Load a never-run Observation

- **GIVEN** an Observation Definition exists but no run-history item references it
- **WHEN** the definition request succeeds and the dialog renders choices
- **THEN** that Observation is selectable exactly once in API order
- **AND** no synthetic run-history item is required

#### Scenario: Definitions are still loading

- **WHEN** the launch dialog's definition request is pending
- **THEN** it presents a loading state and disables confirmation
- **AND** does not infer choices from run history

#### Scenario: Definition loading fails

- **WHEN** the definition request fails
- **THEN** the dialog presents retryable error feedback and disables confirmation
- **AND** does not present the failure as an empty definition collection

#### Scenario: No definitions exist

- **WHEN** the definition request succeeds with an empty array
- **THEN** the dialog presents an explicit no-Observations state with a `New Observation` action
- **AND** sends no launch request

#### Scenario: Retry definition loading

- **GIVEN** definition loading previously failed
- **WHEN** the user activates Retry and the request succeeds
- **THEN** the selector shows the returned definitions
- **AND** confirmation remains disabled until an eligible definition is selected

#### Scenario: Launch from supported expressions

- **WHEN** a user enters `now-15m` for From and `now` for To and confirms
- **THEN** both expressions resolve from the same captured current instant
- **AND** the submitted window spans exactly 15 minutes

#### Scenario: Launch an absolute UTC interval

- **WHEN** a user enters `2026-09-10 10:00:00 UTC` for From and `2026-09-10 17:00:00 UTC` for To and confirms after that interval
- **THEN** the dialog previews and submits the exact canonical UTC timestamps `2026-09-10T10:00:00.000Z` and `2026-09-10T17:00:00.000Z`
- **AND** the values are unchanged by the browser's local timezone

#### Scenario: Reject an incomplete or invalid absolute interval

- **WHEN** either absolute endpoint is absent or is not a valid UTC calendar date-time
- **THEN** the dialog presents actionable validation feedback and disables confirmation
- **AND** sends no launch request

#### Scenario: Reject a reversed absolute interval

- **WHEN** an absolute From value is equal to or later than its To value
- **THEN** the dialog explains that From must be earlier than To
- **AND** sends no launch request

#### Scenario: Reject a future absolute interval

- **WHEN** an absolute To value is later than the captured current instant
- **THEN** the dialog explains that To cannot be in the future
- **AND** sends no launch request

#### Scenario: Reject unsupported date math

- **WHEN** a user enters an expression other than `now`, `now-15m`, or `now-1h`
- **THEN** the dialog presents actionable validation feedback
- **AND** sends no launch request

#### Scenario: Block a known active Observation

- **GIVEN** the loaded history contains an active run for an Observation
- **WHEN** the launch dialog opens
- **THEN** that Observation cannot be selected for another run
- **AND** other eligible Observations remain selectable

#### Scenario: Close while definitions are loading

- **WHEN** the user closes the dialog during the definition request
- **THEN** the request is aborted and no run is launched
- **AND** reopening starts a fresh definition load
