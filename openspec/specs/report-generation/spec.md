# Report Generation Specification

## Purpose

Convert one validated Observation analysis result into a faithful, human-readable English Markdown report while keeping analysis and presentation strictly separated.

## Requirements

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

### Requirement: Produce the minimal Markdown ObservationReport envelope

On success, the capability SHALL produce exactly one immutable `ObservationReport` containing the source `observation_id`, source `observation_run_id`, an injected UTC `generated_at`, `format="markdown"`, and non-blank Markdown `content`. The report SHALL have no domain schema version. Generation SHALL NOT mutate the source analysis result. Only deterministic rendering code SHALL author Markdown structure; model-authored and source-authored strings SHALL be rendered as plain escaped content.

#### Scenario: Build a correlated report

- **GIVEN** a valid report request and successful presentation output
- **WHEN** the final report is built
- **THEN** its Observation and run identities equal those of the source analysis result
- **AND** its format is `markdown`
- **AND** its generated time is the injected UTC time
- **AND** its content is non-blank Markdown

#### Scenario: Preserve the analytical artifact

- **GIVEN** a valid immutable `ObservationAnalysisResult`
- **WHEN** report generation succeeds
- **THEN** the source result remains unchanged
- **AND** the report remains a separate presentation artifact without a domain schema version

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

### Requirement: Keep report generation presentation-only

The capability SHALL NOT create a new finding or hypothesis, alter `overall_state`, increase or add certainty, infer root cause, perform Lens or Relationship analysis, add a recommendation, expand the observed data scope, or use external/internal model knowledge as report evidence. The capability SHALL have no retrieval or other analytical tool capability. Deterministic validation SHALL enforce the representable structural guarantees: exact source membership and item types, unchanged identity and `overall_state`, absence of undeclared fields or sections, source-owned references, and renderer-owned Markdown structure. Meaning and certainty preservation inside permitted English presentation prose SHALL be enforced by the agent instruction and adversarial evaluation boundary; runtime validation SHALL NOT use keyword blacklists, heuristic language detection, or another model invocation to claim proof of arbitrary prose equivalence.

#### Scenario: Reject structurally representable analytical additions

- **GIVEN** structured presentation output introduces an unknown item, source key, field, reference, or arbitrary section not declared by the report presentation contract
- **WHEN** the output is validated
- **THEN** generation fails and no `ObservationReport` is produced

#### Scenario: Reject a recommendation section

- **GIVEN** structured presentation output adds a recommendation, prescribed action, newly inferred root cause, or another undeclared analytical field or section
- **WHEN** the output is validated
- **THEN** generation fails and no `ObservationReport` is produced

#### Scenario: Evaluate semantic faithfulness without lexical classification

- **GIVEN** the model supplies source-keyed English presentation prose for an admitted analytical item
- **WHEN** report-generation behavior is evaluated
- **THEN** representative adversarial cases verify that the agent preserves meaning and certainty and does not add recommendations or causal claims
- **AND** runtime validation does not reject or accept the prose solely because it contains a keyword such as `recommendation` or `root cause`

#### Scenario: Reject tool use

- **GIVEN** the model attempts to invoke retrieval or any other non-output tool
- **WHEN** the report invocation executes
- **THEN** the attempt is treated as a policy violation
- **AND** no `ObservationReport` is produced

### Requirement: Bound and isolate the presentation invocation

One report-generation execution SHALL make at most one model request, SHALL disable retries, and SHALL expose no tools. Supplied analysis statements and references SHALL be treated as untrusted data rather than instructions. Provider or model state from other agents or report executions SHALL NOT become report input. Model-authored and source-authored strings SHALL NOT control Markdown headings, lists, blockquotes, links, code blocks, or other document structure.

#### Scenario: Generate within the fixed request bound

- **GIVEN** a valid report request
- **WHEN** generation executes successfully
- **THEN** no more than one model request is made
- **AND** no tool is available or invoked

#### Scenario: Treat analytical text as untrusted data

- **GIVEN** a supplied finding or knowledge reference contains text resembling instructions
- **WHEN** generation executes
- **THEN** that text is treated only as reportable source data
- **AND** it cannot enable a tool, alter the output contract, or disclose hidden execution context
- **AND** it cannot create Markdown structure outside the deterministic renderer

### Requirement: Fail closed with a safe typed outcome

The capability SHALL return either report success containing one `ObservationReport` or a typed failure containing only a fixed code from `report_model_failed`, `report_model_timed_out`, `report_policy_violated`, or `report_result_invalid` and a controlled component from `request_validation`, `report_generation`, or `report_builder`. Invalid input or output, missing or duplicate analytical items, altered identity or overall state, unsupported additions, model failure, timeout, request-limit exhaustion, or policy violation SHALL produce no partial or fallback report. Failure output SHALL contain no exception text, prompt content, report input, credential, provider response, model reasoning, stack trace, or other sensitive diagnostic. Caller cancellation SHALL propagate unchanged without a typed outcome or retry.

#### Scenario: Normalize a model timeout

- **GIVEN** the report model exceeds its configured deadline
- **WHEN** generation executes
- **THEN** the capability returns `report_model_timed_out` for `report_generation`
- **AND** no report or diagnostic detail is returned

#### Scenario: Reject incomplete presentation output

- **GIVEN** presentation output omits or duplicates a source finding, hypothesis, limitation, or required traceability association
- **WHEN** the output is validated
- **THEN** the capability returns `report_result_invalid`
- **AND** no partial or fallback report is produced

#### Scenario: Propagate caller cancellation

- **GIVEN** the caller cancels report generation
- **WHEN** cancellation is observed
- **THEN** cancellation propagates unchanged
- **AND** no typed failure, retry, or report is produced

### Requirement: Preserve flexible Markdown presentation and downstream ownership boundaries

The public report contract SHALL NOT require one exact heading sequence or engineer/operator template variant. Any layout that satisfies English readability, completeness, traceability, and presentation-only constraints SHALL be valid. The capability SHALL be side-effect free: it SHALL NOT persist the report, coordinate an ObservationRun, transition lifecycle state, expose a public API, render Markdown to another format, send a notification, or select a localization policy beyond English for this change.

#### Scenario: Accept a semantically complete alternate layout

- **GIVEN** generated Markdown uses a heading structure different from an example architecture template
- **WHEN** it remains readable in English and faithfully presents all required source material and traceability
- **THEN** the layout is accepted

#### Scenario: Return an in-memory artifact only

- **GIVEN** report generation succeeds
- **WHEN** the outcome is returned
- **THEN** it contains an in-memory `ObservationReport`
- **AND** no persistence, lifecycle transition, API publication, rendering, or notification side effect has occurred

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

### Requirement: Produce an informative overall assessment from the supplied analysis

The Report Agent SHALL use `overall_assessment` to explain the supplied `overall_state` in concise engineering language using only the supplied findings and deterministic limitations. It SHALL NOT merely restate the enum label or a tautology such as “significant findings are present.” For `significant_findings_present`, the assessment SHALL identify the evidence-backed concern or contrast represented by at least one supplied finding. For `uncertain`, it SHALL explain the relevant supplied evidence-availability limitation without increasing certainty. For `no_significant_findings`, it SHALL summarize the supplied evidence-only conclusion without asserting universal normality.

The assessment is presentation only. It SHALL NOT add a finding, omit required source-item presentation, infer a causal link, introduce a recommendation, or quote raw Observation objective text as evidence.

#### Scenario: Explain a significant state with mixed evidence

- **GIVEN** supplied findings show stable directly relevant Metric evidence and a separate notable auxiliary Metric spike
- **WHEN** the report draft is produced with `overall_state=significant_findings_present`
- **THEN** the overall assessment identifies that evidence contrast in concise language
- **AND** it does not claim that the auxiliary spike caused or proved a problem in the directly relevant Metric

#### Scenario: Avoid an enum paraphrase

- **GIVEN** one or more supplied findings support `significant_findings_present`
- **WHEN** `overall_assessment` is evaluated
- **THEN** it contains evidence-derived meaning beyond the analytical-state label
- **AND** it is not only “significant findings are present” or an equivalent tautology

#### Scenario: Explain uncertainty only from supplied limitations

- **GIVEN** `overall_state=uncertain` and deterministic limitations identify missing or partial evidence
- **WHEN** the report draft is produced
- **THEN** the overall assessment relates uncertainty to those supplied limitations
- **AND** it adds no unsupported explanation or confidence claim

### Requirement: Present source items concisely without quantitative meaning drift

The Report Agent SHALL present every source finding, hypothesis, and limitation exactly once as already required, while using concise English that avoids unnecessary verbatim duplication across the overall assessment and item presentations. It MAY combine clauses inside one item's presentation, but SHALL NOT merge source keys, remove materially distinct evidence-backed meaning, or change modality and certainty.

Quantitative presentation SHALL preserve the source statement's meaning. A symmetric relative change SHALL remain identified as symmetric and SHALL NOT be converted into ordinary percentage increase/decrease. Current/reference means, timestamps, counts, and other supplied values SHALL retain their orientation and units. The Report Agent SHALL NOT recalculate a new metric from unavailable Lens evidence.

#### Scenario: Present consolidated findings without repeating the assessment

- **GIVEN** the overall assessment summarizes the main contrast and the source contains multiple findings
- **WHEN** finding presentations are produced
- **THEN** every finding key appears exactly once with its complete meaning
- **AND** the report avoids copying the entire overall assessment into each finding presentation

#### Scenario: Preserve symmetric comparison language

- **GIVEN** a source finding describes a symmetric relative change or cites current/reference means
- **WHEN** the report paraphrases it
- **THEN** the same quantitative interpretation is preserved
- **AND** no ordinary percentage claim is introduced

#### Scenario: Preserve possible-explanation modality

- **GIVEN** a knowledge-grounded hypothesis is supplied
- **WHEN** its report presentation is produced
- **THEN** it remains a possible explanation associated with its source key
- **AND** concise wording does not promote it to a confirmed cause

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

### Requirement: Evaluate synthesis guidance against representative trace-backed cases

The finding, overall-state, and report guidance SHALL be covered by deterministic request/prompt tests and representative adversarial evaluation cases. The evaluation set SHALL include objective-aligned direct versus auxiliary Metric evidence, absent Relationship evidence, repetitive current/reference/History facts, conflicting evidence, empty knowledge-grounded hypotheses, symmetric relative change, uncertain evidence availability, and attempts to introduce causal, percentage, severity, recommendation, or confidence language.

Live model evaluation SHALL remain opt-in and outside `make check`. When performed against the Home DEV Observation, it SHALL record only the run ID and rubric outcomes; full agent traces remain private local diagnostic data. A live failure SHALL not weaken deterministic validation or be converted into a passing result.

#### Scenario: Verify deterministic guidance coverage

- **WHEN** repository checks execute without provider credentials
- **THEN** prompt/request and scripted-output tests cover every required quality boundary
- **AND** no live model or Prometheus call is required

#### Scenario: Evaluate the Home DEV result privately

- **GIVEN** an operator enables development traces and launches the approved Home DEV Observation
- **WHEN** the quality rubric is applied
- **THEN** it checks objective alignment, non-causal separation, consolidation, comparison semantics, state rationale, and report usefulness
- **AND** only the run ID and rubric outcomes may enter the implementation handoff

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
