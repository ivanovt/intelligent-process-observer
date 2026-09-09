# Alerts Analysis Pipeline — подробна архитектура, компоненти, взаимодействия и процеси

**Проект:** „Интелигентна мулти-агентна система за откриване на аномалии и супервизия на технологични процеси“  
**Статус:** Работна нормативна референция за MVP  
**Версия:** 2.1
**Актуализирано:** 2026-09-09

## 1. Предназначение

Този документ описва подробно `Alerts Analysis Pipeline` като самостоятелен specialized Lens pipeline: entry/exit contract, internal stages, deterministic и agentic components, data artifacts, decision points, failure/partial propagation, persistence boundary и integration към Observation workflow-а.

Документът е предназначен да служи като техническа база за архитектурната и проектната част на дипломната работа.

## 2. Архитектурна роля

Pipeline-ът има една основна отговорност:

> Да преобразува bounded provider alert records за конкретен `Alert LensRun` в проверим, структуриран и достатъчно компактен `AlertAnalysisResult`, без да прави system-level diagnosis или cross-lens reasoning.

Control plane остава в `Observation Orchestrator`; domain-local alert processing е encapsulated в този pipeline.

## 3. Entry и exit

### 3.1. Entry

```text
Alert LensRun
```

LensRun осигурява:

- identity на Observation/Lens execution;
- `analysis_window`;
- fixed `analysis_timestamp`;
- reference-period configuration;
- link към immutable Alert Lens definition.

### 3.2. Exit

Успешен/partial outcome:

```text
AlertAnalysisResult
```

Failure outcome:

```text
LensRun.status = failed
LensRun.reason = structured reason
NO AlertAnalysisResult
```

## 4. Component map

```text
Alert LensRun
   ↓
Alert Provider Adapter
   ↓
Mandatory Fetch Current Alerts
   ↓
Mandatory Normalize / Validate Records
   ↓
Mandatory Fetch Reference Periods
   ↓
Deterministic Alert Analyzer
   ↕
Mandatory analytical tools/capabilities
   ↓
record_count == 0 ?
   ├─ yes -> skip agent -> fixed zero-record analytical output
   └─ no  -> Alert Analysis Agent
               ↕ 0..10 calls
            Optional analytical tools
               ↓
            findings + overall_importance
   ↓
AlertAnalysisResult Builder / Validator
   ↓
Persist AlertAnalysisResult
   ↓
AlertAnalysisResult
```

## 5. Stage 1 — Resolve immutable execution context

Pipeline-ът приема вече създаден `LensRun`; не променя Observation/Lens scope.

Фиксирани за run-а са:

```text
observation_id
observation_run_id
lens_id
lens_run_id
analysis_window
analysis_timestamp
source/provider
selector/query
reference offsets
```

Агент или downstream stage няма право да разширява този scope.

## 6. Stage 2 — Alert Provider Adapter

`Alert Provider Adapter` encapsulate-ва provider-specific access и mapping semantics.

### Responsibilities

- изпълнява provider-native selector;
- прилага analysis/reference time-window semantics;
- връща provider records за normalization;
- map-ва provider fields към canonical alert fields;
- запазва provider status и importance value за traceability.

### Non-responsibilities

- не прави analytical findings;
- не оценява overall importance;
- не нормализира global severity vocabulary;
- не променя provider query според собствена преценка;
- не прави cross-provider correlation.

Текущ MVP provider: `Jira Track and Release`.

## 7. Stage 3 — Fetch current alerts

Current query използва Lens selector-а и `analysis_window`.

Membership semantics:

```text
started_at < window.end
AND
(ended_at is null OR ended_at > window.start)
```

### Failure

```text
provider query error   -> LensRun failed / current_query_failed
provider query timeout -> LensRun failed / current_query_timeout
```

Failure приключва pipeline-а; няма `AlertAnalysisResult`.

## 8. Stage 4 — Normalize and validate current records

Provider data се преобразува към canonical current records.

### Validation requirements

Record е usable само ако може надеждно да се определи lifecycle membership и duration.

Минимално:

```text
id present
title present
started_at valid
ended_at null OR valid
ended_at >= started_at when present
```

### Invalid-record behavior

```text
some records invalid + usable remain -> continue, final status partial
all current returned records invalid -> failed
```

Rejected records не се включват в analytical evidence и result, но се логват operationally.

Primary partial reason за този случай:

```yaml
reason:
  code: invalid_records
```

## 9. Stage 5 — Fetch reference periods

Всеки configured reference се fetch-ва със:

- същия Lens selector;
- същата window duration;
- offset назад във времето.

Reference periods са supplementary analysis. Failure на един или всички reference queries не прави current analysis unusable.

```text
reference query success -> use comparison evidence
reference query failure -> omit comparison, mark partial
```

Primary reason:

```yaml
reason:
  code: reference_unavailable
  component: reference_period_analysis   # optional
```

Historical records не се предават към agent/result.

## 10. Stage 6 — Deterministic Alert Analyzer

Този component гарантира и координира формирането на всички mandatory measurable quantities. Вътрешната реализация използва тесни deterministic analytical tools/capabilities; pipeline-ът гарантира изпълнението им и те не са subject на LLM избор.

### Inputs

```text
usable normalized current records
usable normalized reference records/results
analysis_timestamp
```

### Outputs

```text
alert_activity
status_distribution
duration_statistics [when record_count>0]
provider_importance_distribution [when available]
occurrence comparisons [for successful references]
```

### Core algorithms

#### Effective occurrence

```text
record.occurrence_count present -> use value
record.occurrence_count missing -> use 1
```

#### Current activity

```text
record_count = number of usable current records
occurrence_count = sum(effective_occurrence_count)
```

#### Status distribution

Counts records, not occurrences.

#### Duration

```text
resolved: ended_at - started_at
active:   analysis_timestamp - started_at
```

Serialization uses seconds.

#### Reference comparison

```text
delta = current_occurrence_count - reference_occurrence_count
```

```text
delta > 0 -> increased
delta < 0 -> decreased
delta = 0 -> unchanged
```

### Mandatory analytical tool model

Логическият mandatory набор покрива най-малко:

```text
activity counting
status analysis
duration analysis
provider importance aggregation
reference occurrence comparison
```

Тези capabilities могат implementation-level да бъдат отделни tools/services/functions, но owner на mandatory evidence остава `Deterministic Alert Analyzer`.

### Failure

Analyzer или mandatory analytical tool failure означава, че mandatory evidence не може да бъде произведено:

```text
LensRun -> failed
reason.code = deterministic_analysis_failed
```

No Builder/Result/Persist path follows.

## 11. Stage 7 — Zero-record decision

Decision:

```text
record_count == 0 ?
```

Това е единственият trigger за zero-alert fast path.

### Yes path

```text
skip Alert Analysis Agent
findings = []
overall_importance = none
```

Reference comparisons вече са опитани и могат да присъстват.

### No path

`Alert Analysis Agent` е mandatory analytical stage.

`occurrence_count == 0` не е fast-path criterion, ако `record_count > 0`.

## 12. Stage 8 — Prepare Agent input

Pipeline-ът подава само bounded, source-agnostic evidence и вече наличните normalized datasets, върху които optional tools могат да работят:

```text
lens_context:
  name
  description

current normalized alert records
current deterministic aggregates
successful reference comparisons
successful reference comparisons; optional tool runtime може при нужда да използва bounded internal handle към already-fetched configured reference data, без raw reference records да се подават в LLM context
```

Не се подава/разрешава:

```text
нов provider-native query за agent/tool scope expansion
raw provider payload към LLM
metrics/logs/relationships
RAG/external knowledge
unconfigured time/reference scope
```

## 13. Stage 9 — Alert Analysis Agent + bounded optional tool loop

Agentът произвежда:

```text
findings[]
overall_importance
```

Той не сглобява крайния result contract.

### Reasoning boundary

Allowed:

- descriptive Lens-local patterns;
- recurrence/activity interpretation;
- prolonged active/resolved lifecycle observations;
- provider-priority observations;
- semantic interpretation на title/description, grounded в records;
- 0..10 calls към allowed optional alert analytical tools.

Forbidden:

- root cause;
- recommendation;
- cross-lens correlation;
- RAG/external knowledge;
- clustering;
- missing-data inference;
- provider fetch за нови alerts;
- selector/window/reference/scope expansion.

### Optional tool execution semantics

```text
max_optional_tool_calls = 10
max_model_requests = 11
same tool may be invoked repeatedly
all attempts count: success | failed | timeout | not_applicable
```

След clean десетия admitted tool attempt остава най-много един completion-only model
request. Response 11 не може да стартира tool; такъв call fail-ва policy преди
execution/ledger append и няма request 12. Multi-call response използва remaining
capacity в response order; excess call terminates agent path без continuation.

Minimal MVP registry:

```text
Recurrence Concentration Analysis Tool
Duration Outlier Analysis Tool
Reference Pattern Analysis Tool
```

Successful tool outputs са transient analytical evidence за agent reasoning/findings и не се persist-ват като отделни result sections.

```text
optional tool failed/timeout
-> log technical details
-> optional call budget consumed
-> agent continues with available evidence
-> LensRun status unchanged by this failure alone
```

`not_applicable` е normal tool outcome, не failure.

### Agent failure

```text
agent error   -> failed / agent_failed
agent timeout -> failed / agent_timeout
```

No partial result се създава, защото при `record_count > 0` agent output остава mandatory.

## 14. Stage 10 — AlertAnalysisResult Builder / Validator

Builder е deterministic contract-owner.

### Inputs

```text
LensRun metadata
normalized current records
deterministic evidence
pipeline partial flags/reason
agent output OR zero-record fixed output
minimal failed/timeout optional-tool trace when present
minimal provenance
```

### Responsibilities

- assembly на common envelope;
- schema validation;
- controlled vocabulary validation;
- `overall_importance` invariant validation;
- `findings` presence validation;
- `evidence_refs` resolution validation;
- omission на unavailable optional sections;
- final status `completed|partial`;
- optional `optional_tool_execution` само при реални optional `failed|timeout` calls.

### Non-responsibilities

- няма LLM;
- няма provider query;
- няма reasoning;
- няма persistence.

Ако result contract не може да бъде построен/валидирано изпълнен, няма usable result и LensRun трябва да приключи failed според общата lifecycle semantics.

## 15. Stage 11 — Persist AlertAnalysisResult

Persistence е отделна deterministic стъпка след Builder.

```text
Builder -> AlertAnalysisResult -> Persist stage -> storage
```

Точният repository/database/storage technology не е фиксиран.

Persist се изпълнява само за:

```text
completed
partial
```

При failed path няма `AlertAnalysisResult` за persistence.

## 16. Main flow diagram

```mermaid
flowchart TD
    A([Alert LensRun]) --> B[Alert Provider Adapter]
    B --> C[Mandatory current fetch]
    C --> D[Mandatory normalize + validate]
    D --> E[Mandatory configured reference fetch]
    E --> F[Deterministic Alert Analyzer]
    F --> MT[Mandatory analytical tools / capabilities]
    MT --> F
    F --> G{record_count = 0?}
    G -->|Да| H[Пропускане на Alert Analysis Agent]
    H --> I[findings=[]; overall_importance=none]
    G -->|Не| J[Подготовка на bounded agent input]
    J --> K[Alert Analysis Agent]
    K -->|0..10 optional calls| OT[Allowed optional analytical tool]
    OT --> K
    K --> L[findings + overall_importance]
    I --> M[AlertAnalysisResult Builder / Validator]
    L --> M
    M --> N[Persist AlertAnalysisResult]
    N --> O([AlertAnalysisResult])
```

## 17. Failure и partial flow

```mermaid
flowchart TD
    A([Alert LensRun]) --> B[Fetch current alerts]
    B --> C{Current query successful?}
    C -->|Не| F1([LensRun failed\ncurrent_query_failed / timeout])
    C -->|Да| D[Normalize + validate records]
    D --> E{Usable current data?}
    E -->|Не| F2([LensRun failed\ninvalid_records])
    E -->|Да| R[Fetch reference periods]
    R --> RQ{All configured references available?}
    RQ -->|Не| RP[Mark partial\nreference_unavailable]
    RQ -->|Да| DA[Deterministic Alert Analyzer]
    RP --> DA
    DA --> DS{Analyzer successful?}
    DS -->|Не| F3([LensRun failed\ndeterministic_analysis_failed])
    DS -->|Да| Z{record_count = 0?}
    Z -->|Да| ZERO[findings=[]\noverall_importance=none]
    Z -->|Не| AG[Alert Analysis Agent]
    AG --> OT[0..10 optional tool calls as needed]
    OT --> AS{Agent successful?}
    AS -->|Не| F4([LensRun failed\nagent_failed / agent_timeout])
    AS -->|Да| AO[findings + overall_importance]
    ZERO --> BLD[AlertAnalysisResult Builder / Validator]
    AO --> BLD
    BLD --> P[Persist AlertAnalysisResult]
    P --> OK([completed / partial AlertAnalysisResult])
```

Забележка: `some invalid current records + usable remain` също маркира `partial` с `invalid_records`, без да спира pipeline-а. Optional analytical tool `failed|timeout` не влиза в този failure/partial propagation: agentът продължава и call-ът се записва минимално в result само като execution trace.

## 18. Stage responsibility matrix

| Stage / component | Тип | Основен вход | Основен изход | При failure |
|---|---|---|---|---|
| Alert Provider Adapter | deterministic integration component | Lens selector + time scope | provider/canonical records | current/reference semantics според caller stage |
| Fetch Current Alerts | deterministic stage | LensRun | provider records | failed |
| Normalize / Validate | deterministic stage | provider records | usable canonical records + rejected-record log | partial или failed |
| Fetch Reference Periods | deterministic stage | offsets + selector | reference activity inputs | partial |
| Deterministic Alert Analyzer | deterministic analytical component/coordinator | normalized records | structured measurable evidence чрез mandatory analytical tools/capabilities | failed |
| Zero-record gate | deterministic decision | record_count | agent skip / agent invocation | n/a |
| Alert Analysis Agent | bounded LLM agent | current records + mandatory evidence | findings + overall_importance; optional tool loop 0..10 | failed само при agent failure/timeout |
| Optional Alert Analytical Tool | deterministic bounded tool | already-available Alert Lens data/evidence | transient analytical evidence / not_applicable | non-fatal; agent continues |
| AlertAnalysisResult Builder / Validator | deterministic component | all valid outputs | final contract | failed if contract unusable |
| Persist AlertAnalysisResult | deterministic infrastructure stage | completed/partial result | durable artifact | implementation-specific runtime failure policy |

Persistence transport/retry semantics са implementation details и не трябва да се смесват с analytical classification.

## 19. Status propagation

### completed

Всички mandatory stages са успешни и няма известна supplementary incompleteness.

### partial

Mandatory analytical result е usable, но има bounded incompleteness, например:

```text
reference_unavailable
invalid_records (some dropped, usable remain)
```

### failed

Няма usable analytical result.

Failure не означава „няма alerts“. Optional analytical tool failure/timeout сам по себе си не е `partial` или `failed`.

## 20. Primary reason semantics

Final usable `partial` result пази една primary structured причина:

```yaml
reason:
  code: reference_unavailable
  component: reference_period_analysis
```

Operational logs могат да пазят повече технически details. Ако има едновременно няколко partial causes, exact precedence rule още не е фиксиран.

## 21. Current record handling

### All valid

```text
status unaffected
```

### Some invalid

```text
log rejected records
continue with usable subset
result -> partial / invalid_records
```

### All invalid

```text
LensRun -> failed
NO AlertAnalysisResult
```

## 22. Reference handling

Reference periods са независими supplementary queries.

```text
1d success, 7d success -> both comparisons included
1d success, 7d failure -> only 1d comparison, partial
all fail              -> no valid comparison entries, partial
```

Не се записват unavailable placeholder comparison objects.

## 23. Data passed to Observation Reasoning

Observation Reasoning получава `AlertAnalysisResult` само ако е usable (`completed|partial`).

Failed Alert Lens се представя чрез:

```yaml
unavailable_lenses:
  - lens_id: ...
    type: alert
    reason:
      code: agent_timeout
```

Reasoning Agent не получава operational logs или raw provider data.

## 24. Traceability chain

```text
Alert Lens definition
   ↓
LensRun identity + window
   ↓
normalized current alert record ids
   ↓
deterministic evidence
   ↓
Alert finding evidence_refs
   ↓
AlertAnalysisResult
   ↓
Observation finding evidence_refs
```

Това позволява thesis/implementation design да демонстрира provenance без free-text agent chains.

## 25. Testable MVP scenarios

Минималният integration test matrix трябва да включва:

1. successful current query, zero records;
2. successful current query, records, all references available;
3. one reference unavailable -> partial;
4. all references unavailable -> partial;
5. some invalid current records + usable remain -> partial;
6. all current records invalid -> failed;
7. current query failure -> failed;
8. current query timeout -> failed;
9. deterministic analyzer failure -> failed;
10. agent failure -> failed;
11. agent timeout -> failed;
12. evidence_ref not resolvable -> builder rejects result;
13. agent returns `overall_importance=none` with records -> builder rejects output;
14. `record_count=0` -> agent is not invoked;
15. active alert duration uses fixed `analysis_timestamp`;
16. optional duration-outlier tool with <8 valid durations -> `not_applicable`, no status change;
17. optional tool timeout -> agent continues, call counts toward max 10, minimal unsuccessful trace may be serialized;
18. same optional tool invoked repeatedly -> allowed while total attempts <=10;
19. ten sequential optional tools -> at most one completion-only model request, total model requests <=11;
20. tool call in model response 11 -> policy failure before execution/ledger append, no request 12;
21. multi-call response crosses remaining capacity -> in-capacity calls preserve response order, first excess call fails policy without continuation.

## 26. Observability of the pipeline itself

Operational observability може да пази:

- stage start/end duration;
- query latency;
- number of returned/invalid/usable records;
- reference availability;
- agent invocation/timeout;
- optional tool invocation count, tool name, status and latency;
- builder validation errors;
- persistence outcome.

Тази telemetry не е част от `AlertAnalysisResult` и не се подава към Observation Reasoning.

## 27. Implementation boundaries still open

- concrete orchestration framework;
- adapter/repository interfaces;
- retry/backoff values;
- timeout values;
- storage technology;
- exact schema validator technology;
- exact prompt serialization;
- exact optional tool invocation/result serialization internal to agent runtime;
- exact evidence-ref syntax;
- volume/truncation strategy beyond MVP.

## 28. Related documents

- `13_alert_lens_and_analysis_concept.md`
- `15_alert_analysis_result_contract.md`
- `16_alert_analysis_agent.md`
- `17_deterministic_alert_analyzer.md`
- `18_alert_analysis_result_builder.md`
- `19_alert_provider_adapter.md`
- `20_alert_analytical_tools.md`
- `02_architecture_principles_and_runtime.md`
- `06_runtime_contracts_and_execution_semantics.md`
