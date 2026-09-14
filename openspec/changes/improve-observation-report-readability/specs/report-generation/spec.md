## MODIFIED Requirements

### Requirement: Accept only the approved report-generation input boundary

The capability SHALL accept one strict `ObservationAnalysisResult` and minimal correlated report context containing the same `observation_id` and `observation_run_id`, an Observation name, optional description and analytical objective, and the exact UTC start and end of that run's immutable observed analysis window. The supplied window SHALL have a start before its end and SHALL retain the run's exact boundaries without rounding. The caller SHALL derive it from the immutable run execution context rather than a current mutable Observation definition. The capability SHALL reject mismatched identity, malformed window, or other malformed input before report generation. Lens results, Relationship definitions, raw telemetry, raw logs or alerts, retrieved content beyond references already retained by the analysis result, full Observation configuration, execution policy, and provider queries SHALL NOT be admitted.

#### Scenario: Generate from correlated minimal input

- **GIVEN** a valid `ObservationAnalysisResult` and minimal report context with matching Observation and run identities and an exact UTC observed window
- **WHEN** report generation is requested
- **THEN** the capability accepts the request without requiring any upstream evidence artifact or full Observation configuration

#### Scenario: Reject mismatched identity

- **GIVEN** the report context and `ObservationAnalysisResult` identify different Observations or runs
- **WHEN** report generation is requested
- **THEN** generation fails before a report is produced

#### Scenario: Reject invalid observed window

- **GIVEN** the report context has a missing, non-UTC, reversed, or zero-length observed window
- **WHEN** report generation is requested
- **THEN** generation fails before a report is produced

#### Scenario: Preserve source window boundaries

- **GIVEN** the run execution context has exact UTC observed-window boundaries including seconds or fractions
- **WHEN** the caller constructs the report request
- **THEN** the request carries those same boundaries without rounding, timezone reinterpretation, or lookup of a current Observation definition

#### Scenario: Reject undeclared report input

- **GIVEN** a report request contains raw telemetry, a Lens result, retrieved content, or another undeclared field
- **WHEN** the request is validated
- **THEN** the request is rejected and no report is produced

### Requirement: Present the complete analysis faithfully in English

The Markdown report SHALL be written in English and SHALL clearly present the Observation identity or an English-presented objective summary, the source `overall_state`, every finding, every hypothesis, every limitation, and all traceability information available on those items. Findings SHALL remain grounded in their source `evidence_refs`. Hypotheses SHALL remain possible explanations, preserve their `supported_by` and `knowledge_refs`, and SHALL NOT be worded as confirmed causes. Empty findings, hypotheses, or limitations SHALL be represented honestly rather than filled with fabricated content. Reordering and presentation-level paraphrasing or translation are permitted only when meaning and certainty are preserved. Raw Observation name, description, or objective text SHALL NOT be copied directly into the final Markdown. When a non-blank analytical objective is admitted, the presentation draft SHALL supply a neutral English objective summary through an explicitly declared, validated field, and the renderer SHALL present it. Without an admitted objective, the draft SHALL omit that summary and the renderer SHALL use correlated identifiers without inventing an objective.

#### Scenario: Present a populated result

- **GIVEN** an analysis result with multiple findings, hypotheses, limitations, evidence references, finding references, and knowledge references
- **WHEN** report generation succeeds
- **THEN** the English Markdown represents every supplied analytical item exactly once as that item type
- **AND** each item's supplied traceability remains associated with that item
- **AND** hypotheses are presented as possible rather than confirmed explanations

#### Scenario: Present an English objective summary

- **GIVEN** an analytical objective and a validated English presentation summary that preserves its intent without asserting an outcome
- **WHEN** report generation succeeds
- **THEN** the header shows the neutral summary rather than raw objective text
- **AND** the objective summary is not treated as observational evidence

#### Scenario: Reject a missing required objective summary

- **GIVEN** the admitted context has a non-blank analytical objective but the presentation draft omits its English summary
- **WHEN** the draft is validated
- **THEN** report generation fails without a partial report

#### Scenario: Avoid an invented objective

- **GIVEN** the admitted context has no analytical objective
- **WHEN** report generation succeeds
- **THEN** the header uses deterministic correlated identity instead of an objective summary

#### Scenario: Present a result without findings or hypotheses

- **GIVEN** an analysis result with `overall_state="no_significant_findings"`, no findings, no hypotheses, and zero or more limitations
- **WHEN** report generation succeeds
- **THEN** the English Markdown states that no significant findings were identified in the available analysis
- **AND** it does not fabricate a finding, hypothesis, recommendation, or claim of universal normality
- **AND** it still presents every supplied limitation

#### Scenario: Preserve uncertainty with findings

- **GIVEN** an analysis result with `overall_state="uncertain"` and one or more findings
- **WHEN** report generation succeeds
- **THEN** the report presents both the uncertain overall assessment and every finding
- **AND** it does not suppress the findings or replace uncertainty with a stronger classification

#### Scenario: Preserve an empty limitation set

- **GIVEN** an analysis result without limitations
- **WHEN** report generation succeeds
- **THEN** the report does not invent an analytical limitation

#### Scenario: Keep non-English semantic context out of the English artifact

- **GIVEN** the Observation name, description, or analytical objective contains non-English text
- **WHEN** report generation succeeds without a declared English presentation of those fields
- **THEN** the Markdown presents the correlated Observation and run identifiers using deterministic English labels
- **AND** it does not copy the non-English context text into the report

## ADDED Requirements

### Requirement: Lead with objective-oriented observed evidence and run context

The current MVP Markdown renderer SHALL place a concise, human-oriented opening before detailed findings. The header SHALL show the exact observed window start and end in UTC and a short Observation ID excerpt for orientation; the full Observation and run IDs, exact source `overall_state`, and report generation time SHALL remain available in technical details. The short ID SHALL NOT be represented as globally unique. When an English objective summary is available, the opening assessment SHALL address the objective's directly relevant evidence first, then briefly identify any separate auxiliary observed event needed to explain the supplied overall state. It SHALL not treat the objective as evidence, equate reference periods or History with an expected baseline, or claim an unsupported cross-Lens causal or confirming relationship.

The opening SHALL use available current values and configured reference-period comparisons when those values are supplied by the source findings and materially aid interpretation. If multiple supplied comparisons differ materially, it SHALL convey that contrast without selecting one as normal. It SHALL remain concise by grouping compatible observations, while preserving material contradictions and leaving every source finding complete in the detailed section. It SHALL NOT introduce severity, priority, anomaly classification, numerical values, or an interpretation caveat not supplied by the analysis. An evidence-availability reason SHALL be brief in the opening when a source limitation supports it; the complete limitation remains in its own section.

#### Scenario: Answer a multi-part objective from available findings

- **GIVEN** the objective concerns device-count stability and spike-free logging, with a stable device-count finding and a separate logging-spike finding
- **WHEN** the report is generated
- **THEN** the opening presents the device-count evidence and the logging event as separate parts of the objective
- **AND** it does not claim the logging event caused or proved a device-connectivity problem

#### Scenario: Preserve a mixed reference comparison

- **GIVEN** one source finding supplies a current value and materially different 1-day and 7-day comparisons
- **WHEN** the opening presents quantitative context
- **THEN** it conveys both reference perspectives without calling either an expected baseline or converting a symmetric relative change to an ordinary percentage

#### Scenario: Keep a many-finding opening concise

- **GIVEN** several related objective findings and distinct auxiliary findings
- **WHEN** the opening is generated
- **THEN** it groups compatible observations in a concise assessment, identifies any material contrast, and does not impose a severity ranking or omit an individual finding from the detailed section

#### Scenario: Preserve uncertainty and available auxiliary events

- **GIVEN** the source overall state is `uncertain`, a limitation identifies unavailable objective evidence, and an auxiliary finding describes a detected event
- **WHEN** the report is generated
- **THEN** the opening briefly says the objective cannot be assessed from available evidence and separately names the observed auxiliary event
- **AND** it does not present the auxiliary event as an answer to the objective

#### Scenario: Avoid invented uncertainty from an absent number

- **GIVEN** a supplied finding names an evidence-backed event but supplies no current or reference numerical value and no limitation about that absence
- **WHEN** the report is generated
- **THEN** it retains the event without inventing a value, an analytical limitation, or an uncertain state

### Requirement: Make detailed findings and possible explanations easy to scan

The renderer SHALL present every finding exactly once in the same objective-first order used by the opening, with material auxiliary findings following. Each finding SHALL have a short, source-grounded subject-and-observed-event heading when the source permits one, and concise prose that states the current observation before relevant reference and History context. The main finding section SHALL use report-local readable numbers instead of emphasizing opaque source IDs. It SHALL NOT suppress, merge, rank, or reclassify source findings. Every report-local number SHALL map unambiguously to its exact source finding ID in technical details.

Possible explanations SHALL remain a separate section after findings. Each hypothesis SHALL remain explicitly possible, SHALL show its support through readable finding numbers, and SHALL map to its exact source hypothesis ID and knowledge references in technical details. Analysis limitations SHALL remain a separate section, with absence described honestly. Neither the opening nor a finding heading SHALL imply a confirmed cause, prescribe manual checks, or introduce a recommendation.

#### Scenario: Reorder findings without losing source identity

- **GIVEN** the source lists an objective-relevant finding after a separate auxiliary finding
- **WHEN** the report is generated
- **THEN** the objective-relevant finding appears first in the report's detailed reading order
- **AND** each displayed finding number maps to exactly one unchanged source finding ID and all its traceability

#### Scenario: Present an unconfirmed hypothesis with readable support

- **GIVEN** a hypothesis is supported by two source findings and has knowledge references
- **WHEN** the report is generated
- **THEN** it appears after the findings as a possible explanation with readable support links to both displayed finding numbers
- **AND** its exact source hypothesis ID and knowledge references remain available separately from observational evidence

#### Scenario: Keep unsupported explanations absent

- **GIVEN** the analysis supplies no hypotheses
- **WHEN** the report is generated
- **THEN** the possible-explanations section states that none was produced without implying that no cause exists

### Requirement: Preserve complete traceability in a final technical appendix

The current MVP Markdown renderer SHALL place technical traceability after the narrative, explanations, and limitations. Evidence references SHALL be grouped first by displayed finding and then by exact `(source_type, source_id)` pair; each pair SHALL be printed once per finding group, followed by all exact associated locators. The appendix SHALL preserve the exact source finding-ID mapping, all evidence references, full Observation/run identities, exact overall-state value, and generation time. Hypothesis source-ID mappings, exact supported finding IDs, and knowledge references SHALL remain distinct from observational evidence. Grouping SHALL not erase duplicate source references if distinct source entries exist, alter an identifier or locator, or break source ownership.

#### Scenario: Compact repeated Metric references

- **GIVEN** one finding cites many locators from one Metric result
- **WHEN** the appendix is rendered
- **THEN** the exact source type and source ID are shown once for that finding and all exact cited locators remain inspectable

#### Scenario: Preserve multiple evidence sources and hypothesis knowledge

- **GIVEN** a finding cites multiple source pairs and a hypothesis cites a knowledge source
- **WHEN** the appendix is rendered
- **THEN** each evidence source remains associated with its owning finding
- **AND** the knowledge source remains associated with its owning hypothesis and is not presented as observational evidence

#### Scenario: Keep exact identity behind a short header ID

- **GIVEN** a report header displays only a short Observation ID excerpt
- **WHEN** a reader inspects technical details
- **THEN** the complete exact Observation and run IDs are present without relying on the excerpt for uniqueness

### Requirement: Keep copied Markdown readable and inert

Ordinary punctuation in generated English prose SHALL read naturally in both the persisted Markdown and its exact copied form, without blanket backslash escaping. Deterministic rendering SHALL continue to own headings, lists, blockquotes, and inline-code boundaries; source-authored and model-authored text SHALL remain inert and SHALL NOT introduce Markdown structure, links, HTML, or executable content. The output SHALL remain within the accepted browser renderer's safe Markdown subset, and Copy Markdown SHALL still copy the exact persisted content without browser-side rewriting.

#### Scenario: Copy ordinary engineering prose

- **GIVEN** a finding contains an ordinary metric name, decimal values, timestamps, commas, parentheses, and hyphens
- **WHEN** the report is generated and copied
- **THEN** the copied Markdown reads with ordinary punctuation rather than backslashes before every punctuation mark

#### Scenario: Contain hostile source text

- **GIVEN** an objective, finding, hypothesis, reference, or presentation string contains Markdown syntax, HTML-like content, control characters, or link-like text
- **WHEN** the report is rendered and copied
- **THEN** that content remains plain inert data inside renderer-owned structure
- **AND** no additional section, active link, HTML element, or executable content is created
