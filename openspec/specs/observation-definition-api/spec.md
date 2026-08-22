# observation-definition-api Specification

## Purpose

Provide a versioned backend interface for storing, reading, navigating, and preflighting predefined Observation definitions before any Observation runtime execution exists.

## Requirements

### Requirement: Create an atomic, versioned Observation definition

The system SHALL expose `POST /api/v1/observations` to atomically create one predefined Observation definition with its ordered Lens definitions and Relationships. It SHALL generate an opaque stable Observation identity and return the complete persisted definition with HTTP `201 Created`.

The request SHALL contain non-empty `name` and free-form `objective`, optional `description`, `lenses`, and `relationships`. Clients SHALL NOT provide `schema_version`; the server SHALL persist and return the current positive integer version, initially `1`. Definition representations SHALL NOT contain ObservationRun, LensRun, execution status, results, scheduling, timeout, retry, concurrency, or other runtime data.

Lens and Relationship IDs SHALL be unique within the Observation and match `^[a-z][a-z0-9_-]*$`. Their names SHALL be non-empty but may repeat. Submission order SHALL be preserved for presentation only and SHALL have no execution meaning. An invalid member or relationship SHALL reject the entire aggregate without persistence.

#### Scenario: Create a complete valid definition

- **GIVEN** a request has valid Observation metadata, Lens definitions, and Relationships
- **WHEN** the client sends `POST /api/v1/observations`
- **THEN** the system returns `201 Created` with a generated identity, `schema_version: 1`, and the same ordered topology without runtime objects

#### Scenario: Reject an invalid definition atomically

- **GIVEN** a create request has an invalid Lens configuration or Relationship
- **WHEN** the client creates the Observation
- **THEN** the system returns a client-validation error and persists none of the request

### Requirement: Define supported Metric Lenses

Each implemented Lens SHALL include its ID, non-empty name, optional description, `type: metric`, and an enabled compatible `adapter_type`/`source_id` pair. The first implementation SHALL enable only the `prometheus` Metric adapter; Alert and Log Lens creation are deferred to later adapter-integration changes.

A Metric Lens SHALL include non-empty free-form `metric_id` and `unit`, adapter-native `query`, explicit duplicate-free `analysis_objectives`, and explicit duplicate-free `reference_periods`. Objectives SHALL be any subset of `spike`, `drift`, and `oscillation`. Reference offsets SHALL match `^[1-9][0-9]*(m|h|d|w)$`; an empty list means no reference periods and SHALL not receive a default. The query SHALL be intended to resolve to exactly one series; aggregation SHALL be explicit in the query.

#### Scenario: Create a Prometheus Metric Lens

- **GIVEN** an Observation has a valid Metric Lens whose Prometheus adapter/source pair is enabled
- **WHEN** the client creates the Observation
- **THEN** the returned definition preserves its Metric configuration and order as owned definition data

#### Scenario: Reject unavailable acquisition configuration

- **GIVEN** a Lens names a disabled adapter, unknown source, incompatible source, or invalid type-specific configuration
- **WHEN** the client creates the Observation
- **THEN** the system returns a client-validation error and persists none of the request

### Requirement: Define engineer-authored Metric Relationships

The system SHALL permit zero or more Relationships with constrained unique ID, non-empty name, optional description, and 2..N distinct participant Lens IDs. Every participant SHALL be a Metric Lens and SHALL appear in a condition or expectation.

`conditions` and `expected` SHALL be Lens-ID-keyed nested maps. Conditions MAY be empty, meaning always applicable; expected behavior SHALL be non-empty. Descriptors for the same Lens SHALL be conjunctive. Rules SHALL allow only `trend.direction` of `increasing|decreasing|stable`, `trend.rate` of `slow|moderate|fast`, and `variability.state` of `low|moderate|high`. `unknown` and `not_classified` SHALL be rejected in configuration.

#### Scenario: Create a conditional Relationship

- **GIVEN** a Relationship has valid distinct Metric participants and allowed nested conditions/expectations
- **WHEN** the client creates the Observation
- **THEN** every participant resolves to an owned Metric Lens and the Relationship is persisted

#### Scenario: Create an always-applicable Relationship

- **GIVEN** a Relationship has valid participants, empty conditions, and non-empty expected behavior
- **WHEN** the client creates the Observation
- **THEN** the system persists the Relationship as always applicable

#### Scenario: Reject invalid Relationship structure

- **GIVEN** a Relationship has invalid participants, unused participants, unsupported descriptors, or an evidence-quality value
- **WHEN** the client creates the Observation
- **THEN** the system returns a client-validation error and persists none of the request

### Requirement: Read and navigate definitions

The system SHALL expose `GET /api/v1/observations` and return all persisted definitions in deterministic creation order. Each item SHALL be compact: identity, metadata, schema version, and relative `href` references for all owned Lenses and Relationships, without inline full type-specific configuration or runtime data.

`GET /api/v1/observations/{observation_id}` SHALL return the complete definition with relative links. `GET /api/v1/observations/{observation_id}/lenses/{lens_id}` and `GET /api/v1/observations/{observation_id}/relationships/{relationship_id}` SHALL return complete linked owned resources. Unknown resources SHALL return HTTP `404 Not Found` without state changes.

#### Scenario: List compact definitions

- **GIVEN** definitions exist
- **WHEN** the client requests `GET /api/v1/observations`
- **THEN** the system returns `200 OK` with all compact summaries in creation order and relative owned-resource hrefs

#### Scenario: Follow a Lens link

- **GIVEN** an Observation summary provides a Lens href
- **WHEN** the client requests that href
- **THEN** the system returns `200 OK` with the full Lens definition and parent Observation href

### Requirement: Discover enabled Metric acquisition capabilities

The system SHALL expose `GET /api/v1/observation-definition-capabilities`. It SHALL return the enabled Metric adapter type `prometheus` and compatible stable source IDs with human-readable names. It SHALL NOT expose credentials, endpoint URLs, or connection details.

#### Scenario: Read enabled sources

- **GIVEN** configured sources are enabled
- **WHEN** the client requests the capability endpoint
- **THEN** the system returns `200 OK` with Metric Lens type, `prometheus`, source ID, and source name without secret connection data

### Requirement: Preflight candidate Metric Lenses without persistence

The system SHALL expose non-persisting `POST /api/v1/observation-lens-validations/metric`. It SHALL accept only the candidate Prometheus acquisition fields and a relative `validation_window.duration` using the reference-offset grammar. It SHALL not require or create an Observation, Lens, or runtime object.

Metric preflight SHALL send a POST range query to the configured Prometheus source with adapter-selected sampling resolution, a 15-second server timeout, and no automatic retry. A successful response SHALL return `valid: true` only for exactly one series and include resolved timestamps, step, labels, all samples, and provider warnings. Samples SHALL have UTC timestamp and `value_status` of `finite|nan|positive_infinity|negative_infinity`; finite values are numbers and all other values are `null`. Zero/multiple series and rejected PromQL SHALL return `200 OK` and `valid: false`; multiple series SHALL include bounded label-set diagnostics.

Malformed input SHALL return `4xx`; Prometheus authentication/authorization rejection SHALL return `401`/`403`; transport, timeout, provider outage, and unexpected adapter failure SHALL return `5xx`. Client errors SHALL use a machine-readable envelope with stable code, message, and field path where applicable.

#### Scenario: Validate a single Metric series

- **GIVEN** a valid candidate Metric query executes against an enabled source and resolves to one series over `60m`
- **WHEN** the client sends Metric preflight
- **THEN** the system returns `200 OK`, window/step metadata, labels, and all typed samples without persistence

#### Scenario: Report an unsuitable Metric query

- **GIVEN** a valid candidate Metric query executes but resolves to multiple series
- **WHEN** the client sends Metric preflight
- **THEN** the system returns `200 OK`, `valid: false`, a cardinality error code, and bounded label-set diagnostics without persistence
