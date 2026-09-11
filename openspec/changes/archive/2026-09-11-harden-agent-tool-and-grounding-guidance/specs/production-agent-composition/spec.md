## ADDED Requirements

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
