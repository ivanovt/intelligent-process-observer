# runtime-observability Specification

## Purpose

Provide bounded, correlation-friendly backend diagnostics and opt-in development agent interaction traces so trusted MVP developers can troubleshoot executions without weakening public runtime or secret boundaries.

## Requirements

### Requirement: Correlated operational error logging
The backend SHALL emit an operational log event for every application-owned handled or normalized failure and every unhandled exception at startup, HTTP/API, execution orchestration, provider, agent, knowledge retrieval, report generation, background-task management, and persistence boundaries. Each event SHALL include a stable event name, severity, UTC timestamp, safe failure category, exception type when an exception exists, and every correlation identifier available at that boundary. Logging SHALL preserve the existing exception propagation, runtime transition, and public error behavior.

#### Scenario: Normalized execution failure is logged
- **GIVEN** an Observation execution has assigned ObservationRun and LensRun identities
- **WHEN** a provider or agent exception is normalized into an existing safe runtime failure
- **THEN** the backend emits an error event containing the safe category and available ObservationRun, LensRun, Lens, stage, component, and agent-role identifiers
- **AND** the durable status and public reason remain governed by their existing contracts

#### Scenario: Unexpected application exception includes traceback
- **WHEN** an unexpected application exception reaches an application-owned error boundary
- **THEN** the backend emits an error event with its exception type and traceback
- **AND** the original exception propagation or fail-closed lifecycle behavior is unchanged

#### Scenario: Expected client rejection is not misclassified
- **WHEN** local validation or an expected business rule rejects a client request without an internal failure
- **THEN** the backend does not label that rejection as an internal application error or emit an exception traceback

### Requirement: Operational logs exclude secrets and unbounded content
Operational logs SHALL exclude API keys, passwords, bearer tokens, cookies, complete authorization values, provider credential objects, raw provider bodies, raw model prompts or completions, raw provider-native queries, and provider-originated label values. Free-text diagnostic values admitted to operational logs SHALL be explicitly allowlisted and bounded; arbitrary object or exception serialization SHALL NOT be used as a logging shortcut.

#### Scenario: Failure contains secret sentinels
- **GIVEN** configured credentials and an underlying provider exception contain recognizable secret sentinel values
- **WHEN** the failure is logged at any supported boundary
- **THEN** no configured secret, authorization value, credential object, raw request, or raw provider body appears in the emitted event or traceback rendering

#### Scenario: Agent failure is operationally summarized
- **WHEN** an agent request fails at provider, timeout, policy, output-schema, or deterministic validation handling
- **THEN** operational logs identify the role, phase, safe category, model name, timing, request ordinal, and available run correlation
- **AND** they do not contain the model-visible prompt, input, tool content, or completion

### Requirement: Prometheus runtime failures retain safe diagnostic categories
Production Metric acquisition SHALL distinguish safe internal diagnostic categories sufficient to troubleshoot source resolution, target validation, authentication, query rejection, multiple returned series, timeout, transport failure, oversized response, invalid response shape, provider warnings, and invalid sample data. The terminal Metric contract SHALL retain its existing safe public reason, while operational logs SHALL include the internal category and bounded relevant count, status, attempt, and duration metadata.

#### Scenario: Query returns multiple series
- **GIVEN** a Metric Lens query receives a valid Prometheus matrix response containing at least two series
- **WHEN** production acquisition enforces the one-series Metric Lens boundary
- **THEN** the Lens follows the existing `current_metric_acquisition_failed` behavior
- **AND** the correlated operational event identifies `multiple_series_returned` and a bounded observed series count without logging label values or the raw query

#### Scenario: Prometheus rejects query syntax
- **WHEN** Prometheus returns a valid error envelope for an invalid provider-native query
- **THEN** the Lens follows the existing safe acquisition-failure behavior
- **AND** the operational event identifies `query_rejected` with bounded safe status/error-type metadata but no provider-authored error text or raw query

#### Scenario: Authentication and transport failures remain distinct
- **WHEN** acquisition fails because of authentication, timeout, or transport availability
- **THEN** operational logs distinguish those categories and include bounded attempt/timing metadata
- **AND** credentials and transport request details remain absent

### Requirement: Full agent tracing is explicit and development-only
Full agent interaction tracing SHALL be disabled by default. It SHALL be enabled only by an explicit backend setting while `APP_ENV=development`; an attempt to enable it in any other environment SHALL fail configuration safely before the application becomes ready. Trace enablement SHALL NOT be controllable by an HTTP request, Observation definition, or frontend setting.

#### Scenario: Default startup
- **WHEN** the backend starts without explicit agent trace enablement
- **THEN** model interactions execute normally and no full trace artifact is written

#### Scenario: Development trace is enabled
- **GIVEN** `APP_ENV=development`
- **WHEN** the developer explicitly enables full agent tracing
- **THEN** every subsequent supported model invocation produces a correlated backend trace artifact

#### Scenario: Non-development trace enablement is rejected
- **GIVEN** `APP_ENV` is not `development`
- **WHEN** full agent tracing is enabled
- **THEN** backend configuration fails with a safe error before application readiness
- **AND** no model request or trace artifact is produced

### Requirement: Full traces reconstruct every agent interaction
For every Metric, Alert, Observation Reasoning finding/hypothesis/overall-state, and Report model invocation while tracing is enabled, the backend SHALL capture the exact PydanticAI-level system instructions and model-visible input, declared function/output schemas, chronological model requests and responses, admitted tool calls and returned tool outcomes, validated domain completion or validation failure, request timing, model identity, and usage metadata available from the framework. Failed, timed-out, policy-rejected, validation-rejected, and cancelled invocations SHALL retain all message history available before termination.

#### Scenario: Multi-request tool interaction succeeds
- **WHEN** an enabled agent invocation makes one or more admitted tool calls before producing a valid completion
- **THEN** its trace preserves the chronological request, tool call, application tool outcome, model continuation, and validated completion sequence

#### Scenario: Structured output is rejected
- **WHEN** a model response is received but strict output or deterministic grounding validation rejects it
- **THEN** the trace contains the available raw model message parts, the validation boundary, safe exception type/detail, and the absence of a validated completion

#### Scenario: Model call fails before a response
- **WHEN** the provider fails or times out before returning a model response
- **THEN** the trace retains the submitted model-visible messages, timing, safe failure category, and any partial framework history

#### Scenario: Parallel Lens agents are traced independently
- **WHEN** multiple Lens agents execute concurrently for one ObservationRun
- **THEN** every invocation is written to a distinct artifact correlated to its own LensRun
- **AND** message sequences are not interleaved or attributed to another invocation

### Requirement: Trace artifacts remain private, ephemeral, and non-authoritative
Full traces SHALL be stored as backend-local sensitive artifacts under a source-control-ignored temporary trace root, organized so a developer can locate invocations by ObservationRun and LensRun identity. They SHALL NOT be stored in PostgreSQL, included in domain artifacts or provenance, returned by public APIs, exposed by a trace viewer/download route, or used to change execution outcomes. The MVP SHALL document inspection, sensitivity, disk-growth, and explicit cleanup behavior and SHALL NOT perform automatic retention deletion.

#### Scenario: Developer correlates a failed run
- **GIVEN** tracing was enabled for a failed ObservationRun
- **WHEN** the developer searches the configured trace root by the run identifier shown in backend logs or the existing run UI
- **THEN** the developer can locate each attempted agent invocation and its terminal trace state

#### Scenario: Public run detail is requested
- **WHEN** any caller requests list or detail data for a traced run
- **THEN** the response contains only the existing public runtime fields
- **AND** no prompt, message, model setting, stack trace, trace path, or full-trace content is exposed

#### Scenario: Trace serialization fails
- **WHEN** a full trace cannot be serialized or written
- **THEN** the backend emits a safe correlated `trace_write_failed` operational error
- **AND** the agent result, execution lifecycle, and public response are not changed by the diagnostic failure

### Requirement: Agent trace serialization never exposes configured secrets
Trace serialization SHALL use an explicit allowlist for framework/provider metadata and SHALL exclude credential objects, provider transport headers, cookies, authorization values, and configured secret values. Exact model-visible operational content MAY remain in the development trace because it is the subject of debugging, and the trace SHALL be documented and handled as sensitive data.

#### Scenario: Provider metadata carries private transport data
- **WHEN** a framework model response includes provider metadata outside the trace allowlist
- **THEN** that metadata is omitted while model-visible message parts and safe usage data remain inspectable

#### Scenario: Known configured secret appears during serialization
- **GIVEN** a configured secret sentinel is present in data considered for trace serialization
- **WHEN** the artifact is written
- **THEN** the sentinel is absent or replaced with a fixed redaction marker

### Requirement: Record safe curated-knowledge retrieval decisions

After each successfully completed curated-knowledge retrieval search, the backend SHALL emit one correlated informational operational event that distinguishes `strict_admitted`, `relaxed_admitted`, and `no_match`. The event SHALL include only available run correlation, the selected controlled strategy category, and bounded aggregate counts for strict candidates, strict admissions, relaxed candidates, relaxed admissions, and returned passages. Counts for a path that was not evaluated SHALL be represented consistently without implying that the path ran.

The event SHALL NOT contain query text or terms, passage or document text, embeddings, lexical ranks, semantic distances, knowledge source identifiers, provider details, model messages, or credentials. Emission or serialization failure SHALL NOT alter the retrieval outcome, analytical result, runtime lifecycle, or public API response.

#### Scenario: Explain a successful relaxed retrieval safely
- **GIVEN** initial admission is empty and the relaxed fallback returns one or more passages
- **WHEN** the retrieval call completes successfully
- **THEN** one correlated informational event identifies `relaxed_admitted` and its bounded aggregate counts
- **AND** the event contains no query, content, score, distance, source, embedding, provider, or credential value

#### Scenario: Explain a successful no-match result safely
- **GIVEN** neither initial nor relaxed admission returns a passage
- **WHEN** the retrieval call completes successfully
- **THEN** one correlated informational event identifies `no_match` with zero returned passages and bounded aggregate decision counts
- **AND** the existing successful empty retrieval outcome remains unchanged

#### Scenario: Preserve retrieval when diagnostics fail
- **GIVEN** retrieval has selected a valid non-empty or empty result
- **WHEN** the diagnostic event cannot be serialized or emitted
- **THEN** retrieval returns the selected result unchanged
- **AND** no failure, limitation, hypothesis, or lifecycle transition is introduced by the diagnostic problem
