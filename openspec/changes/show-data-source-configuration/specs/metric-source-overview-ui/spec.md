## MODIFIED Requirements

### Requirement: List every safely projected configured Metric source

The system SHALL retrieve Metric-source availability from `GET /api/v1/observation-definition-capabilities`. For every returned Prometheus source, the page SHALL preserve the existing compact default presentation of provider type, stable machine-readable ID, human-readable name, and availability for Metric Lens configuration. It SHALL preserve the returned source ordering and SHALL provide access to the source's API-supplied non-secret configuration without presenting any source lifecycle or connection-test behavior.

The page SHALL NOT display or infer bearer tokens, Basic-auth passwords, masked secret values, Authorization data, raw environment JSON, connection health, or provider diagnostics. The source endpoint, credential type, and Basic-auth username MAY appear only in the user-requested configuration detail view.

#### Scenario: List multiple configured Prometheus sources

- **GIVEN** the capabilities response contains multiple Prometheus sources
- **WHEN** the Data Sources request succeeds
- **THEN** every returned source is displayed once in returned order with its exact ID and name
- **AND** each source is identified as available for Metric Lens configuration
- **AND** each source's configuration detail is collapsed by default

#### Scenario: Keep secret and operational data private

- **WHEN** configured sources or their expanded details are displayed
- **THEN** no bearer token, Basic-auth password, masked secret value, Authorization data, raw environment JSON, connection health, or provider diagnostic is present in browser-visible data

#### Scenario: Keep connection configuration private

- **WHEN** configured source summaries are displayed without a user expanding their details
- **THEN** no source endpoint, credential type, Basic-auth username, secret, connection health, or diagnostic is present in the compact view
- **AND** secrets, connection health, and diagnostics remain absent even after details are expanded

## ADDED Requirements

### Requirement: Inspect a source's non-secret configuration on demand

Each configured source SHALL provide an accessible control that independently expands or collapses a detail pane for that source. The control SHALL expose its expanded state and identify the pane it controls. Expanding one source SHALL retain the compact source summary and show the API-supplied `configuration` object as valid pretty-formatted JSON in a horizontally scrollable, read-only code container. Collapsing the source SHALL remove that detail pane without changing source data or other source disclosure states.

The formatted JSON SHALL preserve the configuration field names and scalar values received from the API, use two-space indentation, and contain no fabricated redaction keys or placeholders. Expanding or collapsing details SHALL make no network request and SHALL not create, mutate, test, enable, or disable a source.

#### Scenario: Expand one configured source

- **GIVEN** configured sources are shown with their detail panes collapsed
- **WHEN** a user activates one source's configuration control
- **THEN** that control reports the expanded state
- **AND** its associated pane shows the source's non-secret configuration as two-space-indented JSON
- **AND** the source's compact summary remains visible

#### Scenario: Keep disclosures independent

- **GIVEN** multiple configured sources are shown
- **WHEN** a user expands one source
- **THEN** no other source is expanded or collapsed as a side effect

#### Scenario: Collapse an expanded source

- **GIVEN** a source's configuration pane is expanded
- **WHEN** the user activates its configuration control again
- **THEN** the pane is removed and the control reports the collapsed state
- **AND** no source data or server state changes

#### Scenario: Display Basic-auth configuration without its password

- **GIVEN** a Basic-auth source configuration is expanded
- **WHEN** the JSON detail is rendered
- **THEN** it includes the source ID, name, base URL, credential type, and username supplied by the API
- **AND** it contains no password field, masked password, or redaction placeholder

#### Scenario: Display Bearer configuration without its token

- **GIVEN** a Bearer-token source configuration is expanded
- **WHEN** the JSON detail is rendered
- **THEN** it includes the source ID, name, base URL, and credential type supplied by the API
- **AND** it contains no token field, masked token, or redaction placeholder
