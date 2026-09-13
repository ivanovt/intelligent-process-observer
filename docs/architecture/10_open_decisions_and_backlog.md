# Open decisions и архитектурен backlog

**Статус:** Open / Deferred register  
**Версия:** 5.3
**Актуализирано:** 2026-09-12

Този файл съдържа **само нерешени или съзнателно deferred** въпроси. Нищо тук не трябва да се използва като implicit requirement.

## 1. Lens configuration

- Retry policy beyond the accepted no-resume/fresh-run and type-specific provider rules.

## 2. Metrics pipeline

- Implementation-private serialization на вече фиксирания structured Metrics Agent
  context; agent-visible data boundary е фиксирана от ADR-156.
- Provider cost/admission limits и бъдещо prompt/model evaluation tuning извън
  фиксираните ADR-169 production defaults и domain tool budget от ADR-155.
- Production Prometheus Metric Provider transport mapping, authentication, retry и
  timeout policy; analytical provider port остава source/framework-neutral.

## 3. Alerts и Logs pipelines

### 3.1. Alerts — resolved architecture, remaining implementation decisions

Концепцията, stage decomposition, agent boundary, failure/partial semantics, `AlertAnalysisResult` и exact Alert Lens definition/API/persistence semantics са Accepted. Alert Lens schema/aggregate ownership са фиксирани от ADR-161..ADR-163. Open остават:

Провайдър API/field mapping и adapter interface (Jira Track and Release, включително Opsgenie alert surface) са съзнателно deferred — ще бъдат изяснени и проектирани заедно с (и като част от) спецификацията и имплементацията на Alerts pipeline-а.

- exact `Jira Track and Release` API/field mapping и provider adapter interface;
- exact retry/timeout values за current/reference provider calls;
- exact canonical `evidence_refs` path/URI grammar;
- precedence на primary `reason`, ако един partial result има повече от една едновременна причина (`invalid_records` + `reference_unavailable`);
- exact validation/build failure reason code;
- volume/truncation/pagination policy beyond MVP;
- provider cost/admission limits и бъдещо prompt/model evaluation tuning за Alert
  Analysis Agent извън фиксираните ADR-169 production defaults;
- exact internal request/response serialization на optional alert tools;
- exact per-tool timeout values;
- exact `evidence_refs` mapping за findings, derived от transient optional tool evidence.

### 3.2. Logs — resolved architecture, remaining implementation decisions

Концепцията, stage decomposition, deterministic/agentic boundaries, RAG boundary, reference/history semantics и `LogAnalysisResult` са Accepted. Open остават:

Провайдър API/client (Loki) и adapter interface са съзнателно deferred — ще бъдат изяснени и проектирани заедно с (и като част от) спецификацията и имплементацията на Logs pipeline-а.

- exact serialized Log Lens configuration schema (`selector`, `reference_periods`, parsing config);
- exact Loki API/client и LogQL mapping;
- aggregate-query implementation strategy;
- bounded-content limit/sampling/retrieval policy и coverage metadata schema;
- exact parser configuration и level-field precedence;
- exact sanitization/redaction rules;
- exact template normalization rules/hash/versioning implementation;
- exact template projection limits (`top_overall`, `top_error_level`);
- exact bucket count/minimum evidence/z-score applicability за Bucketed Log Rate Analysis;
- exact internal request/response serialization на Log analytical tools;
- exact Log Agent prompt/model/token budget;
- exact `knowledge_annotations` serialized schema details и subject vocabulary;
- exact retriever permissions/scope за `retrieve_log_knowledge`;
- exact evidence-ref / knowledge-ref URI grammar;
- precedence на partial reason при multiple simultaneous incompleteness causes;
- exact per-stage retry/timeout values.

## 4. Relationship model

- Exact serialized JSON/YAML schema на `RelationshipEvaluation` (семантиката е фиксирана).
- Дали/кога да се добавят optional properties като `oscillation.state`.
- Numeric/temporal relationship rule language — Deferred.
- Cross-type Relationships (Metric + Alert + Log) — Deferred; MVP е metric-only.

## 5. Observation Reasoning

- Exact serialization details на `ObservationReasoningContext`.
- Exact `evidence_refs` reference syntax/URI scheme.
- Exact `knowledge_refs` provenance/citation syntax.
- Дали limitations се формират изцяло детерминистично от availability metadata или се позволяват и на agent-а в ограничен vocabulary.
- Дали Observation-level history някога ще има отделна retrieval capability извън Lens history.

## 6. Report Agent

- Exact Markdown template/sections за engineer vs operator variants.
- Localization/language policy на report-а.
- Export, notification и други renderer adapters извън приетия MVP browser renderer
  за persisted Markdown artifact-а.

## 7. Triggering and lifecycle

- Periodic и event-driven trigger policies/defaults; on-demand public launch е фиксиран
  от ADR-168.
- Scheduling technology.
- External cancellation API/trigger, automatic-retry trigger policy, idempotency, replay
  и artifact-reuse semantics. ADR-164 фиксира fresh-run retry/restart/re-run behavior, а
  ADR-165 фиксира terminalization при вече наблюдавана top-level cancellation.

## 8. Persistence and infrastructure

- Database technology/schema.
- Multi-process task ownership/claim/lease и distributed worker model; ADR-168 фиксира
  single-process managed `asyncio` host за on-demand MVP execution.
- Production observability остава Open само за aggregation/export backend, dashboards,
  alerting, distributed tracing и automatic retention policy. ADR-171 фиксира минималния
  MVP boundary за correlated backend operational logs, safe failure classification и
  opt-in development-only full agent interaction traces.
- Data retention policy за persisted results.

## 9. RAG / knowledge layer

Следните **behavioral** решения са фиксирани за Observation Reasoning: on-demand tool use, findings-before-retrieval, fixed max 2 direct calls, second-query refinement, hypotheses require knowledge refs. За Log Agent също са фиксирани findings-before-retrieval, max 2 calls и knowledge-annotation separation. Отворени остават:

- exact query-rewriting policy inside retrieval tool;
- Log-specific и future retriever output/context limits и timeout извън фиксирания
  Observation-level MVP boundary на ADR-173.

ADR-173 фиксира за Observation-level MVP manual PDF/Markdown corpus, retained PostgreSQL
document versions, pgvector + lexical hybrid retrieval, approved-version lifecycle,
service-scope filtering и concrete document-version/chunk locator, който resolve-ва към
page-or-heading provenance, както и max 4 whole passages / 8 KiB serialized batch / 30s full-call
budget. Shared knowledge-reference syntax за други future retrievers остава
Open. External source
connectors/sync, OCR, independent Service Catalog, advanced reranking и authorization
остават future decisions.

## 10. Explicitly Deferred beyond MVP

- baseline management;
- operating-mode/adaptive/seasonal baselines;
- runtime relationship discovery;
- global Relationship Registry / Process Model;
- numeric relationship rule engine;
- cross-type Relationships;
- advanced historical pattern classes (`progressive`, `intermittent`);
- autonomous expansion of observational data scope by agents;
- recommendations/prescriptive actions;
- confidence/severity/probability models;
- hypothesis ranking/root-cause selection.
- alert semantic clustering/grouping;
- advanced alert burst/flapping/escalation analysis;
- provider-independent alert severity normalization;
- point-in-time historical alert lifecycle reconstruction;
- automatic provider-query rewriting/linting;
- RAG/external-knowledge tool use inside Alert Analysis Agent;
- persisted Log History Analyzer;
- semantic/embedding log clustering и advanced sequence-based log anomaly models;
- automatic Log Agent data-scope/query expansion;
