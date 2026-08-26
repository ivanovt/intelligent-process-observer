# Changelog

## 6.3 — 2026-08-26

- added ADR-159 clarifying ADR-021 with an exact pair-relative near-zero guard,
  inclusive stable boundary, zero/zero behavior, and no absolute epsilon;
- added ADR-160 clarifying ADR-025 with exact unknown removal, stable-neutral
  directional projection, directional runs, `direction_changes`, and deterministic
  oscillating/reversing/sustained/mixed priority mechanics;
- completed the remaining Metric History implementation semantics without changing
  the accepted History vocabulary, direction algorithm, configuration precedence, or
  default tolerance.

## 6.2 — 2026-08-26

- added ADR-153 with fixed normalized deterministic Metric trend/variability rules;
- added ADR-154 and ADR-155 with the Metric optional registry (`spike`,
  `oscillation`, `stuck_signal`), three-attempt budget, and each-tool-once policy;
- added ADR-156 with the opaque `dataset_ref` boundary, minimal typed agent completion,
  usable-core agent failure semantics, and resilient insufficient-quality path;
- added ADR-157 with partial behavior for unavailable or analytically insufficient
  configured Metric references and primary partial-reason precedence;
- added ADR-158 with event-time History chronology, overlapping-window eligibility,
  deterministic ordering, and infrastructure-failure distinction;
- narrowed the Metrics backlog to genuinely unresolved prompt wording,
  production model/provider limits, and future Prometheus transport details.

## 6.1 — 2026-08-26

- added ADR-152, selecting PydanticAI as the MVP agent-framework integration mechanism after the completed Alert and Observation Reasoning/RAG framework experiments;
- the ADR records a human project-fit tie-break, not an experimental claim of technical superiority over LangChain;
- retained framework-neutral domain contracts, deterministic orchestration, budgets, evidence validation, findings freeze, and retrieval constraints as the owners of runtime semantics;
- clarified that the decision does not select a production model/provider, retrieval stack, vector database, embedding model, observability product, or evidence-reference grammar;
- recorded the shared insufficient-knowledge/refinement validation issue as follow-up work for a future production Observation Reasoning/knowledge-retrieval feature.

## 6.0 — 2026-08-19

Добавен и фиксиран Logs Architecture package:

- приет `Log Lens` като bounded provider-native log perspective; LensRun определя time window;
- Loki е current MVP provider зад source-agnostic Log Provider Adapter boundary;
- log events използват point-event timestamp membership;
- acquisition разделя aggregate evidence от bounded textual log content и не предполага full-corpus materialization;
- parsing/level mapping е deterministic/configured; LLM не infer-ва log level от свободен текст;
- добавена sanitization/redaction boundary за LLM-visible log/template text; log text се третира като untrusted data;
- generic deduplication е изключена по подразбиране;
- mandatory core: log activity/rate, level distribution, error-level activity и level coverage;
- template extraction е deterministic supplementary analysis с versioned extractor provenance и bounded coverage semantics;
- Log Lens поддържа `0..N` reference periods; core comparisons са `log_count` и `error_level_count`;
- persisted Log History Analyzer е извън MVP;
- приет bounded `Log Analysis Agent` с max 3 optional analytical tools, max 1 call/tool;
- minimal tool registry: Bucketed Log Rate, Template Reference Difference, Error-Level Template Concentration;
- optional tool failure/timeout е non-fatal;
- zero-log path е conditional спрямо reference evidence;
- Log Agent failure води до `partial`, ако deterministic current core е usable;
- Log Agent получава bounded knowledge retrieval след freeze на findings, max 2 calls;
- retrieved knowledge не създава/променя Log findings и се пази отделно като `knowledge_annotations`;
- Observation Reasoning може да използва upstream Log knowledge annotations само като knowledge grounding за hypotheses, не като evidence за findings;
- `LogAnalysisResult Builder / Validator` е final deterministic contract owner;
- failed Log LensRun няма `LogAnalysisResult`;
- добавени ADR-136..ADR-151;
- добавени documents `21_...` до `28_...` и актуализирани README, Observation/Lens concept, architecture/runtime, pipeline concepts, runtime contracts, Observation Reasoning, ObservationAnalysisResult, backlog и glossary.

## 5.1 — 2026-08-13

Merged Metrics reference-period architecture updates:

- `previous_period` semantics са заменени с `0..N` configurable Metric `reference_periods`;
- всеки reference window има същата продължителност като current window и backward offset, например `1d`, `7d`, `14d`;
- всеки offset се сравнява независимо по level, trend direction/rate и variability;
- reference periods поддържат periodic/seasonal context, но не са baseline и не са automatic seasonality classification;
- `history` остава отделен analysis върху persisted LensRun results;
- Metrics pipeline използва `Reference Period Comparator`;
- MetricAnalysisResult temporal sections/evidence са current/reference/history;
- ADR-013 и ADR-014 са superseded от ADR-133 и ADR-134; добавен е ADR-135 за MetricAnalysisResult temporal evidence;
- обновени README, Observation/Lens concept, architecture/runtime, pipeline concepts, relationship boundaries, runtime contracts, backlog и glossary.

## 5.0 — 2026-08-13

Актуализиран Alerts Architecture tool model след design refinement:

- приет hybrid mandatory/optional tool approach за Alerts pipeline;
- mandatory fetch/normalize/reference/analysis operations остават гарантирани от deterministic pipeline lifecycle-а;
- `Deterministic Alert Analyzer` остава отделен component и coordinator на mandatory analytical tools/capabilities;
- `Alert Analysis Agent` вече има bounded optional analytical tool loop върху immutable already-fetched Lens scope;
- optional tools не могат да fetch-ват нови alerts или да променят selector, time window, reference configuration или Observation scope;
- фиксиран minimal optional registry: Recurrence Concentration, Duration Outlier и Reference Pattern Analysis;
- Recurrence Concentration използва `top_record_share`;
- Duration Outlier използва high-side IQR с minimum 8 valid durations;
- Reference Pattern използва simple dominant direction и minimum 2 successful comparisons;
- optional tool budget = max 10 calls; repeated calls към същия tool са позволени; всички attempts се броят;
- optional tool `failed|timeout` е non-fatal и agentът продължава с наличното evidence;
- successful/not_applicable optional outputs са transient и не се persist-ват като standalone result sections;
- `AlertAnalysisResult` пази minimal optional-tool trace само за реални `failed|timeout` calls;
- добавени ADR-123..ADR-132;
- добавен `20_alert_analytical_tools.md`;
- обновени README, Observation/Lens concept, architecture/runtime, pipeline concepts, Alert concept/pipeline/contract/components, backlog и glossary.

## 4.0 — 2026-08-09

Добавен и фиксиран Alerts Architecture package:

- единен Alert Lens модел за specific rule и bounded filtered alert set;
- текущ provider `Jira Track and Release` с source-agnostic provider adapter boundary;
- provider-native selector определя scope, LensRun определя time context;
- lifecycle-overlap semantics за current и reference windows;
- retrospective latest-known lifecycle semantics и fixed `analysis_timestamp`;
- canonical alert record с required `started_at`, optional `ended_at`, provider status/importance и occurrence count;
- deterministic `record_count` + `occurrence_count` semantics;
- deterministic status distribution и duration statistics в секунди;
- multiple reference periods, сравнявани само по occurrence_count;
- zero-record fast path по `record_count=0`, без Alert Agent call;
- bounded `Alert Analysis Agent` с Lens-local findings и overall importance;
- без semantic clustering, RAG, metrics/logs или system-level diagnosis в Alert Agent;
- `AlertAnalysisResult` versioned common envelope + minimal provenance;
- findings винаги присъства при completed/partial, evidence_refs са same-result resolvable;
- partial/failure reason е structured `code + optional component`;
- failed Alert LensRun не създава и не persist-ва AlertAnalysisResult;
- deterministic `AlertAnalysisResult Builder / Validator` е final analytical contract owner;
- persistence е отделна pipeline stage, без фиксиран AlertRepository;
- без truncation на current alert records в MVP;
- добавени ADR-089..ADR-122;
- обновени README, architecture, runtime, pipeline concepts, backlog и glossary;
- добавени подробни Alert concept/component/contract документи `13_...` до `19_...`.

## 3.0 — 2026-08-08

Добавени/фиксирани след architecture package 2.0:

- full structured Lens results + compact semantic Observation context като Reasoning input;
- отделно представяне на usable и unavailable Lens results;
- structured reason codes за partial/unavailable analysis;
- self-contained RelationshipEvaluation за downstream reasoning;
- metric-only Relationships за MVP;
- фиксиран минимален `ObservationAnalysisResult`;
- overall-state vocabulary без `normal/anomalous` semantics;
- минимален finding contract без taxonomy;
- hypotheses linked към findings + optional/required-as-used `knowledge_refs`;
- findings са evidence-only и frozen преди RAG;
- RAG е tool в Reasoning Agent, не отделен agent;
- bounded RAG loop с fixed `max_calls=2`;
- вторият retrieval може да refine-ва query чрез first-retrieval context;
- domain hypotheses изискват retrieved knowledge grounding;
- 0..N unranked hypotheses;
- без confidence, severity, recommendations и root-cause ranking за MVP;
- `overall_state` се определя от Reasoning Agent; `uncertain` може да има findings;
- Report Agent е presentation-only, без RAG/new analysis;
- ObservationReport = Markdown artifact;
- актуализирани ADR до ADR-088;
- добавени отделни Reasoning, AnalysisResult и Report концептуални документи;
- обновен open backlog и reusable templates.

## 2.0 — 2026-08-08

- deterministic Observation Orchestrator;
- hierarchical Observation workflow със specialized sub-pipelines;
- Metrics pipeline като deterministic lifecycle с always-invoked bounded Metrics Analysis Agent;
- multi-step optional tool loop без право за data-scope expansion;
- `analysis_objectives` като intent, не tool whitelist;
- отделни Observation Reasoning Agent и Report Agent;
- on-demand knowledge retrieval от Reasoning Agent;
- deterministic Relationship Evaluation stage;
- LensRun independence, configurable concurrency и strict JOIN;
- graceful degradation при partial Lens failures и STOP при zero usable results;
- common Lens pipeline execution contract;
- Relationship Evaluator self-resolves participants;
- `applicability` отделено от `state`;
- Relationship rules ограничени до `current_state` и малък explicit property vocabulary.

## 1.0 — 2026-08-08

Първоначален архитектурен пакет с Observation/Lens, Metric analysis, history/previous-period semantics и ADR-001..042.
