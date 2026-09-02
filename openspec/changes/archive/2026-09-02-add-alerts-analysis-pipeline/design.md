## Context

See [proposal.md](proposal.md) for motivation and the delta specification for the
behavioral contract. The accepted Alert Lens definition already persists the source,
opaque selector, objectives, and ordered reference offsets. Runtime persistence already
has type-aware Alert LensRuns, one JSON artifact slot per run, terminal transition
validation, and the required absence of a failed Alert artifact. The Metrics pipeline
demonstrates the established shape: framework-neutral domain ports, deterministic
pre-transaction work, an injected PydanticAI adapter, a strict builder, and an existing
caller-owned runtime transaction.

The accepted architecture fixes the Alert stage sequence and boundaries but deliberately
leaves provider transport/mapping, agent model settings, tool serialization,
evidence-reference syntax, multiple partial-reason precedence, duration precision, and
some deterministic-tool detail open. The first three groups stay outside this change.
The remaining contract-local details are explicitly proposed below so implementation and
review do not silently infer them.

## Goals / Non-Goals

**Goals:**

- Add one internal application service for an existing running Alert LensRun.
- Keep acquisition, mandatory deterministic evidence, optional tools, agent reasoning,
  validation, and terminal persistence independently testable.
- Reuse the existing runtime persistence aggregate without schema/API work.
- Keep framework/model/provider concerns behind injected infrastructure boundaries.

**Non-Goals:**

- Observation orchestration, LensRun creation, fan-out/JOIN, scheduling, retry,
  idempotency, recovery, or terminal-write retry policy.
- Jira Track and Release transport, endpoints, authentication, credentials, concrete
  API field mapping, pagination, truncation, or provider retry/timeout values.
- Production model/provider selection, credentials, prompt version, model timeout/token
  settings, or live model calls.
- Alert preflight/API/UI work, definition/migration changes, cross-lens reasoning, RAG,
  clustering, provider-independent severity mapping, and raw payload persistence.

## Decisions

### Use a single provider-neutral Alert package and existing persistence boundary

Add an `app.alerts` domain/application package alongside `app.metrics` with strict
contracts, ports, normalization, deterministic analyzer, optional tools, result builder,
and pipeline. Add only `app.infrastructure.agents.pydantic_ai_alerts` as the framework
adapter. The domain package has no SQLAlchemy, PydanticAI, Jira client, or provider SDK
imports.

The pipeline receives a frozen context made from an existing Alert Lens definition and
already-running LensRun. An `AlertProvider` port receives source, opaque selector, and
one derived window and returns a typed outcome containing canonical-mappable fields or
an unavailable/timeout outcome. It neither knows a Jira endpoint nor selects a
transport. An `AlertAnalysisAgent` port receives the strict bounded request plus the
application-owned optional-tool executor. Fakes provide all tests.

Alternative considered: implement Jira access directly in the pipeline. Rejected because
it would conflate the accepted provider adapter boundary with deferred transport and
field mapping. Alternative considered: create a generic global agent/tool runtime.
Rejected because only Alert-local behavior is required and the Metrics implementation
shows a smaller, feature-local boundary.

### Preserve the accepted deterministic stage order and keep long-running work outside the write transaction

The application service performs, in order: validate frozen context; current acquisition;
current normalization and lifecycle-overlap filtering; independent reference acquisition
and preparation; mandatory deterministic analysis; zero-record gate or bounded agent;
strict result building; then terminal transition and artifact persistence in the
caller-owned transaction.

Provider calls, optional tools, and the agent occur before the transaction. The existing
repository transitions the LensRun and inserts at most one correlated artifact after the
builder has produced a `LensAnalysisResultInput`. A failed Alert stage advances only the
LensRun; it never builds/persists a placeholder artifact. Transaction/flush/commit
failures propagate rather than being reclassified as analytical failures.

Alternative considered: hold the transaction across acquisition and agent work. Rejected
because it would unnecessarily hold database resources and differs from the accepted
Metrics persistence pattern.

### Implement canonical validation and mandatory evidence as pure deterministic components

Normalization owns canonical validity and overlap filtering; the provider port owns only
provider-side acquisition/mapping. `DeterministicAlertAnalyzer` owns effective occurrence
defaults, activity, record-based status counts, duration derivation/statistics, native
provider-importance grouping, and successful-reference comparison. Pure models and
functions make all arithmetic and omission behavior testable without a provider/model.

The implementation uses finite JSON-compatible numeric seconds. It does not round the
average before building the result. The exact proposed percentile algorithm for the
optional IQR tool is linear interpolation over sorted values at `(n-1)*p`; this avoids
an implicit dependency on a library's default quantile convention. Recurrence ties are
returned as all top IDs in lexical order rather than selecting a misleading arbitrary
single record.

Alternative considered: allow the agent to calculate counts, duration, or reference
direction. Rejected by ADR-100 through ADR-103 and ADR-123 through ADR-124.

### Model optional tools as a run-local registry with an application-owned ledger

The tool registry owns the current/reference data handles and exposes only the three
accepted deterministic optional capabilities. The agent can request an empty-object call
by registered name; the executor records ordinal and outcome, limits all attempts to ten,
and disallows unknown or scope-expanding calls. Only `failed|timeout` names/statuses
project into `optional_tool_execution`; successful and `not_applicable` outputs remain
transient.

The PydanticAI adapter receives an injected `Model`, exposes no provider/model default,
sets no corrective model or tool-validation retry loop, and translates framework events
to the domain agent outcome. It validates the strict completion before it reaches the
builder: `overall_importance=none`, another invalid controlled value, unknown/missing
completion fields, and malformed findings are `agent_failed`, not builder failures.
The exact prompt and model settings remain adapter-private and are not domain/public
contracts. Its request projection excludes opaque query, provider configuration/payload,
reference records, and all cross-Lens/knowledge data.

Alternative considered: let PydanticAI own the ledger and maximum budget. Rejected:
domain-owned enforcement remains inspectable and independent of framework semantics.

### Explicitly propose the missing result-contract decisions for approval

The following are deliberate implementation-contract proposals, not retrospective
architecture changes. They must be approved with this OpenSpec before implementation:

| Decision | Proposed rule | Why it is needed |
| --- | --- | --- |
| Evidence references | Exact ASCII `alert://` URI grammar: UTF-8 dynamic segments, RFC 3986 unreserved literals only, uppercase `%HH`, exact segment shapes, and single-target resolution | Lets the builder reject malformed/non-canonical/ambiguous references deterministically without raw/transient data. |
| Multiple partial causes | `invalid_records/current_normalization` takes precedence over `reference_unavailable/reference_periods` | Current evidence loss is the stronger public limitation; secondary causes remain operational. |
| Builder failure | fail with `result_validation_failed/alert_result_builder` and no artifact | Gives the existing terminal LensRun a stable structured reason for contract rejection. |
| Duration precision | finite JSON seconds; unrounded arithmetic mean | Makes duration validation/persistence testable while retaining the architecture's seconds semantics. |
| IQR/tied recurrence detail | interpolation index `(n-1)*p`; return every lexical tied top ID | Makes the accepted optional deterministic analyses reproducible without inventing severity categories. |

No unresolved architecture decision remains that changes the selected approach after
these proposals are approved. Jira transport/mapping and production model/provider
questions remain intentionally non-blocking behind ports.

### Use strict AlertAnalysisResult variants and minimal runtime correlation

The result builder is the sole constructor of `completed` and `partial`
AlertAnalysisResult 1.0. It receives only strict valid agent output, then validates
identity correlation, UTC time/window, provider provenance, exact omission/presence
rules, status/count/duration/comparison invariants, failed/timeout trace projection,
canonical evidence-reference syntax, and exact-one target resolution. Contract-invalid
agent output is mapped upstream to `agent_failed`; only contextual/final-result failure
maps to `result_validation_failed/alert_result_builder`. It produces the existing
persistence envelope so the repository retains its generic role and does not understand
Alert analytical sections.

No database migration is required: the current type-discriminated artifact table and
runtime contracts already permit completed/partial Alert results and prohibit failed
ones. No definition/API contract is modified.

Alternative considered: validate only a loose JSON dictionary in the pipeline or
repository. Rejected because ADR-120 assigns Alert contract ownership to the builder and
the repository must remain generic.

## Risks / Trade-offs

- [No real provider adapter exists yet] → use typed fake ports for this internal pipeline;
  later integration supplies a Jira adapter without changing downstream analysis.
- [An injected model cannot produce live value by itself] → keep deterministic adapter
  tests and composition out of scope; later provider configuration is explicit work.
- [All current records are retained, with no truncation policy] → preserve the accepted
  MVP contract and defer volume limits until a provider integration provides evidence.
- [One partial reason hides simultaneous incompleteness] → approve the explicit
  precedence and retain secondary details only in operational diagnostics.
- [PydanticAI minor behavior can change] → retain the existing constrained dependency,
  isolate it in one adapter, and test the domain-owned call budget.

## Migration Plan

1. Deploy the new internal Alert package and PydanticAI adapter with no migration or API
   route.
2. Compose the pipeline only from a future runtime/orchestration capability that creates
   Alert LensRuns; this change itself does not add that composition point.
3. Roll back by removing the unused application path before rolling back code. Existing
   completed/partial Alert JSON artifacts remain readable by generic runtime retrieval;
   no destructive database action is required.

## Open Questions

None for this implementation-ready change after approval of the explicitly proposed
pipeline-local decisions above. Jira transport, credentials, mapping, retry/timeout,
pagination, and production model/provider choices are intentionally deferred and do not
change this task breakdown.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md` — deterministic control
  plane and bounded agentic sub-processes.
- `docs/architecture/03_ADR_log.md` — ADR-089 through ADR-132 define Alert scope,
  evidence, agent, tool, result, and persistence boundaries; ADR-152 fixes PydanticAI
  as the accepted agent-framework integration behind the infrastructure adapter.
- `docs/architecture/04_pipeline_and_agent_concepts.md` — pipeline/stage/agent/tool
  ownership model.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — terminal,
  usable, failed-Alert absence, and persistence semantics.
- `docs/architecture/10_open_decisions_and_backlog.md` — confirms excluded real provider
  and production-agent work plus the local details resolved as proposals here.
- `docs/architecture/13_alert_lens_and_analysis_concept.md` through
  `20_alert_analytical_tools.md` — accepted Alert contracts and stage-specific behavior.
- `openspec/specs/observation-definition-api/spec.md` — existing immutable Alert Lens
  fields and opaque selector behavior.
- `openspec/specs/runtime-persistence/spec.md` — existing terminal artifact correlation
  and Alert failed-result absence.
