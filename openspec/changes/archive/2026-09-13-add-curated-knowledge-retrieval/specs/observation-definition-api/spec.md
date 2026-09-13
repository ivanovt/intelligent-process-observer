## ADDED Requirements

### Requirement: Store optional Observation knowledge scope independently of analytical evidence

Observation Definition create and replacement requests SHALL accept an optional `knowledge_scope`.
When present, it SHALL contain one or more unique canonical service IDs and an optional opaque
non-whitespace service-version label. The canonical definition response SHALL preserve the scope
exactly. The scope SHALL remain semantic context for approved knowledge retrieval only; it SHALL
not alter Lens configuration, Metric/Alert acquisition, Relationship evaluation, evidence catalog
construction, findings, execution scheduling, or persisted history identity.

Omitting `knowledge_scope` SHALL remain valid and SHALL preserve compatibility with existing
definitions. The API SHALL reject an empty scope, duplicate or blank service IDs, a blank version,
or undeclared fields without partially replacing a persisted definition.

#### Scenario: Persist explicit knowledge scope
- **GIVEN** a valid Observation create request includes service ID `mprm-server` and version `2.x`
- **WHEN** the definition is created and later read
- **THEN** the canonical definition retains that exact knowledge scope
- **AND** its Lens and Relationship representations remain unchanged

#### Scenario: Preserve an unscoped definition
- **GIVEN** a valid Observation request omits `knowledge_scope`
- **WHEN** it is created or replaced
- **THEN** the request remains valid and the canonical definition has no knowledge scope
- **AND** no service applicability is inferred or persisted by the API
