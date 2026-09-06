## Why

The accepted MVP architecture requires Observation- and Log-level agents to access external domain knowledge through a bounded, traceable retrieval tool, but the production backend has no reusable retrieval boundary or execution policy yet. Establishing that foundation separately keeps future consuming agents small while preserving the architectural separation between observational evidence and external knowledge.

## What Changes

- Add framework-neutral contracts for grounded knowledge-retrieval requests, retrieved knowledge items, opaque source references, and call outcomes.
- Add a source-agnostic retriever port so a future retrieval backend can be integrated without leaking provider, vector-store, or agent-framework types into domain/application contracts.
- Add a deterministic bounded retrieval executor that requires a frozen finding scope, permits no more than two executed calls, supports an optional second-call refinement, and records an application-owned attempt ledger.
- Define non-fatal handling for empty results, retriever failures, and timeouts without deciding whether returned knowledge is sufficient for a future hypothesis or annotation.
- Exclude corpus ingestion, indexing, chunking, ranking, permissions policy, a concrete retrieval backend, and integration with Observation Reasoning or Log Analysis agents.
- Add focused contract and executor tests. No public HTTP API, persistence schema, frontend behavior, or dependency changes are included.

## Capabilities

### New Capabilities

- `knowledge-retrieval`: Framework-neutral contracts and deterministic bounded execution for finding-grounded external knowledge retrieval.

### Modified Capabilities

None.

## Impact

- Affects new backend knowledge-retrieval domain/application modules and their tests.
- Establishes a future adapter boundary but does not add a production provider, corpus, database migration, or configuration surface.
- Adds no dependencies and does not modify existing runtime, Lens, agent, or public API behavior.

## Required Follow-up

Production retrieval will require a separate, explicitly approved change that implements a concrete adapter behind the source-agnostic retriever port and defines how an approved external domain-knowledge corpus is supplied and maintained. That follow-up must resolve the currently open source-governance, ingestion, permission, retrieval-stack, provenance, resource-limit, security, and operational concerns recorded in `design.md` without expanding the scope of this foundation change.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md`, sections 3.2, 10, 12.2-12.3, and 15.
- `docs/architecture/04_pipeline_and_agent_concepts.md`, sections 2, 6.1, and 8.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, section 8.
- `docs/architecture/07_observation_reasoning_agent.md`, sections 4-7.
- `docs/architecture/21_log_lens_and_analysis_concept.md`, sections 15-16.
- `docs/architecture/24_log_analysis_agent.md`, sections 7-9 and 12-13.
- `docs/architecture/28_log_analytical_tools_and_knowledge_retrieval.md`, sections 6-9.
- `docs/architecture/03_ADR_log.md`: ADR-075 through ADR-081, ADR-149 through ADR-152.
- `docs/architecture/10_open_decisions_and_backlog.md`, section 9; the open retriever/backend, indexing, ranking, permission, citation-grammar, result-budget, and timeout decisions remain open.
