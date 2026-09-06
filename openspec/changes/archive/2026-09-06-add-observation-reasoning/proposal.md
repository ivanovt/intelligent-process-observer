## Why

The MVP now has usable Metric and Alert analytical results, deterministic Relationship evaluations, and a bounded knowledge-retrieval foundation, but it has no production capability that combines those artifacts into one system-level interpretation. Observation Reasoning is the next critical-path feature because report generation and end-to-end Observation execution both depend on a validated `ObservationAnalysisResult`.

## What Changes

- Add strict framework-neutral contracts for the compact Observation semantic context, usable Metric/Alert inputs, unavailable Lens metadata, deterministic limitations, a fine-grained evidence catalog, a three-stage reasoning process with isolated model invocations, typed failures, and `ObservationAnalysisResult` 1.0.
- Add a deterministic Observation Reasoning executor that projects and validates evidence, invokes an evidence-only finding phase and freezes its findings, invokes a retrieval-enabled hypothesis phase, then invokes a knowledge-isolated overall-state phase.
- Allow only the hypothesis phase to make zero, one, or two sequential finding-grounded knowledge calls; every returned item is candidate knowledge, and final hypotheses may cite only references actually returned during the run.
- Determine `overall_state` after hypothesis reasoning in a separate invocation that receives Observation evidence, frozen findings, and deterministic limitations but no hypotheses, retrieved knowledge, knowledge references, retrieval ledger, or retrieval tool.
- Fail closed on model timeout, model failure, or invalid structured output without fabricating an `ObservationAnalysisResult`.
- Add a production PydanticAI adapter and simple OpenRouter configuration with default model `openai/gpt-5.6-terra`, a 120-second per-request timeout, 12,288 default maximum completion tokens, configurable model and bounds, routing/fallback enabled by default, and strict single-provider pinning when fallback is disabled.
- Treat `completed + insufficient` Metric results as unavailable analytical evidence with a deterministic limitation; support current Metric and Alert inputs only, leaving Log integration for its deferred feature.
- Exclude a concrete knowledge retriever/corpus, Report Agent, top-level Observation orchestration, HTTP execution endpoint, persistence coordination, and architecture-document edits.

## Capabilities

### New Capabilities

- `observation-reasoning`: Knowledge-isolated, evidence-grounded Observation synthesis with frozen findings, bounded knowledge-supported hypotheses, deterministic limitations and evidence traceability, strict result construction, fail-closed execution, and OpenRouter-backed PydanticAI configuration.

### Modified Capabilities

None.

## Impact

- Adds a focused backend Observation Reasoning package, framework-neutral ports, deterministic projection/execution/building components, and tests.
- Adds an OpenRouter-specific infrastructure adapter and system settings/environment documentation; no provider-specific type enters domain contracts.
- Changes the existing PydanticAI dependency declaration to include its `openrouter` optional integration and updates the backend lockfile. This dependency change requires approval with the planning artifacts before implementation.
- Reuses the existing knowledge-retrieval contracts/executor, Metric and Alert result contracts, Relationship evaluation contract, and generic runtime persistence envelope without changing their accepted requirements.
- Adds no public API, migration, report generation, top-level run lifecycle, concrete retriever, Log contract, or production retrieval corpus.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`, sections 7-10.
- `docs/architecture/02_architecture_principles_and_runtime.md`, sections 2-5 and 11-16.
- `docs/architecture/03_ADR_log.md`: ADR-050 through ADR-055, ADR-060 through ADR-084, ADR-088, ADR-151, and ADR-152.
- `docs/architecture/04_pipeline_and_agent_concepts.md`, sections 1-3 and 7-10.
- `docs/architecture/05_relationship_evaluator_concept.md`, sections 7-9.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, sections 2 and 5-8.
- `docs/architecture/07_observation_reasoning_agent.md`.
- `docs/architecture/08_observation_analysis_result_contract.md`.
- `docs/architecture/10_open_decisions_and_backlog.md`, sections 5 and 9; the user decisions recorded by this change resolve only the implementation behavior needed for this capability.
- `docs/architecture/11_glossary_and_naming.md`.
