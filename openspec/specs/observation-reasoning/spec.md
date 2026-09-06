# observation-reasoning Specification

## Purpose
Provide a bounded, traceable Observation-level reasoning capability that turns validated Metric, Alert, and Relationship evidence into frozen findings, knowledge-grounded hypotheses, deterministic limitations, and a strict machine-readable analysis result.

## Requirements

### Requirement: Accept one correlated Observation reasoning scope

The system SHALL accept one strict immutable reasoning scope containing the Observation and ObservationRun identity, a compact semantic Observation context, an ordered collection of usable Lens results, an ordered collection of self-contained Relationship evaluations, and an ordered collection of unavailable Lens metadata. For this change, every configured Lens in the semantic context SHALL have type `metric` or `alert`; a context containing a `log` Lens or any other Lens type SHALL be rejected before the exact Lens-scope partition is evaluated. The semantic context SHALL contain only Observation identity, name, optional description, objective, and the identity, type, name, optional description, and ordered analysis objectives of its configured Lenses. It SHALL exclude provider queries, credentials, endpoints, raw telemetry, retry/timeout settings, concurrency settings, persistence settings, and other infrastructure configuration.

For this change, a usable Lens result SHALL be exactly a validated `completed + good|degraded` or `partial + good|degraded` MetricAnalysisResult 1.0, or a validated `completed|partial` AlertAnalysisResult 1.0. A `completed + insufficient` Metric result SHALL NOT be usable analytical evidence and SHALL instead be represented as unavailable with reason code `insufficient_data` and no component. Failed Metric results and failed Alert LensRuns SHALL be represented as unavailable metadata rather than empty usable evidence. Log results, Log Lens identities in the semantic context, and Log-local knowledge annotations SHALL remain outside this capability until the deferred Log feature is introduced.

Unavailable Lens metadata SHALL reuse the accepted structured runtime-reason shape exactly: a required non-empty opaque `code` and an optional `component`, with no message, diagnostic, exception, or additional reason field. It SHALL also carry a reasoning-owned `origin` discriminator. Caller-supplied failed or otherwise non-usable Metric and Alert Lenses SHALL use `origin=caller_unavailable`, preserve the producer-supplied code and component exactly, and project to `missing_lens_evidence`; the reason-code set SHALL remain open to controlled upstream extension. Only the deterministic `completed + insufficient` Metric projection SHALL create `origin=completed_insufficient_metric`, requiring `code=insufficient_data` and an absent component, and it SHALL project to `insufficient_lens_evidence`.

The boundary SHALL require at least one usable result and SHALL require the usable and unavailable collections to form an exact partition of the `(lens_type, lens_id)` identities declared by the semantic Observation context. It SHALL reject duplicate identities within either collection, overlap between the collections, a configured Lens missing from both collections, any usable or unavailable Lens absent from the context, duplicate Relationship IDs, and usable results whose Observation or ObservationRun identity disagrees with the reasoning scope. Relationship evaluations SHALL be accepted only as caller-correlated artifacts for that same run because their accepted contract contains no run identity. The system SHALL preserve the supplied ordering after validation.

#### Scenario: Accept mixed Metric and Alert evidence
- **GIVEN** one correlated reasoning scope contains a completed sufficient Metric result, a partial Alert result, self-contained Relationship evaluations, and unavailable Lens metadata
- **WHEN** reasoning input is validated
- **THEN** the Metric and Alert results remain usable in their supplied order
- **AND** Relationship and unavailable metadata remain distinct inputs

#### Scenario: Treat an insufficient Metric as unavailable
- **GIVEN** current Metric acquisition completed but its validated result has `data_quality=insufficient` and no analytical evidence
- **WHEN** the reasoning scope is formed
- **THEN** the Metric result is excluded from usable analytical evidence
- **AND** the Lens is represented as unavailable with reason code `insufficient_data` and no component

#### Scenario: Reject a context containing a Log Lens
- **GIVEN** the semantic Observation context declares a configured Lens with type `log`
- **WHEN** the reasoning scope is validated
- **THEN** the request is rejected before the usable and unavailable collections are partitioned
- **AND** the Log Lens is not misrepresented as unavailable Metric or Alert evidence

#### Scenario: Preserve a producer-supplied unavailable reason
- **GIVEN** a failed Metric or Alert Lens is supplied as unavailable with a non-empty structured reason code and an optional component
- **WHEN** the reasoning scope is validated
- **THEN** the code and component are preserved exactly in unavailable metadata
- **AND** no reasoning-specific reason translation or free-text diagnostic is introduced

#### Scenario: Reject an invalid unavailable reason shape
- **GIVEN** unavailable Lens metadata has a missing or empty reason code, a free-text message, or another extra field
- **WHEN** the reasoning scope is validated
- **THEN** the request is rejected before model or retrieval work begins

#### Scenario: Reject an empty usable evidence scope
- **GIVEN** every Lens is failed or analytically insufficient
- **WHEN** Observation reasoning is requested
- **THEN** the request is rejected before any model or retrieval call
- **AND** no ObservationAnalysisResult is fabricated

#### Scenario: Reject inconsistent correlation
- **GIVEN** a usable result belongs to another ObservationRun, a Lens is both usable and unavailable, or a `(lens_type, lens_id)` identity is duplicated
- **WHEN** the reasoning scope is validated
- **THEN** the request is rejected without a partial reasoning result

#### Scenario: Require an exact Lens-scope partition
- **GIVEN** a configured context Lens is missing from both input collections or either collection contains a Lens identity absent from the context
- **WHEN** observation reasoning is requested
- **THEN** the request is rejected before model or retrieval work begins
- **AND** no out-of-scope evidence or fabricated availability limitation reaches reasoning

#### Scenario: Exclude technical configuration and raw data
- **GIVEN** a validated reasoning scope is projected for model use
- **WHEN** its fields are inspected
- **THEN** it contains the full structured usable analytical results and compact semantic context
- **AND** it contains no raw samples, provider payloads, provider queries, credentials, endpoints, or execution and persistence settings

### Requirement: Build a deterministic fine-grained evidence catalog

Before finding formation, the system SHALL deterministically build an immutable catalog of the specific admissible analytical elements in the usable Metric and Alert results and Relationship evaluations. Each entry SHALL have a unique run-local catalog ID and a structured resolvable reference containing exactly `source_type`, `source_id`, and `locator`. `source_type` SHALL be one of `metric_result`, `alert_result`, or `relationship_evaluation`; `source_id` SHALL identify the exact LensRun for a Lens result or the exact Relationship for an evaluation; and `locator` SHALL identify a concrete semantic, evidence, record, finding, comparison, or evaluation element inside that validated source artifact.

Catalog entries SHALL cover the available Metric current semantics and numerical evidence, optional Metric semantic/evidence pairs, each available reference-period semantic/evidence element, available History semantics/evidence, Alert current records and deterministic aggregate elements, Alert comparisons and Lens-local findings, Alert overall importance, and Relationship applicability, optional state, and complete condition/expectation evidence elements. Identity, provenance, configuration, unavailable metadata, partial reasons, operational diagnostics, retrieval content, and knowledge references SHALL NOT become finding evidence entries.

Catalog construction SHALL preserve source contract distinctions and SHALL NOT infer new analytical facts, flatten missing optional sections into placeholder values, or treat an unavailable or insufficient Lens as evidence. Every entry SHALL resolve to exactly one existing element in the immutable source set. The catalog itself SHALL be transient; the final finding SHALL retain the corresponding structured references rather than unstable catalog ordinals.

#### Scenario: Catalog exact Metric, Alert, and Relationship elements
- **GIVEN** usable Metric and Alert results and one Relationship evaluation contain current, temporal, record, aggregate, finding, and evaluation elements
- **WHEN** the evidence catalog is built
- **THEN** each admissible existing element receives a unique catalog entry with its exact source identity and locator
- **AND** no unavailable optional element receives a placeholder entry

#### Scenario: Keep non-evidence data out of the catalog
- **GIVEN** source artifacts also contain identity, provenance, partial reasons, provider-native source references, and operational metadata
- **WHEN** catalog entries are enumerated
- **THEN** only contract-defined analytical elements are admissible finding evidence
- **AND** technical configuration, diagnostics, and external knowledge are absent

#### Scenario: Resolve every retained reference
- **GIVEN** a validated final finding contains structured evidence references translated from catalog IDs
- **WHEN** each reference is resolved against the immutable source artifacts for that ObservationRun
- **THEN** every reference identifies exactly one existing analytical element

#### Scenario: Avoid unstable catalog identifiers in the result
- **GIVEN** run-local catalog IDs are assigned for model citation
- **WHEN** the final ObservationAnalysisResult is built
- **THEN** catalog IDs are translated to structured `source_type + source_id + locator` references
- **AND** transient ordinal assignment is not persisted as the analytical traceability contract

### Requirement: Derive evidence-availability limitations deterministically

The system SHALL derive the complete `limitations` collection from validated Lens availability metadata before model reasoning. An unavailable Lens with `origin=caller_unavailable` SHALL produce `missing_lens_evidence`; an unavailable Lens with `origin=completed_insufficient_metric` SHALL produce `insufficient_lens_evidence`; and every partial usable Lens SHALL produce `partial_lens_analysis`. Each limitation SHALL contain its code, `lens_id`, and `lens_type`, plus the source partial-reason component when one exists. Limitations SHALL be ordered by the Observation semantic context's Lens order; unmatched inputs are invalid under the exact Lens-scope partition and SHALL never reach limitation projection.

The limitations collection SHALL be supplied to all reasoning invocations but SHALL not be authored, removed, reordered, or modified by a model. It SHALL describe evidence availability only and SHALL not contain free-text causal uncertainty, confidence, severity, recommendations, retrieval failures, or model diagnostics.

#### Scenario: Derive failed, insufficient, and partial limitations
- **GIVEN** one failed Lens, one completed-insufficient Metric Lens, and one partial usable Lens
- **WHEN** limitations are projected
- **THEN** the result contains respectively `missing_lens_evidence`, `insufficient_lens_evidence`, and `partial_lens_analysis`
- **AND** the partial limitation preserves its structured component

#### Scenario: Produce no limitation for complete usable evidence
- **GIVEN** every supplied Lens result is completed and analytically usable
- **WHEN** limitations are projected
- **THEN** the limitations collection is empty

#### Scenario: Prevent model-authored limitation changes
- **GIVEN** deterministic limitations have been formed
- **WHEN** any reasoning invocation completes
- **THEN** the final result copies the deterministic collection exactly
- **AND** no model output field can add, omit, rewrite, or reorder a limitation

### Requirement: Form and freeze findings before exposing retrieval

Observation reasoning SHALL use a three-stage process with up to three isolated structured model invocations in this order: finding formation, optional hypothesis formation with bounded retrieval, and knowledge-isolated overall-state determination. The finding invocation SHALL receive the compact semantic context, full usable structured results, Relationship evaluations, deterministic evidence catalog, and deterministic limitations. It SHALL have no knowledge-retrieval tool, retrieved statements, knowledge references, provider search capability, or other external-knowledge channel. Its only authored output SHALL be an ordered collection of zero or more findings.

Each finding SHALL contain a unique non-empty ID, a non-empty descriptive statement, and one or more unique catalog IDs. A deterministic boundary SHALL reject an unknown catalog ID, duplicate finding ID, duplicate reference within a finding, extra field, or invalid shape. Once validated, the exact finding IDs, statements, ordering, and translated structured evidence references SHALL become immutable for the rest of the run.

Findings SHALL describe only what the current Observation evidence supports. They SHALL NOT contain a domain cause asserted from external or model-internal knowledge, confidence, severity, probability, recommendation, prescribed action, root-cause classification, or finding taxonomy.

#### Scenario: Freeze valid cross-Lens findings
- **GIVEN** the first phase correlates Metric, Alert, and Relationship evidence using valid catalog IDs
- **WHEN** deterministic finding validation succeeds
- **THEN** the exact ordered findings and their structured evidence references become immutable
- **AND** later invocations cannot add, remove, or alter them

#### Scenario: Permit no significant finding
- **GIVEN** the available structured evidence supports no significant Observation-level conclusion
- **WHEN** the first phase completes
- **THEN** an empty finding collection is valid
- **AND** no retrieval session is exposed because there is no frozen finding anchor

#### Scenario: Reject fabricated evidence
- **GIVEN** the first phase cites a catalog ID that was not supplied
- **WHEN** finding output is validated
- **THEN** reasoning fails closed
- **AND** no finding snapshot or ObservationAnalysisResult is produced

#### Scenario: Keep external knowledge out of finding formation
- **GIVEN** a production retriever and model are configured
- **WHEN** the first phase executes
- **THEN** no retrieval capability or retrieved content is available to that phase
- **AND** findings are formed only from Observation evidence

### Requirement: Perform bounded hypothesis reasoning over frozen findings

The hypothesis invocation SHALL receive the compact semantic context, full usable structured results, Relationship evaluations, deterministic limitations, and the exact frozen findings. It SHALL author only an ordered collection of zero or more hypotheses and SHALL have no `overall_state` field. When the frozen finding collection is non-empty, the invocation SHALL receive exactly one run-scoped knowledge-retrieval session bound to those finding IDs. When the finding collection is empty, the system SHALL skip the model invocation, create the required empty hypothesis collection deterministically, and proceed to overall-state determination without constructing a retrieval session.

The run-scoped session SHALL reuse the accepted knowledge-retrieval capability and permit no more than two sequential executed calls. The model SHALL cite one or more frozen finding IDs in every request. It MAY stop without retrieval or after either call. It MAY make an independent second grounded call. It MAY mark the second call as a refinement only when the first call returned at least one knowledge item and the request includes a non-empty unresolved gap; otherwise a second call SHALL be independent. A rejected or policy-invalid tool request SHALL fail reasoning rather than reset or bypass the retrieval session.

Every valid retrieved item SHALL be treated as untrusted candidate knowledge rather than pre-classified sufficient or insufficient knowledge. Items returned by either executed call SHALL remain available for final hypothesis grounding. A retrieved empty batch, failure, or timeout SHALL expose no available references from that call and SHALL remain non-fatal to reasoning; the phase MAY continue within its remaining call budget and MAY complete with no hypotheses.

#### Scenario: Complete without retrieval
- **GIVEN** frozen findings require no external explanation or no supported explanation is necessary
- **WHEN** the hypothesis invocation completes without calling retrieval
- **THEN** it returns an empty hypothesis collection

#### Scenario: Skip hypothesis model work without findings
- **GIVEN** the immutable finding collection is empty
- **WHEN** hypothesis formation is reached
- **THEN** no hypothesis model request or retrieval session is created
- **AND** an empty hypothesis collection is carried to the final builder

#### Scenario: Ground a hypothesis with either retrieval call
- **GIVEN** one or two grounded retrieval calls return candidate knowledge
- **WHEN** the hypothesis invocation forms hypotheses
- **THEN** it may cite actually used references returned by either call
- **AND** no returned item is automatically required or classified as sufficient

#### Scenario: Refine a partially useful first result
- **GIVEN** the first call returns at least one useful item but leaves a specific knowledge gap
- **WHEN** the model submits its second call as a refinement
- **THEN** the request cites frozen findings and a non-empty unresolved gap
- **AND** it is linked to executed call one under the accepted retrieval contract

#### Scenario: Use an independent second call after no usable first knowledge
- **GIVEN** the first call is empty, failed, or timed out
- **WHEN** the model spends the remaining slot on another grounded query
- **THEN** the second request is independent rather than a refinement
- **AND** the first outcome contributes no final knowledge reference

#### Scenario: Degrade gracefully on retrieval failure
- **GIVEN** a retrieval execution fails or times out
- **WHEN** the hypothesis invocation can still complete validly
- **THEN** it may return `hypotheses=[]` and allow knowledge-isolated overall-state determination to proceed
- **AND** the retrieval failure does not become a finding, limitation, or fabricated hypothesis

### Requirement: Validate knowledge-grounded hypotheses exactly

Each hypothesis SHALL contain a unique non-empty ID, a non-empty statement, one or more unique `supported_by` finding IDs, and one or more unique knowledge references. Every `supported_by` value SHALL identify a frozen finding. Every knowledge reference SHALL exactly match a reference returned in a retrieved item during this reasoning run. References SHALL preserve the accepted opaque non-empty `source_id` and `reference` values without imposing a URI grammar.

A deterministic final boundary SHALL reject a hypothesis grounded only in model-internal knowledge, a missing or unknown finding ID, a missing or unavailable knowledge reference, duplicate IDs or references, ranking, confidence, probability, primary-hypothesis designation, root-cause certainty, recommendation, severity, or any extra field. Hypothesis order SHALL not imply priority.

#### Scenario: Accept a traceable hypothesis
- **GIVEN** a hypothesis cites frozen findings and knowledge references actually returned during the run
- **WHEN** final validation executes
- **THEN** the hypothesis is retained with those exact references

#### Scenario: Reject an invented knowledge reference
- **GIVEN** a hypothesis cites a non-empty reference that no retrieval call returned
- **WHEN** final validation executes
- **THEN** reasoning fails closed without an ObservationAnalysisResult

#### Scenario: Reject an explanation based only on internal knowledge
- **GIVEN** the model proposes a domain explanation without at least one available knowledge reference
- **WHEN** final validation executes
- **THEN** the hypothesis is rejected rather than treated as a valid explanation

#### Scenario: Preserve unranked plural hypotheses
- **GIVEN** multiple hypotheses are validly grounded
- **WHEN** they are serialized
- **THEN** all are retained in authored order without ranking, probability, confidence, or a primary hypothesis

### Requirement: Determine overall state in a knowledge-isolated invocation

After successful hypothesis formation, or after deterministic hypothesis omission for an empty finding set, the system SHALL invoke the Reasoning Agent separately to determine `overall_state`. This invocation SHALL receive the compact semantic context, full usable structured results, Relationship evaluations, deterministic evidence catalog, deterministic limitations, and exact frozen findings. It SHALL receive no hypotheses, retrieved statements, knowledge references, retrieval outcomes, retrieval ledger, retrieval tool, provider search capability, or model history from the hypothesis invocation. Its only authored output SHALL be `overall_state` with exactly one value from `no_significant_findings`, `significant_findings_present`, or `uncertain`.

The invocation SHALL execute after hypothesis reasoning but SHALL evaluate only Observation evidence and evidence availability. Retrieved knowledge SHALL be capable of influencing hypotheses only and SHALL have no data path into overall-state determination. No deterministic classifier SHALL replace this agent-owned assessment, and no hard consistency invariant SHALL be imposed between overall state and finding count.

#### Scenario: Determine state after hypothesis reasoning without knowledge
- **GIVEN** hypothesis reasoning completed with one or more knowledge-grounded hypotheses
- **WHEN** overall-state determination begins
- **THEN** it receives the Observation evidence, frozen findings, and deterministic limitations
- **AND** it receives none of the hypotheses, retrieved content, knowledge references, retrieval state, or hypothesis-phase model history

#### Scenario: Determine state after empty findings
- **GIVEN** finding formation returned no findings and hypothesis model work was skipped
- **WHEN** overall-state determination executes
- **THEN** the agent still returns one valid overall-state value from Observation evidence and limitations

#### Scenario: Preserve uncertainty with valid findings
- **GIVEN** valid frozen findings exist but missing or partial evidence prevents a reliable overall assessment
- **WHEN** the isolated invocation returns `uncertain`
- **THEN** that state is accepted without removing the findings

#### Scenario: Expose no retrieval capability for state determination
- **GIVEN** a production retriever is configured and was used during hypothesis formation
- **WHEN** the overall-state invocation is inspected
- **THEN** no retrieval tool or external-knowledge content is available to it

### Requirement: Produce the strict ObservationAnalysisResult 1.0 contract

On success, a deterministic builder SHALL produce one strict immutable `ObservationAnalysisResult` containing exactly `schema_version="1.0"`, identity, `overall_state`, the exact frozen findings, the validated hypotheses, and the exact deterministic limitations. Identity SHALL contain the existing UUID-valued `observation_id` and `observation_run_id` from the reasoning scope. The builder SHALL obtain overall state only from the isolated overall-state invocation and SHALL obtain hypotheses only from the hypothesis invocation.

`overall_state` SHALL be authored in the knowledge-isolated final invocation and SHALL be exactly `no_significant_findings`, `significant_findings_present`, or `uncertain`. It SHALL represent the overall analytical assessment rather than an absolute normal/anomalous classification. The contract SHALL permit `uncertain` with zero or more findings and SHALL impose no hard invariant between overall state and finding count.

The result SHALL forbid raw Lens results, the evidence catalog, retrieved statements, retrieval ledgers, prompts, model messages, provider/model details, technical diagnostics, report narrative, severity, confidence, probability, recommendations, root cause, finding taxonomy, and hypothesis ranking. It SHALL validate against the existing runtime persistence envelope without performing persistence in this capability.

#### Scenario: Build a complete successful result
- **GIVEN** every required reasoning invocation and deterministic validation succeeds
- **WHEN** the result is built
- **THEN** it contains exact identity, overall state, frozen findings, validated hypotheses, and deterministic limitations under schema version 1.0

#### Scenario: Preserve uncertainty with findings
- **GIVEN** valid findings exist but missing or partial evidence prevents a reliable overall assessment
- **WHEN** the knowledge-isolated overall-state invocation returns `overall_state=uncertain`
- **THEN** the findings remain present
- **AND** strict validation does not force another state

#### Scenario: Exclude transient reasoning data
- **GIVEN** model and retrieval interactions occurred
- **WHEN** the final result is serialized
- **THEN** it contains no catalog, retrieved statements, ledgers, prompts, framework messages, provider details, or diagnostics

#### Scenario: Remain side-effect free
- **GIVEN** a valid result is produced
- **WHEN** this capability completes
- **THEN** it returns the in-memory artifact without persisting it, changing ObservationRun lifecycle, generating a report, or invoking an HTTP endpoint

### Requirement: Fail closed with a safe typed reasoning error

The capability SHALL return a typed failure and no ObservationAnalysisResult when any required model invocation fails, times out, exceeds its model-request bound, violates tool policy, returns invalid structured output, or fails deterministic finding, hypothesis, reference, or final-result validation. The public failure SHALL contain one fixed code from `reasoning_model_failed`, `reasoning_model_timed_out`, `reasoning_policy_violated`, or `reasoning_result_invalid`, plus a controlled component from `finding_phase`, `hypothesis_phase`, `overall_state_phase`, or `result_builder`. It SHALL contain no exception text, prompt content, Lens data, retrieved statement, credential, provider response, model reasoning, stack trace, or other sensitive diagnostic.

Caller task cancellation SHALL propagate unchanged, create no typed success or failure artifact, and SHALL not be converted into a retry. Broader ObservationRun lifecycle and HTTP error mapping SHALL remain owned by the later Observation execution feature.

#### Scenario: Fail when any model invocation fails
- **GIVEN** the finding, hypothesis, or overall-state invocation encounters a model error
- **WHEN** reasoning terminates
- **THEN** it returns `reasoning_model_failed` for the corresponding component
- **AND** no partial or fabricated ObservationAnalysisResult exists

#### Scenario: Fail on a model timeout
- **GIVEN** a model request exceeds the configured per-request timeout
- **WHEN** the timeout is mapped
- **THEN** the capability returns `reasoning_model_timed_out` without provider diagnostic detail

#### Scenario: Fail on invalid output or references
- **GIVEN** a phase returns malformed output or deterministic validation rejects a finding, hypothesis, or final result
- **WHEN** failure is mapped
- **THEN** the capability returns a controlled policy or result-invalid code
- **AND** no invalid artifact crosses the boundary

#### Scenario: Propagate caller cancellation
- **GIVEN** the caller cancels an active reasoning operation
- **WHEN** cancellation is observed
- **THEN** cancellation propagates unchanged
- **AND** the capability performs no automatic retry or artifact construction

### Requirement: Bound model requests and completion size

The finding invocation SHALL permit exactly one model request and expose no framework validation retry. For a non-empty finding set, the hypothesis invocation SHALL permit at most three model requests: its initial request plus at most one continuation after each of the two possible sequential retrieval calls. The overall-state invocation SHALL permit exactly one model request and expose no tool or framework validation retry. Every actual request to the model SHALL count toward the applicable invocation ceiling. A hypothesis model request that attempts a tool call when no continuation budget remains SHALL terminate with a typed policy failure and SHALL not create an additional request. A run with non-empty findings SHALL therefore issue at most five model requests; a run with empty findings SHALL issue exactly two when both required invocations succeed.

Each model request SHALL use a system-configured positive timeout with default 120 seconds and a system-configured positive maximum completion-token value with default 12,288. The capability SHALL use zero framework output/tool validation retries. OpenRouter's routing of one submitted request MAY fail over under the separate system routing policy, but such provider routing SHALL NOT reset application phase state, findings, retrieval budget, or model-request accounting.

#### Scenario: Enforce the finding request ceiling
- **GIVEN** the finding phase starts
- **WHEN** its first model response is invalid
- **THEN** the phase fails without issuing a corrective second request

#### Scenario: Enforce the hypothesis request ceiling
- **GIVEN** the hypothesis phase uses both retrieval calls
- **WHEN** the continuation after the second tool result completes
- **THEN** at most three model requests have been issued in that phase
- **AND** no fourth request is permitted

#### Scenario: Enforce the overall-state request ceiling
- **GIVEN** the overall-state invocation starts
- **WHEN** its first model response is invalid
- **THEN** the invocation fails without issuing a corrective second request

#### Scenario: Bound total requests with findings
- **GIVEN** findings are non-empty and hypothesis formation uses both retrieval calls
- **WHEN** the overall-state invocation completes
- **THEN** the run has issued at most five model requests across all invocations

#### Scenario: Apply production defaults
- **GIVEN** no timeout or completion-token override is configured
- **WHEN** any reasoning invocation invokes the model
- **THEN** the request uses a 120-second timeout and a 12,288 maximum completion-token value

#### Scenario: Accept positive system overrides
- **GIVEN** an operator configures positive timeout and maximum completion-token values outside any artificial 8–12k range
- **WHEN** settings are validated
- **THEN** those positive values are accepted and applied system-wide to Observation Reasoning model requests

### Requirement: Configure a production OpenRouter model boundary

The production model boundary SHALL use OpenRouter with default model slug `openai/gpt-5.6-terra` and SHALL obtain its credential from `OPENROUTER_API_KEY`. The Observation Reasoning model slug SHALL be system-configurable as a non-empty OpenRouter model identifier so an operator can experiment with another compatible model without changing domain or application code. Configuration and adapter types SHALL remain outside all reasoning, evidence, finding, hypothesis, limitation, result, and retrieval contracts.

OpenRouter provider routing and fallback SHALL be enabled by default. The system SHALL expose system-wide configuration for an optional ordered provider list and an `allow_fallbacks` Boolean. When `allow_fallbacks=false`, configuration SHALL require exactly one non-empty provider identifier and SHALL send both that provider restriction and disabled fallback policy to OpenRouter. Any disabled-fallback configuration with zero or multiple providers SHALL fail settings validation. When fallback is enabled, zero or more ordered providers SHALL be valid and OpenRouter MAY route or fail over within that policy.

Missing or invalid credentials and invalid routing/model configuration SHALL fail model composition safely without logging or returning the secret. No OpenRouter request SHALL contain provider queries, infrastructure credentials other than the OpenRouter authorization credential, raw telemetry, or fields outside the validated model projection.

#### Scenario: Compose the default production model
- **GIVEN** a valid OpenRouter credential and no model override
- **WHEN** the Observation Reasoning adapter is composed
- **THEN** it targets `openai/gpt-5.6-terra` through OpenRouter
- **AND** provider-specific objects remain outside framework-neutral contracts

#### Scenario: Switch models through configuration
- **GIVEN** an operator supplies another non-empty compatible OpenRouter model slug
- **WHEN** the adapter is composed
- **THEN** all reasoning invocations use that configured model without a domain-contract change

#### Scenario: Allow default provider routing and fallback
- **GIVEN** fallback remains enabled and no provider order is configured
- **WHEN** a model request is sent
- **THEN** OpenRouter may select and fail over between compatible providers under its routing policy

#### Scenario: Pin one provider
- **GIVEN** fallback is disabled and exactly one provider is configured
- **WHEN** a model request is sent
- **THEN** OpenRouter is instructed to use only that provider without fallback

#### Scenario: Reject ambiguous disabled routing
- **GIVEN** fallback is disabled with either zero or more than one configured provider
- **WHEN** system settings are validated
- **THEN** configuration fails before any model request

#### Scenario: Protect the OpenRouter credential
- **GIVEN** model composition or a request fails
- **WHEN** the failure is returned or logged
- **THEN** the OpenRouter credential is absent from public errors, diagnostics, model projections, and analytical artifacts

### Requirement: Preserve feature and framework boundaries

The capability SHALL consume the existing bounded knowledge-retrieval port and executor as though a working production retriever is injected, but SHALL not implement, select, ingest, index, or configure the concrete knowledge corpus or retriever backend. It SHALL not implement Log reasoning, Report generation, top-level Observation execution, strict JOIN detection, the usable-results gate, ObservationRun lifecycle transitions, persistence coordination, scheduling, notification, or a public execution API.

The production agent integration SHALL use the approved PydanticAI framework behind framework-neutral reasoning ports. Supporting the native OpenRouter integration SHALL be the only dependency-surface change. PydanticAI, OpenRouter client, model-provider, and framework message types SHALL not appear in domain/application contracts or persisted analytical artifacts.

#### Scenario: Exercise reasoning with deterministic fakes
- **GIVEN** fake phase-agent and retriever implementations satisfy the framework-neutral ports
- **WHEN** the complete reasoning contract is tested
- **THEN** evidence projection, finding freeze, retrieval policy, hypothesis validation, limitations, result building, and failures are verifiable without a network call

#### Scenario: Run against an injected production-ready retriever
- **GIVEN** a working retriever is supplied through the accepted knowledge port
- **WHEN** the second reasoning phase requests knowledge
- **THEN** the same bounded two-call and reference-validation semantics apply without knowledge-backend types entering reasoning contracts

#### Scenario: Leave downstream workflow work separate
- **GIVEN** Observation reasoning succeeds or fails
- **WHEN** this capability returns to its caller
- **THEN** it does not persist the outcome, generate Markdown, transition an ObservationRun, or map the outcome to HTTP
