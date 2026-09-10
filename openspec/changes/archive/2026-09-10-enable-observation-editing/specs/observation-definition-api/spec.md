## MODIFIED Requirements

### Requirement: Persist Alert Lenses as owned definition data

The system SHALL persist Alert Lenses as ordered children owned by their Observation Definition. Recognized scalar and ordered-list values SHALL round-trip without loss or reordering, and no Alert Lens SHALL have an independent persistence lifecycle outside its parent aggregate.

Replacing an Observation Definition SHALL treat `alert_lenses` as the desired complete ordered snapshot. Alert Lenses present in the request SHALL be created or replaced as owned rows, and previously owned Alert Lenses omitted from the request SHALL be physically removed in the same transaction. Deleting an Observation Definition through the supported repository/database boundary SHALL cascade to its Alert Lens definition data so no orphan Alert Lens remains. The system SHALL NOT expose a standalone Alert Lens update or delete endpoint or introduce an independent soft-delete lifecycle.

#### Scenario: Round-trip ordered Alert children

- **GIVEN** an Observation is created with multiple Alert Lenses and ordered list properties
- **WHEN** the aggregate is read through repository and API projections
- **THEN** every recognized Alert value and each configured order match the accepted input

#### Scenario: Replace ordered Alert children

- **GIVEN** an Observation owns multiple Alert Lenses
- **WHEN** a valid aggregate replacement changes one Alert Lens, adds another, reorders the collection, and omits an existing Alert Lens
- **THEN** the canonical definition contains exactly the submitted Alert Lens snapshot in submitted order
- **AND** the omitted Alert Lens has no remaining owned definition row

#### Scenario: Cascade owned Alert rows on parent deletion

- **GIVEN** an Observation Definition without deletion-blocking runtime dependents owns Alert Lens definitions
- **WHEN** the parent is deleted through the repository/database boundary
- **THEN** all of its Alert Lens definition data is deleted in the same transaction and no orphan remains

## ADDED Requirements

### Requirement: Replace an existing Observation definition atomically

The system SHALL expose `PUT /api/v1/observations/{observation_id}` to replace the complete mutable configuration of one existing Observation Definition. The request SHALL use the same public aggregate fields and validation rules as `ObservationCreate`: `name`, optional `description`, `objective`, ordered Metric `lenses`, ordered `alert_lenses`, and ordered `relationships`. The request SHALL NOT accept Observation identity, `schema_version`, runtime state, or runtime artifacts.

The replacement SHALL preserve the Observation's opaque `id`, `schema_version`, creation order, and existing relative Observation `href`. It SHALL atomically replace metadata and all three owned ordered child collections using the submitted values as the desired final snapshot. Any invalid metadata, child, enabled-source reference, type-local identity set, or Relationship topology SHALL reject the complete request without changing the stored definition. A successful replacement SHALL return HTTP `200 OK` with the complete canonical persisted definition. An unknown Observation identity SHALL return `404 Not Found` without persistence.

#### Scenario: Replace the complete configuration

- **GIVEN** an existing Observation has metadata, Metric Lenses, Alert Lenses, and Relationships
- **WHEN** a client submits a valid full replacement that edits metadata and existing children, adds children, removes children, and changes collection order
- **THEN** the system returns `200 OK` with the same Observation identity and a canonical definition matching the submitted mutable snapshot
- **AND** no omitted owned child remains in the persisted definition

#### Scenario: Preserve aggregate identity and version

- **GIVEN** an existing Observation Definition has a stable identity, schema version, and creation position
- **WHEN** it is replaced successfully
- **THEN** its `id`, `schema_version`, `href`, and relative position in the definitions list remain unchanged

#### Scenario: Reject an invalid replacement atomically

- **GIVEN** a replacement has no Lens overall, an unavailable Metric source, an invalid child, duplicate type-local IDs, or an invalid Relationship topology
- **WHEN** the client submits the replacement
- **THEN** the system returns a client-validation error
- **AND** the previously persisted metadata and all owned child collections remain unchanged

#### Scenario: Reject replacement of an unknown definition

- **WHEN** a client replaces an Observation identity that does not exist
- **THEN** the system returns `404 Not Found`
- **AND** no Observation or owned child is created or changed

### Requirement: Isolate definition replacement from Observation runs

A successful definition replacement SHALL affect only Observation Runs initialized after the replacement commits. An already initialized run SHALL continue using its frozen definition snapshot, and existing runtime records, results, evaluations, and reports SHALL remain unchanged.

Metric History identity SHALL retain its accepted `observation_id + lens_id` behavior. Editing a persisted Metric Lens while preserving its `id` SHALL preserve that identity's existing History continuity. Removing that Lens and adding a new Metric Lens with a newly generated `id` SHALL establish a new History identity with no candidates from the removed Lens ID.

#### Scenario: Replace a definition during an active run

- **GIVEN** an Observation Run has already frozen its definition snapshot
- **WHEN** the Observation Definition is replaced before that run finishes
- **THEN** the active run continues with its frozen metadata, Lens topology, provider configuration, and Relationships
- **AND** a later run loads the replacement definition

#### Scenario: Preserve History for a stable Metric Lens identity

- **GIVEN** an edited Metric Lens retains its existing `lens_id`
- **WHEN** a future Metric LensRun evaluates persisted History
- **THEN** accepted earlier results with that same `observation_id + lens_id` remain eligible under the existing History rules

#### Scenario: Start fresh History with a new Metric Lens identity

- **GIVEN** an existing Metric Lens is removed and a replacement Metric Lens is added with a new `lens_id`
- **WHEN** the replacement Lens first runs
- **THEN** results stored under the removed Lens ID are not eligible for its History
