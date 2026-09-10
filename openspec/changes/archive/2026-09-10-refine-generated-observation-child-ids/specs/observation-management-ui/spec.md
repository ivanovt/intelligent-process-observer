## MODIFIED Requirements

### Requirement: Generate stable IDs for new Observation children
The Metric Lens, Alert Lens, and Relationship editors SHALL generate the new child's ID when the user leaves its name field after entering a non-whitespace name and the child does not already have an ID. The generated ID SHALL have the exact composition `<type-prefix>_<normalized-name>_<random-part>` and SHALL match the public identifier syntax `^[a-z][a-z0-9_-]*$`. Metric Lens IDs SHALL use `metr`, Alert Lens IDs SHALL use `alrt`, and Relationship IDs SHALL use `rel` as their type prefix. The random part SHALL contain eight lowercase hexadecimal characters generated from browser-provided randomness. The complete ID SHALL NOT exceed 255 characters.

Name normalization SHALL apply Unicode NFKD decomposition, remove Unicode combining marks, convert the result to lowercase, replace each sequence of remaining characters outside ASCII `a-z0-9` with one underscore, and remove leading and trailing underscores. When normalization produces no leading ASCII lowercase letter, the normalized-name segment SHALL fall back to `item`. The UI SHALL truncate only the normalized-name segment as needed to keep the complete generated ID within 255 characters; it SHALL preserve the type prefix and random part.

The generated value SHALL avoid a duplicate among the relevant current draft collection. Metric IDs SHALL be compared only with other Metric IDs, Alert IDs only with other Alert IDs, and Relationship IDs only with other Relationship IDs; the backend contract's allowance for cross-type Lens ID equality SHALL remain unchanged. If the initial random candidate already exists, the UI SHALL append `_2` and increment the numeric discriminator until the candidate is unique. For every collision attempt, it SHALL further truncate only the normalized-name segment as needed to preserve the type prefix, random part, complete discriminator, identifier syntax, and 255-character maximum.

The editors SHALL NOT present the child ID as an input or other editable form control. Once generated, the ID SHALL appear as secondary non-editable text adjacent to the Name field identity, formatted as `(id: <generated-id>)` and exposed as text to assistive technology. Before generation, the Name field guidance SHALL explain that the ID is generated after the initial non-empty name is entered. Once a new child receives an ID, later name edits SHALL NOT regenerate or otherwise change it. Reopening an already-applied draft child SHALL display and preserve its existing ID exactly, including an ID created before this typed format was introduced. ID generation and editor cancellation SHALL make no HTTP write and SHALL not mutate the aggregate draft until `Apply changes` succeeds.

#### Scenario: Generate a Metric Lens ID from its initial name
- **GIVEN** a new Metric Lens has no ID
- **WHEN** the user enters `Cooling Pressure` as its name and leaves the name field
- **THEN** the editor displays secondary identity text matching `(id: metr_cooling_pressure_<random-part>)`
- **AND** the random part contains eight lowercase hexadecimal characters
- **AND** the generated ID satisfies the public identifier syntax
- **AND** no separate Lens ID input is present

#### Scenario: Generate IDs with each child type prefix
- **WHEN** the UI generates IDs for a Metric Lens, an Alert Lens, and a Relationship
- **THEN** their IDs begin with `metr_`, `alrt_`, and `rel_` respectively
- **AND** each ID retains the normalized-name and random components

#### Scenario: Keep a generated ID stable after renaming
- **GIVEN** a new child has received a generated ID
- **WHEN** the user changes its name and leaves the name field again
- **THEN** the generated ID remains unchanged
- **AND** the secondary identity text continues to show that unchanged value

#### Scenario: Preserve an existing draft child ID
- **GIVEN** an already-applied Metric Lens, Alert Lens, or Relationship is reopened for editing
- **WHEN** its editor is displayed or its name is changed
- **THEN** its existing ID remains unchanged even when it does not use the new typed prefix
- **AND** the existing ID is presented as secondary non-editable identity text rather than an input

#### Scenario: Generate a valid fallback ID
- **GIVEN** a new Alert Lens has no ID
- **WHEN** the user enters a non-whitespace name whose normalization has no leading lowercase Latin letter and leaves the name field
- **THEN** the generated ID matches `alrt_item_<random-part>`
- **AND** it satisfies the public identifier syntax

#### Scenario: Normalize decomposable Latin diacritics consistently
- **GIVEN** a new Relationship has no ID
- **WHEN** the user enters `Crème Pressure` as its name and leaves the name field
- **THEN** the generated ID begins with `rel_creme_pressure_`
- **AND** the remaining random part contains eight lowercase hexadecimal characters

#### Scenario: Bound an ID generated from a long name
- **GIVEN** a new child has a name whose normalized-name segment would make the generated ID longer than 255 characters
- **WHEN** the name is committed
- **THEN** the UI truncates the normalized-name segment
- **AND** the generated ID preserves its complete type prefix and random part, satisfies the public identifier syntax, and is at most 255 characters long

#### Scenario: Avoid a same-collection collision
- **GIVEN** the relevant draft collection already contains the initial generated candidate
- **WHEN** a new child receives the same normalized name and random part
- **THEN** the editor displays a distinct valid ID produced by adding or incrementing a numeric discriminator
- **AND** any required additional normalized-name truncation keeps the complete ID at most 255 characters long

#### Scenario: Preserve type-local Lens identity
- **GIVEN** existing persisted or draft Metric and Alert Lenses use equal legacy IDs
- **WHEN** the UI displays or submits those existing values
- **THEN** it preserves both IDs unchanged
- **AND** the backend identifier grammar and type-local uniqueness behavior remain unchanged

#### Scenario: Leave the ID empty for a blank name
- **GIVEN** a new child has no ID
- **WHEN** the user leaves a name field containing only whitespace
- **THEN** no ID is generated or displayed
- **AND** the Name guidance explains when generation occurs
- **AND** the existing required-name validation remains applicable

#### Scenario: Cancel after local ID generation
- **GIVEN** a nested editor has generated an ID in editor-local state
- **WHEN** the user cancels the editor
- **THEN** the aggregate Observation draft remains unchanged
- **AND** no HTTP write request is made
