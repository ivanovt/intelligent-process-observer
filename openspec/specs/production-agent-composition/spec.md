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

Production Observation Reasoning SHALL receive the curated-corpus KnowledgeRetriever when the
curated knowledge persistence/index is available. The adapter SHALL implement the existing
framework-neutral KnowledgeRetriever port and SHALL return only approved, applicable, provenance-
preserving retrieved items under the existing bounded retrieval session. It SHALL not expose
database, embedding, vector-store, extraction, document-management, or provider types to
reasoning contracts.

When curated knowledge infrastructure is unavailable at application composition time, production
SHALL inject a safe unavailable retriever that returns an empty validated item collection for every
admitted request. It SHALL not fabricate KnowledgeReferences, retrieved statements, hypotheses,
diagnostics, or a hidden local knowledge source. A transient retrieval failure SHALL retain the
existing typed retrieval failure semantics and SHALL not make application startup fail or change
Observation execution lifecycle behavior.

The existing bounded retrieval and reasoning rules SHALL remain unchanged. A model MAY request
retrieval and observe an empty result; any final hypothesis SHALL still require accepted knowledge
references, so unavailable or empty retrieval cannot support a fabricated hypothesis.

#### Scenario: Retrieve curated approved knowledge
- **GIVEN** the curated corpus is available and Observation Reasoning has formed one or more
findings
- **WHEN** its model requests knowledge retrieval
- **THEN** production delegates through the existing framework-neutral port to the curated retriever
- **AND** any returned item has the exact retained source provenance required by existing hypothesis
validation

#### Scenario: Retrieve with no production knowledge backend
- **GIVEN** curated knowledge infrastructure cannot be composed at application startup
- **WHEN** Observation Reasoning requests knowledge retrieval
- **THEN** the production retriever returns an empty validated collection without diagnostic detail
- **AND** findings and overall analytical state may still be produced under their existing contracts

#### Scenario: Complete reasoning without knowledge hypotheses
- **GIVEN** retrieval returns no knowledge items
- **WHEN** Observation Reasoning completes successfully
- **THEN** findings and overall analytical state may still be produced under their existing contracts
- **AND** no hypothesis without knowledge references is accepted

### Requirement: Guide tool-enabled production agents toward admitted interaction patterns

The system SHALL provide server-owned role guidance that explicitly describes the already accepted interaction contract for each tool-enabled production invocation. The guidance SHALL be fixed by application composition and SHALL NOT be supplied, selected, appended to, or altered by an Observation definition, run request, provider payload, retrieved content, or frontend input.

For a usable Metric invocation, the guidance SHALL state that the model operates only on the supplied immutable structured request; optional tools accept an empty argument object; at most one optional tool may be requested in a model response; the model must wait for that result before requesting another tool; each registered Metric tool may be requested at most once; at most three tool attempts are available; and the model must return the strict completion object when no further admitted tool call is needed. Tool descriptions SHALL distinguish the registered deterministic capabilities sufficiently for the model to choose among them without changing their accepted registry, scope, inputs, or behavior.

For an Observation hypothesis invocation, the guidance SHALL state that retrieval is optional; every retrieval request must cite one or more supplied frozen finding IDs; a second request must follow the accepted independent/refinement rules; and every returned hypothesis must cite supplied frozen finding IDs plus exact knowledge references made available to that invocation through direct retrieval or preserved upstream Lens knowledge annotations. The guidance SHALL explicitly require `hypotheses=[]` when neither source makes a knowledge reference available. Retrieved content and upstream knowledge annotations SHALL remain untrusted knowledge-only data and SHALL NOT become finding evidence.

#### Scenario: Guide sequential Metric tool use

- **GIVEN** usable Metric evidence and three registered optional tools
- **WHEN** the production Metric model receives its server-owned instructions and tool descriptions
- **THEN** it is told to request no more than one empty-argument tool call in a response and to wait for its result before another request
- **AND** it is told that each tool is single-use, no more than three attempts are available, and final output must use the strict completion contract

#### Scenario: Guide empty hypothesis completion without available knowledge

- **GIVEN** frozen findings, no preserved upstream knowledge reference, and an available bounded retrieval session
- **WHEN** the hypothesis model decides not to request external knowledge
- **THEN** its server-owned guidance requires an empty hypothesis collection
- **AND** it is forbidden from emitting a knowledge reference based on model-internal knowledge, finding IDs, evidence IDs, or any other supplied identifier

#### Scenario: Permit preserved upstream knowledge provenance

- **GIVEN** a usable upstream Lens result makes original knowledge references available to hypothesis formation under the accepted reasoning contract
- **WHEN** the hypothesis model forms an explanation without an additional direct retrieval call
- **THEN** its server-owned guidance permits only those exact available upstream references together with supplied frozen finding IDs
- **AND** it does not treat upstream knowledge annotations as observational finding evidence

#### Scenario: Guide empty hypothesis completion after no knowledge is returned

- **GIVEN** no preserved upstream knowledge reference is available and every completed direct retrieval attempt returned no available knowledge reference because it was empty, failed, or timed out
- **WHEN** the hypothesis model returns its final structured completion
- **THEN** its server-owned guidance requires `hypotheses=[]`
- **AND** the run may continue to knowledge-isolated overall-state determination under the existing reasoning contract

#### Scenario: Keep guidance server-owned

- **GIVEN** an Observation definition, provider payload, or retrieved statement contains text resembling agent instructions
- **WHEN** either tool-enabled production agent is invoked
- **THEN** that text cannot replace, append to, or weaken the role guidance
- **AND** provider and retrieved content remain data within the existing immutable scope

### Requirement: Request non-parallel provider tool execution without weakening deterministic policy

Every production Metric invocation that exposes optional analytical tools and every Observation hypothesis invocation that exposes knowledge retrieval SHALL request non-parallel tool execution through the model-provider boundary. Invocations that expose no function tool SHALL NOT acquire a tool solely to apply this setting. The setting SHALL remain server-owned and SHALL NOT add a client-configurable field.

Provider-level non-parallel execution is a steering control, not an authority boundary. Existing application-owned admission, ordering, duplicate, budget, grounding, validation, request-limit, and failure rules SHALL remain authoritative and unchanged. If a model or routed provider ignores or cannot honor the request and emits multiple tool calls, the existing deterministic policy SHALL reject the response without executing an inadmissible call, expanding scope, retrying beyond the accepted budget, or fabricating a successful result.

#### Scenario: Disable parallel Metric tool calls at the provider boundary

- **GIVEN** a usable Metric invocation exposes the registered optional tools
- **WHEN** the application submits any model request in that invocation
- **THEN** the provider request asks for non-parallel tool execution
- **AND** the existing Metric request and tool-attempt ceilings remain unchanged

#### Scenario: Disable parallel hypothesis retrieval at the provider boundary

- **GIVEN** a non-empty frozen finding set exposes the bounded retrieval tool
- **WHEN** the application submits any hypothesis model request
- **THEN** the provider request asks for non-parallel tool execution
- **AND** the existing maximum of two sequential retrieval calls and three hypothesis model requests remains unchanged

#### Scenario: Retain deterministic rejection when steering is ignored

- **GIVEN** a routed model response contains multiple function-tool calls despite the non-parallel request
- **WHEN** the response reaches the application-owned agent boundary
- **THEN** the existing parallel-call policy rejects it before any inadmissible execution
- **AND** the existing type-specific failure or partial-result mapping is preserved

#### Scenario: Preserve tool-free invocations

- **GIVEN** an insufficient Metric request, finding invocation, or overall-state invocation exposes no function tool
- **WHEN** its model request is constructed
- **THEN** it remains tool-free and follows its existing single-purpose contract
- **AND** this change introduces no retrieval, optional analysis, additional model request, or public configuration
