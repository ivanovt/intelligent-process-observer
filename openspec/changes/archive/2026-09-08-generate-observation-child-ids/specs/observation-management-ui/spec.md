## MODIFIED Requirements

### Requirement: Place management in the Observations product area
The system SHALL present Observation management under the existing `Observations` navigation area using the frozen UI Direction v1.2 shell, hierarchy, terminology, and restrained engineering-dashboard visual language. It SHALL provide routes for the definitions list, read-only definition inspection, aggregate creation, and nested Metric Lens, Alert Lens, and Relationship editors without exposing a separate Admin area.

The management capability SHALL NOT expose monitoring/run-analysis screens, Observation update/delete controls, standalone Lens lifecycle controls, Log Lens configuration, dark-mode controls, or unsupported agent, model, prompt, tool-budget, severity, confidence, recommendation, or runtime-relationship configuration.

#### Scenario: Enter Observation management
- **WHEN** a user selects `Observations` in the application navigation
- **THEN** the Observation definitions list is shown within the shared ObserveAI shell
- **AND** no separate Admin navigation area is present

#### Scenario: Keep later UI out of scope
- **WHEN** a user navigates through the Observation Management flow
- **THEN** the UI exposes only definition list, read-only definition inspection, aggregate creation, and the three supported nested configuration editors
- **AND** it does not expose monitoring or run-analysis screens

## ADDED Requirements

### Requirement: Generate stable IDs for new Observation children
The Metric Lens, Alert Lens, and Relationship editors SHALL generate the new child's ID when the user leaves its name field after entering a non-whitespace name and the child does not already have an ID. The generated ID SHALL combine a normalized name-derived prefix with the lowercase base-36 encoding of the generation time in Unix epoch milliseconds and SHALL match the public identifier syntax `^[a-z][a-z0-9_-]*$`. Its total length SHALL NOT exceed 255 characters.

Name normalization SHALL apply Unicode NFKD decomposition, remove Unicode combining marks, convert the result to lowercase, replace each sequence of remaining characters outside ASCII `a-z0-9` with one underscore, and remove leading and trailing underscores. When normalization produces no leading ASCII lowercase letter, the prefix SHALL fall back to the child type: `metric`, `alert`, or `relationship`. The UI SHALL truncate only the normalized prefix as needed to keep the complete generated ID within 255 characters; it SHALL preserve the timestamp suffix.

The generated value SHALL avoid a duplicate among the relevant current draft collection. Metric IDs SHALL be compared only with other Metric IDs, Alert IDs only with other Alert IDs, and Relationship IDs only with other Relationship IDs; cross-type equality between one Metric ID and one Alert ID SHALL remain valid. If the initial timestamp-derived candidate already exists, the UI SHALL append `_2` and increment the numeric discriminator until the candidate is unique. For every collision attempt, it SHALL further truncate only the normalized prefix as needed to preserve the timestamp, complete discriminator, identifier syntax, and 255-character maximum.

The ID control SHALL be read-only. Once a new child receives an ID, later name edits SHALL NOT regenerate or otherwise change it. Reopening an already-applied draft child SHALL preserve its existing ID. ID generation and editor cancellation SHALL make no HTTP write and SHALL not mutate the aggregate draft until `Apply changes` succeeds.

#### Scenario: Generate a Metric Lens ID from its initial name
- **GIVEN** a new Metric Lens has no ID
- **WHEN** the user enters `Cooling Pressure` as its name and leaves the name field
- **THEN** the editor displays a read-only ID with the prefix `cooling_pressure_` followed by a timestamp-derived lowercase alphanumeric suffix
- **AND** the generated ID satisfies the public identifier syntax

#### Scenario: Keep a generated ID stable after renaming
- **GIVEN** a new child has received a generated ID
- **WHEN** the user changes its name and leaves the name field again
- **THEN** the generated ID remains unchanged

#### Scenario: Preserve an existing draft child ID
- **GIVEN** an already-applied Metric Lens, Alert Lens, or Relationship is reopened for editing
- **WHEN** its editor is displayed or its name is changed
- **THEN** its existing ID remains unchanged and read-only

#### Scenario: Generate a valid fallback ID
- **GIVEN** a new Alert Lens has no ID
- **WHEN** the user enters a non-whitespace name whose normalization has no leading lowercase Latin letter and leaves the name field
- **THEN** the generated ID begins with `alert_`
- **AND** it satisfies the public identifier syntax

#### Scenario: Normalize decomposable Latin diacritics consistently
- **GIVEN** a new Relationship has no ID
- **WHEN** the user enters `Crème Pressure` as its name and leaves the name field
- **THEN** the generated ID begins with `creme_pressure_`
- **AND** the remaining suffix is the lowercase base-36 generation timestamp

#### Scenario: Bound an ID generated from a long name
- **GIVEN** a new child has a name whose normalized prefix would make the generated ID longer than 255 characters
- **WHEN** the name is committed
- **THEN** the UI truncates the normalized prefix
- **AND** the generated ID preserves its complete timestamp suffix, satisfies the public identifier syntax, and is at most 255 characters long

#### Scenario: Avoid a same-collection collision
- **GIVEN** the relevant draft collection already contains the initial generated candidate
- **WHEN** a new child ID is generated from the same normalized name and timestamp component
- **THEN** the editor displays a distinct valid ID produced by adding or incrementing a numeric discriminator
- **AND** any required additional prefix truncation keeps the complete ID at most 255 characters long

#### Scenario: Preserve type-local Lens identity
- **GIVEN** an Alert Lens already has the same candidate ID that will be generated for a new Metric Lens
- **WHEN** the Metric Lens name is committed
- **THEN** the Metric editor may retain that candidate because no other Metric Lens uses it

#### Scenario: Leave the ID empty for a blank name
- **GIVEN** a new child has no ID
- **WHEN** the user leaves a name field containing only whitespace
- **THEN** no ID is generated
- **AND** the existing required-name validation remains applicable

#### Scenario: Cancel after local ID generation
- **GIVEN** a nested editor has generated an ID in editor-local state
- **WHEN** the user cancels the editor
- **THEN** the aggregate Observation draft remains unchanged
- **AND** no HTTP write request is made
