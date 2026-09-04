## Why

The implemented Metrics Analysis Pipeline has a framework-neutral provider port but no
production provider behind it, so current and configured-reference analysis can run
only with injected fakes. A bounded Prometheus integration is needed to turn the
already-configured Metric Lens scope into real provider-neutral samples without moving
transport concerns into the analytical pipeline.

## What Changes

- Add a production Prometheus implementation behind the existing
  `MetricSeriesProvider` port, reusing the server-managed Prometheus source registry and
  its credential boundary without changing shared registry loading or existing public
  behavior.
- Define the Prometheus HTTP API v1 range-query request, exact current/reference window
  projection, deterministic step, single-float-series mapping, response validation,
  volume limits, timeouts, retry/backoff, and safe typed provider outcomes.
- Add source-aware composition that resolves `source_id` and injects the provider while
  leaving the Metrics Analysis Pipeline and provider-neutral contracts unchanged.
- Add provider-focused configuration, HTTP-boundary, resilience, mapping, composition,
  and injected-pipeline verification with no live Prometheus dependency.
- Align the existing Metrics pipeline capability with the separately specified
  production provider while retaining transport-free domain and pipeline tests.

## Capabilities

### New Capabilities

- `prometheus-metric-provider`: Acquire one bounded float sample series from Prometheus
  for an immutable current or reference Metric analysis window through the existing
  provider-neutral boundary.

### Modified Capabilities

- `metrics-analysis-pipeline`: Permit separately composed production Prometheus
  acquisition behind the existing injected port while preserving all analytical,
  lifecycle, result, reference-period, and persistence semantics.

## Impact

- Affected areas: `app.infrastructure.prometheus`, provider composition/application
  state, production-provider validation of a selected existing Prometheus source,
  `.env.example`, and focused backend tests. Shared `PROMETHEUS_SOURCES` loading remains
  compatible.
- The existing `httpx` dependency is sufficient; no dependency change is proposed.
- Prometheus receives read-only HTTP API v1 range queries for the already-approved
  opaque PromQL and exact pipeline-supplied windows. Secret credential material means
  the Bearer token and Basic-auth password; both remain server-side deployment secrets
  and are never stored in definitions, results, diagnostics, or the repository.
- No public API, database schema, MetricAnalysisResult, deterministic analysis,
  History, Metrics Analysis Agent, reference-period meaning, Observation orchestration,
  or Observation lifecycle change is proposed.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — one-metric Lens scope and the
  distinct current, configured-reference, and History perspectives.
- `docs/architecture/02_architecture_principles_and_runtime.md` and
  `04_pipeline_and_agent_concepts.md` — deterministic Metrics pipeline and immutable
  agent/provider boundaries.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — typed runtime,
  failure, and partial-result semantics.
- `docs/architecture/03_ADR_log.md` — ADR-003, ADR-045 through ADR-048, ADR-133 through
  ADR-135, and ADR-157 for configured-reference incompleteness and partial-result
  precedence.
- `openspec/specs/metrics-analysis-pipeline/spec.md` — canonical provider-port,
  current failure, reference unavailability, and Metric result behavior preserved by
  this provider integration.
- `docs/architecture/10_open_decisions_and_backlog.md` — explicitly deferred production
  Prometheus transport, authentication, retry, and timeout details resolved by this
  change without changing the accepted architecture.
