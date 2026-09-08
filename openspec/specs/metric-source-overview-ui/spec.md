# metric-source-overview-ui Specification

## Purpose

Provide safe read-only visibility and environment-configuration guidance for the Prometheus sources available to Metric Lens configuration.

## Requirements

### Requirement: Present Metric sources in the Data Sources product area
The system SHALL provide a `/data-sources` page within the shared ObserveAI shell and SHALL make the existing `Data Sources` navigation item interactive and active on that route. The page SHALL identify Metric sources as environment-managed Prometheus configuration and SHALL NOT present source create, edit, delete, enable, disable, or credential-management controls.

#### Scenario: Open Data Sources
- **WHEN** a user activates `Data Sources` in the main navigation
- **THEN** the Data Sources page is shown within the existing ObserveAI shell
- **AND** the navigation item is marked active
- **AND** no application-managed source lifecycle control is present

### Requirement: List every safely projected configured Metric source
The system SHALL retrieve Metric-source availability from `GET /api/v1/observation-definition-capabilities`. For every returned Prometheus source, the page SHALL show its provider type, stable machine-readable ID, and human-readable name. It SHALL preserve the returned source ordering and SHALL NOT display or infer the configured base URL, credentials, Authorization data, Basic username, connection health, or other diagnostics.

#### Scenario: List multiple configured Prometheus sources
- **GIVEN** the capabilities response contains multiple Prometheus sources
- **WHEN** the Data Sources request succeeds
- **THEN** every returned source is displayed once in returned order with its exact ID and name
- **AND** each source is identified as available for Metric Lens configuration

#### Scenario: Keep connection configuration private
- **WHEN** configured sources are displayed
- **THEN** no source endpoint, secret, credential metadata, username, Authorization value, or inferred health state is present

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
