## Why

The MVP has Metric Lens definitions and generic runtime-result persistence, but no production pipeline that converts one immutable Metric Lens execution into trustworthy deterministic, agent-assisted, reference-aware, historically contextualized Metric evidence. This bounded capability is required before downstream Relationship Evaluation and Observation Reasoning can consume production `MetricAnalysisResult` artifacts.

## What Changes

- Add the internal deterministic Metrics Analysis Pipeline for exactly one already-created Metric Lens/LensRun execution.
- Add framework-neutral execution, single-series provider, Metrics Agent, deterministic-tool, and eligible-history contracts while preserving immutable metric/query/window/reference scope.
- Add exact deterministic sample preparation, quality assessment, mandatory `mean/std/min/max/slope`, and normalized trend/variability semanticization.
- Add the bounded optional registry `spike`, `oscillation`, and `stuck_signal`, with at most three attempted calls and each tool requested at most once.
- Add an always-invoked Metrics Analysis Agent behind a PydanticAI adapter with two strict framework-neutral request projections: usable current data exposes bounded evidence, semantics, tool metadata, and an opaque run-scoped `dataset_ref`, while insufficient current data exposes identity/window/quality only.
- Fix the usable agent projection's three strict tool descriptors and registry order, disable framework validation retries, and cap one agent run at four model requests so the three-attempt domain tool budget cannot be bypassed.
- Add deterministic independent comparison for `0..N` configured reference offsets and accepted partial behavior when acquisition, malformed data, or analytical insufficiency prevents a configured comparison.
- Add History analysis over eligible persisted same-`observation_id + lens_id` Metric results using analysis-window event-time chronology, the exact pair-relative near-zero transition guard, and stable-neutral directional-run pattern mechanics.
- Add strict discriminated `MetricAnalysisResult` 1.0 construction for completed-sufficient, completed-insufficient, partial, and minimal failed outcomes, preserving the existing six identity types and exact `analysis_window.from/to`.
- Add deterministic primary partial-reason component selection while keeping secondary reference, tool, and agent diagnostics outside the public Metric result.
- Add stable public error-code/message mapping and context-derived Prometheus provenance for minimal failed Metric results, including failures before a successful provider outcome.
- Reuse the existing caller-owned runtime transaction for terminal LensRun state plus its Metric artifact; extend the existing repository only with the bounded history-read query.
- Add focused unit, adapter, pipeline, contract, and PostgreSQL integration coverage using fakes for provider/model behavior.
- Exclude real Prometheus transport, provider authentication/retry, production model/provider selection, top-level Observation orchestration, other Lens pipelines, Relationships/Reasoning/Reports, RAG, scheduling, UI, baselines, and advanced anomaly models.

## Capabilities

### New Capabilities

- `metrics-analysis-pipeline`: Analyze one immutable Metric Lens execution, form the accepted deterministic/agent-assisted current, reference, and History semantics, construct a strict `MetricAnalysisResult`, and persist it through the existing runtime boundary.

### Modified Capabilities

None. The canonical `observation-definition-api` already supplies one metric, objectives, and explicit duplicate-free reference offsets with no default. `runtime-persistence` already owns Metric result storage; this change adds behavior through the new capability and a bounded read operation without changing its accepted public requirements.

## Impact

- Expected later implementation areas: a new backend Metric analysis package, one PydanticAI infrastructure adapter, a bounded read extension to the existing runtime repository, provider/model-neutral composition, and backend tests.
- No public HTTP endpoint, frontend behavior, database table, Alembic migration, Prometheus HTTP implementation, or top-level ObservationRun orchestration is added.
- Later implementation requires separate dependency approval for `pydantic-ai-slim>=2,<3` without provider extras. A provider-specific extra/client remains deferred until a production model/provider is approved.
- Existing Prometheus preflight behavior is not a production runtime provider and supplies no authorization to add transport code here.

## Architecture References

- `docs/architecture/README.md` — navigation and normative precedence.
- `docs/architecture/01_observation_lens_concept.md` — one-metric scope, mandatory semantics/evidence, reference periods, and persisted History.
- `docs/architecture/02_architecture_principles_and_runtime.md` — deterministic orchestration, bounded agency, lifecycle degradation, and persistence boundaries.
- `docs/architecture/03_ADR_log.md` — ADR-003, ADR-015–041, ADR-043–049, ADR-059, ADR-068, ADR-133–135, ADR-152, and ADR-153–160.
- `docs/architecture/04_pipeline_and_agent_concepts.md` — Metrics pipeline and agent responsibilities.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — terminal/usable semantics, Metric result envelope, structured reasons, and persistence.
- `docs/architecture/10_open_decisions_and_backlog.md` — remaining non-blocking prompt/model/provider/transport decisions.
- `docs/architecture/11_glossary_and_naming.md` — canonical terminology.
- `openspec/specs/observation-definition-api/spec.md` — current identity/objective/reference-offset primitive contracts.
- `openspec/specs/runtime-persistence/spec.md` — existing Metric artifact correlation, usability, and minimal-failure persistence behavior.
