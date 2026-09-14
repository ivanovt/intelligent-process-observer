# metric-source-overview-ui Specification

## Purpose

Provide safe read-only visibility and environment-configuration guidance for the Prometheus sources available to Metric Lens configuration.

## Requirements

### Requirement: Present Metric sources in the Data Sources product area
The system SHALL provide a `/data-sources` page within the shared IPO shell and SHALL make the existing `Data Sources` navigation item interactive and active on that route. The page SHALL identify Metric sources as environment-managed Prometheus configuration and SHALL NOT present source create, edit, delete, enable, disable, or credential-management controls.

#### Scenario: Open Data Sources
- **WHEN** a user activates `Data Sources` in the main navigation
- **THEN** the Data Sources page is shown within the existing IPO shell
- **AND** the navigation item is marked active
- **AND** no application-managed source lifecycle control is present

### Requirement: List every safely projected configured Metric source
The system SHALL retrieve Metric-source availability from `GET /api/v1/observation-definition-capabilities`. For every returned Prometheus source, the page SHALL preserve the existing compact default presentation of provider type, stable machine-readable ID, human-readable name, and availability for Metric Lens configuration. It SHALL preserve the returned source ordering and SHALL provide access to the source's API-supplied non-secret configuration without presenting any source lifecycle or connection-test behavior.

The page SHALL NOT display or infer bearer tokens, Basic-auth passwords, masked secret values, Authorization data, rejected unsafe URL values, raw environment JSON, connection health, or provider diagnostics. A production-safe source endpoint supplied by the API, credential type, and Basic-auth username MAY appear only in the user-requested configuration detail view.

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
- **AND** secrets, rejected unsafe URL values, connection health, and diagnostics remain absent even after details are expanded

### Requirement: Inspect a source's non-secret configuration on demand
Each configured source SHALL provide an accessible control that independently expands or collapses a detail pane for that source. The control SHALL expose its expanded state and identify the pane it controls. Expanding one source SHALL retain the compact source summary and show the API-supplied `configuration` object as valid pretty-formatted JSON in a horizontally scrollable, read-only code container. Collapsing the source SHALL remove that detail pane without changing source data or other source disclosure states.

The formatted JSON SHALL preserve the configuration field names and scalar values received from the API, use two-space indentation, and contain no fabricated redaction keys or placeholders. When the API omits an unsafe `base_url`, the UI SHALL render the supplied configuration as-is without adding `base_url`, the rejected value, a placeholder, a reason, a validity/health indicator, or a diagnostic. Expanding or collapsing details SHALL make no network request and SHALL not create, mutate, test, enable, or disable a source.

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

#### Scenario: Display a source whose unsafe base URL was omitted
- **GIVEN** the capabilities response contains a source configuration without `base_url`
- **WHEN** that source's JSON detail is expanded
- **THEN** the pane shows the exact supplied ID, name, and credential projection without a `base_url` member
- **AND** it does not add a rejected URL value, placeholder, reason, validity/health indicator, or diagnostic

### Requirement: Provide explicit loading, failure, empty, and refresh behavior
The Data Sources page SHALL distinguish loading, retryable request failure, a successful empty Metric-source registry, and one or more configured sources. A retry or refresh action SHALL request the same capabilities endpoint again without creating, mutating, or testing a source.

#### Scenario: Load Metric-source availability
- **WHEN** the capabilities request is pending
- **THEN** the page presents an explicit loading state
- **AND** does not present the registry as empty or configured

#### Scenario: Fail to load Metric-source availability
- **WHEN** the capabilities request fails
- **THEN** the page presents an error notice and retry action
- **AND** does not present the failure as an empty registry

#### Scenario: Refresh after environment configuration
- **WHEN** a user activates refresh after the backend has restarted with updated environment configuration
- **THEN** the page requests capabilities again
- **AND** replaces the displayed loading, error, empty, or configured state with the latest successful response

### Requirement: Explain environment-managed multi-source configuration safely
When no Metric source is available, the page SHALL explain that `PROMETHEUS_SOURCES` is an optional JSON array in the backend root environment, that multiple entries are supported, and that backend restart is required after changes. It SHALL show placeholder-only examples for the accepted Bearer-token and Basic-auth shapes and SHALL clearly identify them as non-production values.

The guidance SHALL state that real credentials belong only in local or deployment environment configuration, never in frontend environment variables or committed files. It SHALL NOT provide an in-browser credential form, write `.env`, or imply that refresh can reload a running backend's Settings.

#### Scenario: Guide an empty registry
- **WHEN** the capabilities request succeeds with no Metric sources
- **THEN** the page shows safe `PROMETHEUS_SOURCES` setup guidance and both accepted placeholder credential shapes
- **AND** explains backend restart followed by page refresh
- **AND** provides no browser-based persistence control

#### Scenario: Describe multiple sources
- **WHEN** setup guidance is shown
- **THEN** it explains that each JSON-array entry requires a unique stable ID, display name, base URL, and exactly one accepted credential shape
- **AND** explains that all successfully configured entries become Metric Lens source choices

### Requirement: Keep configured sources selectable by Metric Lenses
The Metric Lens editor SHALL continue to offer every source returned by the capabilities API and SHALL preserve the exact selected source ID in the Observation draft and final aggregate payload. The Data Sources overview SHALL not introduce a default or fallback source.

#### Scenario: Select one of multiple configured sources
- **GIVEN** the capabilities response contains more than one Prometheus source
- **WHEN** a user configures a Metric Lens
- **THEN** every returned source is available as a distinct choice by name
- **AND** the chosen source's exact ID is retained in the Metric Lens configuration

#### Scenario: Keep Metric Apply unavailable without a source
- **WHEN** no Metric source is configured
- **THEN** Metric Lens Apply remains unavailable under the existing Observation Management behavior
- **AND** the Data Sources page explains how an operator can configure the backend environment
