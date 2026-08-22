# Component / Agent: Alert Analysis Agent

**Тип:** bounded analytical agent  
**Owner stage:** Alerts Analysis Pipeline  
**Статус:** Accepted MVP design  
**Версия:** 2.0  
**Актуализирано:** 2026-08-13

## 1. Purpose

`Alert Analysis Agent` интерпретира текущите normalized alert records и mandatory deterministic evidence в рамките на един Alert LensRun. При нужда използва bounded optional analytical tools върху същия immutable data scope и връща Lens-local descriptive findings + една обща `overall_importance` оценка.

## 2. Inputs

```text
minimal lens_context:
  name
  description

current normalized alert records
alert_activity
status_distribution
duration_statistics [if applicable]
provider_importance_distribution [if available]
successful occurrence comparisons
```

## 3. Outputs

```yaml
agent_output:
  findings:
    - id: af_1
      statement: "..."
      evidence_refs:
        - ...

  overall_importance: moderate
```

Agentът не връща final `AlertAnalysisResult`.

## 4. Responsibilities

- да прегледа occurrence activity и reference comparisons;
- да прецени дали има смислени Lens-local findings;
- да анализира prolonged/current active alert lifecycle;
- да използва provider importance като evidence, когато е налична;
- да използва title/description semantic content без да измисля липсваща информация;
- да deduplicate/merge strongly overlapping findings;
- да върне `overall_importance` по controlled vocabulary;
- да решава дали са нужни 0..N optional tool calls в рамките на фиксиран max 10 budget;
- да използва optional tool outputs само като допълнително evidence за reasoning/findings.

## 5. Non-responsibilities

Agentът не:

- fetch-ва provider data или кара optional tool да fetch-ва нови alerts;
- брои records/occurrences;
- изчислява durations/statistics;
- изчислява reference deltas;
- променя Lens scope/window/query;
- анализира metrics/logs;
- използва RelationshipEvaluation;
- използва RAG/external knowledge;
- прави root-cause diagnosis;
- дава recommendations;
- semantic cluster-ва records;
- infer-ва missing fields;
- persist-ва резултат.

## 6. Allowed capabilities/tools

Agentът работи върху bounded structured input и има достъп до предварително разрешен **optional alert analytical tool registry**.

Minimal MVP registry:

```text
recurrence_concentration_analysis
duration_outlier_analysis
reference_pattern_analysis
```

Tools са deterministic и работят само върху already-available current/reference data/evidence за текущия LensRun. Няма RAG/external-knowledge tools. Detailed contracts: `20_alert_analytical_tools.md`.

## 7. Forbidden capabilities/boundaries

### No missing-data inference

Не може да infer-ва:

```text
status
severity/priority
description
lifecycle timestamps
cause
```

### No semantic grouping

Не формира нови synthetic groups от „подобни“ alert-и и не твърди relationships между records, които не са explicit evidence.

### No cross-lens reasoning

Cross-metric/log/alert correlation е отговорност на `Observation Reasoning Agent`.

### Immutable optional-tool scope

Optional tool call не може да:

```text
change selector/query
change analysis_window
add unconfigured reference period
fetch new alerts
fetch metrics/logs
use external knowledge
expand Observation scope
```

## 8. Guided reasoning checklist

Agentът трябва да разгледа, когато evidence е налично:

1. occurrence activity и reference direction;
2. repeated/recurring occurrences;
3. duration/prolonged records;
4. active/resolved balance;
5. provider importance distribution;
6. title/description semantic meaning;
7. други директно evidence-grounded Lens-local observations.

Checklist-ът не е fixed taxonomy и не изисква finding за всяка точка.

## 9. Finding semantics

Finding:

```yaml
- id: af_1
  statement: "..."
  evidence_refs:
    - ...
```

Допустими са 0..N findings.

Няма mandatory:

```text
type
category
severity
confidence
```

Findings трябва да са descriptive, не causal/prescriptive.

## 10. overall_importance

Controlled vocabulary:

```text
low | moderate | high | critical
```

Agentът се извиква само когато `record_count > 0`, следователно не може да връща `none`.

`none` се задава детерминистично само в zero-record fast path.

Не се връща rationale field.

## 11. Lifecycle / invocation

```text
Deterministic Alert Analyzer
   ↓
record_count > 0
   ↓
prepare bounded agent input
   ↓
Alert Analysis Agent
   ↕ 0..10 optional analytical tool calls
   ↓
findings + overall_importance
   ↓
AlertAnalysisResult Builder / Validator
```

При `record_count=0` agentът не се извиква.

## 12. Failure / uncertainty semantics

Agentът е mandatory за non-zero current records.

```text
agent error   -> LensRun failed / agent_failed
agent timeout -> LensRun failed / agent_timeout
```

Не се прави partial result от incomplete/missing mandatory agent output.

Missing optional provider fields сами по себе си не означават partial; agentът просто не ги използва.

Optional tool execution:

```text
tool success        -> agent may use result
tool not_applicable -> agent continues
tool failed         -> agent continues; no LensRun status change by itself
tool timeout        -> agent continues; no LensRun status change by itself
```

Failed/timeout details се логват operationally и минимално могат да се отразят в `AlertAnalysisResult`.

## 13. Configuration and budgets

Exact LLM model, prompt version, token budget и timeout са implementation decisions.

Accepted bounded tool budget:

```text
max_optional_tool_calls = 10
```

Един и същ tool може да бъде извикван многократно. Всеки invocation attempt се брои към лимита, включително `success`, `failed`, `timeout` и `not_applicable`. При достигане на 10 calls агентът трябва да приключи reasoning-а с наличното evidence.

## 14. Observability / traceability

Operationally е полезно да се логва:

- agent invocation id;
- input record/evidence counts;
- latency;
- timeout/error;
- output validation errors;
- optional tool name/status/latency и total call count.

Prompt/raw model trace не е част от public result contract.

## 15. Related ADRs

ADR-106..ADR-110, ADR-119, ADR-123..ADR-132.

## 16. Open questions

- exact prompt serialization/template;
- model/provider choice;
- token/latency budget;
- exact internal tool-call/result serialization;
- exact evidence-ref mapping за findings derived от transient optional tool evidence.

## 17. Deferred extensions

- richer optional analytical tool registry beyond the accepted minimal MVP set;
- semantic clustering;
- RAG;
- alert-specific taxonomy/confidence;
- prescriptive recommendations.
