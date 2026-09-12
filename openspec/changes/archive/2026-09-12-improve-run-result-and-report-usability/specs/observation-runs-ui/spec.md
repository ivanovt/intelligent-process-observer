## ADDED Requirements

### Requirement: Present Metric run evidence through explicit semantic fields

The run-detail Metrics section SHALL render accepted Metric result fields explicitly rather than enumerating arbitrary runtime object entries or applying generic object-to-string conversion. For a usable result, it SHALL present the Metric reference and unit as the primary Lens identity, retain a compact Lens ID as secondary traceability, and keep current numerical evidence, semantic state, optional analytical results, reference-period comparisons, and History visually distinct.

Numerical values SHALL use consistent bounded display precision without changing persisted values. Mean, standard deviation, minimum, and maximum SHALL be formatted for scanning; slope SHALL retain enough significant precision to distinguish a small non-zero value from zero. Reference-period presentation SHALL show current and reference means plus the accepted `relative_level_change` using an explicit label such as `symmetric relative change`; it SHALL NOT describe that value as ordinary percentage increase or decrease. Full exact values remain available from the unchanged run-detail payload and are not rewritten or persisted by the UI.

Optional `spike`, `oscillation`, and `stuck_signal` results SHALL display their semantic state and relevant accepted evidence when present. Explicit `absent` and `unknown` states SHALL remain distinct from a `null` or omitted result, which SHALL be labeled only as unavailable in this result because the public artifact does not preserve whether the tool was unrequested, not applicable, or otherwise produced no semantic section. None of these cases SHALL render as `[object Object]`, the literal word `null`, zero, normality, or a fabricated result.

#### Scenario: Inspect usable Metric evidence

- **GIVEN** a completed Metric result contains numerical evidence, semantic current state, and a successful spike result
- **WHEN** the Metrics section renders
- **THEN** the user sees named formatted numerical values and the spike state/evidence in separate semantic groups
- **AND** no structured object is coerced into generic text

#### Scenario: Preserve a small non-zero slope

- **GIVEN** a Metric slope is finite, non-zero, and smaller than the normal fixed-decimal display threshold
- **WHEN** it is formatted for the UI
- **THEN** the display retains a meaningful non-zero representation
- **AND** the underlying value is not rounded or persisted differently

#### Scenario: Explain symmetric reference change

- **GIVEN** current mean `2.28`, reference mean `1.04`, and `relative_level_change=0.7456`
- **WHEN** reference evidence is displayed
- **THEN** the UI identifies `0.7456` as a symmetric relative change rather than “74.56% higher”
- **AND** current and reference means are both visible for interpretation

#### Scenario: Preserve only supported optional-analysis distinctions

- **GIVEN** one optional result is explicitly `unknown`, another is explicitly `absent`, and a third is `null`
- **WHEN** the Metric result renders
- **THEN** the explicit states use distinct labels and the null result is labeled unavailable in this result
- **AND** the UI does not infer whether the null result was unrequested, not applicable, failed, or otherwise unproduced

### Requirement: Make structured analysis traceability understandable on demand

The Analysis section SHALL keep Finding, Hypothesis, Evidence, Relationship, and Knowledge semantics distinct while making each available reference inspectable. A collapsed reference control SHALL show a concise human label based on source type and compact source identity. Expanding or focusing it SHALL reveal the exact source ID, a human-readable locator path, and the referenced value or state when that value can be resolved from the already loaded run-detail response.

The UI SHALL resolve references without fetching provider data, changing analysis, interpreting knowledge as evidence, or inventing a value when the locator is absent or cannot be resolved. Multiple references to the same source but different locators SHALL remain distinguishable. Unknown source types, missing source artifacts, and invalid locator paths SHALL show traceability unavailable rather than throwing, hiding the finding, or displaying a fabricated value.

#### Scenario: Inspect two references to one Metric result

- **GIVEN** one finding cites `current_state.trend.direction` and `evidence.current.mean` from the same LensRun
- **WHEN** its reference controls render
- **THEN** their collapsed labels or expanded details distinguish the two locator paths
- **AND** each resolves to the corresponding already-loaded value

#### Scenario: Preserve unresolved traceability honestly

- **GIVEN** a reference identifies a missing source or an unresolvable locator
- **WHEN** the Analysis section renders
- **THEN** the finding remains visible and the reference reports that traceability is unavailable
- **AND** the UI performs no provider request and invents no replacement value

### Requirement: Present persisted Markdown as a safe formatted report with exact-copy access

The Report section SHALL present non-empty persisted Markdown as a readable document rather than as one raw preformatted block. Without adding a dependency, it SHALL support the renderer-owned subset needed for headings, paragraphs, blockquotes, unordered lists, and inline code. All report content SHALL be inserted as text; raw HTML SHALL not be interpreted, links SHALL not become active navigation, and unsupported Markdown constructs SHALL fall back to visible plain text rather than being dropped or executed.

The existing `Copy Markdown` action SHALL copy the exact persisted `report.content` byte-for-byte. The formatted view SHALL not create, remove, reorder, summarize, or reinterpret analytical content. Legacy or alternate valid Markdown layouts SHALL remain readable through the safe fallback behavior.

#### Scenario: Read a generated report

- **GIVEN** persisted report content contains renderer-owned headings, blockquotes, lists, and inline-code identifiers
- **WHEN** the Report section renders
- **THEN** those structures are presented with accessible semantic HTML and readable spacing
- **AND** Markdown control characters are not shown as ordinary report prose

#### Scenario: Copy exact Markdown

- **GIVEN** a formatted report is visible
- **WHEN** the user activates `Copy Markdown`
- **THEN** the clipboard receives the exact persisted Markdown content
- **AND** formatting the visible document has not mutated the artifact

#### Scenario: Render unsupported or hostile content safely

- **GIVEN** a persisted legacy report contains raw HTML, a Markdown link, or an unsupported construct
- **WHEN** the Report section renders
- **THEN** the content remains visible as inert text or safe fallback text
- **AND** no HTML executes and no active link or new analytical structure is created

### Requirement: Use meaning-oriented absence language in run analysis views

Completed Analysis and Report views SHALL describe empty findings, hypotheses, limitations, relationships, and optional evidence in terms of what the completed result contains or supports, not in terms of database persistence. Empty wording SHALL preserve the distinction between “none produced,” “not available,” and “execution not complete,” and SHALL NOT infer normality, absence of cause, or complete evidence coverage.

#### Scenario: Explain empty hypotheses after successful analysis

- **GIVEN** Observation analysis completed with findings and no hypotheses
- **WHEN** the Analysis section renders
- **THEN** it states that no knowledge-grounded possible explanation was produced
- **AND** it does not say that nothing was persisted or that no cause exists

#### Scenario: Keep unavailable distinct from empty

- **GIVEN** one run has completed analysis with an empty collection and another run has no analysis artifact
- **WHEN** each run detail renders
- **THEN** the first communicates a valid empty analytical result
- **AND** the second communicates unavailable analysis without treating it as empty or normal
