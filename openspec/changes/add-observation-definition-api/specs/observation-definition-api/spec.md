## Purpose

Provide a versioned backend interface for storing, reading, navigating, and preflighting predefined Observation definitions before any Observation runtime execution exists.

## ADDED Requirements

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

### Requirement: Define supported typed Lenses

Each Lens SHALL include its ID, non-empty name, optional description, and one `type`: `metric`, `alert`, or `log`. Its `adapter_type` and `source_id` SHALL be currently enabled and compatible.

A Metric Lens SHALL include non-empty free-form `metric_id` and `unit`, adapter-native `query`, explicit duplicate-free `analysis_objectives`, and explicit duplicate-free `reference_periods`. Objectives SHALL be any subset of `spike`, `drift`, and `oscillation`. Reference offsets SHALL match `^[1-9][0-9]*(m|h|d|w)$`; an empty list means no reference periods and SHALL not receive a default. The query SHALL be intended to resolve to exactly one series; aggregation SHALL be explicit in the query.

An Alert Lens SHALL include an adapter-native scope `query` and explicit duplicate-free reference offsets using the same grammar. The query SHALL NOT establish runtime time windows.

A Log Lens SHALL include adapter-native `query`, explicit duplicate-free reference offsets, and non-empty ordered `level_parsing.strategies` of label, JSON-field, or regex extractors. The first non-empty extracted value SHALL win. Mapping SHALL trim whitespace and compare case-insensitively to `error`, `warning`, `info`, `debug`, `trace`, or `unknown`; unmatched/extraction failures SHALL yield `unknown`.

#### Scenario: Create all supported Lens types
- **GIVEN** an Observation has valid Metric, Alert, and Log Lenses whose adapter/source pairs are enabled
- **WHEN** the client creates the Observation
- **THEN** the returned definition preserves their types, metadata, configurations, and order as owned definitions

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

### Requirement: Discover enabled acquisition capabilities

The system SHALL expose `GET /api/v1/observation-definition-capabilities`. It SHALL return enabled adapters grouped by Lens type and compatible stable source IDs with human-readable names. It SHALL NOT expose credentials, endpoint URLs, or connection details.

#### Scenario: Read enabled sources
- **GIVEN** configured sources are enabled
- **WHEN** the client requests the capability endpoint
- **THEN** the system returns `200 OK` with Lens type, adapter type, source ID, and source name without secret connection data

### Requirement: Preflight candidate Lenses without persistence

The system SHALL expose non-persisting `POST /api/v1/observation-lens-validations/metric`, `/alert`, and `/log`. Each SHALL accept only acquisition/parsing fields relevant to the Lens type and a relative `validation_window.duration` using the reference-offset grammar. No preflight SHALL require or create an Observation, Lens, or runtime object.

Metric preflight SHALL use adapter-selected sampling resolution and return `valid: true` only for exactly one series. A successful response SHALL include resolved timestamps, step, labels, and all samples. Samples SHALL have UTC timestamp and `value_status` of `finite|nan|positive_infinity|negative_infinity`; finite values are numbers and all other values are `null`. Zero/multiple series SHALL return `200 OK` and `valid: false`; multiple series SHALL include bounded label-set diagnostics.

Alert/Log preflight SHALL return `200 OK` and `valid: true` for every successful provider query, including zero records. Adapter-selected bounded raw, unchanged provider previews SHALL be transient. Alert output SHALL include total count, preview limit, and truncation. Log output SHALL also include level distribution, unknown count, and parsing warnings, but SHALL not annotate individual raw records. Log sanitization remains required only for future LLM contexts.

Malformed input SHALL return `4xx`; unavailable adapter/source SHALL return `5xx`. Client errors SHALL use a machine-readable envelope with stable code, message, and field path where applicable.

#### Scenario: Validate a single Metric series
- **GIVEN** a valid candidate Metric query executes against an enabled source and resolves to one series over `60m`
- **WHEN** the client sends Metric preflight
- **THEN** the system returns `200 OK`, `valid: true`, window/step metadata, labels, and all typed samples without persistence

#### Scenario: Report an unsuitable Metric query
- **GIVEN** a valid candidate Metric query executes but resolves to multiple series
- **WHEN** the client sends Metric preflight
- **THEN** the system returns `200 OK`, `valid: false`, a cardinality error code, and bounded label-set diagnostics without persistence

#### Scenario: Preview Alert records
- **GIVEN** a valid Alert candidate query executes against an enabled source
- **WHEN** the client sends Alert preflight
- **THEN** the system returns `200 OK`, `valid: true`, total count, bounded raw preview, applied limit, and truncation state without persistence

#### Scenario: Warn about Log parsing quality
- **GIVEN** a valid Log query executes but its parsing strategies classify all matching records as `unknown`
- **WHEN** the client sends Log preflight
- **THEN** the system returns `200 OK`, `valid: true`, raw preview, aggregate parsing metadata, and a parsing warning without persistence
