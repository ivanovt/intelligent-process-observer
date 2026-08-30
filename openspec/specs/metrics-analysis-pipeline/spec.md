# metrics-analysis-pipeline Specification

## Purpose
Define the production behavior that analyzes one immutable Metric Lens execution into deterministic, bounded-agent-assisted, reference-aware, historically contextualized, strictly validated, and atomically persisted Metric evidence.

## Requirements

### Requirement: Execute one immutable Metric Lens scope through a deterministic pipeline

The system SHALL execute one already-created running Metric LensRun as one immutable metric scope containing the existing six identity values, provider/source/query address, exact current `analysis_window.from/to`, ordered configured reference offsets, analysis objectives, and effective History policy. The deterministic pipeline SHALL own stage order, terminal outcome mapping, result construction, persistence invocation, and interaction with the existing LensRun lifecycle. The Metrics Analysis Agent SHALL NOT orchestrate the pipeline or mutate any part of the execution scope.

Where analytically applicable, stage order SHALL be: resolve immutable context; acquire current and configured reference series through the provider port; prepare and assess data; calculate mandatory evidence and semantics; invoke the bounded Metrics Analysis Agent and optional deterministic tools; finalize optional semantics; compare valid references independently; load and analyze eligible persisted History; build and validate the Metric result; atomically persist terminal LensRun state and artifact.

#### Scenario: Execute a successful current-window analysis

- **GIVEN** one running Metric LensRun has a fixed definition, identity, current window, and no configured references
- **AND** current acquisition, mandatory analysis, agent completion, History access, result validation, and persistence succeed
- **WHEN** the Metrics Analysis Pipeline executes
- **THEN** it persists one completed MetricAnalysisResult for the unchanged identity and current window
- **AND** it starts no Observation-level orchestration or unrelated Lens execution

#### Scenario: Reject agentic scope expansion

- **GIVEN** the Metrics Analysis Agent is executing for one immutable Metric Lens scope
- **WHEN** it requests optional analysis
- **THEN** the request remains bound to the already acquired run-scoped current dataset
- **AND** it cannot change the metric, query, source, window, reference configuration, Observation scope, persistence, or LensRun/ObservationRun lifecycle

### Requirement: Acquire metric series only through the internal provider boundary

The pipeline SHALL depend on a framework-neutral single-series provider port accepting the immutable provider address and an exact requested window. It SHALL use that port for current and reference acquisition and SHALL NOT depend on Prometheus HTTP/client types, implement transport authentication/retry, or select a production provider implementation.

Each configured reference window SHALL have the current window's duration and be shifted backward by its exact positive configured offset. An explicit empty offset list SHALL cause no reference request and SHALL receive no default.

#### Scenario: Acquire zero configured references

- **GIVEN** `reference_periods=[]`
- **WHEN** the pipeline acquires Metric data
- **THEN** it requests only the current window
- **AND** it creates no default reference or `previous_period`

#### Scenario: Acquire one configured reference

- **GIVEN** one configured offset
- **WHEN** the pipeline acquires references
- **THEN** it requests one equal-duration window shifted backward by that exact offset
- **AND** it keeps current and reference series distinct

#### Scenario: Acquire multiple references independently

- **GIVEN** multiple ordered configured offsets
- **WHEN** the pipeline acquires references
- **THEN** each request and outcome remains attributable to exactly one offset
- **AND** no offset is interpreted as a baseline, normality definition, or automatic seasonality class

#### Scenario: Test without provider transport

- **GIVEN** a fake satisfies the provider port
- **WHEN** the pipeline is tested
- **THEN** all current/reference behavior is executable without Prometheus HTTP, credentials, retries, or a provider SDK

### Requirement: Prepare samples and calculate mandatory evidence deterministically

The deterministic preparer SHALL normalize timestamps to timezone-aware UTC, accept only samples satisfying `analysis_window.from <= timestamp <= analysis_window.to`, sort samples by ascending timestamp, and reject duplicate timestamps or out-of-window samples as malformed provider data. Preparation SHALL apply independently to the current series and to every configured reference series.

Malformed current data SHALL be a technical mandatory-stage failure: the mandatory current analysis cannot be produced, the LensRun SHALL fail, and the pipeline SHALL produce only the accepted minimal failed Metric result. Malformed data for one configured reference SHALL instead make only that reference comparison unavailable under the reference-completeness requirement; it SHALL NOT fail an otherwise usable current analysis.

The preparer SHALL remove NaN and positive/negative infinity before analysis. It SHALL classify current quality as:

- `good` when at least three finite samples remain and none were removed;
- `degraded` when at least three finite samples remain after one or more non-finite values were removed;
- `insufficient` when fewer than three finite samples remain.

This MVP SHALL NOT infer cadence, gap, or coverage quality because no expected sampling cadence is part of the execution contract. It SHALL not emit `data_quality=unknown`.

For `good|degraded` series, mandatory current/reference evidence SHALL contain finite arithmetic `mean`, population `std` with divisor `n`, finite `min`, finite `max`, and ordinary-least-squares `slope` over actual elapsed seconds from `analysis_window.from`:

```text
x_i = timestamp_i - analysis_window.from, in seconds
slope = sum((x_i - x_mean) * (y_i - y_mean))
        / sum((x_i - x_mean)^2)
```

No new statistics dependency SHALL be required.

#### Scenario: Calculate exact statistics

- **GIVEN** at least three distinct-timestamp finite samples with known expected arithmetic mean, population standard deviation, extrema, and elapsed-time OLS slope
- **WHEN** mandatory evidence is calculated
- **THEN** all five values equal the deterministic formulas
- **AND** the agent does not calculate or replace them

#### Scenario: Degrade after removing non-finite samples

- **GIVEN** acquired current data contains non-finite values and at least three finite samples remain
- **WHEN** preparation completes
- **THEN** the non-finite samples do not participate in evidence
- **AND** `data_quality=degraded`

#### Scenario: Complete insufficient current data

- **GIVEN** current acquisition succeeds but fewer than three finite samples remain
- **WHEN** quality assessment completes successfully
- **THEN** the result is `completed + insufficient`
- **AND** it omits `current_state`, `reference_periods`, `history`, and `evidence`
- **AND** it is ineligible for future Metric History

#### Scenario: Fail a malformed current series with duplicate timestamps

- **GIVEN** two samples acquired for the current window have the same normalized UTC timestamp
- **WHEN** current preparation validates the series
- **THEN** it treats the series as malformed technical input
- **AND** the LensRun produces the accepted minimal failed Metric result rather than merging, selecting, or averaging duplicates

#### Scenario: Fail a malformed current series with an out-of-window sample

- **GIVEN** the provider returns a sample outside the requested current `analysis_window.from/to`
- **WHEN** current preparation validates the series
- **THEN** the mandatory current analysis fails
- **AND** the LensRun produces the accepted minimal failed Metric result without current analytical sections

### Requirement: Form mandatory trend and variability using the fixed normalized policy

For every `good|degraded` current/reference series, the deterministic semanticizer SHALL calculate:

```text
duration = analysis_window.to - analysis_window.from, in seconds
scale = max(abs(mean), max - min)
normalized_trend_change = abs(slope) * duration / scale
normalized_variability = population_std(OLS residuals) / scale
```

When `scale == 0`, it SHALL produce `trend.direction=stable`, `trend.rate=not_classified`, and `variability.state=low`. Otherwise it SHALL apply:

```text
normalized_trend_change < 0.05       -> stable / not_classified
0.05 <= value < 0.15                 -> sign(slope) / slow
0.15 <= value < 0.35                 -> sign(slope) / moderate
value >= 0.35                        -> sign(slope) / fast

normalized_variability < 0.05        -> low
0.05 <= value < 0.15                 -> moderate
value >= 0.15                        -> high
```

The classifications SHALL be descriptive and SHALL NOT imply baseline, normality, severity, safety, or confidence.

#### Scenario: Classify trend threshold boundaries

- **GIVEN** sufficient series whose normalized trend changes are immediately below, exactly at, and immediately above `0.05`, `0.15`, and `0.35`
- **WHEN** mandatory trend is formed
- **THEN** stable/slow/moderate/fast follow the exact inclusive/exclusive boundaries
- **AND** increasing/decreasing follows the slope sign only outside the stable band

#### Scenario: Classify variability threshold boundaries

- **GIVEN** sufficient series whose normalized residual variability is immediately below, exactly at, and immediately above `0.05` and `0.15`
- **WHEN** mandatory variability is formed
- **THEN** low/moderate/high follow the exact inclusive/exclusive boundaries

#### Scenario: Semanticize a constant series

- **GIVEN** a sufficient series has `scale=0`
- **WHEN** semanticization executes
- **THEN** it produces stable/not_classified trend and low variability without division by zero

### Requirement: Provide exactly three deterministic optional analytical tools

The runtime allowlist SHALL contain exactly `spike`, `oscillation`, and `stuck_signal`. Each SHALL operate only on the immutable prepared current series. `drift` SHALL NOT be a separate optional tool because mandatory trend owns within-window direction/rate and History owns operating-level evolution across runs.

For every tool, a successful `present|absent|unknown` evaluation SHALL produce the matching optional `current_state` property and matching deterministic `evidence.current` tool evidence. A tool that was not evaluated or returned `not_applicable` SHALL produce neither property nor public tool evidence and SHALL not cause partial status. A failed/timeout tool SHALL produce neither successful property nor public evidence.

Spike SHALL require at least five samples. With `MAD>0`, it SHALL use `modified_z=0.6745*(value-median)/MAD` and detect samples where `abs(modified_z)>3.5`. With `MAD==0`, it SHALL count samples not exactly equal to the median: zero deviations yields `absent`; at most `max(1,floor(0.1*n))` deviations yields `present` with those deviations as spikes; more deviations yields `unknown`. Its evidence SHALL identify `modified_z` or `mad_zero_exact_deviation`, detected timestamps/count, deviation count for the fallback, and maximum absolute modified-z only when MAD is non-zero.

Oscillation SHALL require at least eight samples. It SHALL use the mandatory OLS residuals, a deadband of `0.05*scale`, and signs of residuals whose absolute value exceeds the deadband. All-zero residuals yield `absent`; fewer than four significant residuals yield `unknown`; otherwise `present` requires at least three sign changes and `sign_changes/(significant_count-1) >= 0.60`, and all other applicable cases yield `absent`. Its evidence SHALL contain deadband, significant-residual count, sign-change count, and the ratio, defined as zero when fewer than two significant residuals exist.

Stuck signal SHALL require at least five samples and SHALL calculate the longest consecutive run of exactly equal values, choosing the earliest run on equal length. A longest-run share of at least `0.80` yields `present`; otherwise it yields `absent`. Its evidence SHALL contain the exact repeated value, run length, and share. This describes exact repeated provider values and SHALL NOT claim proof that a physical sensor is stuck.

#### Scenario: Detect spike with non-zero MAD

- **GIVEN** at least five samples have non-zero MAD
- **WHEN** spike analysis executes
- **THEN** only samples with absolute modified-z greater than `3.5` are detected
- **AND** modified-z evidence is present

#### Scenario: Apply all zero-MAD spike outcomes

- **GIVEN** at least five samples have `MAD=0`
- **WHEN** the deviation count is zero, within the sparse limit, or above the sparse limit
- **THEN** spike state is respectively absent, present, or unknown
- **AND** fallback evidence is present without a fabricated modified-z score

#### Scenario: Skip inapplicable spike

- **GIVEN** fewer than five usable samples
- **WHEN** spike is requested
- **THEN** it returns `not_applicable`
- **AND** no spike property, public spike evidence, or partial status is produced

#### Scenario: Classify oscillation outcomes

- **GIVEN** applicable residual sequences cover present, absent, and fewer-than-four-significant unknown cases
- **WHEN** oscillation analysis executes
- **THEN** each state and evidence follows the exact deadband/sign-change rule

#### Scenario: Skip inapplicable oscillation

- **GIVEN** fewer than eight usable samples
- **WHEN** oscillation is requested
- **THEN** it returns `not_applicable` without public property/evidence or partial status

#### Scenario: Classify exact stuck-signal outcomes

- **GIVEN** applicable sequences have longest exact-equality run shares below and at `0.80`
- **WHEN** stuck-signal analysis executes
- **THEN** state is respectively absent and present
- **AND** evidence identifies the deterministic earliest longest run

#### Scenario: Skip inapplicable stuck signal

- **GIVEN** fewer than five usable samples
- **WHEN** stuck-signal is requested
- **THEN** it returns `not_applicable` without public property/evidence or partial status

### Requirement: Invoke the Metrics Analysis Agent through a bounded framework-neutral contract

Every current path that produces either a usable mandatory core or a successfully determined insufficient-quality outcome SHALL invoke the Metrics Analysis Agent through exactly one of two strict framework-neutral request models. Implementations SHALL use two explicit models or a strict discriminated union that guarantees these shapes; they SHALL NOT use one permissive model whose forbidden fields are merely nullable.

`MetricAgentUsableRequest` SHALL be used only for `data_quality=good|degraded` and SHALL contain exactly:

- the six-field Metric identity (`observation_id`, `observation_run_id`, `lens_id`, `lens_run_id`, `metric_ref`, `unit`);
- exact `analysis_window.from/to`;
- immutable `analysis_objectives`;
- `data_quality=good|degraded`;
- mandatory current numerical evidence (`mean`, population `std`, `min`, `max`, `slope`);
- mandatory current semantic descriptors (`trend` and `variability`);
- the exact ordered `allowed_tools` descriptor tuple defined below; and
- one opaque run-scoped `dataset_ref`.

Its `allowed_tools` field SHALL be an ordered three-item tuple of strict descriptor variants with no free-text description field:

```text
{name: "spike",        capability: "isolated_extreme_detection",          minimum_samples: 5}
{name: "oscillation",  capability: "detrended_residual_alternation",      minimum_samples: 8}
{name: "stuck_signal", capability: "exact_repeated_value_run_detection",  minimum_samples: 5}
```

The tuple order SHALL always be `spike`, `oscillation`, `stuck_signal`; each literal name SHALL correlate with exactly its literal capability and minimum-sample value. Exact natural-language prompt and framework tool-description prose SHALL remain adapter-private and SHALL NOT change registry membership, order, applicability, input scope, or deterministic tool behavior.

`MetricAgentInsufficientRequest` SHALL be used only for `data_quality=insufficient` and SHALL contain exactly the six-field Metric identity, exact `analysis_window.from/to`, and `data_quality=insufficient`. It SHALL contain no `analysis_objectives`, `dataset_ref`, tool registry/descriptions, raw or prepared series, mandatory evidence, `current_state`, reference-period data, or History data. No analytical tool SHALL be exposed for this invocation.

The `dataset_ref` in a usable request SHALL not be a provider query, metric selector, provider address, or raw/compact telemetry; the model cannot supply or modify it, and only registered deterministic tools SHALL resolve it.

The only LLM-authored final contract SHALL be strict `MetricAgentCompletion{state: Literal["completed"]}`. It SHALL contain no summary, findings, severity, confidence, recommendations, or tool-list restatement. The authoritative tool-attempt ledger SHALL be application/domain-owned and SHALL not depend on PydanticAI types.

The tool loop SHALL allow three available request slots and each registered tool at most once. Each of the first three requested actions consumes one slot whether it succeeds, is `not_applicable`, fails, times out, or is rejected as duplicate, unregistered, or parallel. A duplicate SHALL not execute the tool again. A request after all three slots are consumed SHALL be recorded as an over-budget rejection but SHALL NOT consume or execute a fourth slot. Tool failure/timeout and rejected invalid/budget-exceeding requests SHALL contribute `optional_analysis_failed`; `not_applicable` and a successful deterministic `state=unknown` SHALL not.

The production PydanticAI adapter SHALL disable automatic framework retries for both tool-input and final-output validation (`tools=0`, `output=0`) and SHALL install no model-retry hook that can create another request. One agent invocation SHALL permit at most four model requests: the initial request plus at most one continuation after each of the three domain tool attempts. Every actual request to the model counts toward this ceiling. An invalid tool call or invalid/unacceptable structured completion SHALL terminate the adapter run without a corrective model request. A tool request in the fourth model response after three tool attempts SHALL be rejected as over budget and SHALL terminate without a fifth model request.

For usable current data, framework retry exhaustion, model-request-limit exhaustion, invalid tool input/protocol, or invalid/unacceptable completion SHALL map to the already defined `partial + optional_analysis_failed/metrics_agent` outcome. For insufficient current data, the same adapter outcomes SHALL remain operational diagnostics and preserve `completed + insufficient`. Provider transport retry/timeout, model/provider selection, token, cost, and model-request timeout settings remain outside this contract.

Within `optional_analysis_failed`, any Metrics Agent/model/protocol failure SHALL select `reason.component=metrics_agent`. This priority includes model request failure, agent timeout, invalid structured completion, unknown/unregistered, duplicate, parallel, or over-budget tool requests, and any other violation owned by the agent boundary, even if a deterministic tool also failed. If no agent/protocol failure occurred, `reason.component` SHALL be the registered tool name of the earliest `failed|timeout` attempt by application-owned attempt ordinal. A `not_applicable` outcome or successful `state=unknown` SHALL never be selected as the component.

For current `good|degraded`, agent failure, timeout, or invalid/unacceptable final completion SHALL produce a usable partial result with `reason.code=optional_analysis_failed` and `reason.component=metrics_agent`. Valid deterministic optional results already produced MAY still be semanticized.

For current `insufficient`, the agent SHALL be invoked with `MetricAgentInsufficientRequest`. Failure, timeout, or invalid completion SHALL be recorded operationally and deterministically treated as no optional analysis; it SHALL NOT replace the valid `completed + insufficient` outcome. A technical failure to produce the current quality determination or mandatory core SHALL produce a failed LensRun under the mandatory failure rules.

#### Scenario: Project good current data into the usable request

- **GIVEN** current quality is good
- **WHEN** the framework-neutral agent request is built
- **THEN** it is `MetricAgentUsableRequest` containing exact identity, window, objectives, quality, mandatory evidence, trend/variability, allowed-tool metadata, and `dataset_ref`
- **AND** it contains no raw/prepared series, provider query, mutable selector, reference data, or History data

#### Scenario: Project degraded current data into the same usable request

- **GIVEN** current quality is degraded after deterministic non-finite filtering
- **WHEN** the framework-neutral agent request is built
- **THEN** it uses the same complete `MetricAgentUsableRequest` shape with `data_quality=degraded`

#### Scenario: Project insufficient current data into the narrow request

- **GIVEN** current quality is insufficient
- **WHEN** the framework-neutral agent request is built
- **THEN** it is `MetricAgentInsufficientRequest` containing only exact identity, window, and `data_quality=insufficient`
- **AND** objectives, tools, `dataset_ref`, series, evidence, current state, reference data, and History data are absent

#### Scenario: Project the deterministic allowed-tool registry

- **GIVEN** current quality is good or degraded
- **WHEN** `MetricAgentUsableRequest.allowed_tools` is built
- **THEN** it contains exactly the strict `spike`, `oscillation`, and `stuck_signal` descriptor variants in that order
- **AND** each descriptor carries its fixed capability literal and minimum sample count
- **AND** it contains no natural-language prompt or description field

#### Scenario: Complete with zero tool calls

- **GIVEN** current mandatory core is usable
- **WHEN** the agent returns valid completion without a tool request
- **THEN** the pipeline continues with unchanged mandatory evidence
- **AND** no optional property/evidence is added

#### Scenario: Use all three tools once

- **GIVEN** the agent requests each registered tool once
- **WHEN** all three execute successfully within the budget
- **THEN** all three attempts are recorded
- **AND** valid outputs are deterministically semanticized

#### Scenario: Reject a duplicate request

- **GIVEN** one tool has already been requested
- **WHEN** the agent requests it again
- **THEN** the duplicate consumes an available attempt but does not execute the tool
- **AND** optional analysis is marked incomplete

#### Scenario: Reject a fourth request

- **GIVEN** three attempts have exhausted the budget
- **WHEN** the agent requests another tool
- **THEN** no fourth tool executes
- **AND** optional analysis is marked incomplete

#### Scenario: Enforce the hard model-request ceiling without validation retries

- **GIVEN** one Metrics Agent invocation starts
- **WHEN** framework validation fails or the run reaches its fourth model request
- **THEN** no automatic tool/output validation retry or fifth model request occurs
- **AND** an unusable final/protocol outcome follows the existing quality-specific result mapping

#### Scenario: Preserve usable core on agent failure

- **GIVEN** current quality is good or degraded
- **WHEN** the agent fails, times out, or returns invalid/unacceptable completion
- **THEN** the LensRun/result are partial and usable
- **AND** the reason is `optional_analysis_failed/metrics_agent`
- **AND** mandatory mean/std/min/max/slope, trend, and variability remain unchanged

#### Scenario: Preserve insufficient determination on agent failure

- **GIVEN** current quality was deterministically classified insufficient
- **WHEN** the required narrow agent invocation fails, times out, or returns invalid completion
- **THEN** the pipeline records the diagnostic but produces `completed + insufficient`
- **AND** it fabricates no analytical sections or failed analytical result

#### Scenario: Keep PydanticAI outside domain contracts

- **GIVEN** the production adapter uses PydanticAI
- **WHEN** domain/application contracts and their fake-based tests are inspected
- **THEN** they contain no PydanticAI model, message, tool, result, usage, or provider types

### Requirement: Compare valid reference periods independently with ordered relations

Every `good|degraded` reference SHALL receive the same mandatory evidence and semantics as current. The comparator SHALL calculate:

```text
relative_level_change =
  0                                                    when both means are zero
  2 * (current_mean - reference_mean)
    / (abs(current_mean) + abs(reference_mean))        otherwise
```

Level SHALL be `higher` above `0.05`, `lower` below `-0.05`, and `similar` otherwise. Trend direction relation SHALL be `same|different|not_comparable`. Trend rate SHALL order `slow < moderate < fast` and compare the current descriptor to reference as `faster|slower|same|not_comparable`. Variability SHALL order `low < moderate < high` and compare current to reference as `higher|lower|similar|not_comparable`. A relation SHALL be `not_comparable` when either relevant descriptor is `unknown` or `not_classified`.

Each semantic comparison SHALL contain offset, exact reference `analysis_window.from/to`, level relation, reference trend direction/rate plus direction/rate relations, and reference variability state plus relation. Matching reference evidence SHALL contain the same offset/window, exact reference mean/std/min/max/slope, and finite `relative_level_change`. Semantic and evidence lists SHALL preserve configured order among successful unique offsets.

#### Scenario: Compare ordered reference descriptors

- **GIVEN** current/reference descriptors exercise faster, slower, same, higher, lower, similar, and non-comparable cases
- **WHEN** one reference is compared
- **THEN** every relation is oriented as current relative to reference
- **AND** reference descriptors and numerical evidence remain independently traceable

#### Scenario: Preserve multiple independent comparisons

- **GIVEN** multiple configured references are analytically usable
- **WHEN** comparisons execute
- **THEN** one semantic/evidence pair is produced per successful offset in configured order
- **AND** one offset's evidence does not influence another

### Requirement: Make missing configured reference analysis partial without placeholders

When current quality is `good|degraded`, any of the following SHALL mean that one configured comparison could not be produced: provider/query acquisition failure or timeout; duplicate normalized reference timestamps; a reference sample outside that offset's requested window; or acquired reference quality `insufficient` after non-finite filtering. The result SHALL remain usable but become partial with public primary reason `reference_unavailable/reference_periods`. This reason SHALL describe result incompleteness and MAY cover acquisition failure, malformed reference data, or analytically insufficient reference data; it SHALL NOT assert provider failure.

Operational diagnostics SHALL retain each unsuccessful offset and its specific internal cause. Successful offsets SHALL remain; unsuccessful offsets SHALL be omitted from semantic/evidence lists, and no fake unknown comparison SHALL be serialized. A malformed reference SHALL never fail an otherwise usable current analysis.

When current quality is `insufficient`, reference comparisons are not formable and their absence SHALL NOT change `completed + insufficient` into partial.

#### Scenario: Omit an acquisition-unavailable reference

- **GIVEN** current core is usable and one configured reference provider request fails or times out
- **WHEN** the pipeline completes
- **THEN** it preserves successful offsets, omits the failed offset, and produces partial `reference_unavailable/reference_periods`
- **AND** operational diagnostics identify acquisition unavailability

#### Scenario: Omit an analytically insufficient reference

- **GIVEN** current core is usable and one acquired reference has fewer than three finite samples after preparation
- **WHEN** the pipeline completes
- **THEN** it preserves successful offsets, omits the insufficient offset, and produces partial `reference_unavailable/reference_periods`
- **AND** operational diagnostics identify analytical insufficiency

#### Scenario: Omit a reference with duplicate timestamps

- **GIVEN** current core is usable and one configured reference contains duplicate normalized UTC timestamps
- **WHEN** reference preparation executes independently
- **THEN** the result is partial `reference_unavailable/reference_periods`
- **AND** it omits only that malformed offset, retains every successful offset, and records the duplicate cause operationally

#### Scenario: Omit a reference with an out-of-window sample

- **GIVEN** current core is usable and one configured reference contains a sample outside that offset's requested window
- **WHEN** reference preparation executes independently
- **THEN** the result is partial `reference_unavailable/reference_periods`
- **AND** it omits that offset without failing or changing the mandatory current analysis

#### Scenario: Preserve successful references when another reference is malformed

- **GIVEN** current core and at least one configured reference are usable while another configured reference is malformed
- **WHEN** all references are evaluated independently
- **THEN** all successful semantic/evidence pairs are preserved in configured order
- **AND** the malformed offset is omitted rather than represented by a fake unknown comparison or a failed Metric result

### Requirement: Analyze eligible persisted Metric History in event-time order

The pipeline SHALL load History only from persisted MetricAnalysisResult artifacts with the same `observation_id + lens_id`. Eligible results SHALL be `completed|partial` with `good|degraded` data quality; failed and insufficient results SHALL be excluded. Effective policy SHALL use accepted Lens > Observation > System precedence with defaults `lookback_runs=5` and `level_change_tolerance=0.05`.

An eligible earlier candidate SHALL satisfy `historical.analysis_window.to < current.analysis_window.to`; overlapping windows are allowed. Candidates SHALL be totally ordered by `analysis_window.to`, then `analysis_window.from`, then lexical `lens_run_id`. The newest effective lookback candidates SHALL be selected and supplied oldest-to-newest before appending current. `history.run_ids` SHALL contain only selected previous IDs in that order.

The deterministic History Analyzer SHALL use successive current-evidence means. For every consecutive pair `previous=p`, `current=c`, it SHALL use effective `level_change_tolerance=t` selected by the accepted Lens > Observation > System precedence with default `0.05`, and classify exactly:

```text
if p == 0 and c == 0:
    transition = stable
else:
    pair_scale = max(abs(p), abs(c))
    near_zero_reference = abs(p) <= t * pair_scale

    if near_zero_reference:
        transition = unknown
    else:
        relative_change = (c - p) / abs(p)

        if abs(relative_change) <= t:
            transition = stable
        elif relative_change > t:
            transition = increasing
        else:
            transition = decreasing
```

Both the near-zero and stable tolerance boundaries SHALL be inclusive. The algorithm SHALL use no absolute epsilon or metric-unit-specific threshold. Zero followed by zero SHALL be stable. The near-zero guard SHALL mean only that relative comparison is unstable; it SHALL NOT indicate abnormality. Unknown transitions SHALL remain counted in `unknown_transitions` but excluded from History direction and pattern denominators under ADR-022.

For pattern classification, the analyzer SHALL remove `unknown` transitions from the chronological sequence while preserving `increasing|decreasing|stable` order as `classifiable_transitions`. If fewer than two remain, pattern SHALL be `unknown`. Otherwise it SHALL remove `stable` only for directional detection, preserving order, and compress consecutive identical `increasing|decreasing` values into `directional_runs`. Stable transitions SHALL remain classifiable and participate in sustained shares, but SHALL neither create nor reset a directional run.

The public evidence count SHALL be `direction_changes=max(0,len(directional_runs)-1)`. Pattern SHALL then follow the accepted priority exactly:

1. `unknown` when fewer than two classifiable transitions exist;
2. `oscillating` when `len(directional_runs) >= 3`;
3. `reversing` when `len(directional_runs) == 2`;
4. `sustained`, only if neither earlier rule matched and increasing, decreasing, or stable has share `>=0.70` over all classifiable transitions;
5. `mixed` otherwise.

Unknown transitions SHALL be removed before every pattern calculation. Stable transitions SHALL not be removed from the sustained denominator. The separate `history.direction` calculation SHALL remain ADR-023's 70% dominance rule over all classifiable transitions and SHALL not use directional runs. Current SHALL participate in transitions but not `run_ids`; raw historical telemetry or mean sequences SHALL not be fetched or serialized.

No eligible results SHALL mean normal omitted History without partial status. Eligible inputs producing accepted unknown direction/pattern SHALL serialize unknown state/evidence without partial status. Unexpected deterministic History computation failure with usable current core SHALL produce partial `history_analysis_failed/history`. Failure to execute the required repository query or its transaction SHALL propagate as an infrastructure/persistence error and SHALL NOT be converted to absent History or a fabricated persisted terminal result.

#### Scenario: Omit History normally

- **GIVEN** no previous result is eligible
- **WHEN** History loading succeeds
- **THEN** `history` and `evidence.history` are absent
- **AND** status does not become partial

#### Scenario: Include overlapping earlier History

- **GIVEN** an eligible previous window overlaps current but ends before current ends
- **WHEN** candidates are selected
- **THEN** the previous result is eligible despite overlap

#### Scenario: Order History deterministically

- **GIVEN** eligible candidates include equal end times, late persistence, and differing starts/IDs
- **WHEN** the lookback is selected
- **THEN** event-time and the specified tie-break determine the same ordered `run_ids` independently of completion/persistence order

#### Scenario: Serialize analytical unknown without partial

- **GIVEN** eligible inputs exist but accepted transition rules produce unknown History
- **WHEN** History analysis succeeds
- **THEN** unknown state and supporting aggregate evidence are serialized
- **AND** status does not become partial

#### Scenario: Classify exact near-zero and zero boundaries

- **GIVEN** consecutive eligible means and the effective tolerance `t`
- **WHEN** `p=0,c=0`, `abs(p)=t*max(abs(p),abs(c))` with a non-zero pair, and a non-zero pair immediately outside that near-zero boundary are classified
- **THEN** zero/zero is stable
- **AND** exact near-zero-boundary equality is unknown
- **AND** the immediately outside pair proceeds to relative-change classification without an absolute epsilon

#### Scenario: Classify inclusive relative-change boundaries

- **GIVEN** the previous mean is not near zero
- **WHEN** relative change is exactly `-t`, exactly `t`, immediately below `-t`, and immediately above `t`
- **THEN** exact `-t` and `t` are stable
- **AND** the values outside the inclusive band are respectively decreasing and increasing

#### Scenario: Classify sustained History patterns

- **GIVEN** chronological transition sequences `[increasing, increasing]`, `[stable, stable]`, and `[stable, unknown, stable]`
- **WHEN** pattern classification executes
- **THEN** every sequence produces `sustained`
- **AND** unknown does not contribute to the denominator while stable does

#### Scenario: Classify reversing History patterns

- **GIVEN** chronological transition sequences `[increasing, decreasing]`, `[increasing, increasing, decreasing, decreasing]`, `[increasing, stable, decreasing]`, and `[increasing, unknown, decreasing]`
- **WHEN** pattern classification executes
- **THEN** every sequence produces `reversing`
- **AND** stable creates no directional run and unknown is removed before directional projection

#### Scenario: Classify oscillating History patterns

- **GIVEN** chronological transition sequences `[increasing, decreasing, increasing]`, `[decreasing, increasing, decreasing]`, and `[increasing, increasing, decreasing, decreasing, increasing]`
- **WHEN** pattern classification executes
- **THEN** every sequence produces `oscillating`
- **AND** oscillating priority applies before sustained share evaluation

#### Scenario: Classify a stable-neutral mixed pattern

- **GIVEN** chronological transitions `[increasing, stable, increasing]`
- **WHEN** pattern classification executes
- **THEN** the single directional run does not match oscillating or reversing
- **AND** no transition type reaches a 70% share over all three classifiable transitions
- **AND** pattern is `mixed`

#### Scenario: Require two classifiable transitions for a pattern

- **GIVEN** fewer than two transitions remain after removing unknown transitions
- **WHEN** pattern classification executes
- **THEN** pattern is `unknown`

#### Scenario: Count public History direction changes from directional runs

- **GIVEN** any chronological transition sequence
- **WHEN** unknown is removed, stable is removed from directional projection, and identical consecutive directional values are compressed
- **THEN** `evidence.history.direction_changes` equals `max(0,len(directional_runs)-1)`
- **AND** stable neither creates nor resets a direction change

#### Scenario: Preserve oscillating and reversing priority over sustained

- **GIVEN** a classifiable sequence whose directional runs match oscillating or reversing and whose full classifiable shares could otherwise satisfy sustained
- **WHEN** pattern classification executes
- **THEN** oscillating or reversing wins according to the fixed priority

#### Scenario: Degrade on deterministic History failure

- **GIVEN** eligible History inputs were loaded and current core is usable
- **WHEN** deterministic History computation unexpectedly fails
- **THEN** the result is partial with `history_analysis_failed/history`

#### Scenario: Propagate History repository failure

- **GIVEN** the required History query or surrounding persistence transaction fails
- **WHEN** the pipeline attempts History loading
- **THEN** it propagates an infrastructure/persistence error
- **AND** it does not reinterpret failure as no History or fabricate completed/partial persistence

### Requirement: Build the exact strict MetricAnalysisResult 1.0 contract

The deterministic builder SHALL be the only MetricAnalysisResult constructor. Every nested model SHALL use strict validation and forbid unknown fields. Identity SHALL reuse existing primitive types exactly:

- `observation_id: UUID`;
- `observation_run_id: UUID`;
- `lens_id: non-empty string`;
- `lens_run_id: UUID`;
- `metric_ref: non-empty string`, copied from existing Metric Lens `metric_id`;
- `unit: non-empty string`.

Every result SHALL contain `schema_version="1.0"`, `lens_type="metric"`, full identity, exact timezone-aware UTC `analysis_window.from/to` with `from<to`, and provenance `source="prometheus"` plus UTC `generated_at`. It SHALL reject `analysis_window.start/end`, `previous_period`, non-finite public numbers, raw samples, `dataset_ref`, transient tool/model messages, and framework/provider transport objects.

The strict variants SHALL be:

1. Completed sufficient: `status={state: completed}`, `data_quality=good|degraded`, required `current_state`, and required `evidence.current`; optional non-empty paired `reference_periods/evidence.reference_periods`; optional paired `history/evidence.history`.
2. Completed insufficient: only common envelope plus `status={state: completed}` and `data_quality=insufficient`; it SHALL forbid `reason`, `current_state`, `reference_periods`, `history`, and `evidence`.
3. Partial: `status={state: partial}`, `data_quality=good|degraded`, required structured primary `reason`, `current_state`, and `evidence.current`; reference/History pairs remain optional.
4. Failed: only common envelope plus `status={state: failed,error: MetricFailedError}`; it SHALL forbid partial `reason`, `data_quality`, `current_state`, `reference_periods`, `history`, and `evidence`.

`MetricFailedError` SHALL use exactly one stable public code/message pair:

| Mandatory failure source | `error.code` | Exact public `error.message` |
| --- | --- | --- |
| current provider-port unavailable/failure/timeout before usable current data | `current_metric_acquisition_failed` | `Current metric data acquisition failed.` |
| current duplicate timestamps or out-of-window sample | `current_metric_series_malformed` | `Current metric series is malformed.` |
| unexpected mandatory statistics, semanticization, or sufficient-result validation failure | `mandatory_metric_analysis_failed` | `Mandatory metric analysis failed.` |

Provider error text, exception text, rejected samples, query details, and stack traces SHALL remain operational diagnostics and SHALL NOT alter or extend the public message. Failed-result `provenance.source` SHALL be copied from the immutable validated execution context's existing Metric adapter discriminator. For this contract that discriminator SHALL be `prometheus`, so failure before any successful provider response still serializes `source="prometheus"`; it does not claim acquisition succeeded. `provenance.generated_at` SHALL come from the pipeline's injected UTC clock when the failed result is built, not from a provider response.

`current_state` SHALL require mandatory trend and variability and MAY contain `spike|oscillation|stuck_signal` with `state=present|absent|unknown` only under the exact successful-tool/evidence co-occurrence rules. `history` SHALL contain accepted direction, pattern, and one-to-effective-`lookback_runs` previous `run_ids`; `evidence.history` SHALL contain effective tolerance, classifiable/unknown and increasing/decreasing/stable transition counts, and direction-change count. Classifiable SHALL equal increasing + decreasing + stable, and classifiable + unknown SHALL equal `len(history.run_ids)`.

One public primary partial reason SHALL be selected with precedence:

```text
reference_unavailable
> history_analysis_failed
> optional_analysis_failed
```

Secondary causes SHALL remain operational diagnostics rather than free-text result fields. The result reason SHALL exactly equal the terminal LensRun reason.

The selected reason component SHALL be deterministic:

- `reference_unavailable` always uses `component=reference_periods`, including multiple failed offsets;
- `history_analysis_failed` always uses `component=history`;
- `optional_analysis_failed` uses `component=metrics_agent` if any agent/model/protocol failure occurred; otherwise it uses the registered tool name of the earliest `failed|timeout` attempt by attempt ordinal.

`not_applicable` and successful deterministic `state=unknown` outcomes SHALL not cause partial status and SHALL not be reason components. All failed offsets, all tool attempts, and all secondary agent/protocol causes MAY remain in application operational diagnostics but SHALL NOT add `reasons[]`, diagnostic strings, or free-text secondary failures to MetricAnalysisResult.

#### Scenario: Build completed sufficient result

- **GIVEN** current mandatory core is usable and no analytical incompleteness occurred
- **WHEN** the builder validates the result
- **THEN** it produces the completed-sufficient variant with correlated current semantics/evidence

#### Scenario: Build completed insufficient result

- **GIVEN** current quality is insufficient and quality determination completed
- **WHEN** the builder validates the result
- **THEN** it produces only the required completed-insufficient envelope
- **AND** all forbidden analytical fields are absent

#### Scenario: Apply primary partial-reason precedence

- **GIVEN** reference, History, and optional-analysis incompleteness occur together
- **WHEN** the partial result is built
- **THEN** its one public reason is `reference_unavailable/reference_periods`
- **AND** secondary causes remain operational only

#### Scenario: Prefer reference component over optional failure

- **GIVEN** at least one reference is unavailable and optional analysis also fails
- **WHEN** the primary partial reason is selected
- **THEN** it is `reference_unavailable/reference_periods`

#### Scenario: Prefer History component over optional failure

- **GIVEN** History analysis and optional analysis both fail without reference incompleteness
- **WHEN** the primary partial reason is selected
- **THEN** it is `history_analysis_failed/history`

#### Scenario: Select the earliest failed tool attempt

- **GIVEN** no agent/protocol violation and two registered tool attempts fail or time out
- **WHEN** optional-analysis component is selected
- **THEN** it is the name of the earliest failed or timed-out tool by attempt ordinal

#### Scenario: Prefer the agent component after an earlier tool failure

- **GIVEN** one registered tool fails and a later Metrics Agent/model/protocol failure occurs
- **WHEN** optional-analysis component is selected
- **THEN** it is `metrics_agent`

#### Scenario: Use the agent component for rejected duplicate and fourth requests

- **GIVEN** the model requests either an already-used tool or a tool after the three-attempt budget is exhausted
- **WHEN** optional-analysis component is selected
- **THEN** it is `metrics_agent`

#### Scenario: Do not make non-failure tool outcomes partial

- **GIVEN** every evaluated tool is either `not_applicable` or successfully returns `state=unknown`
- **WHEN** terminal status and reason are selected
- **THEN** those outcomes create no partial status or reason component
- **AND** successful unknown evidence is retained while not-applicable public evidence remains absent

#### Scenario: Build minimal failed Metric result

- **GIVEN** current acquisition or mandatory deterministic processing fails technically
- **WHEN** the failed result is built
- **THEN** it contains the full identity, failed error, exact window, and provenance
- **AND** it contains none of the forbidden analytical or partial fields
- **AND** it is traceability data rather than usable evidence

#### Scenario: Map a failed Metric error without leaking diagnostics

- **GIVEN** current acquisition, current-series validation, or mandatory analysis fails
- **WHEN** the minimal failed Metric result is built
- **THEN** its public code and exact message are selected from the fixed mapping for that failure stage
- **AND** provider/exception/query details remain operational diagnostics outside the result

#### Scenario: Preserve provenance when current acquisition never succeeds

- **GIVEN** the immutable validated execution context uses the accepted `prometheus` adapter and current acquisition fails before producing a provider outcome
- **WHEN** the minimal failed Metric result is built
- **THEN** `provenance.source="prometheus"` is copied from that context
- **AND** `generated_at` is supplied by the injected UTC clock

#### Scenario: Preserve identity primitive compatibility

- **GIVEN** existing definition/runtime objects supply UUID run/observation identities and string Lens/metric/unit identities
- **WHEN** any Metric result variant is built and round-tripped
- **THEN** every identity field preserves its existing primitive type and value
- **AND** no identity migration or normalization is introduced

#### Scenario: Preserve exact Metric window names

- **GIVEN** any Metric result variant
- **WHEN** it is serialized
- **THEN** it contains `analysis_window.from` and `analysis_window.to`
- **AND** strict validation rejects `start`, `end`, and unknown fields

### Requirement: Persist terminal Metric outcome atomically through the existing repository

The pipeline SHALL use one caller-owned transaction to advance the existing LensRun to its terminal `completed|partial|failed` state and persist at most one correlated validated Metric artifact. It SHALL use the existing runtime repository/artifact table and SHALL NOT create another Metric result persistence model.

An analytical failure that produces a valid minimal failed Metric result SHALL persist that failed LensRun and traceability artifact atomically. A flush or commit failure SHALL roll back both terminal state and artifact, propagate an infrastructure/persistence error, and SHALL NOT claim terminal persistence or fabricate another result. Recovery/retry SHALL remain with the later execution/orchestration capability.

The existing repository SHALL receive only the bounded read operation required for D9 History candidate loading. No raw telemetry, provider payload, prompt trajectory, or transient tool ledger SHALL be persisted.

#### Scenario: Round-trip all Metric result variants

- **GIVEN** validated completed-sufficient, completed-insufficient, partial, and minimal failed Metric results
- **WHEN** each is persisted and retrieved through the existing artifact boundary
- **THEN** strict payload absence/presence, identity, status, reason, window, and provenance round-trip without normalization

#### Scenario: Roll back persistence failure

- **GIVEN** terminal LensRun advancement and artifact insertion are in one caller-owned transaction
- **WHEN** flush or commit fails
- **THEN** both writes roll back
- **AND** an infrastructure/persistence error is surfaced without fabricated terminal persistence

#### Scenario: Avoid transport, model, and framework coupling

- **GIVEN** the completed feature is inspected
- **WHEN** its production modules and dependencies are reviewed
- **THEN** it contains no Prometheus runtime transport implementation and no production model/provider selection
- **AND** PydanticAI appears only in the infrastructure adapter
