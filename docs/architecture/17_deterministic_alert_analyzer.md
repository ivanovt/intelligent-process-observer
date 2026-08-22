# Component: Deterministic Alert Analyzer

**Тип:** deterministic analytical component  
**Owner stage:** Alerts Analysis Pipeline  
**Статус:** Accepted MVP design  
**Версия:** 2.0  
**Актуализирано:** 2026-08-13

## 1. Purpose

`Deterministic Alert Analyzer` е отделен deterministic analytical component и coordinator на mandatory alert analytical tools/capabilities. Той преобразува normalized current/reference alert records в проверимо numerical/structured evidence, което се използва от `Alert Analysis Agent` и `AlertAnalysisResult Builder / Validator`.

## 2. Inputs

```text
usable normalized current alert records
successful reference-period record sets/activity inputs
analysis_timestamp
configured reference offsets
```

## 3. Outputs

```text
alert_activity
status_distribution
duration_statistics [record_count>0]
provider_importance_distribution [if available]
occurrence comparisons
```

## 4. Responsibilities

- effective occurrence counting;
- record counting;
- status distribution by records;
- per-record duration calculation;
- min/max/average duration statistics;
- provider importance distribution;
- current vs reference occurrence comparison;
- deterministic direction classification;
- orchestration/aggregation на mandatory analytical tools/capabilities и гарантиране на mandatory evidence completeness.

## 5. Non-responsibilities

Не:

- интерпретира title/description;
- формулира findings;
- определя overall importance;
- прави semantic clustering;
- използва LLM/RAG;
- fetch-ва unrelated data;
- прави causal inference.

## 6. Mandatory analytical tool/capability model

Минималният mandatory analytical набор покрива:

```text
Alert Activity capability
Status Analysis capability
Duration Analysis capability
Provider Importance Aggregation capability
Reference Comparison capability
```

Тези capabilities могат да бъдат реализирани като отделни deterministic tools/functions/services. Те **не** се извикват по решение на Alert Analysis Agent. `Alerts Analysis Pipeline` гарантира изпълнението на `Deterministic Alert Analyzer`, а Analyzer-ът гарантира required mandatory evidence. Exact interface decomposition остава implementation detail.

## 7. Algorithms

### 7.1. Effective occurrence count

```text
if occurrence_count is present:
    effective = occurrence_count
else:
    effective = 1
```

### 7.2. Activity

```text
record_count = len(usable_current_records)
occurrence_count = sum(effective occurrence counts)
```

### 7.3. Status distribution

```text
active   = number of records normalized active
resolved = number of records normalized resolved
unknown  = number of records normalized unknown
```

Occurrence count не умножава status distribution.

### 7.4. Duration

```text
resolved -> ended_at - started_at
active   -> analysis_timestamp - started_at
```

Serialization: seconds.

Statistics:

```text
min_seconds
max_seconds
average_seconds
```

No median for MVP.

### 7.5. Provider importance distribution

Групира original provider values без mapping:

```yaml
provider_importance_distribution:
  type: priority
  values:
    Highest: 2
    High: 4
```

Section-ът е absent, ако няма values.

### 7.6. Reference comparison

```text
current = current occurrence_count
reference = reference occurrence_count
delta = current - reference
```

```text
current > reference -> increased
current < reference -> decreased
current = reference -> unchanged
```

No tolerance / no percentage classification.

## 8. Failure / uncertainty semantics

Ако Analyzer или mandatory analytical tool/capability не може да произведе mandatory current deterministic evidence:

```text
LensRun -> failed
reason.code = deterministic_analysis_failed
```

Reference-query unavailability се решава upstream като partial; analyzer работи върху available references.

## 9. Configuration and budgets

Няма agentic budget. Algorithms са deterministic и unit-testable.

## 10. Observability / traceability

Useful internal telemetry:

```text
input record_count
invalid count from upstream
computed occurrence_count
reference offsets processed
processing latency
```

## 11. Related ADRs

ADR-098..ADR-105, ADR-118, ADR-123..ADR-124.

## 12. Open questions

- exact numeric precision/rounding за average_seconds;
- provider-specific occurrence count caveats beyond accepted MVP limitation;
- exact internal mandatory tool interfaces/decomposition.

## 13. Deferred extensions

- median/percentiles;
- burst/flapping analysis;
- richer optional agent-driven tools beyond `20_alert_analytical_tools.md`;
- temporal clustering;
- richer reference comparison metrics.
