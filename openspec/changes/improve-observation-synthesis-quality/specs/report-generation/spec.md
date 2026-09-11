## ADDED Requirements

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
