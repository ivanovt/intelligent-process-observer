## MODIFIED Requirements

### Requirement: Make structured analysis traceability understandable on demand

The Analysis section SHALL keep Finding, Hypothesis, Evidence, Relationship, and Knowledge semantics distinct while making each available reference inspectable. Each finding that has Evidence or Relationship references SHALL place all of its reference controls in one accessible `References` disclosure that is collapsed when the finding first renders. Expanding that container SHALL expose the existing independently collapsed reference controls; each control's concise label SHALL show its source type, compact source identity, and locator. Expanding or focusing an individual control SHALL reveal the exact source ID, a human-readable locator path, and the referenced value or state when that value can be resolved from the already loaded run-detail response.

The UI SHALL resolve references without fetching provider data, changing analysis, interpreting knowledge as evidence, or inventing a value when the locator is absent or cannot be resolved. Multiple references to the same source but different locators SHALL remain distinguishable. Unknown source types, missing source artifacts, and invalid locator paths SHALL show traceability unavailable rather than throwing, hiding the finding, or displaying a fabricated value. Findings with no Evidence or Relationship references SHALL not render an empty `References` disclosure; Knowledge references SHALL remain separately presented with their owning hypothesis.

#### Scenario: Open a finding's references only when needed

- **GIVEN** one finding has multiple Metric-result and Relationship-evaluation references
- **WHEN** the Analysis section first renders
- **THEN** the finding statement is visible while its `References` container is collapsed
- **AND** expanding the container exposes distinct collapsed controls for every reference without fetching additional data

#### Scenario: Inspect two references to one Metric result

- **GIVEN** one finding cites `current_state.trend.direction` and `evidence.current.mean` from the same LensRun
- **WHEN** its `References` container and each reference control are expanded
- **THEN** the controls distinguish the two locator paths and show their corresponding already-loaded values

#### Scenario: Preserve unresolved traceability honestly

- **GIVEN** a reference identifies a missing source or an unresolvable locator
- **WHEN** its owning finding's `References` container and reference control are expanded
- **THEN** the finding remains visible and the reference reports that traceability is unavailable
- **AND** the UI performs no provider request and invents no replacement value

### Requirement: Present persisted Markdown as a safe formatted report with exact-copy access

The Report section SHALL present non-empty persisted Markdown as a readable document rather than as one raw preformatted block. Without adding a dependency, it SHALL support the renderer-owned subset needed for headings, paragraphs, blockquotes, unordered lists, inline code, and strong emphasis. Strong emphasis SHALL render as semantic `<strong>` text only for well-formed renderer-owned `**text**` spans; raw HTML SHALL not be interpreted, links SHALL not become active navigation, and unsupported or malformed Markdown constructs SHALL fall back to visible plain text rather than being dropped or executed. All report content SHALL be inserted as text.

The rendered report SHALL visually emphasize deterministic finding numbers and factual values marked by the report renderer, including Metric/Lens identifiers, timestamps, durations, and numeric measurements with their units, without creating, removing, reordering, summarizing, or reinterpreting analytical content. The existing `Copy Markdown` action SHALL copy the exact persisted `report.content` byte-for-byte; visible formatting SHALL not mutate the artifact. Legacy or alternate valid Markdown layouts SHALL remain readable through the safe fallback behavior.

#### Scenario: Read a generated report

- **GIVEN** persisted report content contains renderer-owned headings, blockquotes, lists, inline-code identifiers, and strong-emphasis spans for finding numbers and factual values
- **WHEN** the Report section renders
- **THEN** those structures are presented with accessible semantic HTML, readable spacing, and semantic strong text for the emphasized values
- **AND** Markdown control characters for the supported constructs are not shown as ordinary report prose

#### Scenario: Copy exact Markdown

- **GIVEN** a formatted report is visible
- **WHEN** the user activates `Copy Markdown`
- **THEN** the clipboard receives the exact persisted Markdown content
- **AND** formatting the visible document has not mutated the artifact

#### Scenario: Render unsupported or hostile content safely

- **GIVEN** a persisted legacy report contains raw HTML, a Markdown link, malformed strong emphasis, or an unsupported construct
- **WHEN** the Report section renders
- **THEN** the content remains visible as inert text or safe fallback text
- **AND** no HTML executes and no active link or new analytical structure is created

## ADDED Requirements

### Requirement: Keep Summary result cards independently sized

The Summary section SHALL present availability/limitations and key findings as separate cards without stretching the availability/limitations card to match the height of a longer Key findings card. Each card SHALL retain its own content-driven height while preserving the existing responsive two-column layout and all availability, limitation, and finding content.

#### Scenario: Show short limitations beside many findings

- **GIVEN** a completed analysis has a short availability/limitations list and multiple long key findings
- **WHEN** the Summary section renders at a two-column viewport
- **THEN** the availability/limitations card ends after its own content and does not display unused warning-surface space below it
- **AND** Key findings remains visible in its independent card
