## ADDED Requirements

### Requirement: Render report identity and traceability as safe human-readable Markdown

The deterministic report renderer SHALL preserve every source identity and traceability reference while presenting them in concise human-readable Markdown. Observation IDs, run IDs, finding IDs, hypothesis IDs, source types, source IDs, knowledge references, and locator segments SHALL remain exact and unambiguous, but the rendered labels SHALL NOT expose implementation encodings such as `uuid=`, `string=`, quoted Python representations, hexadecimal list indices, or backslash-escaped punctuation as visible report prose.

Evidence locators SHALL be rendered as familiar field paths with decimal indices, such as `evidence.current.mean` or `reference_periods[0]`, while remaining reversibly associated with the exact structured locator. Untrusted source and model prose SHALL remain escaped so it cannot create Markdown structure, links, HTML, or executable content. Improving readability SHALL NOT remove traceability, alter source identifiers, or allow model-authored document structure.

#### Scenario: Render readable identities

- **GIVEN** a report has UUID Observation/run identities and string finding identifiers
- **WHEN** deterministic Markdown is produced
- **THEN** each exact identifier is presented with an English label and safe inline-code styling
- **AND** visible text contains no type prefix, Python quoting wrapper, or hexadecimal encoding

#### Scenario: Render readable evidence paths

- **GIVEN** a finding cites a Metric evidence locator containing string keys and an array index
- **WHEN** the reference is rendered
- **THEN** the exact source type and source ID remain present
- **AND** the locator is shown as a conventional dotted path with a decimal bracketed index

#### Scenario: Contain hostile traceability text

- **GIVEN** an opaque source identifier or locator segment contains Markdown punctuation, HTML-like text, or line breaks
- **WHEN** deterministic rendering executes
- **THEN** the value remains plain non-executable content within the renderer-owned structure
- **AND** it cannot create a heading, list item, link, HTML element, or additional report section

### Requirement: Describe empty analytical collections in meaning-oriented language

When the source analysis contains no hypotheses, the report SHALL state that no knowledge-grounded possible explanation was produced; it SHALL NOT imply a confirmed absence of causes or describe persistence implementation. When the source contains no limitations, the report SHALL state that no analysis limitation was identified in the supplied result; it SHALL NOT imply that the observed process or system is universally free of limitations. Existing empty-finding wording and presentation-only boundaries remain unchanged.

#### Scenario: Present no hypotheses

- **GIVEN** the source analysis contains findings but `hypotheses=[]`
- **WHEN** the report is rendered
- **THEN** it states that no knowledge-grounded possible explanation was produced
- **AND** it does not say that no cause exists, fabricate an explanation, or mention database persistence

#### Scenario: Present no limitations

- **GIVEN** the source analysis contains `limitations=[]`
- **WHEN** the report is rendered
- **THEN** it states that the supplied analysis identified no limitation
- **AND** it does not claim unlimited evidence coverage or system certainty
