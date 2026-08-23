## Context

See `proposal.md` and `specs/observation-definition-api/spec.md`. This is the first persisted domain aggregate. It stores configuration only: Observation/Lens definitions and Relationships are distinct from runs, results, and execution policy.

The change implements Metric definition serialization, Metric objectives, reference offsets, Prometheus acquisition, and limited resource links. Alert/Log configuration decisions are retained as deferred integration notes, not implemented behavior.

## Goals / Non-Goals

**Goals:**

- Persist one atomic Observation definition aggregate.
- Provide versioned contracts, compact linked summaries, complete detail reads, Prometheus capability discovery, and non-persisting Metric preflight.
- Validate Metric Relationship topology and controlled vocabulary before persistence.

**Non-Goals:**

- Execution, runs, agents, results, RAG, reporting, scheduling, frontend, editing/deleting, or pagination.
- Alert/Jira Track and Release and Log/Loki creation or preflight execution.
- Global Relationship Registry, cross-type Relationships, numeric/temporal rules, or persisting preflight output.

## Decisions

### Aggregate and version boundary

The Observation owns its Lenses and Relationships. `POST` validates and commits the full aggregate; no separate writes create incomplete topology. API transport is `/api/v1`; the server owns persisted positive-integer `schema_version`, initially `1`. It generates Observation IDs. Lens/Relationship IDs are constrained Observation-local references.

### Typed Metric configuration and deferred provider variants

The first implementation accepts only `metric` definitions through enabled Prometheus sources. Reference periods and Metric objectives are explicit, even when empty. PromQL owns both labels and any aggregation, and must yield one series. Sources are deployment-managed: definitions contain compatible adapter/source IDs only; discovery exposes source IDs/names, never connection details or credentials.

Prometheus source profiles are backend settings/environment entries with ID, display name, base URL, and either bearer-token or Basic credentials. The adapter receives a resolved source-profile abstraction rather than a settings type, allowing later database or secret-manager storage. It POSTs `/api/v1/query_range`, applies 15-second timeout/no retry, surfaces provider warnings, maps invalid PromQL to normal `valid: false`, maps provider authentication to `401|403`, and maps system failures to `5xx`.

Alert and Log contracts remain deferred integration notes: they will use the same source-ID/opaque-query boundary. `jira_track_and_release` remains the Alert adapter type even if it later uses Opsgenie internally. Concrete API, raw-record, field-mapping, and LogQL details are deliberately isolated for a later change.

### Metric preflight is an explicit acquisition boundary

Metric preflight accepts only candidate acquisition fields and a relative window. Cardinality failure is a normal `valid: false` result. It is separate from persistence so iterative query validation never depends on definition creation.

### Limited linked navigation

List responses are compact but enumerate relative `href` links for each owned Lens and Relationship. Observation detail is complete; individual resources support navigated reads. No generic hypermedia protocol is introduced.

### Metric-only Relationship configuration

Relationships are Observation-owned, Metric-only rules. Conditions/expectations use readable Lens-keyed nested descriptors. Empty conditions mean always applicable; expectations are required. `unknown` and `not_classified` remain result/evaluation states and are prohibited in configuration.

## Risks / Trade-offs

- [Source removal after persistence] → Preserve source IDs for reads; later source-lifecycle policy needs a separate change.
- [Raw preflight data exposure] → Keep previews bounded/transient and outside LLM contexts.
- [Future provider variants are unresolved] → Do not enable Alert/Jira Track and Release or Log/Loki creation/preflight until a dedicated provider-adapter change defines their integrations.
- [Async HTTP transport] → The approved implementation promotes existing `httpx` to runtime dependency range `>=0.28,<1`; no new package is introduced.
- [Future contract evolution] → Use path versioning, server-owned schema version, discriminated Lens types, and machine-readable errors.

## Migration Plan

1. After implementation approval, promote `httpx` and add a forward definition-persistence migration.
2. Deploy migration before writes; no backfill is needed.
3. Enable definition reads/writes, Prometheus capability discovery, and Metric preflight together; enable later provider adapters only in their own approved changes.
4. Roll back application code before rolling back the definition-only migration.

## Deferred Integrations

Jira Track and Release/Operationsgenie and Loki integration decisions are explicitly deferred to future changes. They do not block Metric-only implementation. Future adapters SHALL preserve the source-ID and opaque-query boundary captured by this change.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — definition/run separation, Lens/reference semantics, and Metric Relationships.
- `docs/architecture/02_architecture_principles_and_runtime.md` — runtime boundaries and Relationship Evaluation placement.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — persistence and definition/runtime separation.
- `docs/architecture/10_open_decisions_and_backlog.md` — remaining provider integration and execution-policy decisions.
- `docs/architecture/11_glossary_and_naming.md` — terminology.
- `docs/architecture/03_ADR_log.md` — ADR-001, ADR-003–011, ADR-043–063, ADR-088–091, ADR-133, ADR-136–138.
