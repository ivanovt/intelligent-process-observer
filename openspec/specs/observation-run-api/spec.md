# observation-run-api Specification

## Purpose

Expose a safe public boundary for launching existing Observations and reading their durable run history and correlated analytical artifacts.

## Requirements

### Requirement: Launch one Observation run asynchronously

The system SHALL expose `POST /api/v1/observation-runs` with a strict request containing exactly an existing `observation_id` and an `analysis_window` with aware UTC `from` and `to` timestamps where `from < to` and `to` is not in the future at validation time. The server SHALL supply execution policy; clients SHALL NOT submit concurrency, deadline, model, tool, retry, provider, or orchestration settings.

During initialization, the system SHALL construct an immutable acceptance summary from the same committed runtime graph without a post-registration database lookup. It SHALL contain the fresh run and Observation identity/name, exact analysis window, `status=running`, `reason=null`, `analytical_state=null`, committed `created_at` and `started_at`, `finished_at=null`, `duration_seconds=null`, and relative detail `href`.

After the complete runtime graph commits, the initializer confirms its recovery generation is unchanged, and exactly one continuation plus that acceptance summary are registered atomically, the endpoint SHALL return `202 Accepted` using the captured summary even if the independent continuation has already advanced the durable run. It SHALL return no acceptance if initialization commit status is uncertain or recovery/shutdown fenced that admission. Response construction SHALL require no database await after continuation registration. Remaining execution SHALL continue independently of the HTTP request.

#### Scenario: Accept a valid launch

- **WHEN** a client launches an existing executable Observation with a valid past-facing UTC window
- **THEN** the endpoint returns `202 Accepted` with the immutable running acceptance summary and detail link captured during initialization
- **AND** execution continues after the response without requiring the client connection

#### Scenario: Return the acceptance snapshot after immediate completion

- **GIVEN** the registered continuation reaches terminal state before the HTTP response is serialized
- **WHEN** the launch endpoint returns
- **THEN** its `202` body remains the captured `status=running` initialization summary with no analytical or finish fields
- **AND** a subsequent list/detail read returns the newer durable terminal state

#### Scenario: Reject an invalid window

- **WHEN** `from` is not before `to`, either value is not an aware UTC timestamp, or `to` is in the future
- **THEN** the endpoint returns a safe validation error
- **AND** no ObservationRun, LensRun, artifact, or background task is created

#### Scenario: Keep execution policy server-owned

- **WHEN** a launch request includes an undeclared timeout, concurrency, retry, provider, model, or tool field
- **THEN** strict request validation rejects it
- **AND** the supplied field does not affect execution

#### Scenario: Do not accept a fenced initializer

- **GIVEN** initialization committed but recovery began before continuation registration
- **WHEN** the launch admission performs its generation recheck
- **THEN** the endpoint returns no `202 Accepted`
- **AND** reconciliation terminalizes the run without an analytical continuation

### Requirement: Map preparation and launch conflicts safely

The launch endpoint SHALL map `observation_not_found` to `404 Not Found`, an already-active same-Observation run to `409 Conflict`, and invalid definition, empty Lens topology, unsupported Lens type, or invalid request to a safe `422 Unprocessable Entity` response. The manager SHALL produce a launch-specific conflict outcome, separate from the closed internal execution outcome, after its serialized durable active lookup. A conflict response SHALL identify that stable existing `observation_run_id` and its relative detail `href` without creating a second runtime record; the run MAY become terminal after lookup without invalidating its identity or detail link.

The named active-run index SHALL remain defense in depth. If initialization nevertheless loses on that index, the transaction SHALL roll back fully and the service SHALL perform exactly one durable active-run lookup. If it finds a run, the API SHALL return the same `409` conflict. If it finds none because the competing run already became terminal or durable state cannot substantiate the conflict, the API SHALL return `503 Service Unavailable` with safe code `launch_admission_uncertain`, create no continuation, and require an explicit client retry. It SHALL NOT automatically re-run initialization. Other infrastructure inability to initialize durably SHALL return a safe server error and SHALL start no continuation.

No error response SHALL expose raw definitions, selectors, queries, credentials, provider responses, exception text, stack traces, prompts, or model details.

#### Scenario: Reject overlap with a useful conflict

- **GIVEN** the selected Observation has a pending or running run
- **WHEN** another launch is requested
- **THEN** the API returns `409 Conflict` with the existing active run identity and detail link
- **AND** no second run or task is created

#### Scenario: Resolve a defensive unique-index loss

- **GIVEN** initialization loses on the named active-run index despite serialized public admission
- **WHEN** one post-rollback lookup finds the committed active run
- **THEN** the API returns `409 Conflict` with that run's identity and detail link
- **AND** performs no automatic initialization retry

#### Scenario: Conflict disappears before defensive lookup

- **GIVEN** initialization loses on the named active-run index
- **WHEN** the one post-rollback lookup finds no active run
- **THEN** the API returns `503 Service Unavailable` with `launch_admission_uncertain`
- **AND** creates no continuation or replacement run without a new client request

#### Scenario: Reject an unsupported definition

- **WHEN** preparation finds an empty topology, invalid stored aggregate, or unsupported Lens type
- **THEN** the API returns a controlled `422 Unprocessable Entity` error
- **AND** includes no internal or provider diagnostic data

### Requirement: List all Observation runs newest first

The system SHALL expose `GET /api/v1/observation-runs` and return the complete non-paginated run history across all Observations in descending run creation order with deterministic run-identity tie-breaking. Every compact item SHALL contain only the run-summary fields defined by the launch response. An Observation analytical state SHALL be present only when a correlated ObservationAnalysisResult exists and SHALL be exactly `no_significant_findings`, `uncertain`, or `significant_findings_present`.

Execution status SHALL remain exactly `pending`, `running`, `completed`, `failed`, or `cancelled` and SHALL never be derived from analytical state. A failed or cancelled run without analysis SHALL return no analytical state; a failed run with an already persisted analysis MAY return that state independently.

#### Scenario: List mixed run outcomes

- **GIVEN** active, completed, failed, and cancelled runs exist across multiple Observations
- **WHEN** the history endpoint succeeds
- **THEN** all runs are returned exactly once newest first without pagination
- **AND** each item keeps execution status separate from its optional analytical state

#### Scenario: List no runs

- **WHEN** no ObservationRun exists
- **THEN** the endpoint returns `200 OK` with an empty array

### Requirement: Retrieve one complete safe run detail

The system SHALL expose `GET /api/v1/observation-runs/{observation_run_id}`. A successful response SHALL contain the compact run summary plus the exact ordered LensRun lifecycle records, each correlated persisted type-specific LensAnalysisResult where present, RelationshipEvaluations ordered by their persisted frozen-definition ordinal, the ObservationAnalysisResult where present, and the ObservationReport where present. Every field in one response SHALL derive from one coherent durable database snapshot; polling MAY observe progress between responses but SHALL NOT receive a torn lifecycle/artifact combination within one response.

Each LensRun item SHALL contain exactly `id`, `lens_id`, `lens_type`, `status`, optional `reason`, `started_at`, `finished_at`, derived optional `duration_seconds`, and optional `result`. `result` SHALL be a discriminated union of the complete existing strict artifact variants and SHALL preserve their exact contract versions:

- Metric schema `1.0`: `CompletedSufficientMetricResult`, `CompletedInsufficientMetricResult`, `PartialMetricResult`, or `FailedMetricResult`, including only their declared identity, status/reason, analysis window, data quality, current/reference/history semantics and evidence where the variant defines them, optional-tool projections where defined, and `source=prometheus`/generation provenance;
- Alert schema `1.0`: `CompletedAlertAnalysisResult` or `PartialAlertAnalysisResult`, including only declared identity, status/reason, analysis timestamp/window, canonical current alerts, mandatory aggregates, comparisons, unsuccessful optional-tool trace where present, Lens-local findings, overall importance, and source-provider/generation provenance.

The complete normalized `CanonicalAlertRecord` fields `id`, `title`, optional `description`, `started_at`, optional `ended_at`, `duration_seconds`, normalized and provider-source status, optional provider-native importance type/value, optional `occurrence_count`, and optional `source_ref` SHALL intentionally be public operational evidence inside trusted-MVP run detail. These strings SHALL be treated as untrusted display data. Raw provider records, rejected/malformed records, acquisition diagnostics, selector/query, provider address, credentials, transport payloads, and optional-tool successful data SHALL NOT be public.

Each RelationshipEvaluation item SHALL contain exactly its existing unversioned domain shape: `relationship_id`, `name`, optional `description`, `conditions`, `expectations`, `applicability`, and `state` only for `applicable`; each evidence item contains `lens_id`, accepted property, expected, optional observed, and optional match. Persistence ordinal controls array order but SHALL NOT appear in the domain payload.

Observation analysis SHALL be exactly `ObservationAnalysisResult` schema `1.0`: identity, overall state, findings with EvidenceReferences, hypotheses with finding IDs and KnowledgeReferences, and limitations. Report SHALL be exactly the existing unversioned `ObservationReport`: Observation/run identities, generated time, `format=markdown`, and content.

The response SHALL preserve these named domain artifact shapes and type-aware Lens identity while exposing only the enumerated runtime wrapper. It SHALL NOT expose credentials, raw execution context, persistence provenance outside accepted artifact provenance, prompts, model/provider settings or messages, internal task state, exception diagnostics, or undeclared ORM fields. Missing artifacts SHALL be represented as absent or `null`, not as successful empty analysis. If any stored artifact fails its named strict contract or wrapper correlation, the endpoint SHALL fail closed with safe `500 runtime_projection_invalid` rather than omit, partially serialize, or return the invalid artifact.

#### Scenario: Retrieve a completed mixed run

- **GIVEN** a completed run has Metric and Alert Lens results, RelationshipEvaluations, ObservationAnalysisResult, and ObservationReport
- **WHEN** its detail is requested
- **THEN** every artifact is returned under its distinct type and correlation
- **AND** Lens, Relationship, finding, hypothesis, limitation, evidence, knowledge, and report concepts remain separate

#### Scenario: Retrieve a progressing run

- **GIVEN** a running execution has only a subset of terminal Lens outcomes
- **WHEN** its detail is requested
- **THEN** current lifecycle records and already committed artifacts are returned
- **AND** future analysis and report artifacts are not fabricated

#### Scenario: Preserve atomic writer visibility

- **GIVEN** a Lens terminal transition and artifact insertion commit while detail is being read
- **WHEN** the API returns the detail response
- **THEN** both values are absent/pending from the earlier snapshot or both are visible from the later snapshot
- **AND** the response never exposes an artifact that contradicts its LensRun lifecycle

#### Scenario: Run detail is missing

- **WHEN** the requested ObservationRun identity does not exist
- **THEN** the endpoint returns a safe `404 Not Found` error

#### Scenario: Expose normalized Alert operational evidence intentionally

- **GIVEN** a valid Alert schema `1.0` artifact contains canonical provider-originated title, description, status source, importance, and source reference values
- **WHEN** trusted-MVP run detail is retrieved
- **THEN** those declared canonical fields are returned as untrusted display data
- **AND** raw provider payloads, query/configuration, credentials, and acquisition diagnostics remain absent

#### Scenario: Fail closed on an invalid stored artifact

- **GIVEN** a persisted artifact fails its named strict contract or run/Lens correlation
- **WHEN** run detail projection validates it
- **THEN** the endpoint returns safe `500 runtime_projection_invalid`
- **AND** does not omit or partially return the invalid artifact or expose validation diagnostics

### Requirement: Keep public run reads side-effect free

Listing or retrieving runs SHALL NOT start, resume, retry, cancel, mutate, or delete execution state or artifacts. Repeated reads SHALL return the latest durable snapshot and MAY observe forward lifecycle progress caused by the independently running execution.

#### Scenario: Poll an active run

- **GIVEN** a run is progressing independently
- **WHEN** a client repeatedly lists or retrieves it
- **THEN** each request performs no runtime mutation
- **AND** later responses may expose newly committed forward-only state and artifacts

### Requirement: Expose fail-closed launch availability during persistence recovery

The launch boundary SHALL accept requests only while the single-process Observation run manager is `ready`. Every admitted initializer SHALL be tracked before database work and fenced by the manager generation. While initialization or detached persistence state is uncertain, managed initializers/tasks are quiescing, or cancellation/reconciliation has not been durably verified, `POST /api/v1/observation-runs` SHALL return `503 Service Unavailable` with safe code `execution_recovery_pending` and SHALL create no new runtime record or task. The response SHALL NOT expose the failed operation, database diagnostic, affected run content, or retry internals.

Run list and detail reads SHALL remain best-effort during recovery because they do not mutate runtime state. A read SHALL return the latest durable projection when persistence is available and a safe `503` when it is not; it SHALL NOT infer or fabricate a terminal state from manager memory.

#### Scenario: Reject launch during recovery

- **GIVEN** a detached persistence failure placed the manager in `recovery_required`
- **WHEN** any Observation launch is requested
- **THEN** the API returns `503 Service Unavailable` with `execution_recovery_pending`
- **AND** creates no ObservationRun, LensRun, or task

#### Scenario: Fence an already-admitted launch during recovery

- **GIVEN** one launch initializer was admitted before recovery advanced the generation
- **WHEN** that initializer later attempts continuation registration or response release
- **THEN** it returns no `202` and registers no continuation
- **AND** the API exposes only safe recovery/unavailable behavior

#### Scenario: Read durable state during recovery

- **GIVEN** launch admission is blocked but persistence reads are available
- **WHEN** a client lists or retrieves runs
- **THEN** the API returns only the latest durable database state
- **AND** does not synthesize cancellation or failure from process-local state

#### Scenario: Persistence read is unavailable during recovery

- **WHEN** a list or detail read cannot reach persistence
- **THEN** the API returns a safe `503 Service Unavailable`
- **AND** exposes no database or execution diagnostic

### Requirement: Operate without authentication only inside the trusted MVP boundary

The MVP run API SHALL require no application-level login, authentication token, user identity, role, or authorization check. Every reachable caller SHALL be treated as the same trusted single operator. The application SHALL NOT add permissive cross-origin access or expose credentials to compensate for the missing identity layer.

Because launch incurs provider/model work and detail exposes operational evidence, deployment SHALL restrict the backend and frontend to a trusted local or internal environment through host, firewall, reverse-proxy, or equivalent operator-owned network controls. Direct exposure to the public internet or another untrusted network SHALL be unsupported. “Public API” in this capability means a documented HTTP application boundary, not unrestricted network availability.

Authentication, authorization, multi-user identity, per-user audit attribution, and untrusted-network rate/admission policy SHALL remain outside this change and SHALL require a separate approved security design before broader exposure.

#### Scenario: Use the MVP without login

- **GIVEN** the application is deployed inside the documented trusted boundary
- **WHEN** the operator opens Runs, launches an Observation, or reads run detail
- **THEN** no login, token, user identity, or role is required
- **AND** the same API behavior is available to that trusted operator

#### Scenario: Keep cross-origin access closed

- **WHEN** the unauthenticated run API is configured
- **THEN** this change does not enable permissive cross-origin access for arbitrary origins
- **AND** no browser-visible secret is introduced

#### Scenario: Reject untrusted deployment as unsupported

- **WHEN** an operator considers exposing the MVP run API directly to an untrusted network
- **THEN** deployment documentation identifies that topology as unsupported without a later authentication/authorization change
- **AND** does not describe one-active-run overlap as an access-control mechanism
