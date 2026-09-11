## Context

See `proposal.md` for motivation. The backend currently normalizes failures into safe runtime reasons at many local `except` boundaries but has no application logging layer. Production Metric acquisition intentionally collapses several provider outcomes, while the separate Metric preflight adapter already returns actionable query-authoring feedback. PydanticAI adapters construct a fresh agent per role invocation and existing wrapper models already intercept every provider request/response for tool-policy enforcement.

The installed `pydantic-ai-slim` 2.36.0 exposes `capture_run_messages()` and `ModelMessagesTypeAdapter`, including partial message history for failed or interrupted calls. Agent inputs already carry ObservationRun/LensRun identities through framework-neutral contracts. The current public run API explicitly excludes prompts, model/framework messages, acquisition diagnostics, and execution internals. UI Direction v1.7 explicitly admits advisory Metric query preflight while keeping backend logs and full traces out of the browser.

## Goals / Non-Goals

**Goals:**

- Make every application-owned error boundary operationally visible with safe correlation.
- Preserve enough internal Prometheus classification to identify why acquisition failed.
- Reconstruct exact model-visible agent exchanges during explicitly enabled local development tracing, including invalid output before normalization.
- Keep diagnostics observational: logging/tracing failure must never alter runtime semantics.
- Reuse the existing Metric preflight API to prevent avoidable one-series query mistakes during configuration.

**Non-Goals:**

- A production telemetry backend, log shipper, metrics dashboard, distributed trace system, or alerting facility.
- PostgreSQL persistence, lifecycle management, automatic retention, or public download/view APIs for traces.
- Prompt/model tuning, agent retries, fallback behavior, failure propagation changes, or analytical-contract changes.
- Raw Prometheus query/provider-response logging or automatic query rewriting.
- Authentication/authorization or support for untrusted-network exposure.

## Decisions

### 1. Emit one-line structured application events through standard-library logging

Add a small application-owned diagnostic module that emits deterministic JSON objects through a named Python logger inherited by the existing Uvicorn backend output. Events use an allowlisted envelope:

```text
timestamp, level, event, category,
observation_run_id?, lens_run_id?, lens_id?,
agent_role?, phase?, stage?, component?,
model?, request_ordinal?, attempt_count?, duration_ms?,
http_status?, observed_series_count?, exception_type?, traceback?
```

Call sites provide typed scalar fields rather than arbitrary dictionaries. UUIDs and enum-like strings are serialized canonically. Expected API validation/business rejections remain access/domain events rather than internal errors. Unexpected exception tracebacks are formatted through the diagnostic module, scrubbed of known configured secret values, and bounded before emission; callers do not use raw `logger.exception(...)` on provider/framework exceptions.

This module is used at the boundaries that currently catch or normalize failures. Uncaught HTTP exceptions receive a final application exception handler solely for safe logging and are re-raised/returned according to existing FastAPI behavior. Execution/persistence boundaries keep their existing propagation and terminalization rules.

Alternative considered: adopting structlog or an OpenTelemetry SDK. Rejected because the MVP needs no new dependency or external telemetry architecture.

### 2. Carry safe Prometheus classifications to the correlated pipeline boundary

Refine private production acquisition outcomes so `_AttemptFailure`-style values retain a closed internal category plus bounded scalar metadata. Response classification distinguishes at least target/source resolution, authentication/status rejection, provider query error kind, multiple-series response, warning presence, response size/shape/sample rejection, timeout, and transport failure. `limit=2` still bounds cardinality work; `multiple_series_returned` means at least the observed bounded count and does not claim total provider cardinality.

Low-level provider code does not log raw transport objects. It returns the safe internal classification to the Metric pipeline, where the execution context supplies ObservationRun/LensRun correlation for one terminal operational event. Existing `MetricSeriesAcquisitionOutcome`, failed Metric artifact, and public `current_metric_acquisition_failed` behavior remain stable.

Alternative considered: exposing raw provider errors in run detail. Rejected because it conflicts with the accepted public contract and is unnecessary when safe logs and explicit preflight serve different audiences.

### 3. Use a dedicated backend trace recorder around each PydanticAI invocation

Add an infrastructure-owned trace recorder with a disabled no-op implementation and an enabled development file implementation. Production composition injects the recorder into Metric, Alert, Observation Reasoning, and Report PydanticAI adapters; framework-neutral agent interfaces do not gain PydanticAI types.

Each adapter creates a fixed trace context from its typed request before calling `agent.run`:

```text
trace_version
invocation_id
observation_run_id
lens_run_id? / lens_id?
agent_role
phase
model
started_at / finished_at / duration_ms
terminal_state
```

One `capture_run_messages()` scope surrounds exactly one `agent.run`, satisfying the framework's first-run-per-scope behavior and isolating concurrent Lens tasks through context-local state. Existing wrapper models also send allowlisted model settings, function/output tool schemas, and request ordinal metadata to the recorder. `ModelMessagesTypeAdapter` provides the base message serialization, followed by an application allowlist/redaction pass that removes provider transport metadata and known configured secrets while retaining exact model-visible message parts.

The adapter records its strict typed completion or framework validation exception. A small framework-neutral diagnostic observer, injected only where deterministic post-adapter validation occurs, appends correlated validation events such as finding freeze, hypothesis grounding, overall-result building, or report rendering. This lets the trace distinguish malformed framework output from a syntactically valid completion rejected by domain grounding without moving validation ownership into infrastructure.

Alternative considered: logging prompts and outputs directly to the operational logger. Rejected because full content is sensitive, verbose, hard to correlate under concurrent execution, and unsafe as an always-on default.

### 4. Store one atomic JSON artifact per invocation under a fixed ignored root

Enabled traces are written beneath:

```text
tmp/agent-traces/<observation_run_id>/<invocation_id>-<role>-<phase>.json
```

Only server-generated UUIDs and closed role/phase values participate in paths. A temporary sibling file plus atomic replacement prevents readers from seeing a partially serialized final artifact; file work runs outside the event loop. Follow-up deterministic validation updates use the same safe rewrite path. Concurrent invocations never share a file.

The existing `tmp/` ignore rule keeps artifacts out of source control. No automatic deletion is introduced. The development guide documents sensitivity, the fixed lookup convention, disk growth, and explicit cleanup. Diagnostic write/serialization errors are caught, safely logged as `trace_write_failed`, and do not replace the agent's original result or exception.

Alternative considered: a database trace table. Rejected because traces are non-authoritative, sensitive, high-volume diagnostics and would introduce migration/retention/public-read pressure.

### 5. Gate tracing through backend settings before composition

Add `AGENT_TRACE_ENABLED` with default `false`. Settings validation rejects `true` unless `APP_ENV=development`. The trace root remains fixed under the repository's ignored `tmp/agent-traces` directory to avoid arbitrary filesystem destinations. The setting is documented in `.env.example`; no `VITE_*`, API, or Observation field controls it.

At startup, composition selects either the no-op or file recorder. Missing OpenRouter configuration still uses the existing unavailable agents and emits safe operational configuration events; because no model invocation occurs, it creates no fabricated interaction trace.

Alternative considered: a runtime UI toggle. Rejected because the unauthenticated API must not activate sensitive backend capture or disclose its state.

### 6. Treat known secrets and model-visible content differently

The recorder builds a redaction set from non-empty server-configured secret values without ever logging that set. Known values are replaced with a fixed `[REDACTED]` marker in the final serialized representation. Header/cookie/credential-shaped provider metadata is dropped structurally, and only explicitly selected usage/model/message fields survive.

Exact model-visible content is retained after known-secret scrubbing because reconstructing that content is the feature's purpose. It can include normalized alert text, structured Metric evidence, findings, or retrieved statements, so every artifact and documentation warning treats the entire trace directory as sensitive.

Alternative considered: aggressively redacting arbitrary strings. Rejected because it would make the trace non-faithful and still could not reliably infer every domain-sensitive value.

### 7. Integrate preflight as isolated editor state

Add a typed frontend client for the existing `POST /api/v1/observation-lens-validations/metric` contract. The Metric Lens editor owns a request sequence/AbortController and an isolated state machine:

```text
idle -> pending -> valid | invalid | request_failure
```

`Validate query` sends only the selected source, exact query, and fixed `15m` duration. Any source/query edit clears the current result. A later request supersedes the previous one, and editor cancellation/unmount aborts it. This mirrors existing capability-load race handling without placing preflight data in the Observation draft reducer.

The result view renders success window/labels/sample count; zero/multiple-series and query rejection details; and safe API authentication/availability/failure messages. Multiple label sets use a compact semantic list rather than a table abstraction. React text rendering is retained for untrusted provider strings. Validation never rewrites the query or gates `Apply changes`.

Alternative considered: validate automatically on every edit or require success before Apply. Rejected because it would generate avoidable provider traffic and incorrectly block valid sparse queries during transient source conditions.

### 8. Preserve public run contracts and use existing correlation

No field is added to run list/detail, Metric result, or structured reason contracts. Existing run and Lens-run identifiers remain the bridge from the UI to backend operational output and the fixed trace directory. Human-readable UI reason improvements may only map existing safe codes; they cannot expose trace paths or internal categories.

## Risks / Trade-offs

- **[Full traces expose operational content]** → Disabled by default, development-only settings validation, fixed ignored backend path, known-secret redaction, no HTTP exposure, and explicit sensitivity documentation.
- **[A traceback embeds a configured secret in its exception message]** → Central formatting scrubs all known configured secret values before emitting a bounded traceback; raw exception logging is prohibited at instrumented boundaries.
- **[Trace serialization masks or replaces the original application outcome]** → Recorder calls are fail-open for diagnostics and emit only a secondary safe `trace_write_failed` event.
- **[Concurrent runs interleave or overwrite messages]** → One capture scope and one UUID-named artifact per invocation; no shared append stream.
- **[Trace capture adds memory and I/O cost]** → No-op recorder by default; enabled work occurs only in development and file I/O runs outside the event loop.
- **[No automatic retention can consume disk]** → Use the ignored temporary root, document inspection/cleanup, and leave automated retention to a later production observability decision.
- **["All errors" coverage drifts as new boundaries are added]** → Central helper plus a boundary coverage matrix in tests/documentation; public interface docstrings require future adapters to use the same diagnostic boundary.
- **[Preflight result becomes stale]** → Clear on every source/query edit and suppress obsolete responses.
- **[Preflight succeeds but a later run fails]** → Present preflight as a point-in-time advisory check, never as a persistence or future-availability guarantee.

## Migration Plan

1. Add the no-op operational/trace composition and settings validation without enabling full tracing by default.
2. Add safe logging and diagnostic classifications while retaining all public/durable contracts.
3. Instrument agent invocations and deterministic validation boundaries.
4. Add Metric editor preflight and documentation.
5. Verify default-off and enabled-development modes, then run the full repository check.

Rollback requires disabling `AGENT_TRACE_ENABLED` and reverting code/configuration changes; no database downgrade exists. Previously written local trace files remain sensitive and require explicit developer removal.

## Architecture References

- `docs/architecture/03_ADR_log.md`: ADR-152 keeps PydanticAI infrastructure-only; ADR-169 fixes production agent composition; ADR-170 fixes the trusted unauthenticated boundary; ADR-171 authorizes the two-level diagnostic model used here.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: existing durable/public reasons and diagnostic non-exposure remain unchanged.
- `docs/architecture/10_open_decisions_and_backlog.md`: log aggregation/export, dashboards, alerting, distributed tracing, and automatic retention remain unresolved and outside this design.
- `docs/architecture/01_observation_lens_concept.md`: preflight feedback enforces rather than changes the one-Metric-Lens/one-metric boundary.
- `docs/ui/ui_implementation_handoff_v1.md`: UI Direction v1.7 makes preflight advisory nested-editor validation and does not persist a standalone Lens or expose backend internals.
