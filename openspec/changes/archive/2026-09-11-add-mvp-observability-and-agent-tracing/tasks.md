## 1. Diagnostic foundation and configuration

- [x] 1.1 Add the application-owned structured operational event emitter, typed allowlisted fields, bounded secret-scrubbed traceback formatting, and no-op diagnostic observer; verify unit tests cover deterministic JSON, UTC timestamps, UUID/scalar handling, configured-secret sentinels, traceback preservation, and rejection of arbitrary payload fields.
- [x] 1.2 Add disabled-by-default `AGENT_TRACE_ENABLED` settings validation and fixed `tmp/agent-traces` resolution; verify settings tests accept enabled development mode, reject every non-development enabled mode before composition, and create no trace directory while disabled.
- [x] 1.3 Wire the diagnostic components through application lifespan/production composition without changing public or domain contracts; verify composition tests select no-op versus development trace implementations and missing OpenRouter configuration emits only safe operational metadata.

## 2. Prometheus failure classification and logging

- [x] 2.1 Replace collapsed private production acquisition failures with closed safe categories and bounded scalar metadata for source/target, authentication/query/status, multiple-series, warning, oversized/invalid response, invalid sample, timeout, and transport cases; verify provider tests exercise every category while preserving retry, deadline, response-size, one-series, and public outcome semantics.
- [x] 2.2 Emit one correlated Metric acquisition failure event at the pipeline/adapter boundary using ObservationRun, LensRun, Lens, source, category, attempt/count/status, and duration fields; verify integration tests distinguish the reproduced multiple-series and query-rejected cases without logging raw queries, labels, provider bodies, credentials, or authorization values.
- [x] 2.3 Verify existing failed Metric artifacts and public run-detail projections remain byte-shape compatible with `current_metric_acquisition_failed` and contain no new internal diagnostic fields.

## 3. Application error-boundary coverage

- [x] 3.1 Instrument startup, FastAPI unhandled errors, and safe API error normalization while keeping expected validation/business rejection behavior distinct; verify backend tests capture unexpected tracebacks and confirm expected 4xx paths are not logged as internal errors.
- [x] 3.2 Instrument Observation execution initialization, orchestration stages, fan-out/deadline handling, managed background tasks/recovery, and persistence failures with available correlation; verify lifecycle tests prove logging does not change cancellation propagation, durable transitions, recovery behavior, or exception identity.
- [x] 3.3 Instrument Metric/Alert agent, knowledge retrieval, Observation reasoning, deterministic validation, and report generation normalization boundaries with safe role/phase/category/model/request metadata; verify focused tests distinguish provider, timeout, policy, schema, grounding, and internal failures without prompt/output/tool content in operational logs.
- [x] 3.4 Add a maintained error-boundary coverage matrix to backend tests or development documentation and verify each currently application-owned `except` normalization path is represented by either an operational event assertion or an explicit expected-rejection exemption.

## 4. Full development agent interaction traces

- [x] 4.1 Implement the versioned no-op/file trace recorder, invocation context, PydanticAI message/schema/settings allowlist serializer, known-secret redactor, and atomic per-invocation writer; verify tests cover fixed safe paths, exact message-part round trips, provider-metadata omission, secret replacement, atomic replacement, and non-fatal `trace_write_failed` behavior.
- [x] 4.2 Wrap every Metric and Alert PydanticAI `agent.run` call in a distinct capture scope and record model-visible instructions/input, chronological requests/responses, admitted tool calls/results, validated completion or framework failure, timing, usage, and correlation; verify successful, invalid-output, provider-failure, timeout, policy-rejection, cancellation, multi-request tool, and parallel-Lens tests.
- [x] 4.3 Wrap Observation Reasoning finding, hypothesis, and overall-state calls and Report generation in distinct capture scopes; verify each phase has a separately discoverable artifact and failed/interrupted calls retain available message history.
- [x] 4.4 Append correlated deterministic finding-freeze, hypothesis-grounding, final-result, and report-render validation outcomes without moving validation ownership into infrastructure; verify a syntactically valid hypothesis with unavailable knowledge references records the exact model output and the later grounding rejection category.
- [x] 4.5 Add end-to-end execution coverage with instrumented fake models proving one run directory reconstructs all attempted agent interactions in phase order, concurrent Lens traces never interleave, disabled mode writes nothing, and trace failures never change the final ObservationRun/LensRun outcomes.

## 5. Metric query preflight in the editor

- [x] 5.1 Add exact frontend types and an API client for the existing Metric preflight request/success/failure contracts; verify client tests send exactly source ID, unchanged query, and `validation_window.duration=15m` with no draft, credential, trace, or log fields.
- [x] 5.2 Add isolated idle/pending/valid/invalid/request-failure preflight state and the accessible `Validate query` action to the Metric Lens editor; verify component tests cover enablement, retry, valid labels/window/sample count, zero series, multiple bounded label sets, rejected PromQL text, authentication/unavailable/generic request errors, and unchanged Apply behavior.
- [x] 5.3 Clear validation on every source/query edit, cancel or supersede prior requests, abort on editor exit, and suppress obsolete responses; verify race tests cover late success/failure after input change, repeated validation, cancellation, and navigation between draft Lenses.
- [x] 5.4 Verify UI tests render provider messages and label values only as text, never rewrite PromQL, never mutate the Observation draft during preflight, and retain aggregate-only Lens persistence semantics.
- [x] 5.5 Verify the implemented interaction and accessibility behavior conforms to accepted UI Direction v1.7 and that backend operational logs/full traces remain absent from browser-visible state and controls.

## 6. Developer documentation and safety verification

- [x] 6.1 Update `.env.example` and `docs/development-guide.md` with trace enablement, default-off/development-only enforcement, fixed lookup path, correlation workflow, sensitive-content warning, disk-growth behavior, and explicit cleanup instructions; verify examples contain placeholders only and no trace setting is added to frontend environment files.
- [x] 6.2 Add a local manual verification scenario for a multiple-series Prometheus query and an invalid-grounding agent completion, confirming operational logs identify safe causes and enabled traces expose exact model interactions while public run APIs remain unchanged.
- [x] 6.3 Run targeted backend and frontend tests for diagnostics, provider acquisition, execution lifecycle, agent adapters, reasoning/reporting, and Metric editor preflight; record and resolve any failures without weakening secret, lifecycle, or aggregate boundaries.
- [x] 6.4 Run `make check` as the final local verification and report every failure accurately before archive or pull-request preparation.
