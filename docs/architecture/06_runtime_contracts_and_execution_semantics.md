# Runtime contracts и execution semantics

**Статус:** Работна нормативна референция за MVP  
**Версия:** 5.0  
**Актуализирано:** 2026-08-19

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
terminal = completed | partial | failed
usable   = completed | partial, subject to type/data-quality rules
```

`partial` означава usable mandatory result + failed/missing optional sub-analysis. `failed` означава липса на usable analytical result.

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
