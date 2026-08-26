## Context

See `proposal.md` for motivation and `specs/metrics-analysis-pipeline/spec.md` for normative behavior.

The backend currently separates definition/API behavior under `backend/src/app/observations/` from SQLAlchemy runtime persistence under `backend/src/app/infrastructure/persistence/`. A Metric Lens definition already stores one `metric_id`, string `lens_id`, unit, Prometheus address/query metadata, explicit objectives, and explicit duplicate-free `reference_periods: list[str]`. Runtime persistence already stores one type-discriminated JSON artifact per LensRun, recognizes completed/partial usability and minimal failed Metric traceability, and deliberately delegates successful type-specific validation to the producer.

ADR-153–160 resolve the previously blocking Metric semantic, optional-tool, agent-data, reference, and History decisions. ADR-135 delegates the exact MetricAnalysisResult serialization to this implementation contract. Remaining prompt/model/provider/transport questions are non-blocking because the adapter receives a model and the pipeline consumes internal ports.

## Goals / Non-Goals

**Goals:**

- Supply an implementation-ready domain/application design for one already-created running Metric LensRun.
- Preserve deterministic orchestration, mandatory evidence/semantics, budgets, result construction, and persistence outside PydanticAI.
- Reuse existing definition identity types and the existing runtime persistence aggregate.
- Make every cross-stage correlation, omission, partial/failure, and transaction rule testable.

**Non-Goals:**

- Creating ObservationRun/LensRun records or implementing the top-level Observation Orchestrator.
- Prometheus runtime HTTP, authentication, retry, timeout, or query transport.
- Selecting a production LLM model/provider or provider-specific dependency/settings.
- Alert/Log pipelines, Relationships, Observation Reasoning, reporting, RAG, UI, scheduling, baselines, recommendations, confidence/severity, or advanced anomaly/ML models.

## Decisions

### 1. Use one Metric domain/application package and existing infrastructure adapters

The expected minimal placement is:

```text
backend/src/app/metrics/
  contracts.py       strict execution, stage, evidence, semantic, tool, agent, result models
  ports.py           MetricSeriesProvider, MetricsAnalysisAgent, MetricHistoryReader protocols
  preprocessing.py   raw-series validation, quality, mandatory statistics
  semantics.py       normalized trend/variability and optional-property projection
  tools.py           spike, oscillation, stuck_signal deterministic implementations/registry
  references.py      offset-window derivation and independent comparison
  history.py         accepted transition/direction/pattern analyzer
  result_builder.py  sole MetricAnalysisResult constructor/validator
  pipeline.py        deterministic async application service and outcome mapping

backend/src/app/infrastructure/
  agents/pydantic_ai_metrics.py       PydanticAI adapter
  persistence/repository.py           existing repository plus History read method
```

Pure models/algorithms have no SQLAlchemy, PydanticAI, Prometheus client, or provider SDK imports. `pipeline.py` accepts an already-running LensRun context and an existing transaction/session boundary; it does not create ObservationRun/LensRun records.

Alternatives rejected:

- Extending `app.observations.service` would mix definition/API ownership with a type-specific runtime pipeline.
- A PydanticAI graph would make the framework the deterministic orchestrator, contrary to ADR-045 and ADR-152.
- A second Metric repository/table would duplicate the accepted runtime artifact aggregate.

### 2. Reuse exact existing identity primitives in a frozen execution context

`MetricLensExecutionContext` is frozen and contains:

```text
identity:
  observation_id: UUID
  observation_run_id: UUID
  lens_id: str constrained non-empty
  lens_run_id: UUID
  metric_ref: str constrained non-empty
  unit: str constrained non-empty

provider_scope:
  adapter_type: existing definition adapter discriminator
  source_id: existing non-empty identifier string
  query: existing non-empty string

analysis_window:
  from: timezone-aware UTC datetime
  to: timezone-aware UTC datetime

analysis_objectives: immutable ordered values copied from definition
reference_periods: immutable ordered unique offset strings
history_policy:
  lookback_runs: positive integer, effective default 5
  level_change_tolerance: finite non-negative float, effective default 0.05
```

`metric_ref` is copied from the existing Metric Lens `metric_id`; it is not a new identifier type. `observation_id` comes from `ObservationModel.id`; `observation_run_id` and `lens_run_id` come from runtime UUIDs; `lens_id` remains the definition-owned string. No definition, database, API, or persistence identity migration is included.

The provider projection receives `provider_scope`; the agent projection never receives query/source address. The context cannot be mutated or replaced after pipeline entry.

### 3. Keep acquisition transport-free and return typed stage outcomes

`MetricSeriesProvider.acquire(scope, window)` returns one of:

- `MetricSeriesAvailable`: one framework-neutral series plus source provenance;
- `MetricSeriesUnavailable`: bounded application category and operational diagnostic;
- `MetricSeriesFailure`: malformed/contract-violating provider outcome.

The analytical series contains typed timestamp/value samples but no HTTP response/client type. Current unavailability/failure maps to mandatory technical failure. Reference unavailability maps to the ADR-157 completeness path. Provider retry/auth/timeout policy belongs to the later Prometheus adapter.

Reference windows are derived by parsing the already-validated offset and subtracting it from both current `from` and `to`; no default or provider-selected window is allowed.

The accepted result provenance remains:

```text
source: Literal["prometheus"]
generated_at: UTC datetime
```

The pipeline copies the source discriminator from the successful provider context/outcome; using the accepted string does not import Prometheus transport types.

### 4. Make preparation and mandatory semanticization pure functions

`prepare_series(series, window)` performs the exact D1 contract from the delta spec: UTC normalization, closed-window validation, ascending sort, duplicate rejection, non-finite removal, and three-finite-sample sufficiency.

Outputs are discriminated:

- `PreparedUsableSeries(data_quality=good|degraded, samples, evidence)`;
- `PreparedInsufficientSeries(data_quality=insufficient)`;
- `MalformedSeriesFailure`.

`MalformedSeriesFailure` is a preparation outcome, not a context-free terminal decision. `pipeline.py` maps it by series role:

- for the mandatory current series, duplicate timestamps or any out-of-window sample prevent the mandatory core and produce the minimal failed Metric result;
- for one configured reference series, the same conditions make only that offset unavailable, preserve all successful offsets, and contribute partial `reference_unavailable/reference_periods` when the current core is usable.

Reference preparation is invoked separately for each requested offset/window. Its malformed, acquisition-unavailable, and insufficient outcomes remain distinguishable in operational diagnostics, although they share the public reference-completeness reason. No preparation path clips out-of-window values, merges duplicates, or creates a placeholder comparison.

The sufficient output owns arithmetic mean, population standard deviation, extrema, and elapsed-time OLS slope. Intermediate OLS fit/residuals may be retained in memory for variability and tools but are not result fields.

`semanticize_mandatory` implements ADR-153 exactly and is reused for current and each sufficient reference. Threshold comparisons must use the formulas directly rather than rounded display values. Public evidence values remain finite; implementation may use `math.fsum` for stable summation but adds no dependency.

### 5. Bind tools to an opaque run-scoped dataset catalog

At each usable current run, the application creates an unpredictable opaque `dataset_ref` mapped to exactly one immutable `PreparedUsableSeries` in a run-scoped in-memory catalog. It is not a query, path, metric name, or caller-selectable identifier. Catalog lifetime ends after the agent stage.

Agent tool schemas take no metric/query/window/dataset selector. Infrastructure dependencies bind every exposed tool closure to the one `dataset_ref`. An unregistered, parallel, duplicate, or over-budget request is rejected before deterministic execution.

Framework-neutral tool outcomes are:

```text
ToolSuccess(name, state=present|absent|unknown, evidence)
ToolNotApplicable(name)
ToolFailed(name, diagnostic)
ToolTimedOut(name, diagnostic)
ToolRejected(name/request, reason)
```

The application-owned ledger records ordinal, requested name, outcome, and whether execution occurred. It is operational/transient and not serialized in MetricAnalysisResult.

#### Spike

Minimum `n=5`. Median and MAD use deterministic sorted finite values. With `MAD>0`, modified-z and strict `>3.5` detection apply. Evidence uses one of two strict variants:

```text
SpikeModifiedZEvidence:
  method: "modified_z"
  detected_sample_count: non-negative int
  detected_timestamps: ordered UTC datetime list
  max_abs_modified_z: finite non-negative float

SpikeZeroMadEvidence:
  method: "mad_zero_exact_deviation"
  deviation_count: non-negative int
  detected_sample_count: non-negative int
  detected_timestamps: ordered UTC datetime list
```

For zero MAD, absent has no deviations; present identifies every allowed sparse deviation; unknown records deviation count but has zero detected spikes and no fabricated score.

#### Oscillation

Minimum `n=8`. Reuse current OLS residuals and ADR-153 scale. Significant residuals satisfy strict `abs(residual) > 0.05*scale`; exact deadband equality is not significant. All-zero residuals are absent. Fewer than four significant residuals are unknown. Otherwise, at least three sign changes and ratio `>=0.60` is present; other cases are absent.

```text
OscillationEvidence:
  deadband: finite non-negative float
  significant_residual_count: non-negative int
  sign_change_count: non-negative int
  sign_change_ratio: finite float in [0,1]
```

The ratio is zero for fewer than two significant residuals.

#### Stuck signal

Minimum `n=5`. Scan timestamp order for the longest consecutive run of exactly equal values; an equal-length tie selects the earliest run. Share `>=0.80` is present, otherwise absent.

```text
StuckSignalEvidence:
  repeated_value: finite float
  longest_run_sample_count: positive int
  longest_run_share: finite float in (0,1]
```

The label means exact repeated provider values only, not proof of a physically stuck sensor. No epsilon/per-unit configuration is added.

### 6. Keep two strict Metrics Agent request projections minimal and resilient

The domain/application boundary defines two explicit strict request models, combined as a union selected by `data_quality`. It does not define one model with nullable analytical fields.

```text
MetricAgentUsableRequest:                 # good | degraded only
  identity:
    observation_id
    observation_run_id
    lens_id
    lens_run_id
    metric_ref
    unit
  analysis_window:
    from
    to
  analysis_objectives
  data_quality: good | degraded
  evidence:
    mean
    std
    min
    max
    slope
  semantics:
    trend
    variability
  allowed_tools:
    - {name: spike, capability: isolated_extreme_detection, minimum_samples: 5}
    - {name: oscillation, capability: detrended_residual_alternation, minimum_samples: 8}
    - {name: stuck_signal, capability: exact_repeated_value_run_detection, minimum_samples: 5}
  dataset_ref: opaque run-scoped reference

MetricAgentInsufficientRequest:           # insufficient only
  identity: same exact six fields
  analysis_window: same exact from/to shape
  data_quality: insufficient
```

Both models forbid unknown fields. `MetricAgentInsufficientRequest` has no objectives, dataset reference, tool metadata, series, evidence, current state, reference data, or History data, and the adapter exposes no tools. `MetricAgentUsableRequest` has every listed field required; none are nullable merely to accommodate the insufficient path. Its `allowed_tools` value is a fixed-length tuple of three strict variants in the displayed order; name, capability, and minimum samples are correlated literals. Raw/prepared series, provider queries/addresses, mutable selectors, reference data, and History data are absent from both projections. Natural-language prompt/tool-description prose stays adapter-private and cannot change the typed registry.

The only LLM-authored output is:

```python
class MetricAgentCompletion(StrictDomainModel):
    state: Literal["completed"]
```

The domain port returns completion plus the application-owned ledger/outcome metadata needed for deterministic status mapping; the model does not author the ledger.

Budget enforcement:

- maximum three executable/request slots;
- each registered tool at most once;
- each of the first three requested actions consumes a remaining slot, including success, not-applicable, failure, timeout, duplicate, unregistered, or parallel rejection;
- a duplicate never re-executes;
- unregistered/parallel requests are rejected as unacceptable;
- after three slots, a fourth request is recorded as an over-budget rejection without consuming or executing a fourth slot;
- PydanticAI tool and output validation retry budgets are both zero; neither validation failure nor a custom model-retry hook may generate a corrective request;
- `UsageLimits(request_limit=4)` (or the exact PydanticAI 2.x equivalent) is mandatory for each run: one initial request plus at most three post-tool continuations;
- a tool request returned by the fourth model request after three attempts is recorded as over-budget and aborts without a fifth model request.

Tool failure/timeout, duplicate/unregistered/parallel rejection, or fourth-call rejection marks optional analysis incomplete. `not_applicable` does not. A successful tool result with `state=unknown` is also complete analytical execution: its property/evidence are retained and it does not contribute partial status. The agent may continue only while a slot remains. A valid agent completion does not erase a prior optional failure.

For good/degraded current data, the adapter receives `MetricAgentUsableRequest`. Adapter/model failure, timeout, first invalid tool/output validation, request-limit exhaustion, or unacceptable final completion maps to partial `optional_analysis_failed/metrics_agent`; successful tool projections already produced remain valid. For insufficient current data, the adapter receives `MetricAgentInsufficientRequest` without tools or dataset reference. Any adapter/model/completion failure remains an operational agent-stage outcome, but the deterministic pipeline completes the quality-only path without fabricating a `MetricAgentCompletion`, so the trustworthy `completed + insufficient` result survives.

Exact prompt prose, provider-specific settings, and model-dependent token/cost/time limits remain adapter-private/open and cannot change these typed semantics.

### 7. Use PydanticAI only in one injected-model adapter

`backend/src/app/infrastructure/agents/pydantic_ai_metrics.py` implements `MetricsAnalysisAgent`. It receives a PydanticAI `Model` instance or an infrastructure-owned provider-neutral factory; the domain does not resolve a model name.

Later implementation requires explicit dependency approval before adding:

```text
pydantic-ai-slim>=2,<3
```

No provider extra is included. Deterministic adapter tests use the framework's test/function model support or a model double. OpenRouter, GPT-5.6 Terra, OpenAI-compatible settings, credentials, and live calls are absent.

Alternatives rejected:

- `pydantic-ai` installs unnecessary integrations.
- `pydantic-ai-slim[openai]` prematurely selects a provider-family dependency.
- A model-name string in domain settings leaks provider selection into the feature.

### 8. Serialize directional reference comparisons without baseline semantics

Reference semantic/evidence models are:

```text
ReferenceComparison:
  offset: validated offset string
  analysis_window: Window
  level: higher | lower | similar
  trend:
    direction: increasing | decreasing | stable | unknown
    rate: slow | moderate | fast | not_classified | unknown
    direction_relation: same | different | not_comparable
    rate_relation: faster | slower | same | not_comparable
  variability:
    state: low | moderate | high | not_classified | unknown
    relation: higher | lower | similar | not_comparable

ReferenceEvidence:
  offset: same offset
  analysis_window: same Window
  mean: finite float
  std: finite non-negative float
  min: finite float
  max: finite float
  slope: finite float
  relative_level_change: finite float
```

Relations orient current relative to reference. Rate order is slow < moderate < fast; variability order is low < moderate < high. Stable current trend has `rate=not_classified`, therefore rate relation is not comparable. Descriptors remain descriptive, not good/bad or normal/abnormal.

Only successful good/degraded reference outcomes enter paired lists. Acquisition-unavailable, malformed-reference (duplicate timestamp or out-of-window sample), and insufficient-reference outcomes all create `reference_unavailable/reference_periods`, retain specific internal cause/offset diagnostics, and create no placeholder. A failed offset cannot discard a successful offset or fail an otherwise usable current analysis.

### 9. Extend the existing repository only for event-time History reads

Add one query method to `RuntimePersistenceRepository` returning bounded candidate payload/metadata rows for:

- same Observation definition ID through the ObservationRun parent;
- same string `lens_id`;
- result type metric;
- completed/partial status;
- payload data quality good/degraded;
- not current `lens_run_id`;
- `payload.analysis_window.to < current.analysis_window.to`.

The query orders by parsed/event-time values required by ADR-158 and retrieves enough candidates to select the effective lookback. If JSON timestamp ordering cannot be expressed safely/portably in the repository query, the repository may retrieve a bounded relationally filtered candidate set and the domain reader must validate/parse/order it before selecting; it must not use creation/completion order as a substitute. The implementation task must keep the scan bounded and test the chosen query strategy in PostgreSQL.

The History Analyzer receives strict previously validated Metric result projections, not ORM/JSON dictionaries. It applies accepted ADR-015–025 behavior as clarified by ADR-159 and ADR-160. Normal no-history and analytical unknown are successful outcomes. Unexpected pure computation failure maps to partial `history_analysis_failed/history`. Any repository/session/transaction error propagates as infrastructure failure and cannot become empty History.

For each consecutive mean pair `(p,c)`, transition classification uses effective tolerance `t`:

```text
if p == 0 and c == 0:
  stable
else if abs(p) <= t * max(abs(p), abs(c)):
  unknown
else:
  relative_change = (c - p) / abs(p)
  abs(relative_change) <= t -> stable
  relative_change > t      -> increasing
  otherwise                -> decreasing
```

Both boundaries are inclusive. No absolute epsilon is used. Pattern processing then:

```text
classifiable_transitions = chronological transitions without unknown
directional_transitions = classifiable_transitions without stable
directional_runs = run-length compression of directional_transitions
direction_changes = max(0, len(directional_runs) - 1)

if len(classifiable_transitions) < 2: unknown
elif len(directional_runs) >= 3:      oscillating
elif len(directional_runs) == 2:      reversing
elif any classifiable transition share >= 0.70: sustained
else:                                mixed
```

Stable remains in the sustained denominator and neither creates nor resets a directional run. Unknown removal happens before all pattern operations, so transitions separated only by unknown become adjacent. This pattern projection does not alter ADR-023 History direction classification.

No table, migration, raw telemetry fetch, or second repository implementation is introduced.

### 10. Use strict discriminated MetricAnalysisResult models

All result/nested models derive from a Metric domain base with:

```python
ConfigDict(extra="forbid", strict=True)
```

They validate timezone-aware UTC timestamps, finite floats, `from < to`, non-empty strings, and cross-section correlations.

Shared structures:

```text
MetricIdentity:
  observation_id: UUID
  observation_run_id: UUID
  lens_id: non-empty str
  lens_run_id: UUID
  metric_ref: non-empty str
  unit: non-empty str

Window:
  from: UTC datetime
  to: UTC datetime

Trend:
  direction: increasing | decreasing | stable | unknown
  rate: slow | moderate | fast | not_classified | unknown

Variability:
  state: low | moderate | high | not_classified | unknown

OptionalProperty:
  state: present | absent | unknown

CurrentState:
  trend: Trend
  variability: Variability
  spike: OptionalProperty [optional]
  oscillation: OptionalProperty [optional]
  stuck_signal: OptionalProperty [optional]

MandatoryEvidence:
  mean/std/min/max/slope: finite floats; std >= 0

CurrentEvidence extends MandatoryEvidence:
  spike: SpikeModifiedZEvidence | SpikeZeroMadEvidence [optional]
  oscillation: OscillationEvidence [optional]
  stuck_signal: StuckSignalEvidence [optional]

History:
  direction: increasing | decreasing | stable | mixed | unknown
  pattern: sustained | reversing | oscillating | mixed | unknown
  run_ids: list[UUID], length 1..effective lookback, previous only, oldest first

HistoryEvidence:
  level_change_tolerance: finite non-negative float
  classifiable_transitions: non-negative int
  unknown_transitions: non-negative int
  increasing_transitions: non-negative int
  decreasing_transitions: non-negative int
  stable_transitions: non-negative int
  direction_changes: non-negative int
```

Evidence/history invariants:

```text
classifiable = increasing + decreasing + stable
classifiable + unknown = len(history.run_ids)
```

Optional semantic/evidence fields co-occur only after successful evaluation:

| Tool outcome | Property | Public tool evidence | Partial contribution |
| --- | --- | --- | --- |
| not evaluated | absent | absent | no |
| success present/absent/unknown | matching state | required | no |
| not_applicable | absent | absent | no |
| failed/timeout/rejected | absent | absent | optional_analysis_failed |

Strict top-level union:

```text
CompletedSufficientMetricResult:
  schema_version: "1.0"
  lens_type: "metric"
  identity: MetricIdentity
  status: {state: "completed"}
  analysis_window: Window
  data_quality: good | degraded
  current_state: CurrentState
  reference_periods: non-empty list[ReferenceComparison] [optional]
  history: History [optional]
  evidence:
    current: CurrentEvidence
    reference_periods: non-empty list[ReferenceEvidence] [optional]
    history: HistoryEvidence [optional]
  provenance: {source: "prometheus", generated_at: UTC datetime}

CompletedInsufficientMetricResult:
  common schema/lens/identity/window/provenance
  status: {state: "completed"}
  data_quality: insufficient
  forbid reason/current_state/reference_periods/history/evidence

PartialMetricResult:
  common schema/lens/identity/window/provenance
  status: {state: "partial"}
  reason: one strict StructuredReason variant
  data_quality: good | degraded
  current_state: CurrentState
  reference_periods/history optional as above
  evidence required and correlated as above

FailedMetricResult:
  common schema/lens/identity/window/provenance
  status:
    state: "failed"
    error: MetricFailedError
  forbid reason/data_quality/current_state/reference_periods/history/evidence
```

`MetricFailedError` is a strict three-variant union with fixed code/message pairs:

```text
current_metric_acquisition_failed -> "Current metric data acquisition failed."
current_metric_series_malformed   -> "Current metric series is malformed."
mandatory_metric_analysis_failed  -> "Mandatory metric analysis failed."
```

The builder accepts a typed mandatory-stage failure category rather than provider or exception text. Provider-port unavailable/failure/timeout maps to acquisition failure; duplicate/out-of-window current input maps to malformed series; unexpected statistics, semanticization, or sufficient-result validation failure maps to mandatory analysis failure. Detailed causes stay in operational diagnostics.

Every result, including a failure before acquisition succeeds, gets `provenance.source` from `MetricLensExecutionContext.provider_scope.adapter_type`, validated as the accepted `prometheus` discriminator for this feature. `generated_at` comes from an injected UTC clock at build time. Provenance therefore identifies configured source ownership and generation time, not provider-call success.

Partial reasons are a strict union:

```text
{code: reference_unavailable, component: reference_periods}
{code: history_analysis_failed, component: history}
{code: optional_analysis_failed,
 component: metrics_agent | spike | oscillation | stuck_signal}
```

Reason code and component selection are one deterministic operation:

1. If any reference comparison is unavailable, select `reference_unavailable/reference_periods`.
2. Otherwise, if deterministic History analysis failed, select `history_analysis_failed/history`.
3. Otherwise, for optional incompleteness:
   - if any model request failure, agent timeout, invalid structured completion, duplicate/unregistered/parallel/over-budget request, or other agent-boundary protocol violation occurred, select `optional_analysis_failed/metrics_agent`;
   - otherwise select `optional_analysis_failed/<tool-name>` for the earliest registered tool attempt whose outcome is failed or timeout, ordered by the application-owned attempt ordinal.

Thus an agent/protocol violation outranks a tool failure within the optional reason even when the tool failure occurred first. Between tool failures alone, earliest ordinal wins. `not_applicable` and successful `state=unknown` are excluded from incompleteness/component selection. The selected reason must equal the terminal LensRun reason.

Reference semantic/evidence lists co-occur with identical offset/window/order. History/evidence.history co-occur. Empty optional lists are omitted. The builder rejects aliases, unknown fields, raw/transient data, and provider/framework objects before forming `LensAnalysisResultInput`.

### 11. Compose terminal writes in the existing caller-owned transaction

`RuntimePersistenceRepository` already flushes without committing and documents caller transaction ownership. The application composes:

```text
begin caller-owned transaction
  load/validate History candidates
  build strict terminal Metric result
  advance running LensRun to completed | partial | failed with matching reason
  persist correlated LensAnalysisResultInput
commit
```

The LLM/tool stages occur before opening the History/write transaction so they do not hold a database transaction. History query and terminal writes share the transaction/snapshot needed for consistent candidate selection.

Analytical mandatory failure still builds/persists a minimal failed Metric artifact. Repository flush or commit failure rolls back terminal LensRun state and artifact and propagates a persistence error; the pipeline must not claim success or try to persist another failed result through the unavailable backend. Retry/recovery is deferred to the future execution capability.

### 12. Map stage outcomes and one primary partial reason deterministically

Terminal mapping:

| Condition | Terminal intent |
| --- | --- |
| Current acquisition/preparation/mandatory semantic technical failure | failed minimal Metric result |
| Current quality insufficient, including narrow agent failure | completed insufficient |
| Good/degraded + reference acquisition unavailable, malformed, or reference insufficient | partial reference_unavailable |
| Good/degraded + deterministic History computation failure | partial history_analysis_failed |
| Good/degraded + agent/tool/protocol optional failure | partial optional_analysis_failed |
| Good/degraded + no incompleteness | completed sufficient |
| History repository or terminal persistence transaction failure | propagate infrastructure error; no claimed persisted terminal result |

One reason is selected:

```text
reference_unavailable
> history_analysis_failed
> optional_analysis_failed
```

Secondary diagnostics remain structured operational records, never free-text result sections.

`select_primary_reason` applies both code precedence and component selection. It always assigns `reference_periods` to a reference reason and `history` to a History reason. For an optional reason it first checks the ledger/agent outcome for any agent or protocol failure; only if none exists does it select the earliest failed/timed-out registered tool attempt. Complete ledgers and per-offset causes may remain in application diagnostics, but the result builder accepts only the selected strict `StructuredReason` and cannot serialize diagnostic arrays or strings.

## Test Design

- Pure preparation/statistics tests: UTC ordering, closed-window validation, duplicates, non-finite filtering, all quality classes, population std, elapsed-time OLS slope; pipeline mapping tests distinguish malformed current failure from per-offset malformed reference incompleteness.
- Semantic boundary tests: exact trend/variability thresholds, signed/near-zero/constant values, and no rounded-threshold decisions.
- Tool unit tests: spike normal and every zero-MAD branch; oscillation present/absent/unknown/not-applicable; stuck present/absent/not-applicable and tie behavior.
- Agent/ledger tests: exact good/degraded usable projections, fixed descriptor variants/order, and identity/window/quality-only insufficient projection; zero/all calls, each-tool-once, duplicate/unregistered/parallel/fourth rejection, zero tool/output validation retries, hard four-request/no-fifth-request enforcement, attempt counting, not-applicable and successful-unknown non-failure, failure/timeout, valid/invalid completion, usable-core partial, insufficient-quality resilience, and preservation of earlier valid tool results.
- Reference tests: zero/one/many windows; exact window arithmetic/formula; every directional relation; acquisition, malformed duplicate, malformed out-of-window, and insufficient causes; successful-offset preservation/order; no placeholders.
- History tests: eligibility/defaults/overrides, no History, analytical unknown, overlapping windows, total ordering/ties/late persistence, lookback, exact zero/near-zero/relative-change boundaries, all ADR-160 normative sustained/reversing/oscillating/mixed sequences, fewer-than-two unknown, unknown-denominator exclusion, stable-neutral run behavior, direction-change count, priority, deterministic failure, and repository failure.
- Contract tests: all four strict result variants, three exact failed-error mappings, failure-before-provider-success provenance, identity primitive compatibility, window names, finiteness, optional co-occurrence, reference/history correlation, exact reason-code/component tie-breaking, and rejected aliases/transient/framework/provider objects.
- Pipeline tests with fakes: completed sufficient/insufficient, partial causes, minimal failed, agent behavior, and infrastructure propagation.
- PostgreSQL integration tests: History query/filter/order/lookback and completed/partial/failed round-trip; rollback of terminal state plus artifact on flush/commit failure.
- Boundary checks: no Prometheus runtime transport, no provider/model selection, and no PydanticAI import outside infrastructure adapter.
- Final verification: focused pytest followed by repository `make check`.

Live provider/model tests are excluded because production provider/model selection remains open.

## Risks / Trade-offs

- [Fixed normalized thresholds are descriptive rather than domain-calibrated] → Document them as versioned MVP semantics and do not infer safety/normality.
- [Exact-equality stuck detection can miss physically stuck noisy signals] → Keep the label limited to repeated provider values; defer epsilon/unit policies.
- [JSONB event-time filtering may be awkward or inefficient] → Use strict parsing plus a bounded relationally filtered candidate scan when necessary; add no index/migration without measured need and approval.
- [Agent calls add cost even for insufficient data] → Use the narrow no-tool context and preserve the deterministic quality result on agent failure.
- [PydanticAI minor releases may change adapter APIs] → Keep it in one adapter, constrain `>=2,<3`, and lock/test the resolved version during approved implementation.
- [Primary reason hides simultaneous causes] → Preserve deterministic precedence publicly and keep secondary diagnostics operational.

## Migration Plan

1. Obtain explicit plan and dependency approval before apply.
2. During approved implementation, add the Metric package, adapter, existing-repository read method, and tests without database migration.
3. Add `pydantic-ai-slim>=2,<3` and update the backend lock only after explicit dependency approval; add no provider extra.
4. Run focused tests and `make check`.
5. Rollback removes the new modules and repository read method; existing definitions/tables/artifacts require no schema rollback.

## Open Questions

- Exact Metrics Agent prompt wording and field-to-message serialization inside the approved typed boundary.
- Production LLM model/provider and provider-specific dependency/configuration.
- Model-dependent request timeout, token, and cost limits in addition to the fixed three-attempt domain tool budget.
- Production Prometheus transport/authentication/retry/timeout mapping in the future provider capability.

These prompt/model/provider/transport items stay non-blocking behind the approved boundaries and do not change domain behavior, result shape, or module ownership.

## Architecture References

- `docs/architecture/README.md` — precedence and navigation.
- `docs/architecture/01_observation_lens_concept.md` — one-metric scope, controlled semantics, reference periods, History.
- `docs/architecture/02_architecture_principles_and_runtime.md` — deterministic sub-pipeline, failure propagation, persistence.
- `docs/architecture/03_ADR_log.md` — ADR-003, ADR-015–041, ADR-043–049, ADR-059, ADR-068, ADR-133–135, ADR-152, ADR-153–160.
- `docs/architecture/04_pipeline_and_agent_concepts.md` — agent/tool/component responsibilities.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — status, usability, reason, failed Metric result, transaction boundaries.
- `docs/architecture/10_open_decisions_and_backlog.md` — remaining non-blocking Metrics questions.
- `docs/architecture/11_glossary_and_naming.md` — naming.
- `openspec/specs/observation-definition-api/spec.md` — existing definition and identity primitive behavior.
- `openspec/specs/runtime-persistence/spec.md` — existing runtime artifact correlation and usability.
