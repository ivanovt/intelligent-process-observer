# Alert Analytical Tools — hybrid mandatory/optional tool model

**Проект:** „Интелигентна мулти-агентна система за откриване на аномалии и супервизия на технологични процеси“  
**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-13

## 1. Purpose

Този документ фиксира tool model-а на `Alerts Analysis Pipeline`: кои analytical operations са mandatory и гарантирани от deterministic lifecycle-а, кои tools са optional и agent-driven, какви scope/budget ограничения важат и какъв е минималният optional registry за MVP.

## 2. Hybrid tool model

```text
Alerts Analysis Pipeline
   ↓
mandatory acquisition / normalization / reference retrieval
   ↓
Deterministic Alert Analyzer
   ↕
mandatory deterministic analytical tools/capabilities
   ↓
mandatory structured evidence
   ↓
Alert Analysis Agent
   ↕ 0..10 calls
optional analytical tools
   ↓
findings + overall_importance
```

Основният принцип е:

> Mandatory completeness се гарантира от pipeline-а и deterministic components; agentът използва tools само за допълнителен bounded analysis.

## 3. Mandatory tool/capability class

Mandatory operations не са optional agent decisions. Pipeline-ът гарантира provider access, current fetch, normalization/validation и configured reference retrieval. `Deterministic Alert Analyzer` остава отделен owner/coordinator на mandatory analytical evidence.

Минималните analytical capabilities са:

```text
Alert Activity
Status Analysis
Duration Analysis
Provider Importance Aggregation
Reference Occurrence Comparison
```

Техните exact API/function boundaries са implementation detail. Нормативно е, че mandatory evidence трябва да бъде произведено детерминистично и да не зависи от LLM tool selection.

## 4. Optional tool execution boundary

Optional tools се извикват директно от `Alert Analysis Agent`.

Те могат да използват само:

- normalized current alert records;
- mandatory deterministic evidence;
- successful reference comparison evidence и, ако бъде необходимо за allowed deterministic tool, bounded internal access до already-fetched configured reference data без raw records да се експонират в LLM context.

Не могат да:

```text
fetch-ват нови alerts
променят provider selector/query
променят analysis_window
добавят unconfigured reference offset
fetch-ват metrics/logs
използват RAG/external knowledge
разширяват Observation/Lens scope
```

## 5. Bounded tool loop

```text
max_optional_tool_calls = 10
```

Rules:

- един и същ tool може да бъде извикван многократно;
- всеки invocation attempt се брои към лимита;
- `success`, `failed`, `timeout` и `not_applicable` всички консумират един call;
- след call #10 не се разрешава нов optional call; agentът приключва с наличното evidence.

## 6. Failure semantics

Optional tools са best-effort analytical enrichment.

```text
success        -> result may be used by agent
not_applicable -> normal outcome; agent continues
failed         -> log + agent continues
timeout        -> log + agent continues
```

`failed|timeout` optional call **не** променя сам по себе си `LensRun.status` на `partial` или `failed`.

Техническите details остават в execution logs. В `AlertAnalysisResult` може да присъства само минимален trace за `failed|timeout` calls.

## 7. Persistence semantics

Successful optional tool outputs са transient analytical evidence:

```text
optional tool result
   ↓
Alert Analysis Agent reasoning
   ↓
finding / overall_importance
```

Те не се persist-ват като самостоятелни analytical sections в `AlertAnalysisResult`.

`not_applicable` също не се сериализира. Само реални `failed|timeout` calls могат да се отразят минимално чрез `optional_tool_execution.unsuccessful_calls`.

## 8. Minimal optional MVP registry

### 8.1. Recurrence Concentration Analysis Tool

**Цел:** да покаже дали текущата occurrence activity е концентрирана в един доминиращ alert record.

Input:

```text
current usable alert records
record-level effective occurrence counts
current total occurrence_count
```

Metric:

```text
top_record_share = max(effective_occurrence_count_i) / total_occurrence_count
```

Output example:

```yaml
recurrence_concentration_analysis:
  status: completed
  dominant_alert:
    alert_id: ALERT-A
    occurrence_count: 12
  total_occurrence_count: 16
  top_record_share: 0.75
```

Rules:

- tool-ът не map-ва резултата към `low|high|critical`;
- semantic interpretation остава за agent-а;
- при `total_occurrence_count=0` резултатът е `not_applicable`.

### 8.2. Duration Outlier Analysis Tool

**Цел:** да открива нетипично дълги current alert durations чрез прост deterministic IQR метод.

Configuration:

```text
method = IQR
minimum_valid_durations = 8
outlier_side = high
```

Algorithm:

```text
IQR = Q3 - Q1
upper_bound = Q3 + 1.5 * IQR

duration_seconds > upper_bound -> high duration outlier
```

Ако валидните duration values са по-малко от 8:

```yaml
duration_outlier_analysis:
  status: not_applicable
  reason: insufficient_sample
  sample_size: ...
  minimum_required: 8
```

`not_applicable` не е LensRun partial/failure.

Tool-ът не определя сам дали outlier-ът е critical/anomalous; това е semantic responsibility на agent-а.

### 8.3. Reference Pattern Analysis Tool

**Цел:** да агрегира вече изчислените independent reference occurrence comparisons и да покаже доминиращата посока.

Applicability:

```text
minimum_reference_comparisons = 2
```

Input directions:

```text
increased | decreased | unchanged
```

Algorithm:

```text
count each direction
unique most frequent direction -> dominant_direction
no unique winner / tie          -> mixed
```

Няма weights според offset, tolerance, percentage score или global anomaly score.

Example:

```yaml
reference_pattern_analysis:
  status: completed
  compared_periods: 3
  directions:
    increased: 2
    decreased: 0
    unchanged: 1
  dominant_direction: increased
```

При по-малко от две successful comparisons:

```text
status = not_applicable
```

## 9. Agent interpretation boundary

Optional tools връщат измерими/структурирани facts. Те не формулират system diagnosis, root cause или recommendation.

```text
tool -> quantitative/structured fact
agent -> Lens-local semantic finding
Observation Reasoning Agent -> cross-lens/system-level reasoning
```

## 10. Traceability

Operationally всеки optional invocation трябва да може да се trace-не чрез поне:

```text
tool name
invocation order
status
latency
```

Public result пази само минимален unsuccessful trace за `failed|timeout`, ако такъв има.

## 11. Open decisions

- exact internal tool request/response serialization;
- exact timeout per optional tool;
- exact evidence-ref mapping за findings, derived от transient optional tool evidence;
- future additions към optional registry.

## 12. Related documents

- `02_architecture_principles_and_runtime.md`
- `04_pipeline_and_agent_concepts.md`
- `13_alert_lens_and_analysis_concept.md`
- `14_alerts_analysis_pipeline_detailed.md`
- `15_alert_analysis_result_contract.md`
- `16_alert_analysis_agent.md`
- `17_deterministic_alert_analyzer.md`
- `18_alert_analysis_result_builder.md`
- `03_ADR_log.md`
