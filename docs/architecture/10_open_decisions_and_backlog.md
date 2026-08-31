# Open decisions и архитектурен backlog

**Статус:** Open / Deferred register  
**Версия:** 5.1
**Актуализирано:** 2026-08-26

Този файл съдържа **само нерешени или съзнателно deferred** въпроси. Нищо тук не трябва да се използва като implicit requirement.

## 1. Lens configuration

- Exact machine-readable schema на `analysis_objectives`.
- Exact config location/default hierarchy за `max_parallel_lens_runs`.
- Exact per-Lens timeout/retry policy.

## 2. Metrics pipeline

- Exact prompt wording и implementation-private serialization на вече фиксирания
  structured Metrics Agent context; agent-visible data boundary е фиксирана от ADR-156.
- Production Metrics LLM model/provider и свързаните provider-specific dependencies.
- Model-dependent request timeout, token и cost limits извън фиксирания domain tool
  budget от ADR-155.
- Production Prometheus Metric Provider transport mapping, authentication, retry и
  timeout policy; analytical provider port остава source/framework-neutral.

## 3. Alerts и Logs pipelines

### 3.1. Alerts — resolved architecture, remaining implementation decisions

Концепцията, stage decomposition, agent boundary, failure/partial semantics и `AlertAnalysisResult` са Accepted. Open остават:

- exact serialized Alert Lens configuration schema (`selector`, `reference_periods`, defaults);
- exact `Jira Track and Release` API/field mapping и provider adapter interface;
- exact retry/timeout values за current/reference provider calls;
- exact canonical `evidence_refs` path/URI grammar;
- precedence на primary `reason`, ако един partial result има повече от една едновременна причина (`invalid_records` + `reference_unavailable`);
- exact validation/build failure reason code;
- volume/truncation/pagination policy beyond MVP;
- exact prompt/model/token budget за Alert Analysis Agent;
- exact internal request/response serialization на optional alert tools;
- exact per-tool timeout values;
- exact `evidence_refs` mapping за findings, derived от transient optional tool evidence.

### 3.2. Logs — resolved architecture, remaining implementation decisions

Концепцията, stage decomposition, deterministic/agentic boundaries, RAG boundary, reference/history semantics и `LogAnalysisResult` са Accepted. Open остават:

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
- Rendering/notification adapters извън Markdown artifact-а.

## 7. Triggering and lifecycle

- Periodic vs on-demand vs event-driven trigger policies/defaults.
- Scheduling technology.
- Overlap policy, ако нов trigger пристигне при running ObservationRun.
- Cancellation/retry/idempotency/replay semantics.

## 8. Persistence and infrastructure

- Database technology/schema.
- Workflow/orchestration framework (custom, graph/workflow engine и др.).
- Queue/executor model за parallel LensRuns.
- Observability/telemetry на самата multi-agent система.
- Data retention policy за persisted results.

## 9. RAG / knowledge layer

Следните **behavioral** решения са фиксирани за Observation Reasoning: on-demand tool use, findings-before-retrieval, fixed max 2 direct calls, second-query refinement, hypotheses require knowledge refs. За Log Agent също са фиксирани findings-before-retrieval, max 2 calls и knowledge-annotation separation. Отворени остават:

- retriever architecture;
- chunking/index strategy;
- vector vs hybrid retrieval;
- source ranking/reranking;
- exact query-rewriting policy inside retrieval tool;
- knowledge permissions/scope;
- citation/provenance identifiers;
- max retrieved chunks/context-token budget/timeout.

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
