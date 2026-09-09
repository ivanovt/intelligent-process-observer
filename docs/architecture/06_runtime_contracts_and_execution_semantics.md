# Runtime contracts и execution semantics

**Статус:** Работна нормативна референция за MVP  
**Версия:** 5.1
**Актуализирано:** 2026-09-09

## 1. Common Lens Pipeline interface

```text
execute(LensRun) -> terminal LensRun outcome
```

Usable outcome (`completed|partial`) включва type-specific `LensAnalysisResult`. При `failed` винаги има terminal LensRun; наличието на отделен failed type-specific result artifact е type-specific policy. За Alerts и Logs MVP failed LensRun **не** създава съответно `AlertAnalysisResult` или `LogAnalysisResult`.

Common lifecycle envelope:

```text
schema_version
identity
lens_type
status
provenance
[type-specific analytical payload]
```

## 2. Lens status и usability

```text
terminal = completed | partial | failed | cancelled
usable   = completed | partial, subject to type/data-quality rules
```

`partial` означава usable mandatory result + failed/missing optional sub-analysis. `failed` означава липса на usable analytical result.
`cancelled` означава, че top-level cancellation е прекъснала незавършен LensRun; то не е usable analytical result.

За Metric history eligibility:

```text
completed/partial + good/degraded -> usable for history
insufficient                     -> not usable for history
```

## 3. Fan-out, concurrency и strict JOIN

LensRuns са logically independent. Runtime може да ги изпълнява concurrent с configurable maximum concurrency.

JOIN condition:

```text
ALL LensRuns of current ObservationRun are terminal
```

Не се използва early continuation. Timeout трябва да доведе LensRun до terminal failure.
При top-level cancellation normal JOIN continuation се прекратява: terminal LensRuns се
запазват, `pending|running` LensRuns и ObservationRun преминават към `cancelled`, след
което cancellation се propagate-ва (ADR-165).

On-demand public execution се host-ва от точно един application process/worker за MVP
(ADR-168). Durable runtime graph и `ObservationRun=running` се commit-ват преди public
launch да върне identity. Post-initialization workflow-ът продължава в една managed
`asyncio` task. Graceful shutdown използва ADR-165; orphaned active records след hard
process interruption се terminalize-ват при startup като
`cancelled/execution_cancelled` и никога не се resume-ват.

Persistence налага най-много един `pending|running` ObservationRun за едно Observation.
Това е overlap invariant, не multi-process ownership protocol. Single-process
deployment е нормативно ограничение, докато няма отделен claim/lease design.

Public admission за едно Observation се сериализира process-locally през durable active
lookup и initialization commit. Намерен active run дава отделен launch conflict със
stable run identity. Partial unique index е defense in depth; негов loser прави точно
един post-rollback lookup. Ако active run вече липсва, API връща
`launch_admission_uncertain` и не retry-ва initialization без нов client request.

При detached persistence uncertainty manager-ът fail-ва closed: преминава в
`recovery_required`, спира launch admission, quiesce-ва process-owned tasks и retry-ва
само durable cancellation/reconciliation веднага и после през `5s`. Analytical stages
не се retry-ват. `ready` се възстановява само след successful commit и fresh durable
read без active ObservationRuns. Startup не става ready при failed reconciliation;
graceful shutdown не claim-ва completion без durable cancellation. Public reads са
best-effort и показват единствено persist-ната истина.

Initialization admission е tracked преди първия database await и носи monotonic
recovery generation. След commit continuation + accepted response snapshot се
register-ват atomic само ако manager остава `ready` на същата generation. Indeterminate
commit outcome влиза в recovery. Recovery increment-ва generation и чака всички
older-generation initializer/continuation tasks и transaction/session scopes да се
затворят преди reconciliation; така final active-state verification не може да бъде
последван от late initializer commit. Fenced initializer не връща `202` и не се retry-ва.

Accepted response snapshot се materialize-ва от initialization transaction-а и не
изисква database read след continuation registration. То е explicit point-in-time
`running` representation с null analytical/finish fields. Ако continuation завърши
преди HTTP serialization, `202` не се rewrite-ва; следващ list/detail read показва
актуалния durable terminal state.

Всеки public run-detail response трябва да е coherent database snapshot. Ако ORM load
използва множество queries, те се изпълняват в една read-only PostgreSQL
`REPEATABLE READ` transaction. Concurrent atomic Lens terminal transition + artifact
insert се виждат или изцяло преди, или изцяло след snapshot-а, никога като torn
status/artifact combination. Summary list response използва една ordered statement.

Persist-натите RelationshipEvaluations пазят zero-based ordinal от frozen Relationship
definition order. Ordinal-ът е persistence metadata, не domain payload field; той е
unique и contiguous за run-а и е единственият source за public/detail ordering.

Trusted-MVP public run detail reuse-ва exact strict Metric/Alert schema `1.0`,
unversioned RelationshipEvaluation, ObservationAnalysisResult `1.0` и unversioned
ObservationReport contracts. Alert `CanonicalAlertRecord` fields, включително
provider-originated title/description/source status/provider importance/source_ref, са
explicit public operational evidence и се render-ват като untrusted text. Raw provider
records, selectors/queries, credentials, acquisition diagnostics, execution context,
prompts/model data и transient successful tool outputs не се expose-ват. Invalid stored
artifact или correlation fail-ва целия detail projection със safe
`runtime_projection_invalid`, без partial omission.

## 4. Post-JOIN gate

```text
if usable_results.count == 0:
    ObservationRun -> failed
    STOP
else:
    continue -> Relationship Evaluation
```

## 5. Relationship Evaluation contract

```text
Input:
  Relationship[]
  LensAnalysisResult[]

Output:
  RelationshipEvaluation[]
```

Evaluator-ът self-resolve-ва participant results. За MVP configured Relationships са metric-only.

## 6. Observation Reasoning input contract

Conceptual top-level form:

```yaml
observation_reasoning_input:
  observation_context:
    observation:
      id: ...
      name: ...
      description: ...
      objective: ...
    lenses:
      - id: ...
        type: metric
        description: ...
        analysis_objectives: [...]

  usable_lens_results:
    - # full structured completed/partial LensAnalysisResult

  relationship_evaluations:
    - # self-contained RelationshipEvaluation

  unavailable_lenses:
    - lens_id: ...
      type: log
      reason:
        code: data_source_unavailable
```

### 6.1. ObservationReasoningContext

Това е **semantic projection**, не копие на full Observation configuration. Не включва Prometheus/Loki queries, retry/timeout, concurrency, storage/infrastructure settings и други execution details.

### 6.2. Usable results

`completed` и `partial` result-и се подават в `usable_lens_results`. Те могат да бъдат пълните structured analytical contracts, включително current/reference/history evidence. Raw telemetry не се подава.

Partial result включва кратък structured reason, например:

```yaml
partial_reason:
  code: optional_analysis_failed
  component: oscillation_analysis
```

### 6.3. Unavailable results

Failed/non-usable Lens-ове не се подават като празни analytical contracts. Те се представят отделно:

```yaml
unavailable_lenses:
  - lens_id: logs
    type: log
    reason:
      code: data_source_unavailable
```

Reason code речникът остава малък и може да включва `optional_analysis_failed`, `data_source_unavailable`, `insufficient_data`, `analysis_failed`, `timeout`.

## 7. ObservationAnalysisResult contract

Normative minimal structure е описана в `08_observation_analysis_result_contract.md`:

```text
schema_version
identity
overall_state
findings[]
hypotheses[]
limitations[]
```

`overall_state` vocabulary:

```text
no_significant_findings
significant_findings_present
uncertain
```

`uncertain` може да съществува заедно с валидни findings. За MVP няма допълнителни hard consistency invariants между overall_state и броя findings.

## 8. Knowledge retrieval execution semantics

RAG е tool capability вътре в Observation Reasoning Agent.

```text
fixed system max_calls = 2
```

Rules:

- findings се формират преди първия retrieval;
- retrieved knowledge не променя findings;
- query трябва да произлиза от един или повече findings;
- second retrieval може да използва useful context от first retrieval и unresolved gap;
- agent може да спре преди max_calls;
- domain hypothesis изисква `supported_by` + `knowledge_refs`;
- ако няма достатъчно knowledge, `hypotheses: []` е валидно.

## 9. Report Generation contract

```text
Input:
  ObservationAnalysisResult
  minimal Observation semantic context

Output:
  ObservationReport (Markdown presentation artifact)
```

Report Agent не получава raw Lens results, Relationship definitions, telemetry или retrieval capability.

Minimal envelope example:

```yaml
observation_report:
  observation_id: ...
  observation_run_id: ...
  generated_at: ...
  format: markdown
  content: |
    ## Обща оценка
    ...
```

## 10. AlertAnalysisResult summary

Usable Alert result (`completed|partial`) съдържа:

```text
schema_version
identity:
  observation_id
  observation_run_id
  lens_id
  lens_run_id
lens_type = alert
status
reason [partial only]
analysis_timestamp
analysis_window
provenance
alerts[]
alert_activity
status_distribution
duration_statistics [optional when records exist]
provider_importance_distribution [optional]
comparisons
findings[]
overall_importance
optional_tool_execution [optional; only failed/timeout optional calls]
```

Key invariants:

```text
record_count = 0 -> skip Alert Analysis Agent -> findings=[] -> overall_importance=none
record_count > 0 -> overall_importance in low|moderate|high|critical
optional analytical tool failed/timeout -> continue; no LensRun status change by itself
failed Alert LensRun -> NO AlertAnalysisResult
```

Reference raw records не се включват. Unavailable reference comparisons се пропускат; result става partial с structured reason. Successful optional tool outputs са transient reasoning evidence и не се сериализират като самостоятелни analytical sections. Ако optional call завърши с `failed|timeout`, може да се добави минимален `optional_tool_execution.unsuccessful_calls` trace; `not_applicable` не се счита за failure.

## 11. LogAnalysisResult summary

Usable Log result (`completed|partial`) съдържа концептуално:

```text
schema_version
identity
lens_type = log
status
reason [partial only]
analysis_window
provenance
log_activity
level_distribution
error_level_activity
templates [optional/supplementary]
comparisons[]
findings[]
overall_importance [absent when agent unavailable]
knowledge_annotations[] [optional; external knowledge layer]
```

Key semantics:

```text
aggregate counts/rates are not required to derive from bounded textual content
Log findings are observational evidence-grounded
knowledge_annotations are NOT observational evidence
knowledge retrieval occurs only after findings are frozen
max optional analytical tool calls = 3, each tool max once
max Log knowledge retrieval calls = 2
Log Agent failure + usable deterministic core -> partial
failed Log LensRun -> NO LogAnalysisResult
```

Observation Reasoning may use Log `knowledge_annotations` only as knowledge grounding for hypotheses. They cannot support Observation findings.

## 12. MetricAnalysisResult summary

Основни sections:

```text
schema_version
identity
status
analysis_window
data_quality
current_state
reference_periods [optional]
history [optional]
evidence
provenance
```

При `failed` се използва minimal contract. Identity:

```text
observation_id
observation_run_id
lens_id
lens_run_id
metric_ref
unit
```

Data quality:

```text
good | degraded | insufficient | unknown
```

History traceability се осигурява чрез `history.run_ids`; raw historical sequence не се пази в result-а.

## 13. Failure propagation principles

```text
optional analyzer failure
-> Lens partial, ако mandatory core е usable

single Lens failed
-> Observation не се проваля автоматично

Alert reference unavailable
-> Alert Lens partial, ако current mandatory analysis е usable

Alert current query / deterministic core / required agent failed
-> Alert Lens failed; no AlertAnalysisResult

Log current acquisition / minimal deterministic core failed
-> Log Lens failed; no LogAnalysisResult

Log Agent failed/timeout + deterministic core usable
-> Log Lens partial; LogAnalysisResult remains usable

Log optional analytical tool / knowledge retrieval failed/timeout
-> non-fatal best-effort; continue

all Lens unusable
-> Observation failed / STOP

top-level cancellation
-> preserve terminal LensRuns and committed artifacts
-> pending/running LensRuns cancelled
-> ObservationRun cancelled / STOP / propagate cancellation

relationship condition evidence missing
-> applicability unknown

relationship applicable but expected evidence missing
-> state uncertain
```

## 14. Persistence boundaries

Минимално persistable:

```text
Observation/Lens/Relationship definitions
ObservationRun
LensRun
LensAnalysisResult(s)
RelationshipEvaluation(s)
ObservationAnalysisResult
ObservationReport
```

Database technology/schema остава Open.

Type-specific notes:
- failed Alert LensRun persist-ва runtime failure state/logs, но не type-specific `AlertAnalysisResult`;
- failed Log LensRun persist-ва runtime failure state/logs, но не type-specific `LogAnalysisResult`.
