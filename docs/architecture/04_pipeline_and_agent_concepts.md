# Концепции за pipelines, agents и component responsibilities

**Статус:** Работна нормативна референция за MVP  
**Версия:** 5.0  
**Актуализирано:** 2026-08-19

## 1. Нива на orchestration

```text
Level 1 — Observation Workflow
Level 2 — Specialized Lens Pipelines
Level 3 — Internal deterministic/agentic stages
Level 4 — Tool calls inside bounded agentic loops
```

## 2. Pipeline vs Stage vs Agent vs Tool

- **Pipeline** — многостъпков workflow с ясен вход/изход и lifecycle.
- **Stage** — node/стъпка в по-голям workflow; може да е component, agent или sub-pipeline.
- **Agent** — LLM/agentic component с ограничена автономност за reasoning/tool use/presentation.
- **Tool** — тясна capability с структуриран contract, извиквана от agent/component.

## 3. Observation Orchestrator

**Тип:** deterministic component  
**Owner stage:** top-level workflow control

### Responsibilities

- instantiate ObservationRun/LensRuns;
- фиксира execution context;
- dispatch specialized Lens pipelines;
- enforce concurrency limit;
- strict JOIN;
- usable-result gate;
- invoke Relationship Evaluation;
- invoke Observation Reasoning;
- invoke Report Generation;
- manage lifecycle/terminal state.

### Non-responsibilities

- domain analysis;
- semantic descriptor calculation;
- relationship rule evaluation;
- RAG decisions;
- findings/hypotheses;
- report narrative.

## 4. Metrics Analysis Pipeline

**Тип:** deterministic orchestrated sub-pipeline with bounded analytical agent

### Core stages

```text
1. Resolve immutable context
2. Fetch current + configured reference-period metric data
3. Preprocess / assess data quality
4. Mandatory evidence: mean/std/min/max/slope + trend + variability
5. Metrics Analysis Agent
6. Optional analytical tools, 0..N
7. Semantic state finalization
8. Reference Period Comparator
9. History Analyzer
10. Result validation/build
11. Persistence
```

## 5. Metrics Analysis Agent

**Тип:** bounded analytical agent

### Can

```text
interpret analysis objectives
select allowed analytical tool
inspect result
select another allowed tool
stop when evidence is sufficient
```

### Cannot

```text
change metric
change time window
modify data acquisition query
fetch unrelated variable
expand Observation scope
skip mandatory core
control persistence or top-level lifecycle
```

`analysis_objectives` = analytical intent, not hard tool mapping.

## 6. Alerts Analysis Pipeline

**Тип:** deterministic orchestrated sub-pipeline with bounded Lens-local analytical agent

```text
Alert LensRun
  -> Alert Provider Adapter
  -> mandatory current fetch
  -> mandatory normalize/validate
  -> mandatory reference fetch
  -> Deterministic Alert Analyzer
       -> mandatory analytical tools/capabilities
  -> zero-record gate
  -> Alert Analysis Agent when record_count>0
       <-> 0..10 optional analytical tool calls
  -> AlertAnalysisResult Builder / Validator
  -> persistence
```

Alerts pipeline използва **hybrid tool model**. Pipeline-ът гарантира mandatory operations и mandatory evidence; LLM не решава дали те да бъдат изпълнени. `Deterministic Alert Analyzer` остава отделен deterministic coordinator на mandatory analytical capabilities.

`Alert Analysis Agent` връща само `findings + overall_importance`, но може да използва allowed optional analytical tools върху вече наличните normalized current/reference данни. Optional tools не разширяват selector, time window, reference configuration или Observation scope. Agentът няма RAG/cross-lens scope.

Optional loop е bounded до 10 calls; един и същ tool може да се извиква многократно. Всеки call attempt се брои към бюджета. `failed|timeout` optional call е non-fatal и agentът продължава.

При `record_count=0` agentът се пропуска и pipeline-ът задава `findings=[]`, `overall_importance=none`.

При failed Alert LensRun не се създава `AlertAnalysisResult`; failure metadata остава в LensRun.

Detailed documents: `13_...` до `19_...`.

### 6.1. Logs Analysis Pipeline

**Тип:** deterministic orchestrated sub-pipeline with bounded Lens-local analytical agent

```text
Log LensRun
  -> resolve immutable context
  -> Log Provider Adapter (Loki for MVP)
       -> aggregate evidence
       -> bounded textual content
  -> parse / normalize / validate / sanitize
  -> Deterministic Log Analyzer
       -> mandatory activity/rate + level/error-level evidence
       -> supplementary templates + reference comparisons
  -> agent invocation gate
  -> Log Analysis Agent when needed
       <-> 0..3 optional analytical tool calls, each tool <=1
       <-> 0..2 knowledge-retrieval calls after findings are frozen
  -> LogAnalysisResult Builder / Validator
  -> persistence
```

Key boundaries:

- no full-corpus LLM input;
- no data-scope expansion by agent/tools;
- Log findings са observational and evidence-grounded;
- retrieved knowledge не създава/променя findings и се пази като separate `knowledge_annotations`;
- Log Agent няма metrics/alerts/Relationships/system diagnosis;
- failed Log Agent -> `partial`, ако deterministic current core е usable;
- failed Log LensRun -> no `LogAnalysisResult`.

Detailed documents: `21_...` до `28_...`.

## 7. Relationship Evaluator

**Тип:** deterministic analytical component/stage

### Input

```text
Relationship[]
LensAnalysisResult[]
```

Сам resolve-ва participants и необходимите current-state fields. За MVP обработва само Relationships, чиито participants са Metric Lens-ове.

### Output

`RelationshipEvaluation[]` — self-contained structured evidence за semantic identity, applicability и consistency.

### Non-responsibilities

Не прави diagnosis/root cause, не използва LLM/RAG, не fetch-ва telemetry и не открива нови Relationships.

## 8. Observation Reasoning Agent

**Тип:** bounded contextual reasoning agent

### Goal

Да формира system-level interpretation върху вече събраните structured Lens/Relationship резултати.

### Input model

```text
ObservationReasoningContext
usable_lens_results[]
relationship_evaluations[]
unavailable_lenses[]
```

Context-ът е compact semantic projection на Observation config; не включва infrastructure/execution noise. Usable results са full structured analytical results, но без raw telemetry.

### Responsibilities

1. Корелира evidence от Metric/Alert/Log Lens results.
2. Използва current/reference/history evidence.
3. Интерпретира RelationshipEvaluation[] като evidence.
4. Формира findings само от Observation evidence.
5. Решава дали конкретни findings изискват domain knowledge.
6. При hypotheses може да използва upstream knowledge annotations само като knowledge layer, никога като finding evidence.
7. При нужда използва `retrieve_knowledge` в bounded loop.
8. Формира 0..N RAG-grounded hypotheses.
9. Определя `overall_state`.
10. Връща structured `ObservationAnalysisResult`.

### Bounded RAG

```text
fixed max_calls = 2
```

Втори retrieval може да refine-не query върху информация от първия retrieval, но крайната цел остава обяснение на вече frozen findings.

### Cannot

- change observed data scope;
- rewrite Lens/Relationship results;
- use retrieved knowledge to create/change findings;
- invent domain hypothesis без retrieved knowledge reference;
- generate final report as only output.

## 9. Report Agent

**Тип:** presentation/generation agent

### Input

```text
ObservationAnalysisResult
minimal Observation semantic context
```

### Responsibilities

- organize accepted analytical result into coherent human-readable report;
- preserve findings/hypotheses/limitations semantics;
- present available knowledge references where useful;
- output Markdown.

### Non-responsibilities

- no new analysis;
- no Lens/Relationship re-evaluation;
- no RAG;
- no new findings/hypotheses;
- no overall_state changes;
- no recommendations in MVP.

## 10. Preferred communication model

```text
Stage A -> structured artifact -> Stage B
```

Free-text agent-to-agent chains не са основният integration contract.
