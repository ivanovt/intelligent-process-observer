## ADDED Requirements

### Requirement: Mark deterministic report finding facts for safe visual emphasis

The deterministic Markdown renderer SHALL mark report-local finding numbers and factual values it emits with renderer-owned strong-emphasis delimiters. This includes factual Metric/Lens identifiers, UTC timestamps, durations, and numeric measurements with their supplied units when they are rendered as deterministic report content. The renderer SHALL not alter, heuristically parse, or apply Markdown formatting to model-authored or source-authored prose; such prose remains escaped inert text. Strong emphasis is presentation only and SHALL not change finding order, source ownership, traceability, analytical meaning, certainty, or the exact identity/value represented.

#### Scenario: Emphasize deterministic finding facts without changing content

- **GIVEN** a rendered report includes a displayed finding number and deterministic Metric/Lens, timestamp, duration, and numeric measurement values
- **WHEN** the Markdown report is built
- **THEN** each applicable renderer-owned factual value is enclosed in valid strong-emphasis Markdown
- **AND** its visible text, source association, units, and analytical meaning remain unchanged

#### Scenario: Keep model prose inert

- **GIVEN** a model-authored finding presentation contains Markdown-like strong-emphasis syntax or text that resembles a metric, timestamp, duration, or number
- **WHEN** the report is built
- **THEN** the model-authored text is escaped as inert prose rather than being reformatted by the renderer
- **AND** it cannot create additional formatting, document structure, links, or executable content
