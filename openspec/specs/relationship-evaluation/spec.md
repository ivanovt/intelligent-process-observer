# relationship-evaluation Specification

## Purpose

Provide deterministic, auditable evaluation of engineer-defined Metric Relationships against the semantic current state produced for one Observation execution.

## Requirements

### Requirement: Evaluate the complete Relationship batch deterministically

The system SHALL accept an ordered, duplicate-free collection of validated Relationship definitions and the complete collection of Lens analysis results for one ObservationRun. It SHALL return exactly one `RelationshipEvaluation` for every supplied Relationship, including when no participant evidence is usable, and SHALL preserve Relationship definition order. An empty Relationship collection SHALL return an empty collection.

The evaluator SHALL resolve participant results itself. It SHALL use only Metric results whose identity matches a participant, SHALL ignore non-Metric and unrelated Lens results, and SHALL not require callers to project participant fields before evaluation. Missing or non-usable participant evidence SHALL produce the uncertainty behavior defined below rather than aborting evaluation of that Relationship or the remaining batch.

Before evaluation, the input boundary SHALL reject duplicate Relationship IDs, multiple Metric results with the same Lens ID, and every non-empty Lens-result collection whose entries do not all share the same `(observation_id, observation_run_id)` pair. A matching Metric payload SHALL validate as one of the accepted strict MetricAnalysisResult variants; a payload that claims a current-state-bearing completed-sufficient or partial variant but omits or corrupts a mandatory current-state descriptor SHALL reject the whole batch rather than become unavailable evidence. An empty Lens-result collection has no runtime identity to validate and SHALL remain valid. The evaluator SHALL not fetch telemetry, discover Relationships, invoke an agent, or mutate any input.

#### Scenario: Evaluate multiple Relationships in definition order

- **GIVEN** an ordered set of valid Relationships and one complete Lens-result collection for an ObservationRun
- **WHEN** the Relationships are evaluated
- **THEN** the system returns one evaluation per Relationship in the same order
- **AND** participant resolution is based on Metric result identity within the complete collection

#### Scenario: Return an empty batch

- **GIVEN** no configured Relationships and any valid Lens-result collection for one ObservationRun
- **WHEN** the batch is evaluated
- **THEN** the system returns an empty evaluation collection without side effects

#### Scenario: Ignore unrelated and non-Metric results

- **GIVEN** the complete result collection contains unrelated Metric results and Alert or other non-Metric results, including a non-Metric result whose Lens ID equals a participant ID
- **WHEN** a Metric Relationship is evaluated
- **THEN** only the matching Metric participant result contributes semantic evidence

#### Scenario: Reject an inconsistently correlated runtime result collection

- **GIVEN** the input contains duplicate Metric Lens IDs or results that disagree on `observation_id` or `observation_run_id`
- **WHEN** evaluation is requested
- **THEN** the input is rejected without producing a partial evaluation batch

#### Scenario: Reject duplicate Relationship definitions

- **GIVEN** two supplied Relationship definitions have the same Relationship ID
- **WHEN** evaluation is requested
- **THEN** the input is rejected without producing ambiguous or persistence-incompatible evaluations

#### Scenario: Reject a malformed current-state-bearing Metric result

- **GIVEN** a matching Metric payload claims a completed-sufficient or partial result but is missing or corrupts a mandatory current-state descriptor
- **WHEN** evaluation is requested
- **THEN** the malformed producer payload is rejected without producing a partial evaluation batch or uncertainty artifact

### Requirement: Use only the accepted Metric current-state vocabulary

For MVP Relationship rules, the evaluator SHALL read only `current_state.trend.direction`, `current_state.trend.rate`, and `current_state.variability.state`. It SHALL compare each configured value by exact equality and SHALL treat all descriptors within a condition side or expectation side conjunctively.

The evaluator SHALL NOT inspect or infer rule values from reference periods, History, numerical evidence, raw telemetry, optional Metric properties, Alert evidence, or any external knowledge. A reliable observed `trend.rate` value of `not_classified` SHALL remain observable evidence and SHALL be an exact mismatch for any configured `slow|moderate|fast` expectation; it SHALL not be converted into unavailable evidence.

#### Scenario: Match supported current-state descriptors

- **GIVEN** a Relationship condition and expectation use supported descriptors and every required participant has a usable Metric result with current state
- **WHEN** the Relationship is evaluated
- **THEN** every descriptor is compared exactly with its corresponding current-state value
- **AND** the evaluation does not inspect reference, History, numerical, optional-tool, or raw evidence

#### Scenario: Treat not-classified rate as an observed mismatch

- **GIVEN** a rule expects a `slow`, `moderate`, or `fast` trend rate and the participant reliably reports `trend.rate=not_classified`
- **WHEN** that descriptor is evaluated
- **THEN** its evidence records `not_classified` as the observed value and `match=false`

### Requirement: Determine applicability with explicit three-valued semantics

The evaluator SHALL set `applicability` to exactly `applicable`, `not_applicable`, or `unknown`. Empty conditions SHALL be always applicable. Non-empty conditions SHALL be `applicable` when every condition descriptor matches, `not_applicable` when at least one condition descriptor has a reliable mismatch, and `unknown` when no reliable mismatch exists but at least one required condition observation is unavailable.

For the accepted MetricAnalysisResult 1.0 inputs, unavailable semantic evidence SHALL mean that no matching Metric result exists or that a valid completed-insufficient or failed Metric variant contains no `current_state`. A structurally invalid current-state-bearing payload SHALL follow the batch-rejection behavior above and SHALL NOT be treated as unavailable evidence. The current accepted mandatory Metric descriptor vocabularies do not contain a literal `unknown`; adding such an observed value requires a future explicitly approved contract extension.

A reliable mismatch SHALL dominate unavailable observations on the condition side because the conjunctive condition is already known to be false. Applicability SHALL depend only on condition evidence and SHALL not be changed by expectation availability or matches.

#### Scenario: Apply an unconditional Relationship

- **GIVEN** a valid Relationship has no conditions and has one or more expectations
- **WHEN** it is evaluated
- **THEN** its applicability is `applicable`

#### Scenario: Apply matching conditions

- **GIVEN** every configured condition descriptor has available evidence and matches exactly
- **WHEN** the Relationship is evaluated
- **THEN** its applicability is `applicable`

#### Scenario: Mark a condition mismatch as not applicable

- **GIVEN** at least one configured condition descriptor has an available value that does not match, whether or not another condition observation is unavailable
- **WHEN** the Relationship is evaluated
- **THEN** its applicability is `not_applicable`

#### Scenario: Mark unresolved conditions as unknown

- **GIVEN** no configured condition descriptor has a reliable mismatch and at least one required participant has no matching Metric result or has a valid Metric result without current state
- **WHEN** the Relationship is evaluated
- **THEN** its applicability is `unknown`

### Requirement: Determine state only for applicable Relationships

The evaluator SHALL include `state` only when `applicability=applicable`. For an applicable Relationship, it SHALL set state to `consistent` when every expectation descriptor matches, `inconsistent` when at least one expectation descriptor has a reliable mismatch, and `uncertain` when no reliable mismatch exists but at least one required expectation observation is unavailable under the valid-input rules above.

A reliable expectation mismatch SHALL dominate unavailable expectation observations. When applicability is `not_applicable` or `unknown`, the evaluation SHALL omit `state` regardless of expectation evidence.

#### Scenario: Produce a consistent state

- **GIVEN** a Relationship is applicable and every expectation descriptor has available evidence that matches exactly
- **WHEN** its expectations are evaluated
- **THEN** the evaluation state is `consistent`

#### Scenario: Produce an inconsistent state

- **GIVEN** a Relationship is applicable and at least one expectation descriptor has an available mismatching value, whether or not another expectation observation is unavailable
- **WHEN** its expectations are evaluated
- **THEN** the evaluation state is `inconsistent`

#### Scenario: Produce an uncertain state

- **GIVEN** a Relationship is applicable, no expectation descriptor has a reliable mismatch, and at least one expected participant has no matching Metric result or has a valid Metric result without current state
- **WHEN** its expectations are evaluated
- **THEN** the evaluation state is `uncertain`

#### Scenario: Omit state when the rule is not applicable

- **GIVEN** a Relationship has applicability `not_applicable` or `unknown`
- **WHEN** its output contract is serialized
- **THEN** the `state` field is absent

### Requirement: Emit an exact self-contained evaluation contract

Each `RelationshipEvaluation` SHALL contain `relationship_id`, `name`, nullable `description`, `applicability`, optional `state`, a `conditions` evidence list, and an `expectations` evidence list. It SHALL not introduce a domain-level `schema_version`.

Every evidence item SHALL contain `lens_id`, `property`, `expected`, `observed`, and `match`. `property` SHALL be one of `trend.direction`, `trend.rate`, or `variability.state`. For an available observation, `observed` SHALL contain the actual accepted Metric controlled-vocabulary value and `match` SHALL be a Boolean. For unavailable evidence from a missing result or a valid result without current state, both `observed` and `match` SHALL be explicit null values. A literal `unknown` SHALL NOT be admitted as an observed descriptor by this contract because it is not part of the accepted mandatory Metric descriptor vocabulary.

Both evidence lists SHALL be complete for their respective configured rule sides for every applicability outcome. Items SHALL be ordered first by the Relationship's participant order and then by the fixed property order `trend.direction`, `trend.rate`, `variability.state`. The output contract SHALL reject extra fields, unsupported property names or vocabulary values, contradictory `observed`/`match` combinations, a state on a non-applicable evaluation, or a missing state on an applicable evaluation.

#### Scenario: Emit complete evidence for an applicable inconsistency

- **GIVEN** an applicable Relationship has matching conditions and at least one mismatching expectation
- **WHEN** its evaluation is serialized
- **THEN** the artifact carries its semantic identity, `applicable`, `inconsistent`, and all configured condition and expectation evidence in canonical order

#### Scenario: Preserve complete evidence for an unresolved rule

- **GIVEN** required condition or expectation evidence is unavailable
- **WHEN** the Relationship is evaluated
- **THEN** the corresponding evidence item remains present with explicit null `observed` and `match`
- **AND** all other configured evidence items remain present regardless of applicability or state

#### Scenario: Reject a contradictory evaluation artifact

- **GIVEN** an evaluation payload has an invalid applicability/state combination, unsupported vocabulary, extra data, or an evidence item whose observed value contradicts its match field
- **WHEN** the output contract validates the payload
- **THEN** validation rejects the payload

### Requirement: Preserve runtime and persistence ownership boundaries

Relationship evaluation SHALL be a side-effect-free deterministic capability. This change SHALL NOT detect strict JOIN completion, apply the usable-results gate, load runtime aggregates, transition ObservationRun lifecycle, invoke Observation Reasoning or Report Generation, or persist `RelationshipEvaluation` artifacts. Later Observation execution SHALL own post-JOIN invocation and persistence coordination using this capability's output contract.

#### Scenario: Evaluate without runtime side effects

- **GIVEN** valid Relationship definitions and Lens results are supplied directly to the evaluator
- **WHEN** evaluation completes
- **THEN** only validated in-memory evaluation artifacts are returned
- **AND** no run lifecycle, persistence, provider, agent, or report operation occurs
