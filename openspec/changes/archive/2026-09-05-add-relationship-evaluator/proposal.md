## Why

Engineer-defined Metric Relationships are already persisted, and Metric analysis already produces the controlled `current_state` semantics those rules address, but the system cannot yet evaluate the rules into deterministic cross-Metric evidence. Adding that bounded capability now supplies the stable input contract required by later Observation reasoning and end-to-end execution features without prematurely implementing the top-level JOIN/orchestration workflow.

## What Changes

- Add a framework-neutral, deterministic Relationship Evaluator that accepts duplicate-free ordered Relationship definitions and the complete collection of Lens analysis results correlated to one Observation and ObservationRun.
- Resolve Metric participants inside the evaluator and evaluate only the accepted `current_state` properties: `trend.direction`, `trend.rate`, and `variability.state`.
- Produce an exact, validated, self-contained `RelationshipEvaluation` contract carrying relationship identity, applicability, applicable-state outcome, and complete condition/expectation evidence, including explicit unavailable observations.
- Validate batch identity and uniqueness before evaluating all configured Relationships in definition order with deterministic conjunctive and uncertainty semantics.
- Keep post-JOIN invocation, persistence coordination, ObservationRun lifecycle handling, Observation Reasoning, and report generation outside this change; those remain owned by the later `add-observation-execution` and downstream roadmap features.
- Add focused contract and evaluator tests. No public API, database schema, dependency, provider, agent, LLM, or RAG change is introduced.

## Capabilities

### New Capabilities

- `relationship-evaluation`: Deterministically evaluate engineer-defined Metric Relationships against complete Lens result collections and return validated, self-contained evidence artifacts.

### Modified Capabilities

None.

## Impact

- Backend domain code gains a Relationship evaluation contract and deterministic evaluator component, expected under a dedicated relationship-focused module.
- Existing Observation Relationship definitions and MetricAnalysisResult contracts are consumed without changing their public shapes.
- Existing generic RelationshipEvaluation persistence remains compatible but is not invoked or redesigned by this change.
- Later Observation Reasoning can depend on the exact evaluation contract; later Observation execution remains responsible for invoking and persisting evaluations after its strict JOIN and usable-results gate.
- No frontend, HTTP API, migration, dependency, provider, or external-system impact.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`, section 10
- `docs/architecture/02_architecture_principles_and_runtime.md`, sections 4, 11, 15, and 16
- `docs/architecture/03_ADR_log.md`: ADR-004, ADR-005, ADR-006, ADR-008, ADR-009, ADR-010, ADR-053, ADR-060, ADR-061, ADR-062, ADR-063, ADR-066, and ADR-088
- `docs/architecture/04_pipeline_and_agent_concepts.md`, section 7
- `docs/architecture/05_relationship_evaluator_concept.md`
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, sections 4, 5, 13, and 14
- `docs/architecture/07_observation_reasoning_agent.md`, sections 2.3 and 4
- `docs/architecture/10_open_decisions_and_backlog.md`, section 4
