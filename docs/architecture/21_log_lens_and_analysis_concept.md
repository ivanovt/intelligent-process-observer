# Log Lens и Logs Analysis — концепция и нормативен MVP дизайн

**Проект:** „Интелигентна мулти-агентна система за откриване на аномалии и супервизия на технологични процеси“  
**Статус:** Работна нормативна референция за MVP  
**Версия:** 1.0  
**Актуализирано:** 2026-08-19

## 1. Цел

Този документ фиксира концепцията за `Log Lens`, аналитичната семантика на `Logs Analysis Pipeline`, границите между deterministic обработка, bounded agentic reasoning и knowledge retrieval, както и основните result/failure правила за MVP.

`Logs Analysis Pipeline` преобразува bounded перспектива към log source в компактен, структуриран и проверим `LogAnalysisResult`, който може да бъде използван downstream от `Observation Reasoning Agent` без предаване на целия raw log corpus.

## 2. Място в Observation workflow-а

```text
ObservationRun
   ↓
LensRun fan-out
   ├─ Metric LensRun -> Metrics Analysis Pipeline -> MetricAnalysisResult
   ├─ Alert LensRun  -> Alerts Analysis Pipeline  -> AlertAnalysisResult
   └─ Log LensRun    -> Logs Analysis Pipeline    -> LogAnalysisResult
                                                       ↓
                                                    strict JOIN
                                                       ↓
                                            Observation Reasoning
```

`Observation Orchestrator` управлява lifecycle, dispatch, concurrency и JOIN, но не познава Loki-specific query semantics, template extraction или вътрешните analytical stages на Logs pipeline-а.

## 3. Log Lens

`Log Lens` е bounded перспектива към определен набор от логове. За MVP scope-ът се определя чрез provider-native selector, а `LensRun` определя времевия контекст.

```text
selector -> кои логове
LensRun  -> кога се наблюдават
```

Примерна ненормативна конфигурация:

```yaml
log_lens:
  id: database_logs
  type: log
  source: loki
  selector:
    query: '{app="database"}'
  reference_periods:
    - offset: 1d
    - offset: 7d
```

Точната serialized schema остава implementation decision.

## 4. Time membership

Log record е point event и принадлежи към analysis/reference window, ако:

```text
window.start <= log.timestamp < window.end
```

Current и reference periods са независими времеви извличания върху един и същ selector.

## 5. Основен архитектурен принцип

Logs pipeline използва **hybrid deterministic/agentic model**:

```text
immutable Log Lens scope
        ↓
provider acquisition
        ↓
aggregate evidence + bounded textual content
        ↓
parse / normalize / validate / sanitize
        ↓
deterministic analytical evidence
        ↓
bounded Log Analysis Agent
        ↕ optional deterministic analytical tools
        ↕ optional bounded knowledge retrieval
        ↓
findings + knowledge annotations
        ↓
deterministic LogAnalysisResult Builder / Validator
```

Pipeline-ът гарантира lifecycle correctness и mandatory evidence. Agentът добавя адаптивна интерпретация, без да разширява observational data scope-а.

## 6. Aggregate evidence и bounded textual content

Pipeline-ът не предполага, че целият log corpus се materialize-ва локално.

Използват се две логически категории данни:

```text
Aggregate Log Evidence
Bounded Log Content
```

### 6.1. Aggregate Log Evidence

Използва се за количествени характеристики, които могат да бъдат изчислени чрез provider-side aggregation или друго bounded изчисление, например:

```text
log count
logging rate
level counts
reference-period counts
```

### 6.2. Bounded Log Content

Текстовите записи се извличат само до необходимия обем за content-dependent анализи, например template extraction. При голям volume template evidence трябва да носи explicit coverage semantics и да не се представя като абсолютна характеристика на целия corpus.

Точният limit/sampling policy остава Open.

## 7. Parsing, normalization, validation и sanitization

Log formats са heterogeneous. Level или други полета могат да бъдат labels, JSON/logfmt fields или да липсват. Parsing semantics се определят детерминистично чрез конфигурация/provider mapping; LLM не infer-ва log level от свободния текст.

Canonical level vocabulary:

```text
error | warning | info | debug | trace | unknown
```

Преди text content да достигне до LLM-visible context се прилага bounded sanitization/redaction boundary. Log text се третира като **данни, не инструкции**.

Generic deduplication не се извършва по подразбиране, защото повторяемостта може да е аналитично значима.

## 8. Mandatory deterministic evidence

Минималното usable current ядро съдържа:

```text
log activity
logging rate
level distribution
error-level activity
```

Примерна концептуална форма:

```yaml
log_activity:
  record_count: 1240
  logs_per_minute: 20.67

level_distribution:
  error: 28
  warning: 47
  info: 1035
  debug: 40
  trace: 0
  unknown: 90

error_level_activity:
  error_level_count: 28
  known_level_count: 1150
  level_coverage: 0.927
  error_level_rate: 0.0243
```

Използва се `error_level_count`, а не `error_count`, защото evidence описва записи с normalized level `error`, а не абсолютния брой реални software/process faults.

## 9. Template analysis

Template extraction е deterministic supplementary analysis. MVP не използва semantic clustering, embeddings или LLM template extraction.

Пример:

```text
Connection to node 10.0.0.1 failed after 5100 ms
Connection to node 10.0.0.7 failed after 4980 ms
        ↓
Connection to node <IP> failed after <NUM> ms
```

Template extraction algorithm и normalization rules трябва да бъдат versioned в provenance.

За bounded result projection се предпочитат:

```text
top overall templates
top error-level templates
```

а не само глобален Top-N, който може да скрие редки, но важни error-level patterns.

## 10. Reference periods

Log Lens поддържа `0..N` configured reference periods. Всеки reference window има същата продължителност като current window, използва същия selector и е изместен назад с configured offset.

MVP core comparison dimensions са:

```text
log_count
error_level_count
```

Controlled direction:

```text
increased | decreased | unchanged
```

Template differences остават supplementary/optional analysis.

Unavailable reference period води до `partial`, ако current core остава usable.

## 11. Без persisted Log history analysis в MVP

Persisted `LogAnalysisResult`-и могат да образуват история на изпълненията, но Logs pipeline не изпълнява отделен persisted-history analyzer за MVP.

Temporal context е:

```text
current + configured reference periods
```

## 12. Log Analysis Agent

`Log Analysis Agent` е bounded Lens-local reasoning agent. Той работи върху structured Log Lens evidence и bounded template content, а не върху целия raw/normalized corpus.

Agentът може да:

- интерпретира log activity и reference differences;
- разглежда error-level activity и template evidence;
- използва предварително разрешени optional analytical tools;
- формира Lens-local `findings`;
- определя Lens-local `overall_importance`;
- използва bounded knowledge retrieval, когато вече открит finding/template/error code изисква domain explanation.

Agentът не може да:

- променя selector/time window/reference configuration;
- fetch-ва нови logs извън вече фиксирания scope;
- извлича metrics или alerts;
- анализира Relationships;
- прави cross-Lens/system-level diagnosis;
- генерира recommendations.

## 13. Zero-log semantics

`record_count=0` е валидно analytical observation, не failure.

```text
current=0 + references show no activity
-> agent може да бъде пропуснат
-> findings=[] / overall_importance=none

current=0 + references show prior activity
-> invoke agent
-> Lens-local finding за липса на текуща активност спрямо reference evidence

current=0 + reference evidence unavailable
-> не се прави causal интерпретация
```

Log Agent не заключава, че application е спрял или telemetry path е повреден; такива explanations са system-level hypotheses.

## 14. Optional analytical tools

Минималният MVP registry е:

1. `Bucketed Log Rate Analysis`;
2. `Template Reference Difference Analysis`;
3. `Error-Level Template Concentration Analysis`.

Budget:

```text
max_optional_tool_calls = 3
max_calls_per_tool = 1
```

Tools работят само върху вече наличните immutable data/evidence. Те не формират нови Loki queries, които разширяват scope-а.

`failed|timeout` optional tool call е non-fatal best-effort failure и сам по себе си не променя LensRun status.

## 15. Bounded knowledge retrieval в Log Agent

Log Agent може да използва специализирана knowledge retrieval capability за семантично обогатяване на **вече наблюдавано Log Lens evidence**.

Типични retrieval subjects:

```text
specific log template
error code
component-specific message
неясна терминология в log template
```

Retrieval не се използва за откриване на нов observational evidence и не разширява data scope-а.

Budget:

```text
max_log_knowledge_retrieval_calls = 2
```

Последователност:

```text
1. analyze Log evidence
2. form findings
3. freeze findings
4. decide whether domain knowledge is needed
5. optional retrieval #1
6. optional refined retrieval #2
7. form knowledge annotations or finish without them
```

Retrieved knowledge **не може да създава или променя Log findings**.

## 16. Knowledge annotations

RAG-derived interpretation се пази отделно от observational findings.

Концептуален пример:

```yaml
knowledge_annotations:
  - id: log_knowledge_1
    subject:
      template_id: tmpl_17
    statement: >
      Документацията описва съобщението като свързано с липса на
      незабавно достъпна връзка в connection pool.
    supported_by:
      - log_finding_2
    knowledge_refs:
      - source_id: ...
        reference: ...
```

`knowledge_annotations` са **knowledge enrichment**, не observational evidence.

Downstream `Observation Reasoning Agent` не може да ги използва за създаване на Observation findings. Те могат да бъдат използвани като вече retrieved domain knowledge при формиране на hypotheses, ако original `knowledge_refs` се запазят.

## 17. Agent output

Agentът връща bounded contribution:

```text
findings[]
overall_importance
knowledge_annotations[] [optional]
```

`overall_importance` vocabulary:

```text
none | low | moderate | high | critical
```

Това е Lens-local assessment, не system severity.

## 18. Agent failure

Ако agentът failed/timeout, но deterministic current evidence е usable:

```text
Log Agent unavailable + usable deterministic evidence
-> partial LogAnalysisResult
```

`findings=[]`, `overall_importance` липсва и partial reason показва agent failure. Така usable deterministic evidence не се губи поради LLM failure.

## 19. Result/failure semantics

`LogAnalysisResult Builder / Validator` е final deterministic contract owner.

```text
completed | partial -> LogAnalysisResult exists
failed              -> terminal Log LensRun; NO LogAnalysisResult
```

Failed current acquisition, липса на минимално usable current evidence или builder validation failure водят до failed LensRun.

## 20. Downstream boundary

`Observation Reasoning Agent` получава structured `LogAnalysisResult`, но не raw Loki records, raw reference logs или entire normalized corpus.

Log findings са observational Lens evidence. Log `knowledge_annotations` се пренасят като отделен knowledge layer и не са валиден source за Observation findings.

## 21. Deferred

Извън MVP остават:

```text
semantic/embedding log clustering
LLM template extraction
advanced Drain/Spell-style mining
sequence-based log anomaly models
stack-trace semantic analysis
cross-service distributed tracing
causal/root-cause log diagnosis
automatic query expansion
persisted Log History Analyzer
recommendations
```

## 22. Related documents

- `02_architecture_principles_and_runtime.md`
- `04_pipeline_and_agent_concepts.md`
- `06_runtime_contracts_and_execution_semantics.md`
- `22_logs_analysis_pipeline_detailed.md`
- `23_log_analysis_result_contract.md`
- `24_log_analysis_agent.md`
- `25_deterministic_log_analyzer.md`
- `26_log_provider_adapter.md`
- `27_log_analysis_result_builder.md`
- `28_log_analytical_tools_and_knowledge_retrieval.md`
