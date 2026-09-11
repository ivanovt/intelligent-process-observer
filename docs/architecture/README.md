# Архитектурна документация — Master Thesis Architecture Reference

**Проект:** „Интелигентна мулти-агентна система за откриване на аномалии и супервизия на технологични процеси“  
**Статус:** Работна нормативна референция за MVP  
**Версия на пакета:** 6.8
**Актуализирано:** 2026-09-11

## 1. Предназначение

Тази директория е архитектурната референтна база за следващите анализи, диаграми, implementation design и реализация. Тя разделя ясно:

- **концепции** — какви обекти и понятия използва системата;
- **архитектура и runtime** — как се изпълнява Observation workflow-ът;
- **component/agent responsibilities** — кой какво прави и какво изрично не прави;
- **contracts** — какви структурирани артефакти се обменят;
- **ADR** — кои решения са вече приети и защо;
- **open decisions** — какво още не е фиксирано;
- **templates** — как да се добавят следващи concept/component/contract/ADR документи по същия модел;
- **diagrams** — информативни визуални draft артефакти; нормативният източник остава текстовата документация.

Документите са работна нормативна референция за MVP, не финална implementation спецификация.

## 2. Структура

| Файл | Роля |
|---|---|
| `01_observation_lens_concept.md` | Observation/Lens модел, Metric/Alert Lens, времеви перспективи, Relationships. |
| `02_architecture_principles_and_runtime.md` | Главен архитектурен документ за workflow, control/reasoning plane, fan-out/JOIN, Lens pipelines, agents и RAG. |
| `03_ADR_log.md` | Консолидиран регистър на всички приети архитектурни решения. |
| `04_pipeline_and_agent_concepts.md` | Pipeline/Stage/Agent/Tool модел и component boundaries. |
| `05_relationship_evaluator_concept.md` | Детерминистична семантика на Relationship Evaluator. |
| `06_runtime_contracts_and_execution_semantics.md` | Общ execution contract, statuses, usable/terminal, failure propagation и persistence semantics. |
| `07_observation_reasoning_agent.md` | Design contract за Observation Reasoning Agent и bounded knowledge-retrieval loop. |
| `08_observation_analysis_result_contract.md` | Минималният structured `ObservationAnalysisResult` за MVP. |
| `09_report_agent.md` | Роля, вход, граници и Markdown output на Report Agent. |
| `10_open_decisions_and_backlog.md` | Само реално нерешени или deferred въпроси. |
| `11_glossary_and_naming.md` | Терминология и naming conventions. |
| `12_CHANGELOG.md` | История на архитектурния пакет. |
| `13_alert_lens_and_analysis_concept.md` | Пълният приет MVP дизайн на Alert Lens и alert analytical semantics. |
| `14_alerts_analysis_pipeline_detailed.md` | Подробна документация на Alerts pipeline, stages, interactions, failure/partial и процеси. |
| `15_alert_analysis_result_contract.md` | Type-specific contract за `AlertAnalysisResult`. |
| `16_alert_analysis_agent.md` | Подробна component/agent спецификация за `Alert Analysis Agent`. |
| `17_deterministic_alert_analyzer.md` | Подробна спецификация на deterministic alert evidence component. |
| `18_alert_analysis_result_builder.md` | Подробна спецификация на result builder/validator. |
| `19_alert_provider_adapter.md` | Provider abstraction, query/time boundary и normalization ownership. |
| `20_alert_analytical_tools.md` | Hybrid mandatory/optional tool model и минимален MVP registry за Alert Analysis Agent. |
| `21_log_lens_and_analysis_concept.md` | Пълният приет MVP дизайн на Log Lens, log evidence, agent и knowledge boundary. |
| `22_logs_analysis_pipeline_detailed.md` | Подробен Logs pipeline runtime flow и failure/partial semantics. |
| `23_log_analysis_result_contract.md` | Type-specific working contract за `LogAnalysisResult`. |
| `24_log_analysis_agent.md` | Component/agent спецификация за `Log Analysis Agent`, tools и bounded RAG. |
| `25_deterministic_log_analyzer.md` | Mandatory/supplementary deterministic Log evidence semantics. |
| `26_log_provider_adapter.md` | Loki/provider abstraction, aggregate/bounded content acquisition и parsing boundary. |
| `27_log_analysis_result_builder.md` | Deterministic final builder/validator на LogAnalysisResult. |
| `28_log_analytical_tools_and_knowledge_retrieval.md` | Minimal Log analytical tools и отделна bounded knowledge-retrieval capability. |
| `diagrams/` | Информативни draft диаграми от текущата design сесия. |
| `templates/` | Reusable шаблони за бъдещи concept/component/contract/ADR документи. |
| `adr/README.md` | Правило за преминаване към отделни ADR файлове при нужда. |

## 3. Нормативност и приоритет

Използваме следните статуси:

- **Accepted** — решение, което трябва да се следва за MVP;
- **Deferred** — съзнателно изключено от MVP, но допустимо бъдещо разширение;
- **Open** — няма взето решение;
- **Example** — илюстративна форма, която не е задължително окончателна schema форма.

При конфликт между документи приоритетът е:

```text
по-нов ADR
  > актуален concept/architecture/contract документ
  > по-стар пример или работна бележка
```

## 4. Как добавяме ново знание

1. Нова концепция → нов `NN_<concept>.md` по `templates/concept_template.md`.
2. Нов component/agent → документ по `templates/component_template.md`.
3. Нов public result/input contract → документ по `templates/contract_template.md`.
4. Значимо решение/trade-off → нов ADR в `03_ADR_log.md`; при разрастване може да се създаде и отделен файл в `adr/`.
5. Ако решението променя workflow — актуализира се `02_...`.
6. Ако променя execution semantics/contracts — актуализира се `06_...` и съответният type-specific contract.
7. Решен въпрос се премахва от `10_open_decisions_and_backlog.md`.
8. Актуализира се `12_CHANGELOG.md`.

## 5. Архитектурна посока в едно изречение

> Системата използва **детерминистично оркестриран йерархичен workflow**, в който specialized Lens pipelines произвеждат versioned structured evidence, deterministic components поемат проверимите операции, bounded agents добавят локално или system-level reasoning в ясно ограничени boundaries, а отделен Report Agent преобразува structured Observation result в Markdown отчет.

## 6. Metric reference-period архитектурна посока

Metric Lens поддържа `0..N` конфигурируеми `reference_periods`. Всеки reference window има същата продължителност като текущия analysis window и е изместен назад с configured offset, например `1d`, `7d` или `14d`.

Всеки reference period се сравнява независимо с current window по MVP dimensions:

- level;
- trend direction/rate;
- variability.

Reference periods дават periodic/seasonal temporal context, но не са baseline, не са automatic seasonality classification и не заменят persisted Lens history. `history` остава отделна перспектива върху persisted LensRun results.

## 7. Alert-specific архитектурна посока

`Alerts Analysis Pipeline` използва hybrid deterministic/agentic tool model:

```text
Alert Provider Adapter / mandatory acquisition stages
-> current fetch
-> normalize/validate
-> reference fetch
-> Deterministic Alert Analyzer
      -> mandatory analytical tool capabilities
-> zero-record gate
-> Alert Analysis Agent when records exist
      <-> optional analytical tools (bounded loop, max 10 calls)
-> AlertAnalysisResult Builder / Validator
-> persistence
```

Основни boundaries:

- Lens selector определя **which alerts**, LensRun определя **when**;
- current/reference membership използва lifecycle overlap;
- pipeline-ът гарантира всички mandatory acquisition/preparation/analysis operations;
- `Deterministic Alert Analyzer` остава отделен deterministic component и координира mandatory analytical tools/capabilities за counts, status, durations, provider importance и reference comparisons;
- `Alert Analysis Agent` получава mandatory evidence и може да извиква само предварително разрешени optional analytical tools върху вече наличните current/reference данни;
- optional tool loop е bounded до 10 calls; един и същ tool може да бъде извикван многократно и всеки опит се брои към бюджета;
- optional tool failure/timeout е best-effort failure: agentът продължава и LensRun status не се променя само по тази причина;
- минималният optional registry съдържа recurrence concentration, IQR duration-outlier и reference-pattern analysis;
- успешните optional tool outputs са transient evidence за формиране на findings и не се persist-ват като самостоятелни sections;
- no RAG, no metrics/logs, no system diagnosis в Alert Agent;
- `record_count=0` пропуска agent-а и дава `overall_importance=none`;
- failed Alert LensRun не създава/не persist-ва `AlertAnalysisResult`;
- completed/partial result се сглобява от deterministic Builder и се persist-ва в отделна stage.

## 8. Log-specific архитектурна посока

`Logs Analysis Pipeline` използва hybrid deterministic/agentic model:

```text
Log Provider Adapter
-> aggregate evidence + bounded textual content
-> parse / normalize / validate / sanitize
-> Deterministic Log Analyzer
     -> mandatory activity/rate + level/error-level evidence
     -> supplementary templates + reference comparisons
-> Log Analysis Agent when needed
     <-> optional analytical tools (max 3, each max once)
     <-> bounded log knowledge retrieval after findings (max 2)
-> LogAnalysisResult Builder / Validator
-> persistence
```

Основни boundaries:

- no full-corpus LLM input;
- selector определя `which`, LensRun определя `when`;
- parsing е deterministic/configured;
- LLM-visible log content се sanitize-ва и се третира като untrusted data;
- mandatory evidence е отделено от supplementary template/reference analysis;
- Log Agent не може да разширява data scope, да fetch-ва metrics/alerts или да прави system diagnosis;
- Log findings се формират преди knowledge retrieval;
- RAG се използва само за semantic enrichment на вече наблюдаван template/error code/message;
- RAG output се пази отделно като `knowledge_annotations` и не е observational evidence;
- Observation Reasoning може да reuse-не тези knowledge refs за hypotheses, но не и за findings;
- agent failure може да остави `partial` usable LogAnalysisResult;
- failed Log LensRun не създава/не persist-ва `LogAnalysisResult`.

## 9. Информативни литературни опори

Архитектурната посока е съвместима с наличната в проекта литература за agent specialization, staged analytical workflows, hierarchical/distributed CPS/MAS, hybrid deterministic/LLM architectures и structured/validated inter-agent artifacts. Литературните източници са **информативна опора**, не нормативен източник на архитектурните решения.
