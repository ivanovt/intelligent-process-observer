## Context

See `proposal.md` and `specs/observation-definition-api/spec.md`. This is the first persisted domain aggregate. It stores configuration only: Observation/Lens definitions and Relationships are distinct from runs, results, and execution policy.

The change resolves definition serialization for typed Lenses, Metric objectives, reference offsets, Log level parsing, and limited resource links. Provider API/client/field mapping decisions remain open.

## Goals / Non-Goals

**Goals:**

- Persist one atomic Observation definition aggregate.
- Provide versioned contracts, compact linked summaries, complete detail reads, capability discovery, and non-persisting Lens preflight.
- Validate Metric Relationship topology and controlled vocabulary before persistence.

**Non-Goals:**

- Execution, runs, agents, results, RAG, reporting, scheduling, retry/timeout/concurrency policy, frontend, editing/deleting, or pagination.
- Global Relationship Registry, cross-type Relationships, numeric/temporal rules, or persisting preflight output.

## Decisions

### Aggregate and version boundary

The Observation owns its Lenses and Relationships. `POST` validates and commits the full aggregate; no separate writes create incomplete topology. API transport is `/api/v1`; the server owns persisted positive-integer `schema_version`, initially `1`. It generates Observation IDs. Lens/Relationship IDs are constrained Observation-local references.

### Typed, explicit Lens configuration

Lenses use a `metric`/`alert`/`log` discriminator and strict type-specific fields. Reference periods and Metric objectives are explicit, even when empty. Metric PromQL owns both labels and any aggregation, and must yield one series. Sources are deployment-managed: definitions contain compatible adapter/source IDs only; discovery exposes source IDs/names, never connection details or credentials.

### Preflight is an explicit acquisition boundary

Type-specific, non-persisting preflight endpoints accept only acquisition/parsing fields plus a relative window. Metric cardinality failure is a normal `valid: false` result. Alert/Log zero-record results are valid. Alert/Log raw previews are bounded, unchanged, transient provider evidence for engineers. Log parsing appears in aggregate diagnostics, not by modifying raw records.

### Limited linked navigation

List responses are compact but enumerate relative `href` links for each owned Lens and Relationship. Observation detail is complete; individual resources support navigated reads. No generic hypermedia protocol is introduced.

### Metric-only Relationship configuration

Relationships are Observation-owned, Metric-only rules. Conditions/expectations use readable Lens-keyed nested descriptors. Empty conditions mean always applicable; expectations are required. `unknown` and `not_classified` remain result/evaluation states and are prohibited in configuration.

## Risks / Trade-offs

- [Source removal after persistence] → Preserve source IDs for reads; later source-lifecycle policy needs a separate change.
- [Raw preflight data exposure] → Keep previews bounded/transient and outside LLM contexts.
- [Provider integration is unresolved] → Do not implement concrete Prometheus, Jira Track and Release, or Loki preflight adapters without approved provider contracts.
- [Future contract evolution] → Use path versioning, server-owned schema version, discriminated Lens types, and machine-readable errors.

## Migration Plan

1. After implementation approval and provider-integration decisions, add a forward definition-persistence migration.
2. Deploy migration before writes; no backfill is needed.
3. Enable definition reads/writes and capability discovery together; enable each concrete preflight adapter only when approved/configured.
4. Roll back application code before rolling back the definition-only migration.

## Blocking Questions

Concrete preflight execution is blocked until these architecture-open contracts are decided:

1. Prometheus source configuration and query-client boundary.
2. Jira Track and Release API/client, provider adapter interface, and field mapping for Alert preflight.
3. Loki API/client, LogQL mapping, and raw-record acquisition representation for Log preflight.

The approved public contract does not authorize inventing these integration details. Resolve them before implementation tasks or apply.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — definition/run separation, Lens/reference semantics, and Metric Relationships.
- `docs/architecture/02_architecture_principles_and_runtime.md` — runtime boundaries and Relationship Evaluation placement.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — persistence and definition/runtime separation.
- `docs/architecture/10_open_decisions_and_backlog.md` — remaining provider integration and execution-policy decisions.
- `docs/architecture/11_glossary_and_naming.md` — terminology.
- `docs/architecture/03_ADR_log.md` — ADR-001, ADR-003–011, ADR-043–063, ADR-088–091, ADR-133, ADR-136–138.
