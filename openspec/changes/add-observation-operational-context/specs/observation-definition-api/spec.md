## ADDED Requirements

### Requirement: Store optional Observation operational context

The Observation Definition aggregate SHALL accept an optional top-level `operational_context` text value on create and complete replacement. Omission or explicit `null` SHALL mean no context. A non-null value SHALL contain non-whitespace content and no more than 4,000 Unicode code points; valid text, including line breaks and surrounding whitespace, SHALL round-trip without rewriting. Invalid context SHALL reject the complete aggregate request as a client-validation error without persistence. The canonical create, replace, and detail responses SHALL include the value or `null`; compact list summaries SHALL omit the full text. This backward-compatible extension SHALL leave `schema_version` at `1` and SHALL not alter Observation or Lens identity, topology, knowledge scope, or runtime state.

#### Scenario: Create and read a contextual Observation
- **GIVEN** a valid Observation create request includes a multi-line operational context
- **WHEN** the aggregate is created and later read by detail endpoint
- **THEN** both canonical responses contain the exact accepted text
- **AND** the list summary remains compact without the text

#### Scenario: Read an older definition without context
- **GIVEN** a stored Observation predates this field
- **WHEN** the client reads its definition
- **THEN** its canonical detail response contains `operational_context: null`
- **AND** the definition remains valid at schema version `1`

#### Scenario: Replace or clear context atomically
- **GIVEN** an existing Observation has operational context
- **WHEN** a valid complete replacement changes it, or omits it to clear it
- **THEN** the returned and stored definition contains respectively the new exact text or `null`
- **AND** the replacement remains one atomic aggregate mutation

#### Scenario: Reject blank or oversized context
- **GIVEN** an otherwise valid create or replacement request contains whitespace-only context or more than 4,000 Unicode code points
- **WHEN** the request is submitted
- **THEN** the system returns a client-validation error associated with `operational_context`
- **AND** no part of the aggregate is created or changed
