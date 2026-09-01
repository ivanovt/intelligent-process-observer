## ADDED Requirements

### Requirement: Define supported Alert Lenses

Each Alert Lens in `alert_lenses` SHALL include an ID matching `^[a-z][a-z0-9_-]*$`, exact `type: alert`, a non-whitespace `name`, optional non-whitespace `description`, exact supported `source: jira_track_and_release`, and a `selector` whose required `query` contains non-whitespace content.

The selector query SHALL otherwise remain an opaque provider-native string. Validation, persistence, and reads SHALL NOT trim, normalize, parse, lint, rewrite, or add predicates to it.

`analysis_objectives` SHALL be an optional ordered duplicate-free list of non-whitespace opaque strings with default `[]`. It SHALL have no controlled vocabulary, maximum count, priority, inheritance, default hierarchy, or tool-selection meaning. `reference_periods` SHALL be an optional ordered duplicate-free list of string offsets with default `[]`; each item SHALL directly use the existing Metric reference-offset primitive `^[1-9][0-9]*(m|h|d|w)$` (for example `1d` or `7d`), SHALL NOT use an `{offset: ...}` wrapper, and no implicit reference period SHALL be added.

Unknown fields in an Alert Lens or its selector SHALL be accepted and ignored. They SHALL NOT be persisted or returned by canonical reads. Recognized fields SHALL remain subject to all validation rules.

#### Scenario: Create a valid Alert Lens with exact ordered values

- **GIVEN** an Alert Lens has a supported source, a query with non-whitespace content, ordered objectives, and ordered reference offsets
- **WHEN** the client creates its Observation definition
- **THEN** the returned Alert Lens preserves the exact query string value as supplied and preserves the configured objective and reference-period order

#### Scenario: Apply optional Alert defaults

- **GIVEN** a valid Alert Lens omits `description`, `analysis_objectives`, and `reference_periods`
- **WHEN** the client creates its Observation definition
- **THEN** the canonical response omits no required field and returns both optional lists as `[]`

#### Scenario: Ignore unknown Alert input fields

- **GIVEN** a valid Alert Lens and its selector contain unknown extra fields
- **WHEN** the client creates and later reads the Observation definition
- **THEN** the definition is accepted, the recognized values are preserved, and the unknown fields are absent from the canonical response

#### Scenario: Reject invalid Alert configuration atomically

- **GIVEN** an Alert Lens has an invalid ID or type, a blank name or description, an unsupported source, a missing or blank selector query, duplicate or blank objectives, or invalid or duplicate reference offsets
- **WHEN** the client creates its Observation definition
- **THEN** the system returns a client-validation error and persists none of the aggregate

### Requirement: Persist Alert Lenses as owned definition data

The system SHALL persist Alert Lenses as ordered children owned by their Observation Definition. Recognized scalar and ordered-list values SHALL round-trip without loss or reordering, and no Alert Lens SHALL have an independent persistence lifecycle outside its parent aggregate.

Deleting an Observation Definition through the supported repository/database boundary SHALL cascade to its Alert Lens definition data so no orphan Alert Lens remains. This change SHALL NOT expose a public Observation update/delete endpoint or a standalone Alert Lens endpoint. If a future aggregate replacement operation is introduced, Alert Lens removal SHALL follow the architecture-defined snapshot/replacement ownership semantics rather than an independent soft-delete lifecycle.

#### Scenario: Round-trip ordered Alert children

- **GIVEN** an Observation is created with multiple Alert Lenses and ordered list properties
- **WHEN** the aggregate is read through repository and API projections
- **THEN** every recognized Alert value and each configured order match the accepted input

#### Scenario: Cascade owned Alert rows on parent deletion

- **GIVEN** an Observation Definition without deletion-blocking runtime dependents owns Alert Lens definitions
- **WHEN** the parent is deleted through the repository/database boundary
- **THEN** all of its Alert Lens definition data is deleted in the same transaction and no orphan remains

## MODIFIED Requirements

### Requirement: Create an atomic, versioned Observation definition

The system SHALL expose `POST /api/v1/observations` to atomically create one predefined Observation definition with its ordered Metric `lenses`, ordered `alert_lenses`, and Relationships. It SHALL generate an opaque stable Observation identity and return the complete persisted definition with HTTP `201 Created`.

The request SHALL contain non-empty `name` and free-form `objective`, optional `description`, `lenses`, `alert_lenses`, and `relationships`. Omitted collections SHALL be treated as empty; in particular, omitted `alert_lenses` SHALL mean `[]`. The aggregate SHALL contain at least one Lens across `lenses` and `alert_lenses`. Clients SHALL NOT provide `schema_version`; the server SHALL persist and return the current positive integer version, which remains `1` for this backward-compatible API-v1 extension. Definition representations SHALL NOT contain ObservationRun, LensRun, execution status, results, scheduling, timeout, retry, concurrency, or other runtime data.

Metric Lens IDs SHALL be unique within `lenses`, Alert Lens IDs SHALL be unique within `alert_lenses`, and the same ID MAY occur once in each collection. Relationship IDs SHALL be unique within the Observation. Lens and Relationship IDs SHALL match `^[a-z][a-z0-9_-]*$`. Names SHALL satisfy their type-specific validation and may repeat. Submission order within each collection SHALL be preserved for presentation only and SHALL have no execution meaning. An invalid member or relationship SHALL reject the entire aggregate without persistence.

#### Scenario: Create a complete valid definition

- **GIVEN** a request has valid Observation metadata, Metric `lenses`, and Relationships and omits `alert_lenses`
- **WHEN** the client sends `POST /api/v1/observations`
- **THEN** the system returns `201 Created` with a generated identity, unchanged ordered Metric topology, `alert_lenses: []`, and no runtime objects

#### Scenario: Create an Alert-only definition

- **GIVEN** a request has no Metric Lenses, at least one valid Alert Lens, and no Relationships
- **WHEN** the client creates the Observation
- **THEN** the system returns the complete persisted Alert-only definition

#### Scenario: Create a mixed definition with type-local IDs

- **GIVEN** a request has valid Metric and Alert Lenses and one ID occurs once in each type-specific collection
- **WHEN** the client creates the Observation
- **THEN** the system accepts both Lenses as distinct type-aware definitions and preserves both collection orders

#### Scenario: Reject an invalid definition atomically

- **GIVEN** a create request has no Lens in either collection or has an invalid Lens or Relationship
- **WHEN** the client creates the Observation
- **THEN** the system returns a client-validation error and persists none of the request

### Requirement: Define supported Metric Lenses

Each Metric Lens in the existing `lenses` field SHALL include its ID, non-empty name, optional description, `type: metric`, and an enabled compatible `adapter_type`/`source_id` pair. The implementation SHALL continue to enable only the `prometheus` Metric adapter. The field SHALL NOT be renamed to or aliased as `metric_lenses`, and its existing request and response shape SHALL remain unchanged.

A Metric Lens SHALL include non-empty free-form `metric_id` and `unit`, adapter-native `query`, explicit duplicate-free `analysis_objectives`, and explicit duplicate-free `reference_periods`. Objectives SHALL be any subset of `spike`, `drift`, and `oscillation`. Reference offsets SHALL match `^[1-9][0-9]*(m|h|d|w)$`; an empty list means no reference periods and SHALL not receive a default. The query SHALL be intended to resolve to exactly one series; aggregation SHALL be explicit in the query.

#### Scenario: Create a Prometheus Metric Lens

- **GIVEN** an Observation has a valid Metric Lens in `lenses` whose Prometheus adapter/source pair is enabled
- **WHEN** the client creates the Observation
- **THEN** the returned definition preserves its existing Metric configuration and order as owned definition data

#### Scenario: Reject unavailable acquisition configuration

- **GIVEN** a Metric Lens names a disabled adapter, unknown source, incompatible source, or invalid type-specific configuration
- **WHEN** the client creates the Observation
- **THEN** the system returns a client-validation error and persists none of the request

### Requirement: Define engineer-authored Metric Relationships

The system SHALL permit zero or more Relationships with constrained unique ID, non-empty name, optional description, and 2..N distinct participant Lens IDs. Every participant SHALL resolve exclusively to a Metric Lens in `lenses` and SHALL appear in a condition or expectation. An Alert Lens with the same ID SHALL neither create ambiguity nor satisfy a participant reference.

`conditions` and `expected` SHALL be Lens-ID-keyed nested maps. Conditions MAY be empty, meaning always applicable; expected behavior SHALL be non-empty. Descriptors for the same Lens SHALL be conjunctive. Rules SHALL allow only `trend.direction` of `increasing|decreasing|stable`, `trend.rate` of `slow|moderate|fast`, and `variability.state` of `low|moderate|high`. `unknown` and `not_classified` SHALL be rejected in configuration.

#### Scenario: Create a conditional Relationship

- **GIVEN** a mixed Observation has a Relationship with valid distinct Metric participants and allowed nested conditions and expectations
- **WHEN** the client creates the Observation
- **THEN** every participant resolves to an owned Metric Lens in `lenses` and the Relationship is persisted

#### Scenario: Create an always-applicable Relationship

- **GIVEN** a Relationship has valid Metric participants, empty conditions, and non-empty expected behavior
- **WHEN** the client creates the Observation
- **THEN** the system persists the Relationship as always applicable

#### Scenario: Ignore a same-ID Alert Lens during participant resolution

- **GIVEN** a Metric Lens and an Alert Lens share an ID and a Relationship names that ID
- **WHEN** the aggregate topology is validated
- **THEN** the participant resolves only to the Metric Lens

#### Scenario: Reject an Alert-only Relationship participant

- **GIVEN** a Relationship participant ID exists only in `alert_lenses`
- **WHEN** the client creates the Observation
- **THEN** the system returns a client-validation error and persists none of the request

#### Scenario: Reject invalid Relationship structure

- **GIVEN** a Relationship has invalid participants, unused participants, unsupported descriptors, or an evidence-quality value
- **WHEN** the client creates the Observation
- **THEN** the system returns a client-validation error and persists none of the request

### Requirement: Read and navigate definitions

The system SHALL expose `GET /api/v1/observations` and return all persisted definitions in deterministic creation order. Each item SHALL be compact: identity, metadata, schema version, ordered relative `href` references in `lenses`, ordered relative `href` references in `alert_lenses`, and ordered Relationship references, without inline full type-specific configuration or runtime data. Canonical list and detail responses SHALL always contain `alert_lenses`, including `[]`, and SHALL preserve the existing `lenses` field and shape.

`GET /api/v1/observations/{observation_id}` SHALL return the complete definition with relative links. `GET /api/v1/observations/{observation_id}/lenses/{lens_id}` SHALL continue to return a complete owned Metric Lens. `GET /api/v1/observations/{observation_id}/alert-lenses/{lens_id}` SHALL return a complete owned Alert Lens. `GET /api/v1/observations/{observation_id}/relationships/{relationship_id}` SHALL return a complete linked owned Relationship. The type-specific paths SHALL remain unambiguous when a Metric Lens and Alert Lens share an ID. Unknown resources SHALL return HTTP `404 Not Found` without state changes.

#### Scenario: List compact definitions

- **GIVEN** Metric-only, Alert-only, and mixed definitions exist
- **WHEN** the client requests `GET /api/v1/observations`
- **THEN** the system returns `200 OK` with all compact summaries in creation order and independently ordered `lenses`, `alert_lenses`, and Relationship hrefs

#### Scenario: Follow a Lens link

- **GIVEN** an Observation summary provides a Metric Lens href in `lenses`
- **WHEN** the client requests that href
- **THEN** the system returns `200 OK` with the full Metric Lens definition and parent Observation href

#### Scenario: Follow an Alert Lens link

- **GIVEN** an Observation summary provides an Alert Lens href in `alert_lenses`
- **WHEN** the client requests that href
- **THEN** the system returns `200 OK` with only the recognized full Alert Lens definition and parent Observation href

#### Scenario: Resolve equal IDs through type-specific links

- **GIVEN** a mixed Observation has a Metric Lens and Alert Lens with the same ID
- **WHEN** the client follows each collection's href
- **THEN** each type-specific route returns the correct owned definition without ambiguity
