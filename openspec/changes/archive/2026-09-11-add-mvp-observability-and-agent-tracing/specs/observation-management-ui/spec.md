## ADDED Requirements

### Requirement: Metric Lens editor provides advisory query preflight
The Metric Lens editor SHALL provide a `Validate query` action that invokes the existing Metric preflight API with the current source ID, exact provider-native query, and a fixed `15m` validation window. The action SHALL be available only when the local source and query fields are valid, SHALL NOT mutate the Observation draft, and SHALL NOT be required before `Apply changes` or final Observation persistence.

#### Scenario: Valid single-series query
- **GIVEN** a locally valid Metric source and query
- **WHEN** the user activates `Validate query` and preflight returns `valid=true`
- **THEN** the editor shows an accessible success result containing the resolved validation window, returned label set, and sample count
- **AND** the Observation draft remains unchanged until the user activates `Apply changes`

#### Scenario: Validation is advisory
- **GIVEN** query validation has not run, failed, or returned `valid=false`
- **WHEN** all existing Metric Lens fields satisfy their local contract
- **THEN** `Apply changes` remains governed only by the existing Metric Lens validation rules

### Requirement: Metric preflight failures provide actionable feedback
The editor SHALL distinguish successful-empty, multiple-series, query-rejected, authentication/authorization, provider-unavailable, generic provider-failure, and request-failure outcomes without rewriting the configured query. Provider-authored messages and returned label values SHALL be rendered as untrusted text. Multiple-series feedback SHALL show the bounded series count and label sets returned by the existing API and SHALL explain that one Metric Lens must resolve to exactly one series.

#### Scenario: Query returns multiple series
- **WHEN** preflight returns `valid=false`, `code=multiple_series_returned`, a series count, and bounded label sets
- **THEN** the editor shows the count and label sets
- **AND** it advises the user to aggregate the query or select one label combination without automatically changing the query

#### Scenario: Query is rejected by Prometheus
- **WHEN** preflight returns `valid=false`, `code=query_rejected`, and a bounded message
- **THEN** the editor displays that message as text associated with the query validation result
- **AND** it does not interpret, normalize, or rewrite PromQL

#### Scenario: Query returns no series
- **WHEN** preflight returns `valid=false`, `code=no_series_returned`
- **THEN** the editor explains that the query produced no series for the validation window without claiming the syntax is invalid

#### Scenario: Source authentication or availability fails
- **WHEN** preflight responds with a safe API error for authentication, authorization, provider availability, or generic provider failure
- **THEN** the editor identifies the source-side category, offers retry, and exposes no credential or backend diagnostic detail

### Requirement: Metric preflight state is race-safe and invalidated by input changes
The editor SHALL distinguish idle, pending, valid, invalid, and request-failure states. Starting a new validation SHALL cancel or supersede the previous request; changing the source or query after a result SHALL remove the stale result; leaving the editor SHALL abort active validation. A late response from an obsolete request SHALL NOT replace state for newer inputs or a different draft Lens.

#### Scenario: Source or query changes after validation
- **GIVEN** the editor displays a completed preflight result
- **WHEN** the user changes the selected source or any query character
- **THEN** the previous result is cleared immediately and is not presented as validation of the new values

#### Scenario: New validation supersedes an old request
- **WHEN** the user starts another validation before the previous request completes
- **THEN** the previous request is aborted or ignored
- **AND** only the newest request may update the visible validation result

#### Scenario: Editor is closed during validation
- **WHEN** the user cancels or navigates away while preflight is pending
- **THEN** the request is aborted and its later outcome does not modify retained draft or editor state

### Requirement: Metric preflight sends no browser-visible credential material
The frontend SHALL send only the current source ID, exact query, and fixed validation duration to the existing preflight endpoint. It SHALL NOT receive, reconstruct, store, or send Prometheus credentials, source authorization data, backend agent traces, or operational log content.

#### Scenario: Validation request is inspected
- **WHEN** a Metric preflight browser request is created
- **THEN** its body contains exactly `source_id`, `query`, and `validation_window.duration=15m`
- **AND** no credential, authorization, trace, or unrelated Observation draft field is present

