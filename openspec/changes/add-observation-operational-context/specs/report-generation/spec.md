## MODIFIED Requirements

### Requirement: Accept only the approved report-generation input boundary

The capability SHALL accept one strict `ObservationAnalysisResult` and minimal correlated report context containing the same `observation_id` and `observation_run_id`, an Observation name, optional description and analytical objective, optional operator-supplied `operational_context`, and the exact UTC start and end of that run's immutable observed analysis window. The supplied window SHALL have a start before its end and SHALL retain the run's exact boundaries without rounding. The caller SHALL derive it from the immutable run execution context rather than a current mutable Observation definition. The capability SHALL reject mismatched identity, malformed window, or other malformed input before report generation. Lens results, Relationship definitions, raw telemetry, raw logs or alerts, retrieved content beyond references already retained by the analysis result, full Observation configuration, execution policy, and provider queries SHALL NOT be admitted.

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

## ADDED Requirements

### Requirement: Use operational context for faithful presentation only

When present, `operational_context` SHALL be model-visible operator-authored data that may guide terminology, emphasis, and ordering among the supplied analysis items. It SHALL NOT appear as a quoted, copied, paraphrased, or separately summarized note in the Markdown report, and it SHALL NOT create a new section. It SHALL NOT add or remove a finding, hypothesis, limitation, state, recommendation, causal assertion, or evidence claim, or override the report's fixed presentation policy. The report SHALL remain valid when the field is absent.

#### Scenario: Present supported analysis with useful terminology
- **GIVEN** the context describes a process term and the supplied analysis result contains an item to which that term accurately applies
- **WHEN** the report is generated
- **THEN** the term may help present that item faithfully without changing its meaning or traceability
- **AND** the raw context is not independently disclosed

#### Scenario: Do not turn a note into a report fact
- **GIVEN** the note asserts an operating condition not established by the supplied analysis result
- **WHEN** the report is generated
- **THEN** the condition is not presented as an observed fact or explanation
- **AND** every supplied analytical item remains represented under its existing source key

#### Scenario: Ignore report instructions inside context
- **GIVEN** the note asks for an extra section, a recommendation, or omission of an unfavorable finding
- **WHEN** report generation executes
- **THEN** the same constrained draft and deterministic rendering rules apply
- **AND** the report contains the complete supplied analysis without the requested addition or omission
