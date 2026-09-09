# production-agent-composition Specification

## Purpose

Provide the production OpenRouter/PydanticAI agent composition required for real Metric and Alert Lens execution without weakening framework-neutral domain contracts.

## Requirements

### Requirement: Compose all production agents through the existing OpenRouter boundary

The system SHALL compose the Metric Analysis Agent and Alert Analysis Agent through their existing PydanticAI infrastructure adapters and the existing server-owned OpenRouter provider boundary. Metric, Alert, Observation Reasoning, and Report agents SHALL default to the same model identifier at this stage, `openai/gpt-5.6-terra`, while retaining separate role-specific model settings so a later approved change can alter one role without changing domain contracts.

The model/provider objects, credentials, provider routing, framework messages, and model settings SHALL remain infrastructure concerns. They SHALL NOT enter Metric, Alert, Observation execution, persistence, public run API, or frontend domain contracts.

#### Scenario: Compose the default production roles

- **GIVEN** no role-specific model name override is configured
- **WHEN** production Observation execution is composed
- **THEN** Metric, Alert, Reasoning, and Report agent adapters target `openai/gpt-5.6-terra` through OpenRouter
- **AND** every domain pipeline receives only its framework-neutral agent port

#### Scenario: Override one role independently

- **GIVEN** a valid server-side Metric model override is configured
- **WHEN** production agents are composed
- **THEN** only the Metric adapter uses that override
- **AND** no client-facing contract or other role's configured model changes

### Requirement: Promote the existing Metric and Alert prompts as initial system prompts

The production Metric adapter SHALL use the existing implementation-owned Metric system prompt that instructs the model to complete analysis only from the supplied structured request and registered optional tools. The production Alert adapter SHALL use the existing implementation-owned Alert system prompt that limits work to supplied Alert Lens data, grounded Lens-local descriptive findings, and registered optional tools while prohibiting cross-Lens analysis, RAG, system diagnosis, causal claims, and recommendations.

Client requests SHALL NOT supply, replace, append to, or select these prompts. Prompt refinement, prompt version selection, and administrative prompt configuration are outside this change and require a later approved change.

#### Scenario: Use the initial production prompts

- **WHEN** a Metric or Alert agent is invoked in a launched Observation run
- **THEN** its existing role-specific system prompt is supplied by production infrastructure
- **AND** the prompt cannot be altered by the Observation definition, run request, provider data, or frontend

### Requirement: Bound production Metric and Alert model requests

Each Metric and Alert model request SHALL use a server-owned 120-second timeout and a maximum output of 12,288 tokens by default. Metric and Alert SHALL retain independent positive configuration fields for these limits, even though their defaults are equal. These request-level limits SHALL compose with, and SHALL NOT replace or reset, each agent's accepted domain-owned model-request and optional-tool budgets or the top-level per-Lens deadline.

One Alert Agent invocation SHALL issue at most eleven model requests total and SHALL admit at most ten optional-tool attempts. Every actual request to the model SHALL count, including a request that fails or returns invalid output. When the tenth tool attempt is admitted cleanly, at most one additional request MAY ask for the final structured completion. That final request SHALL expose no remaining domain tool capacity: any tool call in it SHALL fail policy without executing a tool, adding an eleventh tool-ledger attempt, or causing a twelfth model request.

When one model response contains multiple optional-tool calls, calls SHALL be considered in response order and only calls within the remaining ten-attempt capacity SHALL reach the domain registry. Any excess call SHALL fail agent policy before execution or ledger insertion, and no continuation request SHALL follow that violation. The agent MAY complete before either ceiling. Request/tool-limit exhaustion SHALL map through the existing Alert agent failure semantics without provider diagnostics.

#### Scenario: Apply the default Lens-agent limits

- **GIVEN** no Metric or Alert request-limit override is configured
- **WHEN** either production adapter sends a model request
- **THEN** the request uses a 120-second timeout and 12,288 maximum output tokens
- **AND** the agent's existing request/tool budget remains independently enforced

#### Scenario: Reject invalid server configuration

- **WHEN** a Metric or Alert timeout or output-token setting is zero or negative
- **THEN** settings validation rejects the configuration before it can be used

#### Scenario: Complete after ten sequential Alert tool attempts

- **GIVEN** the first ten Alert model responses each produce one admitted optional-tool call
- **WHEN** the tenth tool result is available
- **THEN** at most one eleventh model request may produce the final structured completion
- **AND** no twelfth model request is permitted

#### Scenario: Reject a tool call in the final Alert request

- **GIVEN** ten optional-tool attempts are already recorded
- **WHEN** the eleventh model response requests another tool
- **THEN** the invocation fails policy without executing the tool or extending the tool ledger
- **AND** no twelfth model request occurs

#### Scenario: Reject excess calls in one response

- **GIVEN** fewer tool slots remain than the number of tool calls in one Alert model response
- **WHEN** those calls are considered in response order
- **THEN** only calls within the remaining capacity may execute and enter the ledger
- **AND** the first excess call terminates the agent path as a policy failure without another continuation

### Requirement: Fail safely when OpenRouter is unavailable

Application startup and a structurally valid run launch SHALL remain available when the OpenRouter credential is absent. Production composition SHALL inject safe unavailable agent adapters behind the existing framework-neutral ports. The run SHALL create its normal durable identity graph and proceed through existing per-Lens degradation/failure and Observation-level failure semantics; because Observation Reasoning requires a model, a run without a usable OpenRouter integration SHALL eventually become `failed` unless it is cancelled or encounters an earlier terminal infrastructure failure.

No persisted reason, API response, UI message, or analytical artifact SHALL expose an API key, credential presence test, provider exception, prompt, model response, or other sensitive diagnostic. Restoring configuration SHALL not resume the failed run; a user SHALL launch a fresh run identity.

#### Scenario: Launch without an OpenRouter credential

- **GIVEN** the OpenRouter credential is not configured
- **WHEN** a user launches a valid Observation
- **THEN** the API accepts and creates the run rather than rejecting it during launch
- **AND** the execution reaches a safe durable failed/degraded outcome through existing contracts without credential detail

#### Scenario: Configure OpenRouter after a failed run

- **GIVEN** a run failed while model access was unavailable
- **WHEN** valid server configuration is later supplied
- **THEN** the failed run remains immutable
- **AND** a subsequent launch creates a fresh run under the restored production composition

### Requirement: Keep production model configuration server-only

OpenRouter API key, provider order/fallback policy, four role-specific model names, and Metric/Alert request limits SHALL be read only from backend environment/settings. They SHALL NOT be returned by Observation capabilities, Observation Definition responses, run list/detail responses, health responses, or frontend-visible `VITE_*` configuration.

#### Scenario: Read run detail after model-backed execution

- **WHEN** a client retrieves a run produced by OpenRouter-backed agents
- **THEN** the response contains only accepted runtime and analytical projections
- **AND** contains no model identifier, provider routing, token limit, timeout, credential, prompt, or model message

### Requirement: Use an explicit empty KnowledgeRetriever until knowledge integration exists

Production Observation Reasoning SHALL receive a framework-neutral KnowledgeRetriever that returns an empty validated item collection for every admitted request and performs no external retrieval while no production knowledge backend is approved. It SHALL NOT fabricate KnowledgeReferences, retrieved statements, hypotheses, diagnostics, or a hidden local knowledge source.

The existing bounded retrieval and reasoning rules SHALL remain unchanged. A model MAY request retrieval and observe an empty result; any final hypothesis SHALL still require accepted knowledge references, so empty retrieval cannot support a fabricated hypothesis. Replacing this adapter with a real retriever requires a separate approved architecture and OpenSpec change.

#### Scenario: Retrieve with no production knowledge backend

- **GIVEN** Observation Reasoning has formed one or more findings
- **WHEN** its model requests knowledge retrieval
- **THEN** the production retriever returns an empty validated collection
- **AND** no KnowledgeReference or retrieved statement is invented

#### Scenario: Complete reasoning without knowledge hypotheses

- **GIVEN** retrieval returns no knowledge items
- **WHEN** Observation Reasoning completes successfully
- **THEN** findings and overall analytical state may still be produced under their existing contracts
- **AND** no hypothesis without knowledge references is accepted
