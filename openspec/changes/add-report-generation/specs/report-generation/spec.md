## Purpose

Convert one validated Observation analysis result into a faithful, human-readable English Markdown report while keeping analysis and presentation strictly separated.

## ADDED Requirements

### Requirement: Accept only the approved report-generation input boundary

The capability SHALL accept one strict `ObservationAnalysisResult` and minimal Observation semantic context containing the same `observation_id` and `observation_run_id`, an Observation name, and optional description and analytical objective. It SHALL reject mismatched identity or malformed input before report generation. Lens results, Relationship definitions, raw telemetry, raw logs or alerts, retrieved content beyond references already retained by the analysis result, full Observation configuration, execution policy, and provider queries SHALL NOT be admitted.

#### Scenario: Generate from correlated minimal input

- **GIVEN** a valid `ObservationAnalysisResult` and minimal semantic context with matching Observation and run identities
- **WHEN** report generation is requested
- **THEN** the capability accepts the request without requiring any upstream evidence artifact or full Observation configuration

#### Scenario: Reject mismatched identity

- **GIVEN** the semantic context and `ObservationAnalysisResult` identify different Observations or runs
- **WHEN** report generation is requested
- **THEN** generation fails before a report is produced

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

The Markdown report SHALL be written in English and SHALL clearly present the Observation identity or an English-presented name, the source `overall_state`, every finding, every hypothesis, every limitation, and all traceability information available on those items. Findings SHALL remain grounded in their source `evidence_refs`. Hypotheses SHALL remain possible explanations, preserve their `supported_by` and `knowledge_refs`, and SHALL NOT be worded as confirmed causes. Empty findings, hypotheses, or limitations SHALL be represented honestly rather than filled with fabricated content. Reordering and presentation-level paraphrasing or translation are permitted only when meaning and certainty are preserved. Raw Observation name, description, or objective text SHALL NOT be copied directly into the final Markdown; the deterministic renderer SHALL use the correlated Observation and run identifiers unless an English presentation of that context is supplied through an explicitly declared presentation field.

#### Scenario: Present a populated result

- **GIVEN** an analysis result with multiple findings, hypotheses, limitations, evidence references, finding references, and knowledge references
- **WHEN** report generation succeeds
- **THEN** the English Markdown represents every supplied analytical item exactly once as that item type
- **AND** each item's supplied traceability remains associated with that item
- **AND** hypotheses are presented as possible rather than confirmed explanations

#### Scenario: Present a result without findings or hypotheses

- **GIVEN** an analysis result with `overall_state="no_significant_findings"`, no findings, no hypotheses, and zero or more limitations
- **WHEN** report generation succeeds
- **THEN** the English Markdown states that no significant findings were identified
- **AND** it does not fabricate a finding, hypothesis, or recommendation
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
