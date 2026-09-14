## ADDED Requirements

### Requirement: Freeze and project operational context for one Observation Run

An accepted Observation Run SHALL freeze the configured `operational_context` with its detached definition snapshot. Reasoning and Report Generation SHALL receive the same frozen value through their respective compact semantic contexts. The value SHALL NOT be projected to Metric or Alert Lens agents, Relationship evaluation, data acquisition, the knowledge-scope suggestion flow, evidence catalogs, or persisted analytical result and report contracts. A later definition replacement SHALL affect only runs initialized after it commits.

#### Scenario: Preserve context through a concurrent definition edit
- **GIVEN** an Observation Run has initialized with context A
- **WHEN** its definition is replaced with context B before reasoning or reporting
- **THEN** both downstream agents for the active run receive context A
- **AND** a later run receives context B

#### Scenario: Preserve absence without changing execution
- **GIVEN** an existing Observation Definition has no operational context
- **WHEN** an Observation Run executes
- **THEN** Reasoning and Report Generation receive an absent optional context
- **AND** the run follows the same existing execution and persistence semantics

#### Scenario: Keep the note out of Lens and evidence boundaries
- **GIVEN** a run has operational context
- **WHEN** Lens assignments, Relationship evaluation, and evidence catalog inputs are constructed
- **THEN** the text is absent from those inputs
- **AND** it does not change scope, data selection, tool budgets, or evidence identity
