## Why

Safe runtime reason codes currently collapse distinct provider, agent, validation, and orchestration failures, leaving a trusted MVP developer unable to determine why an execution failed. The MVP needs bounded backend observability and an opt-in exact agent-interaction trace so end-to-end manual testing is functional, failures are correlatable, and invalid Prometheus queries can be corrected before execution.

## What Changes

- Add correlated backend operational logging for application-owned handled, normalized, and unhandled errors across startup, API, execution, provider, agent, knowledge, reporting, background-task, and persistence boundaries.
- Preserve safe internal Prometheus failure categories and log enough bounded metadata to distinguish query rejection, multiple series, source/authentication/transport/timeout, oversized response, and invalid response conditions.
- Add disabled-by-default, development-only full tracing for Metric, Alert, Observation Reasoning, and Report model interactions, including exact model-visible instructions/input, schemas, chronological requests/responses, admitted tool calls/results, validated output or validation failure, timing, and usage.
- Store full traces as sensitive ephemeral backend artifacts outside PostgreSQL and source control, with explicit developer cleanup and no public trace endpoint or UI viewer.
- Integrate the existing Metric preflight API into the Metric Lens editor as an advisory `Validate query` workflow with actionable zero-series, multiple-series, provider rejection, authentication, timeout, unavailable, and success feedback.
- Improve backend/UI troubleshooting guidance through existing safe reason codes and correlation identifiers without exposing raw traces, prompts, stack traces, provider responses, credentials, or filesystem paths through the public API.
- Document local configuration, trace sensitivity, inspection, correlation, and cleanup. No external observability platform or new dependency is added.

## Capabilities

### New Capabilities

- `runtime-observability`: Correlated backend operational logging, safe diagnostic classification, and opt-in development-only full agent interaction tracing.

### Modified Capabilities

- `observation-management-ui`: Add advisory Metric query preflight and actionable validation feedback to the existing aggregate-owned Metric Lens editor.

## Impact

- Backend: settings, application/error boundaries, execution and provider adapters, PydanticAI infrastructure adapters, and local trace serialization/storage.
- Frontend: Metric Lens editor state, API client integration, accessible validation results, stale-result invalidation, and tests.
- UI authority: UI Direction v1.7 and its implementation handoff explicitly govern the advisory Metric query preflight interaction.
- Public API: no new endpoint; the existing Metric preflight endpoint and existing safe run contracts are reused without exposing trace content.
- Persistence: no database migration and no trace storage in PostgreSQL.
- Dependencies: none added, removed, or replaced; use Python logging and the installed PydanticAI message capture/serialization facilities.
- Operations: full traces can contain sensitive operational context and consume local disk until explicitly removed.

## Architecture References

- `docs/architecture/03_ADR_log.md` — ADR-152, ADR-169, ADR-170, and ADR-171.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — safe runtime reasons, public run-detail non-exposure, and reasoning/retrieval boundaries.
- `docs/architecture/10_open_decisions_and_backlog.md` — production observability capabilities that remain Open.
- `docs/architecture/01_observation_lens_concept.md` — one Metric Lens observes one metric.
- `docs/ui/ui_implementation_handoff_v1.md` — UI Direction v1.7 advisory preflight behavior, aggregate-owned Metric Lens editor, and trusted MVP UI boundaries.
