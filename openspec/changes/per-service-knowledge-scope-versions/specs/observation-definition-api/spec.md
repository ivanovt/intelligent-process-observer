## MODIFIED Requirements

### Requirement: Store optional Observation knowledge scope independently of analytical evidence

Observation Definition create and replacement requests SHALL accept an optional `knowledge_scope`. When present, it SHALL contain an ordered, non-empty collection of service entries. Each entry SHALL contain one unique, non-whitespace canonical service ID and its own optional opaque, non-whitespace service-version label. A missing or null label on one entry SHALL not assign a version to that service or to any other entry. The canonical definition response SHALL preserve the service order and each entry's own label, returning null for an omitted label.

The scope SHALL remain semantic context for approved knowledge retrieval only; it SHALL not alter Lens configuration, Metric/Alert acquisition, Relationship evaluation, evidence catalog construction, findings, execution scheduling, or persisted history identity. Omitting `knowledge_scope` SHALL remain valid and SHALL preserve compatibility with existing unscoped definitions.

Already-persisted scopes in the preceding shared-version format SHALL remain readable. A legacy scope with one shared version SHALL be represented canonically as that version on every service entry, preserving its previous retrieval meaning; a legacy scope without a version SHALL produce entries without versions. The API SHALL continue to accept valid legacy create/replacement payloads and normalize them to the per-service shape; canonical responses and newly persisted scopes SHALL use only the per-service shape. The API SHALL reject an empty scope, duplicate or blank service IDs, a blank entry version, mixed legacy/new fields, or undeclared fields without partially replacing a persisted definition.

#### Scenario: Persist different optional versions for different services
- **GIVEN** a valid Observation create request specifies service `mprm-server` at version `1.0` and service `gateway` without a version
- **WHEN** the definition is created and later read
- **THEN** the canonical response preserves both entries and their order, with `1.0` only on `mprm-server` and no version on `gateway`
- **AND** its Lens and Relationship representations remain unchanged

#### Scenario: Persist explicit knowledge scope
- **GIVEN** a valid Observation create request includes a service entry for `mprm-server` with version `2.x`
- **WHEN** the definition is created and later read
- **THEN** the canonical definition retains that exact service entry and version
- **AND** its Lens and Relationship representations remain unchanged

#### Scenario: Preserve an unscoped definition
- **GIVEN** a valid Observation request omits `knowledge_scope`
- **WHEN** it is created or replaced
- **THEN** the request remains valid and the canonical definition has no knowledge scope
- **AND** no service applicability is inferred or persisted by the API

#### Scenario: Read a previously persisted shared-version scope
- **GIVEN** an existing persisted Observation names `mprm-server` and `gateway` under one shared version `1.0`
- **WHEN** the definition is read after this change
- **THEN** the canonical response contains `mprm-server` at `1.0` and `gateway` at `1.0`
- **AND** a run initialized from that definition retains the same knowledge eligibility as before the change

#### Scenario: Accept a legacy request without preserving its old shape
- **GIVEN** a valid legacy create request names `mprm-server` and `gateway` with one shared version `1.0`
- **WHEN** the definition is created and read
- **THEN** the canonical response contains two service entries, each at `1.0`
- **AND** the persisted scope no longer uses the legacy shape

#### Scenario: Reject an invalid service entry atomically
- **GIVEN** an existing Observation definition has a valid knowledge scope
- **WHEN** a replacement submits duplicate or blank service IDs, a blank version, an empty service collection, mixed legacy/new fields, or an undeclared scope field
- **THEN** the request is rejected
- **AND** the previously persisted complete definition remains unchanged
