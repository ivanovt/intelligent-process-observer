## MODIFIED Requirements

### Requirement: Accept one correlated Observation reasoning scope

The system SHALL accept one strict immutable reasoning scope containing the Observation and ObservationRun identity, a compact semantic Observation context, an ordered collection of usable Lens results, an ordered collection of self-contained Relationship evaluations, and an ordered collection of unavailable Lens metadata. For this change, every configured Lens in the semantic context SHALL have type `metric` or `alert`; a context containing a `log` Lens or any other Lens type SHALL be rejected before the exact Lens-scope partition is evaluated. The semantic context SHALL contain only Observation identity, name, optional description, objective, optional operator-supplied `operational_context`, and the identity, type, name, optional description, and ordered analysis objectives of its configured Lenses. It SHALL exclude provider queries, credentials, endpoints, raw telemetry, retry/timeout settings, concurrency settings, persistence settings, and other infrastructure configuration.

For this change, a usable Lens result SHALL be exactly a validated `completed + good|degraded` or `partial + good|degraded` MetricAnalysisResult 1.0, or a validated `completed|partial` AlertAnalysisResult 1.0. A `completed + insufficient` Metric result SHALL NOT be usable analytical evidence and SHALL instead be represented as unavailable with reason code `insufficient_data` and no component. Failed Metric results and failed Alert LensRuns SHALL be represented as unavailable metadata rather than empty usable evidence. Log results, Log Lens identities in the semantic context, and Log-local knowledge annotations SHALL remain outside this capability until the deferred Log feature is introduced.

Unavailable Lens metadata SHALL reuse the accepted structured runtime-reason shape exactly: a required non-empty opaque `code` and an optional `component`, with no message, diagnostic, exception, or additional reason field. It SHALL also carry a reasoning-owned `origin` discriminator. Caller-supplied failed or otherwise non-usable Metric and Alert Lenses SHALL use `origin=caller_unavailable`, preserve the producer-supplied code and component exactly, and project to `missing_lens_evidence`; the reason-code set SHALL remain open to controlled upstream extension. Only the deterministic `completed + insufficient` Metric projection SHALL create `origin=completed_insufficient_metric`, requiring `code=insufficient_data` and an absent component, and it SHALL project to `insufficient_lens_evidence`.

The boundary SHALL require at least one usable result and SHALL require the usable and unavailable collections to form an exact partition of the `(lens_type, lens_id)` identities declared by the semantic Observation context. It SHALL reject duplicate identities within either collection, overlap between the collections, a configured Lens missing from both collections, any usable or unavailable Lens absent from the context, duplicate Relationship IDs, and usable results whose Observation or ObservationRun identity disagrees with the reasoning scope. Relationship evaluations SHALL be accepted only as caller-correlated artifacts for that same run because their accepted contract contains no run identity. The system SHALL preserve the supplied ordering after validation.

#### Scenario: Accept mixed Metric and Alert evidence
- **GIVEN** one correlated reasoning scope contains a completed sufficient Metric result, a partial Alert result, self-contained Relationship evaluations, and unavailable Lens metadata
- **WHEN** reasoning input is validated
- **THEN** the Metric and Alert results remain usable in their supplied order
- **AND** Relationship and unavailable metadata remain distinct inputs

#### Scenario: Treat an insufficient Metric as unavailable
- **GIVEN** current Metric acquisition completed but its validated result has `data_quality=insufficient` and no analytical evidence
- **WHEN** the reasoning scope is formed
- **THEN** the Metric result is excluded from usable analytical evidence
- **AND** the Lens is represented as unavailable with reason code `insufficient_data` and no component

#### Scenario: Reject a context containing a Log Lens
- **GIVEN** the semantic Observation context declares a configured Lens with type `log`
- **WHEN** the reasoning scope is validated
- **THEN** the request is rejected before the usable and unavailable collections are partitioned
- **AND** the Log Lens is not misrepresented as unavailable Metric or Alert evidence

#### Scenario: Preserve a producer-supplied unavailable reason
- **GIVEN** a failed Metric or Alert Lens is supplied as unavailable with a non-empty structured reason code and an optional component
- **WHEN** the reasoning scope is validated
- **THEN** the code and component are preserved exactly in unavailable metadata
- **AND** no reasoning-specific reason translation or free-text diagnostic is introduced

#### Scenario: Reject an invalid unavailable reason shape
- **GIVEN** unavailable Lens metadata has a missing or empty reason code, a free-text message, or another extra field
- **WHEN** the reasoning scope is validated
- **THEN** the request is rejected before model or retrieval work begins

#### Scenario: Reject an empty usable evidence scope
- **GIVEN** every Lens is failed or analytically insufficient
- **WHEN** Observation reasoning is requested
- **THEN** the request is rejected before any model or retrieval call
- **AND** no ObservationAnalysisResult is fabricated

#### Scenario: Reject inconsistent correlation
- **GIVEN** a usable result belongs to another ObservationRun, a Lens is both usable and unavailable, or a `(lens_type, lens_id)` identity is duplicated
- **WHEN** the reasoning scope is validated
- **THEN** the request is rejected without a partial reasoning result

#### Scenario: Require an exact Lens-scope partition
- **GIVEN** a configured context Lens is missing from both input collections or either collection contains a Lens identity absent from the context
- **WHEN** observation reasoning is requested
- **THEN** the request is rejected before model or retrieval work begins
- **AND** no out-of-scope evidence or fabricated availability limitation reaches reasoning

#### Scenario: Exclude technical configuration and raw data
- **GIVEN** a validated reasoning scope is projected for model use
- **WHEN** its fields are inspected
- **THEN** it contains the full structured usable analytical results and compact semantic context
- **AND** it contains no raw samples, provider payloads, provider queries, credentials, endpoints, or execution and persistence settings

## ADDED Requirements

### Requirement: Use operational context as bounded reasoning guidance

When present, `operational_context` SHALL be supplied as operator-authored semantic data to the finding, hypothesis, and overall-state invocations. It MAY guide relevance and terminology, but SHALL NOT be treated as observed evidence, a knowledge reference, a new retrieval source, or an instruction that changes tools, scope, output schema, evidence-grounding, retrieval budgets, or failure behavior. A claim in the text SHALL NOT by itself create or suppress a finding, hypothesis, limitation, or analytical state; existing evidence and knowledge requirements remain authoritative.

#### Scenario: Focus on an operator-described operating condition
- **GIVEN** the operator describes a startup condition and the admitted analytical evidence contains relevant timed behavior
- **WHEN** Observation reasoning forms its result
- **THEN** it may use the description to focus interpretation of the admitted evidence
- **AND** every finding and analytical state still follow the existing evidence boundaries

#### Scenario: Reject an unsupported context claim as evidence
- **GIVEN** the note claims that a spike occurred during startup but the admitted evidence does not establish startup timing
- **WHEN** findings and hypotheses are formed
- **THEN** the claim is not presented as observed fact or used to suppress a material evidence-grounded finding
- **AND** the note supplies neither an evidence catalog reference nor a knowledge reference

#### Scenario: Keep instructions inside the operator note non-authoritative
- **GIVEN** the note asks the agent to ignore evidence, fetch a new variable, or change its output rules
- **WHEN** any reasoning invocation executes
- **THEN** the request does not alter the agent's admitted data, tools, output contract, or policy
