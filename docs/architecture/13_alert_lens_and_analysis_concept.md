# Alert Lens и Alerts Analysis — концепция и нормативен MVP дизайн

**Проект:** „Интелигентна мулти-агентна система за откриване на аномалии и супервизия на технологични процеси“  
**Статус:** Работна нормативна референция за MVP  
**Версия:** 2.0  
**Актуализирано:** 2026-08-13

## 1. Цел

Този документ фиксира концепцията за `Alert Lens`, начина на извличане и нормализиране на alert данни, основните аналитични semantics, ролята на `Alerts Analysis Pipeline`, `Deterministic Alert Analyzer`, `Alert Analysis Agent`, `AlertAnalysisResult Builder / Validator`, failure/partial поведението и downstream contract-а към Observation-level reasoning.

Документът е type-specific допълнение към общите архитектурни принципи. При конфликт приоритет имат по-нов ADR и актуалните runtime/contract документи.

## 2. Място в общия workflow

`Alerts Analysis Pipeline` е sibling pipeline на Metrics и Logs pipelines и се изпълнява за конкретен `Alert LensRun`.

```text
ObservationRun
   ↓
LensRun fan-out
   ├─ Metric LensRun -> Metrics Analysis Pipeline
   ├─ Alert LensRun  -> Alerts Analysis Pipeline
   └─ Log LensRun    -> Logs Analysis Pipeline
```

`Observation Orchestrator` управлява lifecycle, dispatch, concurrency, strict JOIN и post-JOIN continuation. Той не анализира alert-и и не познава вътрешните analytical stages на Alerts pipeline-а.

За usable изпълнение:

```text
Alert LensRun
   ↓
Alerts Analysis Pipeline
   ↓
AlertAnalysisResult (completed | partial)
```

При `failed` Alert LensRun не се създава `AlertAnalysisResult`; failure metadata остава в `LensRun` и operational logs.

## 3. Какво представлява Alert Lens

### 3.1. Единна концепция вместо два различни Lens типа

Един `Alert Lens` модел трябва да покрива и двата практически случая:

1. наблюдение на конкретен alert rule/type;
2. наблюдение на множество alert-и, ограничени до component/asset/service/application scope.

Не се въвеждат две архитектури. Разликата е в селектора:

```text
specific alert rule -> restrictive selector
bounded alert set   -> broader selector
```

### 3.2. Working definition

```yaml
alert_lens:
  id: database_alerts
  type: alert
  name: "Database alerts"
  description: "Alert activity related to the database service"

  source: jira_track_and_release

  selector:
    query: "<provider-native query>"

  reference_periods:
    - offset: 1d
    - offset: 7d
```

Точната serialized configuration schema остава implementation detail; семантиката по-горе е нормативна.

## 4. Provider и query semantics

### 4.1. Current MVP provider

Текущият provider за MVP е `Jira Track and Release`. Дизайнът обаче е source-agnostic на analytical ниво и допуска бъдещи provider adapters.

### 4.2. Provider-native selector

Alert Lens използва provider-native query/filter. Analysis pipeline-ът не трябва да знае provider-specific syntax.

```text
Alert Lens
  -> source/provider
  -> provider-native selector
  -> matching provider records
  -> normalization
  -> source-agnostic alert analysis
```

### 4.3. Scope vs time

Селекторът определя **кои alert-и** са част от Lens scope-а.

`LensRun` определя **кога** се наблюдават.

```text
selector/query -> alert population / semantic scope
LensRun        -> analysis_window + analysis_timestamp
```

Time scope не се скрива във free-text/provider query. Provider adapter-ът трябва да изпълни provider-specific extraction така, че да спази общата time-window semantics.

### 4.4. Lifecycle status не е selector dimension за MVP

Lifecycle status (`active`, `resolved` и provider-specific status) е analytical data, а не средство за scope filtering.

Инженерът не трябва да добавя lifecycle status predicate в provider-native query. За MVP няма автоматична query validation/rewrite логика; системата не модифицира непрозрачно provider query-то.

## 5. Time-window membership

Alert е релевантен, ако lifecycle-ът му се пресича с analysis window-а:

```text
alert.started_at < window.end
AND
(alert.ended_at is null OR alert.ended_at > window.start)
```

Тази overlap semantics важи еднакво за current и reference windows.

Следствия:

- alert, започнал преди window-а и активен в него, е релевантен;
- alert, започнал в window-а и приключил след края му, е релевантен;
- анализът не се ограничава до `created_at inside window`.

## 6. Retrospective lifecycle semantics

Анализът използва най-новата информация, налична към момента на изпълнение.

Ако alert е пресичал исторически reference window, но е resolved по-късно, `ended_at` може да съдържа реалния по-късен момент на приключване. MVP не реконструира point-in-time provider state.

Duration е **пълната lifecycle продължителност**, а не само overlap duration с analysis window-а.

```text
resolved alert:
  duration = ended_at - started_at

active alert:
  duration = analysis_timestamp - started_at
```

`analysis_timestamp` е фиксиран за целия LensRun, за да е възпроизводима продължителността на active alert-и.

## 7. Normalized alert record

### 7.1. Normative working contract

```yaml
alert:
  id: "ALERT-1234"
  title: "Database connection saturation"
  description: "..."                   # optional

  started_at: "2026-08-09T08:12:00Z"
  ended_at: null                        # nullable
  duration_seconds: 8040

  status:
    normalized: active                  # active | resolved | unknown
    source: "In Progress"

  provider_importance:                  # optional
    type: priority
    value: "Highest"

  occurrence_count: 7                   # optional source value
  source_ref: "..."                     # optional
```

### 7.2. Identity

За MVP `id` може да бъде provider identifier. Не се въвежда отделен internal record id + provenance object на ниво alert record.

`source_ref` е optional навигационна/traceability референция, когато provider-ът я предлага.

### 7.3. Required fields

За usable current alert record са задължителни поне:

```text
id
title
started_at
```

`ended_at` е nullable.

Record без валиден `started_at` е invalid, защото не може надеждно да се определи overlap и duration.

Ако:

```text
ended_at < started_at
```

record-ът също е invalid.

### 7.4. Normalized status

MVP vocabulary:

```text
active | resolved | unknown
```

Основното lifecycle mapping е:

```text
ended_at != null -> resolved
ended_at == null -> active
```

`status.source` пази provider status за traceability. `unknown` остава резервна стойност за случаи, при които provider lifecycle не може да бъде надеждно нормализиран, но агентът не трябва сам да infer-ва status.

### 7.5. Provider importance

Не се прави глобална severity/priority нормализация между provider-и.

```yaml
provider_importance:
  type: priority
  value: "Highest"
```

или:

```yaml
provider_importance:
  type: severity
  value: "Critical"
```

Field-ът е optional. Ако provider-ът няма такава концепция, той се пропуска; не се създава изкуствено `unknown`.

## 8. occurrence_count и record_count

### 8.1. Две различни мерки

```yaml
alert_activity:
  record_count: 3
  occurrence_count: 21
```

- `record_count` = брой distinct usable provider records;
- `occurrence_count` = сумата от effective occurrence count на records.

### 8.2. Missing occurrence_count

Provider adapter-ът не нормализира липсващ `occurrence_count` до 1 в самия record.

`Deterministic Alert Analyzer` използва:

```text
effective_occurrence_count =
  occurrence_count, ако е наличен
  1, ако липсва
```

### 8.3. Status distribution не се тегли по occurrence count

Ако има:

```text
1 active record   occurrence_count=15
1 resolved record occurrence_count=8
```

тогава:

```text
status_distribution.active   = 1
status_distribution.resolved = 1
alert_activity.occurrence_count = 23
```

Не се реконструира lifecycle status на отделните historical occurrences.

### 8.4. Accepted limitation

Provider `occurrence_count` може да има semantics, които включват occurrences извън текущия/reference window. MVP приема тази provider limitation; не се прави сложна реконструкция на individual occurrences.

## 9. Deterministic Alert Analyzer

`Deterministic Alert Analyzer` е отделен deterministic component/stage и произвежда проверимо structured evidence. В hybrid tool model-а той координира mandatory analytical tools/capabilities, чието изпълнение е гарантирано от pipeline-а. LLM не решава дали mandatory evidence да бъде произведено и не извършва сам counting/duration/statistics.

### 9.1. Mandatory deterministic evidence

```yaml
alert_activity:
  record_count: ...
  occurrence_count: ...

status_distribution:
  active: ...
  resolved: ...
  unknown: ...

duration_statistics:
  min_seconds: ...
  max_seconds: ...
  average_seconds: ...

provider_importance_distribution:   # optional
  type: priority
  values:
    Highest: 2
    High: 4

comparisons:
  - ...
```

При `record_count = 0` `duration_statistics` липсва.

`provider_importance_distribution` се включва само когато има реални provider importance values.

### 9.2. Deliberately excluded from MVP

Не се включват mandatory:

```text
median duration
burst detection
temporal clustering
semantic clustering
flapping detection
provider-independent severity score
```

`burst/flapping` и semantic clustering остават извън MVP. Ограничен набор от по-прости optional analytical tools е разрешен в Alert Analysis Agent след mandatory evidence, без промяна на Observation workflow-а.

## 10. Reference periods

### 10.1. Multiple independent references

Alert Lens може да конфигурира повече от един reference period.

Всеки reference window:

- има същата продължителност като current analysis window;
- е изместен назад с configured `offset`;
- използва същия Alert Lens selector/scope;
- се сравнява индивидуално с current window.

Пример:

```text
current window: T0..T1
reference 1d:   T0-1d .. T1-1d
reference 7d:   T0-7d .. T1-7d
```

В `AlertAnalysisResult` не се дублират конкретните calculated reference `start/end`; пази се `offset`.

### 10.2. Comparison measure

Historical comparison за MVP използва **само `occurrence_count`**.

```yaml
comparisons:
  - offset: 1d
    occurrence_comparison:
      current: 21
      reference: 8
      delta: 13
      direction: increased
```

Controlled direction:

```text
increased | decreased | unchanged
```

Rule:

```text
current > reference -> increased
current < reference -> decreased
current = reference -> unchanged
```

Няма tolerance и percentage-change classification.

### 10.3. Historical records не се подават downstream

Reference-period raw/normalized alert records:

- не се подават към `Alert Analysis Agent`;
- не се включват в `AlertAnalysisResult`;
- не се подават към Observation Reasoning.

Downstream се използва само compact comparison evidence.

### 10.4. Unavailable reference periods

Ако reference query се провали, резултатът може да остане usable `partial`.

Неуспешният reference period просто липсва от `comparisons`; не се създава placeholder като `status: unavailable` за самия comparison.

Непълнотата се представя чрез:

```yaml
status: partial
reason:
  code: reference_unavailable
  component: reference_period_analysis   # optional
```

## 11. Zero-alert fast path

Fast path се активира **само** при надеждно установено:

```text
record_count = 0
```

Не се използва `occurrence_count = 0` като достатъчно условие, ако има реално върнати records.

Reference queries все пак се изпълняват.

```text
record_count = 0
   ↓
skip Alert Analysis Agent
   ↓
findings = []
overall_importance = none
   ↓
AlertAnalysisResult Builder / Validator
```

Така се избягва ненужно LLM извикване, без да се губи historical comparison context.

## 12. Alert Analysis Agent

### 12.1. Purpose

`Alert Analysis Agent` прави **Lens-local descriptive reasoning** върху вече нормализирани current alert records и mandatory deterministic evidence.

След получаване на mandatory evidence агентът може да използва bounded optional analytical tool loop за допълнително изследване на вече наличните данни. Той не е counting/statistics engine за mandatory core и не е system-level diagnostic agent.

### 12.2. Input

```yaml
lens_context:
  name: "..."
  description: "..."

current:
  alerts:
    - ...
  alert_activity:
    ...
  status_distribution:
    ...
  duration_statistics:
    ...
  provider_importance_distribution:
    ...

comparisons:
  - ...
```

Не се подава:

```text
raw provider payload
historical/reference alert records
provider-native query
metrics
logs
RelationshipEvaluation
external knowledge/RAG context
```

### 12.3. Optional analytical tool boundary

Optional tools могат да работят само върху вече извлечените и нормализирани данни за current window и configured successful reference periods. Те не могат да:

```text
fetch-ват нови alerts
променят provider selector/query
разширяват analysis window
добавят нов reference offset
извличат metrics/logs/external knowledge
разширяват Observation scope
```

Bounded loop:

```text
max_optional_tool_calls = 10
```

Един и същ optional tool може да се извиква многократно. Всеки invocation attempt се брои към лимита, независимо дали е `success`, `failed`, `timeout` или `not_applicable`. `failed|timeout` optional tool не променя сам по себе си LensRun status; agentът продължава с наличното evidence.

Минималният MVP registry е:

1. `Recurrence Concentration Analysis Tool`;
2. `Duration Outlier Analysis Tool`;
3. `Reference Pattern Analysis Tool`.

Detailed semantics: `20_alert_analytical_tools.md`.

### 12.4. Guided but not taxonomic reasoning

Agentът трябва да прегледа:

- occurrence activity и reference comparisons;
- recurrence/repeated occurrences;
- duration/prolonged alerts;
- active vs resolved records;
- provider priority/severity, когато е налична;
- title/description semantic content;
- други директно evidence-grounded patterns, ако са ясно видими.

Checklist-ът не налага задължителни finding categories.

### 12.5. No clustering / no inference of missing data

Agentът не трябва да:

- semantic cluster-ва records в измислени групи;
- infer-ва status при липсваща информация;
- infer-ва severity/priority;
- дописва липсващо description;
- предполага причина за alert;
- прави root-cause diagnosis;
- разширява observational scope;
- използва metrics/logs/RAG;
- използва optional tool за scope expansion или нов provider fetch.

## 13. Alert findings

### 13.1. Contract

```yaml
findings:
  - id: af_1
    statement: "..."
    evidence_refs:
      - alerts.ALERT-1234
      - duration_statistics.max_seconds
```

Не са задължителни:

```text
type
category
severity
confidence
```

### 13.2. Semantics

Finding трябва да е descriptive и Lens-local.

Допустимо:

```text
Occurrence activity is higher than the configured 1d reference.
An active alert has remained unresolved for a prolonged duration.
High provider-priority alert records are present in the current window.
```

Недопустимо:

```text
The pump is failing.
The database is overloaded because of memory pressure.
Maintenance must be performed.
```

Causal/system-level interpretation принадлежи на `Observation Reasoning Agent`.

### 13.3. Empty findings

`findings` може да е празен списък дори когато `record_count > 0`, ако няма смислен нетривиален descriptive finding.

Няма максимален брой findings в MVP, но agentът трябва да merge/deduplicate силно припокриващи се conclusions.

### 13.4. Evidence refs

Всеки `evidence_ref` трябва да може да се resolve-не към реално съществуващ елемент от същия `AlertAnalysisResult`. Успешните optional tool outputs не се persist-ват като отделни sections; те служат като transient evidence за формиране на finding. Finding-ът трябва да реферира underlying persisted records/aggregates/comparisons, когато е възможно. Exact mapping за findings, които са derived от optional analysis, остава Open за contract design.

Точният canonical URI/path syntax остава implementation decision; dotted paths са примерна форма.

## 14. Overall importance

Има една обща оценка за целия `Alert LensRun`:

```text
none | low | moderate | high | critical
```

Semantics:

```text
none -> само при успешно установен record_count = 0
low/moderate/high/critical -> при record_count > 0
```

`Alert Analysis Agent` няма право да връща `none`, когато има current records.

`overall_importance` е отделно от provider-specific priority/severity и не е mapping между provider vocabularies.

Не се добавя `rationale` field за MVP.

Findings и importance са свързани, но не са механично зависими:

```yaml
findings: []
overall_importance: moderate
```

е валидно, ако общото evidence подкрепя оценката, но няма отделен нетривиален finding.

## 15. AlertAnalysisResult

`AlertAnalysisResult` е structured, versioned, persistable analytical artifact за `completed` и `partial` Alert LensRun.

Common envelope:

```yaml
alert_analysis_result:
  schema_version: "1.0"

  identity:
    observation_id: ...
    observation_run_id: ...
    lens_id: ...
    lens_run_id: ...

  lens_type: alert
  status: completed

  analysis_timestamp: "..."
  analysis_window:
    start: "..."
    end: "..."

  provenance:
    source_provider: jira_track_and_release
    generated_at: "..."

  # type-specific payload follows
```

`analysis_timestamp` и `provenance.generated_at` са различни понятия:

- `analysis_timestamp` фиксира semantics на анализа и active duration;
- `generated_at` е технически момент на създаване на artifact-а.

Detailed schema е в `15_alert_analysis_result_contract.md`.

## 16. Status, partial и failure semantics

### 16.1. Usable result

```text
completed -> mandatory result complete
partial   -> mandatory result usable; supplementary/reference evidence incomplete
failed    -> no usable AlertAnalysisResult
```

### 16.2. Accepted outcomes

```text
current provider query fails / timeout      -> failed
all returned current records invalid         -> failed
normalization leaves no usable current data -> failed
deterministic analyzer fails                -> failed
required agent fails / timeout              -> failed

some current records invalid, usable remain -> partial
one/more reference queries fail             -> partial
all reference queries fail                  -> partial
reference timeout                            -> partial
optional analytical tool failed / timeout      -> continue, status unchanged by itself
```

Invalid current records се drop-ват от analytical input, но се логват operationally.

Ако rejected records пречат надеждно да се заключи „няма current alert activity“, zero-alert fast path не се използва.

### 16.3. Structured reason

`partial` и failed LensRun използват една primary structured причина:

```yaml
reason:
  code: reference_unavailable
  component: reference_period_analysis   # optional
```

Примерен малък vocabulary:

```text
reference_unavailable
invalid_records
current_query_failed
current_query_timeout
deterministic_analysis_failed
agent_failed
agent_timeout
```

Ако едновременно възникнат повече от една partial причина, exact precedence policy остава Open; detailed technical diagnostics са в logs.

## 17. Failed result и persistence

За Alert pipeline:

```text
completed -> LensRun + AlertAnalysisResult persisted
partial   -> LensRun + AlertAnalysisResult persisted
failed    -> LensRun(status/reason) + operational logs; NO AlertAnalysisResult
```

При failed path:

- `AlertAnalysisResult Builder / Validator` не се изпълнява;
- не се persist-ва type-specific analytical artifact;
- downstream Observation Reasoning получава unavailable Lens metadata от `LensRun`, а не празен Alert result.

## 18. Result Builder ownership

`Alert Analysis Agent` връща само:

```text
findings
+
overall_importance
```

Финалният `AlertAnalysisResult` се сглобява детерминистично от `AlertAnalysisResult Builder / Validator`.

Builder-ът:

- добавя common envelope;
- комбинира normalized current records + deterministic evidence + agent output;
- валидира controlled vocabularies;
- валидира evidence_refs;
- прилага zero-record output rules;
- създава final result artifact.

Builder-ът не прави alert reasoning и не persist-ва сам.

## 19. Persistence boundary

След Builder има отделна deterministic pipeline стъпка:

```text
AlertAnalysisResult Builder / Validator
       ↓
Persist AlertAnalysisResult
       ↓
Persistent storage
```

Не се въвежда отделен `AlertRepository` в архитектурния MVP design. Database/storage abstraction остава implementation decision.

## 20. Downstream boundary

`AlertAnalysisResult` влиза в:

```text
Observation Reasoning Agent
```

като usable Lens evidence.

Alert pipeline не участва в deterministic metric `Relationship Evaluator` за MVP и не прави cross-lens reasoning.

Observation Reasoning е собственикът на correlation между:

```text
MetricAnalysisResult[]
AlertAnalysisResult[]
LogAnalysisResult[]
RelationshipEvaluation[]
```

## 21. Scalability decision за MVP

За MVP няма truncation/limit върху броя normalized current alert records в `AlertAnalysisResult`.

Това е съзнателно опростяване. Future scalability policy може да въведе truncation, pagination, ranked evidence или compact record projection след измерване на реални обеми.

## 22. Нормативен runtime flow

```mermaid
flowchart TD
    LR[Alert LensRun] --> PA[Alert Provider Adapter / provider access]
    PA --> FC[Fetch current alerts]
    FC --> NV[Normalize + validate current records]
    NV --> FR[Fetch configured reference periods]
    FR --> DA[Deterministic Alert Analyzer]
    DA --> MT[Mandatory analytical tools/capabilities]
    MT --> DA
    DA --> Z{record_count = 0?}
    Z -->|Yes| SKIP[Skip Alert Analysis Agent]
    SKIP --> ZERO[findings=[]; overall_importance=none]
    Z -->|No| AA[Alert Analysis Agent]
    AA -->|0..10 optional calls| OT[Allowed optional analytical tool]
    OT --> AA
    AA --> AO[findings + overall_importance]
    ZERO --> B[AlertAnalysisResult Builder / Validator]
    AO --> B
    B --> P[Persist AlertAnalysisResult]
    P --> R[AlertAnalysisResult]
```

Failure/partial behavior е разгърнато в `14_alerts_analysis_pipeline_detailed.md`.

## 23. Non-responsibilities

Alerts pipeline не трябва да:

- анализира metrics/logs;
- изпълнява system-level diagnosis;
- използва RAG/external knowledge;
- създава Observation-level findings/hypotheses;
- участва в metric Relationship rule evaluation;
- променя Alert Lens scope/runtime window;
- infer-ва missing provider data;
- прави provider-independent severity normalization;
- изпълнява semantic clustering в MVP;
- позволява optional tools да разширяват selector/time/data scope.

## 24. Accepted decisions / ADR range

Текущите Alert решения са консолидирани в `03_ADR_log.md`, ADR-089..ADR-132.

## 25. Open decisions

Остават Open главно implementation/configuration details:

- exact serialized Alert Lens schema;
- exact Jira Track and Release field mapping и adapter interface;
- exact canonical `evidence_refs` syntax и exact mapping при finding, derived от transient optional tool evidence;
- precedence на primary `reason`, ако има няколко partial causes;
- retry/timeout values;
- future volume/truncation policy.

## 26. Deferred extensions

Извън MVP:

- semantic grouping/clustering;
- burst/flapping/escalation analysis;
- richer historical comparison dimensions;
- provider-independent severity mapping;
- cross-type deterministic Relationships;
- RAG/external-knowledge tool use inside Alert Analysis Agent;
- autonomous query rewrite/validation;
- point-in-time reconstruction of historical alert lifecycle;
- record truncation/ranking policies.

## 27. Информативна литературна съгласуваност

Този design е архитектурно съвместим с няколко направления от литературата, налична в проекта, без те да се използват като нормативен източник:

- `2511.03023v1-multi-agent-design-principles-from-llm-based-data-analysis-framework.pdf` — подкрепя decomposition към specialized agents, focused contexts и validation на отделни pipeline stages;
- `A_Distributed_Multi-Agent_Framework_for_Resilience_Enhancement_in_Cyber-Physical_Systems.pdf` — разглежда hierarchical/distributed multi-agent separation на specific tasks и system/context awareness в CPS;
- `2511.18258v1_Hybrid_Agentic_AI_and_Multi-Agent_Systems_in_Smart_Manufacturing.pdf` — подкрепя hybrid layered architecture, в която LLM reasoning се комбинира с deterministic/rule-based specialized components;
- `ai-07-00051.pdf` — показва industrial hybrid pattern, при който deterministic supervision/evidence и LLM-based analytics се разделят за надеждност и explainability;
- `electronics-10-00763-v2.pdf` — подкрепя component-based single-responsibility decomposition и loosely coupled integration в индустриални системи.

Конкретните Alert Lens semantics, contracts и failure rules са решения на настоящия проект.

## 28. Related documents

- `01_observation_lens_concept.md`
- `02_architecture_principles_and_runtime.md`
- `04_pipeline_and_agent_concepts.md`
- `06_runtime_contracts_and_execution_semantics.md`
- `14_alerts_analysis_pipeline_detailed.md`
- `15_alert_analysis_result_contract.md`
- `16_alert_analysis_agent.md`
- `17_deterministic_alert_analyzer.md`
- `18_alert_analysis_result_builder.md`
- `19_alert_provider_adapter.md`
- `20_alert_analytical_tools.md`
- `03_ADR_log.md`
