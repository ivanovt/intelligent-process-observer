## Purpose

Provide a reusable, source-agnostic boundary for bounded external knowledge retrieval that future agents can use without weakening finding grounding or evidence provenance.

## Requirements

### Requirement: Represent source-agnostic retrieval inputs and outputs

The system SHALL define strict, immutable, framework-neutral contracts for a retrieval request, a retrieved knowledge item, a knowledge reference, and every execution outcome. A request SHALL contain a non-empty query and one or more finding IDs that ground the query. Each retrieved item SHALL contain a non-empty knowledge statement and one or more source references actually associated with that statement. A source reference SHALL carry non-empty opaque `source_id` and `reference` values; this capability SHALL NOT impose a URI grammar or interpret provider-specific locator syntax.

The execution outcome SHALL be exactly one of `retrieved`, `failed`, `timed_out`, or `rejected`. A `retrieved` outcome MAY contain zero or more items; an empty item collection represents a successful retrieval with no matching knowledge. Failed, timed-out, and rejected outcomes SHALL expose no retrieved items. These contracts SHALL contain no PydanticAI, model-provider, vector-store, or concrete retriever types.

#### Scenario: Return retrieved knowledge with opaque provenance

- **GIVEN** a valid grounded request and an injected retriever that returns two valid knowledge items
- **WHEN** retrieval completes
- **THEN** the outcome is `retrieved` with both items and their non-empty `source_id` and `reference` values unchanged
- **AND** no provider-specific reference grammar is inferred or validated

#### Scenario: Represent a successful empty retrieval

- **GIVEN** a valid grounded request and an injected retriever that finds no matching knowledge
- **WHEN** retrieval completes successfully
- **THEN** the outcome is `retrieved` with an empty item collection
- **AND** the foundation does not classify the result as sufficient or insufficient

#### Scenario: Keep contracts independent of agent and retriever frameworks

- **GIVEN** the retrieval contracts and source boundary are inspected
- **WHEN** their public types are enumerated
- **THEN** they contain no PydanticAI, LLM-provider, embedding, vector-database, or search-provider types

### Requirement: Bind retrieval to an immutable frozen-finding scope

Each bounded retrieval session SHALL be created for one non-empty, immutable set of frozen finding IDs. Every request SHALL cite at least one finding ID. When an available-budget, idle session receives a request containing any ID outside its frozen set, the executor SHALL reject it as `unknown_finding` before invoking the retriever. Retrieval SHALL not accept raw telemetry, mutable Observation or Lens configuration, provider queries, or a mechanism for expanding the observational data scope.

Finding-ID admission is only the shared grounding minimum. This foundation SHALL NOT represent or validate consumer-specific knowledge subjects. In particular, a future Log consumer SHALL validate that its query is anchored to a concrete already-observed template, error code, component-specific message, or log terminology before submitting the shared request. Acceptance by this executor SHALL NOT be treated as proof that the stricter Log subject contract was satisfied.

#### Scenario: Execute a query grounded in frozen findings

- **GIVEN** a retrieval session bound to frozen finding IDs `finding-1` and `finding-2`
- **WHEN** a request cites `finding-2` and supplies a non-empty query
- **THEN** the request is eligible for execution against the injected retriever

#### Scenario: Reject an unknown finding anchor

- **GIVEN** an idle retrieval session with available budget bound to frozen finding ID `finding-1`
- **WHEN** a request cites `finding-1` and unknown ID `finding-3`
- **THEN** the outcome is `rejected` with reason `unknown_finding`
- **AND** the retriever is not invoked and no retrieval slot is consumed

#### Scenario: Leave Log subject validation to the future Log consumer

- **GIVEN** a request cites a valid frozen Log finding ID but this shared foundation has no Log subject contract
- **WHEN** the request is admitted by the bounded executor
- **THEN** admission establishes finding-ID grounding only
- **AND** it does not establish that a template, error code, component-specific message, or log terminology was resolved from observed Log evidence

### Requirement: Enforce a two-call sequential execution budget

One retrieval session SHALL permit at most two executed retrieval calls. Every admitted call SHALL consume one slot once retriever invocation begins, whether it returns items, returns no items, fails, times out, or is interrupted by caller cancellation. A request after both slots are consumed SHALL be rejected as `over_budget` without invoking the retriever or consuming another slot. The executor SHALL prevent concurrent execution within one session and, while budget remains, SHALL reject an overlapping request as `concurrent` without invoking the retriever or consuming a slot.

For every structurally valid submitted request, the executor SHALL apply admission checks in this exact order and SHALL return the first applicable rejection: (1) `over_budget` when two execution slots are consumed; (2) `concurrent` while another call is active; (3) `unknown_finding` when any cited finding is outside the frozen set; (4) `invalid_refinement` when refinement metadata is not valid for the next execution. Contract-shape validation occurs before submission to the executor and is outside this rejection precedence and ledger.

#### Scenario: Use both retrieval calls

- **GIVEN** a new retrieval session
- **WHEN** two valid requests execute sequentially
- **THEN** both requests invoke the retriever
- **AND** the session reports that both retrieval slots are consumed

#### Scenario: Count failure toward the call budget

- **GIVEN** a new retrieval session whose first valid request fails in the retriever
- **WHEN** a second valid request executes
- **THEN** the second request uses the final available slot
- **AND** the failed first execution and the second execution count as two calls

#### Scenario: Reject a third execution

- **GIVEN** two retrieval calls have executed in one session
- **WHEN** another valid request is submitted
- **THEN** the outcome is `rejected` with reason `over_budget`
- **AND** the retriever is not invoked a third time

#### Scenario: Reject overlapping execution

- **GIVEN** one retrieval call is still executing in a session with one remaining slot
- **WHEN** another request is submitted to the same session
- **THEN** the second outcome is `rejected` with reason `concurrent`
- **AND** the overlapping request does not invoke the retriever or consume a slot

#### Scenario: Prefer budget rejection over finding rejection

- **GIVEN** two retrieval slots are consumed
- **WHEN** another request cites an unknown finding ID
- **THEN** the outcome is `rejected` with reason `over_budget`
- **AND** no later admission rule is evaluated for the outcome

#### Scenario: Prefer concurrency rejection over grounding and refinement rejection

- **GIVEN** one retrieval call is active with one remaining slot
- **WHEN** an overlapping request cites an unknown finding and also declares a premature refinement
- **THEN** the outcome is `rejected` with reason `concurrent`
- **AND** neither `unknown_finding` nor `invalid_refinement` is selected

#### Scenario: Prefer finding rejection over refinement rejection

- **GIVEN** an idle new session with available budget
- **WHEN** the first request cites an unknown finding and declares a premature refinement
- **THEN** the outcome is `rejected` with reason `unknown_finding`
- **AND** `invalid_refinement` is not selected

### Requirement: Allow only a grounded second-call refinement

A request MAY declare itself as a refinement only when exactly one earlier call has executed in the same session. A refinement SHALL carry a non-empty unresolved knowledge gap and SHALL remain grounded exclusively in the session's frozen finding IDs. It SHALL be linked implicitly and exclusively to executed-call ordinal 1; the request SHALL NOT select a submission-ledger ordinal or another target. A refinement submitted before the first executed call SHALL be rejected as `invalid_refinement` without invoking the retriever or consuming a slot. After two calls have executed, every request SHALL follow the budget rule and be rejected as `over_budget` regardless of refinement metadata. The foundation SHALL NOT decide whether prior knowledge is useful enough to justify refinement. The second executed call MAY instead be an independent, non-refinement query grounded in the same frozen-finding scope.

#### Scenario: Refine the first retrieval

- **GIVEN** one grounded retrieval call has executed
- **WHEN** a second grounded request declares refinement and states a non-empty unresolved knowledge gap
- **THEN** the refinement is eligible to execute as the second call
- **AND** it is linked to executed-call ordinal 1 regardless of that call's submission-ledger ordinal

#### Scenario: Reject refinement before an initial call

- **GIVEN** a new retrieval session with no executed call
- **WHEN** its first request declares a refinement
- **THEN** the outcome is `rejected` with reason `invalid_refinement`
- **AND** the retriever is not invoked and no slot is consumed

#### Scenario: Refine after a rejected submission

- **GIVEN** submission 1 was rejected without execution and submission 2 became executed-call ordinal 1
- **WHEN** submission 3 is a valid grounded refinement with a non-empty unresolved knowledge gap
- **THEN** it executes as executed-call ordinal 2 and refines executed-call ordinal 1
- **AND** neither rejected submission 1 nor submission-ledger ordinal 2 is interpreted as the refinement identifier

#### Scenario: Execute an independent second query

- **GIVEN** one grounded retrieval call has executed
- **WHEN** the next valid grounded request contains no refinement metadata
- **THEN** it is eligible to execute as an independent second call
- **AND** no third call can execute afterward

### Requirement: Isolate retriever failures from future analytical behavior

The executor SHALL invoke knowledge acquisition only through an injected asynchronous source-agnostic retriever boundary. A retriever `TimeoutError` SHALL become a `timed_out` outcome with fixed `diagnostic_code=retriever_timed_out`. Any other non-cancellation retriever exception SHALL become a `failed` outcome with fixed `diagnostic_code=retriever_failed`, and an invalid returned contract SHALL become a `failed` outcome with fixed `diagnostic_code=invalid_retriever_result`. Failed and timed-out outcomes SHALL contain no free-text diagnostic, exception type or message, traceback, query text, retrieved document content, credential, or provider-internal detail. These outcomes SHALL remain local to retrieval and SHALL not create findings, hypotheses, knowledge annotations, partial Lens results, or runtime lifecycle transitions.

#### Scenario: Normalize a retriever timeout

- **GIVEN** an admitted request whose retriever raises `TimeoutError`
- **WHEN** the executor handles the call
- **THEN** it returns `timed_out` with `diagnostic_code=retriever_timed_out` and without retrieved items or a propagated exception
- **AND** the executed call consumes one retrieval slot

#### Scenario: Normalize a retriever failure

- **GIVEN** an admitted request whose retriever raises another exception
- **WHEN** the executor handles the call
- **THEN** it returns `failed` with `diagnostic_code=retriever_failed` and no traceback or retrieved items
- **AND** no analytical artifact or runtime state is created or changed

#### Scenario: Normalize an invalid retriever result

- **GIVEN** an admitted request whose retriever returns data that does not satisfy the validated batch contract
- **WHEN** the executor handles the call
- **THEN** it returns `failed` with `diagnostic_code=invalid_retriever_result` and no retrieved items
- **AND** the invalid data does not escape through the outcome or ledger

#### Scenario: Do not disclose retriever exception content

- **GIVEN** a retriever exception message contains sentinel credentials, query text, document text, and provider details
- **WHEN** the executor maps the exception to an outcome and ledger entry
- **THEN** only the fixed `retriever_failed` diagnostic code is observable
- **AND** none of the sentinel values, exception type or message, or traceback is observable

#### Scenario: Propagate caller cancellation and restore executor availability

- **GIVEN** an admitted retrieval call has invoked the retriever and is awaiting completion
- **WHEN** its caller task is cancelled
- **THEN** cancellation propagates unchanged and is not converted to `retrieved`, `failed`, `timed_out`, or `rejected`
- **AND** the started invocation keeps its consumed execution slot, the active-call guard is released, and a later request can be admitted when one slot remains
- **AND** no broader ObservationRun or LensRun cancellation, retry, idempotency, or replay behavior is selected by this capability

### Requirement: Maintain an application-owned transient attempt ledger

The retrieval session SHALL expose an immutable ordered snapshot of every submitted request that returns a typed retrieval outcome. A caller-cancelled invocation SHALL have no typed outcome and no ledger entry; its reserved ordinals SHALL not be reused, so cancellation MAY leave gaps in later ledger ordinals.

Each ledger entry SHALL contain exactly: positive `submission_ordinal`; optional `execution_ordinal` of 1 or 2; `supported_finding_ids`; optional `refines_execution_ordinal`, whose only value is 1; `executed`; `consumed_slot`; `outcome` discriminator; optional controlled `rejection_reason` from `over_budget|concurrent|unknown_finding|invalid_refinement`; optional fixed `diagnostic_code` from `retriever_timed_out|retriever_failed|invalid_retriever_result`; and `knowledge_refs`, populated only from a `retrieved` outcome. It SHALL NOT contain raw query text, unresolved-knowledge-gap text, retrieved knowledge statements, exception information, document content, credentials, provider details, chain-of-thought, or framework-native messages. Rejected entries SHALL have no execution ordinal. The ledger SHALL be application-owned and SHALL not be persisted by this capability.

#### Scenario: Record executed and rejected requests in order

- **GIVEN** two calls execute and a third request is rejected over budget
- **WHEN** the ledger is read
- **THEN** it contains entries with submission ordinals 1, 2, and 3
- **AND** the first two entries have execution ordinals 1 and 2 while the rejected third entry has no execution ordinal
- **AND** only the first two entries are marked executed and slot-consuming

#### Scenario: Keep submission and execution order distinct

- **GIVEN** the first submission is rejected and the next two submissions execute
- **WHEN** the ledger is read
- **THEN** submission ordinals are 1, 2, and 3 while execution ordinals are absent, 1, and 2 respectively
- **AND** a refinement in the third submission can reference only executed-call ordinal 1

#### Scenario: Exclude sensitive request and result text from the ledger

- **GIVEN** a completed refinement contains sentinel query and unresolved-gap text and returns a sentinel knowledge statement with valid references
- **WHEN** the ledger snapshot is read
- **THEN** it contains the supported finding IDs, structural refinement target, outcome discriminator, and returned knowledge references
- **AND** it contains none of the query, unresolved-gap, or knowledge-statement sentinel text

#### Scenario: Omit a caller-cancelled invocation from the ledger without reusing ordinals

- **GIVEN** submission ordinal 1 starts as execution ordinal 1 and is cancelled by its caller before a typed outcome exists
- **WHEN** the next request completes successfully
- **THEN** the ledger contains only the later entry with submission ordinal 2 and execution ordinal 2
- **AND** the cancelled invocation's consumed slot and omitted ordinals are not reused

#### Scenario: Keep the ledger transient and framework-neutral

- **GIVEN** a retrieval session has recorded outcomes
- **WHEN** the capability completes
- **THEN** it performs no database write and emits no runtime analytical artifact
- **AND** the ledger contains no model messages, chain-of-thought, or agent-framework objects
