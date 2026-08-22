# Glossary и naming conventions

**Версия:** 5.0
**Актуализирано:** 2026-08-19

## Observation
Конфигурационна единица, която дефинира цялостна задача за наблюдение и съдържа Lens-ове, Relationships и политики.

## ObservationRun
Конкретно runtime изпълнение на Observation.

## Lens
Атомарна наблюдателна перспектива. Lens е definition/configuration, не изпълнение.

## LensRun
Конкретно изпълнение на Lens в рамките на ObservationRun.

## Lens Pipeline
Специализиран pipeline според Lens type, който приема LensRun и връща LensAnalysisResult.

## LensAnalysisResult
Обща концепция за structured result на Lens pipeline. Конкретни типове: MetricAnalysisResult, AlertAnalysisResult, LogAnalysisResult.

## Stage
Стъпка в workflow. Stage може да бъде component, agent или sub-pipeline.

## Pipeline
Многостъпков processing workflow с ясен вход/изход и lifecycle.

## Observation Orchestrator
Детерминистичен control-plane компонент, който управлява Observation workflow-а.

## Agent
LLM/agentic компонент с ограничена автономност за reasoning/tool use в ясно определена boundary.

## Tool
Специализирана capability с тесен контракт, извиквана от агент или component.

## Metrics Analysis Agent
Агент вътре в Metrics Analysis Pipeline, който избира optional analytical tools в immutable data scope.

## Metric reference period
Configured time window със същата продължителност като current Metric Lens analysis window, изместен назад с offset като `1d`, `7d` или `14d`. Използва се за независимо сравнение на level, trend и variability и предоставя periodic/seasonal temporal context. Не е baseline и е различен от persisted Lens history.

## Relationship
Engineer-defined qualitative rule за очаквано съвместно поведение на 2..N Lens participants.

## Relationship Evaluator
Детерминистичен компонент, който сравнява Relationship expected behavior с current semantic states.

## RelationshipEvaluation
Structured evidence за applicability и consistency на Relationship при текущ ObservationRun.

## Observation Reasoning Agent
Agentic компонент за system-level synthesis, hypotheses и contextual interpretation. Може да използва knowledge retrieval при нужда.

## ObservationReasoningContext
Compact semantic projection на Observation configuration, предназначена за Reasoning Agent; изключва infrastructure/execution noise.

## ObservationAnalysisResult
Structured резултат на Observation Reasoning Agent с MVP ядро `identity`, `overall_state`, `findings`, `hypotheses`, `limitations`.

## Report Agent
Presentation agent, който превръща ObservationAnalysisResult в human-readable ObservationReport.

## Semantic descriptor
Controlled qualitative state, изведен от numerical/structured evidence, например `trend.direction=increasing`.

## Evidence
Проверими numerical/structured факти, върху които се базира semantic или reasoning резултат.

## Applicability
Дали Relationship condition rule е приложим при текущото състояние: `applicable | not_applicable | unknown`.

## Relationship state
Оценка само при applicable relationship: `consistent | inconsistent | uncertain`.

## Terminal state
Runtime LensRun status, при който execution е приключил: `completed | partial | failed`.

## Usable result
Result, който може да бъде използван downstream; не е синоним на terminal.

## Bounded agency
Agent autonomy, ограничена от allowed tools, immutable scope, iteration/time/cost budgets и deterministic lifecycle envelope.


## Finding
Evidence-grounded Observation-level заключение, формирано само от Lens/Relationship evidence. RAG не може да създава или променя finding.

## Hypothesis
Възможно domain explanation на един или повече findings. За MVP domain hypothesis трябва да има `supported_by` и retrieved `knowledge_refs`; няма ranking/confidence.

## Knowledge reference
Traceability reference към външен retrieved source/chunk/section, използван при формиране на hypothesis.

## Unavailable Lens
LensRun без usable analytical result, представен към Reasoning Agent чрез кратки metadata + structured reason вместо празен analytical contract.

## Partial reason
Кратък structured reason (`code` + optional `component`), който показва коя optional част на usable partial result е непълна.

## ObservationReport
Human-readable presentation artifact, генериран от Report Agent. За MVP format = Markdown.

## Alert Lens
Lens type за bounded perspective върху alert activity. Един модел поддържа както конкретен alert rule/type, така и filtered provider set чрез provider-native selector.

## Alert Provider Adapter
Детерминистичен integration component, който изолира provider-specific API/query/field mapping от source-agnostic Alerts Analysis Pipeline.

## Normalized alert record
Canonical representation на usable current alert record с lifecycle timestamps, normalized/source status, optional provider importance, occurrence_count и source reference.

## Alert overlap semantics
Правило за membership в analysis/reference window: alert е релевантен, ако lifecycle interval-ът му се пресича с window-а.

## analysis_timestamp
Фиксирана semantic time reference на LensRun. При active alert се използва за reproducible `duration_seconds`.

## record_count
Брой distinct usable current alert records. Zero-record fast path се определя само чрез `record_count=0`.

## occurrence_count
Мярка за alert activity, получена като сума от provider occurrence_count values с deterministic default 1 при липсваща стойност.

## Provider importance
Optional provider-native priority/severity concept, запазена без cross-provider normalization, например `{type: priority, value: Highest}`.

## Deterministic Alert Analyzer
Deterministic component и coordinator на mandatory alert analytical tools/capabilities. Гарантира activity, status distribution, durations, provider importance distribution и reference occurrence comparisons.

## Mandatory Alert Analytical Tool
Deterministic capability, чието изпълнение се гарантира от pipeline-а/Deterministic Alert Analyzer и не зависи от решение на LLM.

## Optional Alert Analytical Tool
Allowed deterministic analytical capability, извиквана директно от Alert Analysis Agent върху already-available immutable Alert Lens data/evidence. Не може да разширява selector/time/data scope.

## Alert Analysis Agent
Bounded Lens-local reasoning agent в Alerts pipeline. Връща `findings + overall_importance` и може да използва 0..10 optional analytical tool calls; няма metrics/logs/RAG/cross-lens diagnosis.

## Recurrence Concentration Analysis
Optional Alert tool, който изчислява `top_record_share` като дела на най-повтарящия се alert record в общия current `occurrence_count`.

## Duration Outlier Analysis
Optional Alert tool за high-duration outliers чрез IQR (`Q3 + 1.5*IQR`), приложим при минимум 8 валидни duration стойности.

## Reference Pattern Analysis
Optional Alert tool, който при минимум 2 successful reference comparisons определя проста `dominant_direction` чрез броене на `increased|decreased|unchanged`; tie -> `mixed`.

## Alert finding
Lens-local descriptive finding, grounded в current alert records/deterministic evidence чрез `evidence_refs`.

## Alert overall importance
Една Lens-level оценка `none | low | moderate | high | critical`. `none` е допустимо само при надеждно установен `record_count=0`.

## AlertAnalysisResult
Versioned structured analytical artifact за `completed|partial` Alert LensRun. Failed Alert LensRun не създава AlertAnalysisResult в MVP.

## AlertAnalysisResult Builder / Validator
Deterministic final analytical component, който сглобява и валидира AlertAnalysisResult от LensRun metadata, normalized records, deterministic evidence и agent output.

## Reference period (Alert Lens)
Window със същата продължителност като current window, изместен назад с configured offset. MVP comparison използва occurrence_count.

## reference_unavailable
Structured partial reason, когато един или повече configured Alert reference periods не могат да бъдат изчислени, но current mandatory analysis остава usable.

## invalid_records
Structured reason за rejected current alert records. Ако usable records остават — partial; ако не остава usable current data — failed.

## Log Lens
Lens type за bounded перспектива върху log activity. Provider-native selector определя кои логове са релевантни, а LensRun определя current time window.

## Log Provider Adapter
Deterministic integration component, който изолира Loki/provider API и query semantics. Поддържа aggregate evidence и bounded textual content acquisition.

## Aggregate Log Evidence
Количествени log характеристики, получени чрез provider-side aggregation или друго bounded изчисление, без изискване целият textual corpus да бъде transfer-нат локално.

## Bounded Log Content
Ограничен набор от textual log records, използван за content-dependent анализи като template extraction. Coverage semantics трябва да са traceable, когато не се анализира целият corpus.

## Canonical log level
Controlled normalized vocabulary `error | warning | info | debug | trace | unknown`, извличан детерминистично чрез parsing/provider mapping.

## error_level_count
Брой log records, нормализирани с `level=error`. Не е синоним на абсолютен брой реални software/process faults.

## level_coverage
Дял на log population-а, за който canonical level може да бъде определен надеждно.

## Log template
Deterministically normalized текстов pattern, който маскира selected variable tokens (напр. IP/UUID/IDs) и позволява recurrence/template analysis без semantic clustering.

## Deterministic Log Analyzer
Component, който произвежда mandatory log activity/rate/level evidence и supplementary template/reference evidence без LLM.

## Log Analysis Agent
Bounded Lens-local agent, който интерпретира structured Log evidence, използва до 3 optional deterministic tools и при нужда до 2 knowledge-retrieval calls след freeze на findings.

## Log finding
Lens-local observational conclusion, grounded само в deterministic/supplementary Log Lens evidence. External retrieved knowledge не е finding source.

## Log overall importance
Lens-local `none | low | moderate | high | critical` assessment. Не е system severity или Observation overall state.

## Log knowledge retrieval
Bounded external-knowledge capability за обяснение на вече наблюдаван template/error code/message. Не разширява observational data scope и се изпълнява само след freeze на Log findings.

## Knowledge annotation (Log)
RAG-derived Lens-local semantic enrichment, свързано с един или повече Log findings чрез `supported_by` и с външен source чрез `knowledge_refs`. Не е observational evidence.

## Bucketed Log Rate Analysis
Optional deterministic tool, който разделя current window на time buckets и изчислява rate/spike characteristics като min/max/mean и peak-to-mean ratio; z-score може да е optional, когато е приложим.

## Template Reference Difference Analysis
Optional Log tool за сравнение на current observed template evidence с available reference template evidence, без абсолютна novelty claim при bounded content.

## Error-Level Template Concentration Analysis
Optional Log tool, който изчислява концентрацията на observed error-level records около dominant template.

## LogAnalysisResult
Versioned structured analytical artifact за `completed|partial` Log LensRun. Failed Log LensRun не създава LogAnalysisResult. Observational findings и external `knowledge_annotations` са семантично разделени.

## LogAnalysisResult Builder / Validator
Deterministic final contract owner, който сглобява и валидира LogAnalysisResult и гарантира separation между observational evidence и knowledge enrichment.

