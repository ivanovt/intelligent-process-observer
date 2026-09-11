## Why

Development traces from a real Observation run exposed two avoidable model-contract failures: the Metric agent requested multiple optional tools in one response even though the domain policy is sequential, and the hypothesis agent invented knowledge references without retrieving knowledge. The deterministic boundaries correctly rejected both outputs, but the production guidance and provider request settings should steer compatible models toward the already accepted contracts so an empty knowledge backend and optional Metric analysis do not unnecessarily degrade or fail an otherwise valid run.

## What Changes

- Replace the minimal Metric system prompt and generic tool descriptions with explicit, role-owned guidance covering immutable scope, empty tool arguments, one sequential tool call per response, one call per tool, the three-attempt budget, and the final structured completion.
- Send the supported model setting that disables parallel tool calls for Metric requests while retaining deterministic rejection as the authoritative fallback.
- Refine the Observation hypothesis prompt to state that retrieval is optional, every hypothesis must cite frozen finding IDs and exact knowledge references made available to the invocation through direct retrieval or preserved upstream Lens knowledge annotations, and no available knowledge references requires `hypotheses=[]`.
- Send the supported model setting that disables parallel tool calls for hypothesis requests while preserving the existing two-call sequential retrieval budget and policy enforcement.
- Add focused adapter tests for prompt ownership, provider request settings, sequential tool guidance, and empty/unavailable-knowledge completion guidance.
- Add an opt-in, trace-backed manual smoke procedure using the Home DEV Observation to confirm the target model follows the refined interaction contract without making a live provider call part of CI.
- Preserve all current deterministic validators, request/tool budgets, failure mappings, public contracts, and the explicit empty production `KnowledgeRetriever`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `production-agent-composition`: Refine the server-owned Metric and Observation hypothesis interaction guidance and disable provider-level parallel tool calls for those tool-enabled invocations.

## Impact

- Affected backend areas: PydanticAI Metric and Observation Reasoning adapters, their model settings and implementation-owned prompts/tool descriptions, focused adapter/composition tests, and developer troubleshooting documentation.
- Public APIs, persisted contracts, runtime lifecycle semantics, model defaults, timeouts, token limits, and tool/retrieval budgets remain unchanged.
- No database migration, frontend change, architecture-document edit, or dependency change is required.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md` — bounded agents, sequential Metric tools, findings-before-knowledge, and empty-hypothesis semantics.
- `docs/architecture/04_pipeline_and_agent_concepts.md` — agent/tool responsibility and deterministic enforcement boundaries.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — existing partial/failure propagation semantics.
- `docs/architecture/07_observation_reasoning_agent.md` — optional bounded retrieval and exact hypothesis grounding.
- `docs/architecture/03_ADR_log.md` — ADR-152 (PydanticAI adapter boundary), ADR-169 (production OpenRouter composition and deferred prompt refinement), and ADR-171 (development trace evidence).
