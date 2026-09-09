## Why

Observation execution and its durable artifacts already exist, but no public runtime API or frontend screen lets an engineer start a run, monitor active work, browse run history, or inspect a completed result. This change makes that existing capability usable while preserving the separation between execution status and analytical state.

## What Changes

- Add a public Observation-run API that launches one existing Observation asynchronously for a validated finite UTC analysis window, returns the created run promptly, lists all runs newest-first, and retrieves one complete run-detail projection. Managed execution tasks run under the explicitly single-process MVP application host, are cancelled durably during graceful shutdown, and startup reconciliation marks any active records left by an interrupted process as `cancelled` before accepting new launches.
- Fail closed on detached persistence uncertainty: stop launch admission with `503`, quiesce managed tasks, and retry only durable cancellation/reconciliation until no active record remains. Startup does not become ready when reconciliation cannot commit.
- Enforce at most one `pending` or `running` ObservationRun per Observation across all callers. A conflicting launch is rejected until the existing run becomes terminal; later re-runs still create fresh runtime identities.
- Add a top-level `Runs` screen that loads the complete run history without pagination, shows a concise Observation/run summary, keeps execution status independent from the optional analytical state, and filters locally by Observation, execution status, and analytical state.
- Add a `Run Observation` dialog that selects an existing Observation and resolves a finite analysis window from relative presets or a deliberately limited Grafana-style absolute expression set: `now`, `now-15m`, and `now-1h`.
- Return to the Runs list after a successful launch, show the new active row, prevent another launch for the same Observation, and automatically refresh while active runs exist. Manual refresh and explicit loading, empty, error, and retry states remain available.
- Add a run-detail foundation that presents lifecycle and window metadata, Lens outcomes, relationship evaluations, Observation findings, hypotheses, limitations, traceability, and the Markdown report when each artifact exists. Active, degraded, failed, cancelled, and not-yet-produced states remain explicit rather than being inferred as analytical outcomes.
- Complete production agent composition for executable runs by wiring the existing Metric and Alert PydanticAI adapters to OpenRouter. Metric, Alert, Reasoning, and Report default to the same existing model at this stage while retaining role-specific settings; Metric and Alert use the existing prompts as their initial system prompts, a 120-second request timeout, and a 12,288-token maximum output. Alert execution admits at most ten optional-tool attempts and eleven total model requests, reserving at most one final-completion request after tool exhaustion.
- Supply public launches with server-owned, environment-configurable execution defaults of four concurrent Lens runs and a 300-second per-Lens deadline; clients cannot override these policies.
- Keep application startup and launch available without an OpenRouter credential. Such a run is still created and reaches the existing safe failed/degraded paths without exposing configuration or credential details.
- Compose Observation Reasoning with an explicit empty KnowledgeRetriever until a later approved knowledge-backend change; retrieval returns no items and never fabricates knowledge or hypotheses.
- Keep the verification-focused MVP unauthenticated under an explicit trusted single-user/internal deployment boundary. Run endpoints and operational artifacts must not be exposed directly to an untrusted network; authentication, authorization, identities, and multi-user policy remain a later change.
- Use the accepted ObserveAI shell, tokens, domain status components, restrained dashboard organization, and lightweight list/card patterns from existing screens. No new frontend or backend dependency is introduced.
- Keep multi-process/multi-worker execution hosting, authentication/authorization, cancellation controls, scheduling, retry/resume, deletion, export beyond the already persisted Markdown presentation, advanced filter dimensions, and list pagination out of scope.

## Capabilities

### New Capabilities

- `observation-run-api`: Public launch, full-history list, and correlated run-detail read contracts over the existing Observation execution and persisted artifacts.
- `observation-runs-ui`: Runs navigation, launch/time-range interaction, newest-first history, status/state filtering, automatic refresh, and the initial run-detail information architecture.
- `production-agent-composition`: Server-owned OpenRouter/PydanticAI composition, defaults, prompts, limits, missing-credential behavior, and the explicit no-knowledge fallback required by launched runs.

### Modified Capabilities

- `observation-execution`: Permit a public asynchronous launch boundary, expose the initialized run identity before terminal completion, and reject concurrent active execution of the same Observation without weakening the existing orchestration contract.
- `runtime-persistence`: Enforce one active ObservationRun per Observation and provide deterministic read projections needed by run list/detail APIs while preserving runtime and artifact immutability.

## Impact

- Backend: a new runtime API/service boundary, production agent/execution composition, managed in-process `asyncio` task lifecycle, safe response contracts, repository queries, settings, and database enforcement for active-run uniqueness.
- Database: one Alembic migration adding the PostgreSQL active-run index plus a persisted RelationshipEvaluation ordinal backfilled from current immutable Relationship definition order; no runtime or analytical artifact is deleted or semantically rewritten.
- Frontend: activate the existing `Runs` navigation item; add list, launch dialog/time picker, filter controls, status/state presentation, automatic polling, detail route, artifact sections, API types, and focused tests.
- Public API: add asynchronous launch plus run list/detail endpoints; existing Observation Definition endpoints and analytical artifact contracts remain unchanged.
- Security/deployment: deliberately no application authentication for MVP validation; deployment is restricted to a trusted single-user/internal environment and requires external network controls rather than broad public exposure.
- Dependencies: none added, removed, or replaced.
- Architecture/UI documentation: accepted ADRs now record the production Metric/Alert model composition and one-active-run/manual-trigger policy; corresponding Open backlog items, affected runtime/component text, changelog, and UI Direction v1.4 are synchronized before plan approval. Lens, relationship, reasoning, report, and existing cancellation semantics remain unchanged.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md` — top-level trigger, deterministic Observation workflow, strict JOIN, degradation, and lifecycle ownership.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — ObservationRun/LensRun states, terminality, failure propagation, correlation, persistence, and cancellation semantics.
- `docs/architecture/08_observation_analysis_result_contract.md` — Observation analytical state, findings, hypotheses, limitations, and traceability shown by run detail.
- `docs/architecture/09_report_agent.md` — presentation-only Markdown report boundary.
- `docs/architecture/07_observation_reasoning_agent.md` — bounded reasoning and injected KnowledgeRetriever boundary.
- `docs/architecture/16_alert_analysis_agent.md` — Alert prompt/model/budget ownership and agent scope.
- `docs/architecture/03_ADR_log.md` — ADR-152 PydanticAI integration, ADR-164 fresh identities for re-run, ADR-165 durable cancellation, ADR-166 frontend stack, ADR-167 UI authority, ADR-168 execution hosting/overlap, ADR-169 production agent composition, and ADR-170 trusted unauthenticated MVP access.
- `docs/architecture/10_open_decisions_and_backlog.md` — currently open production Metric/Alert model limits, execution-policy defaults, and trigger overlap policy resolved by the approved change.
- `docs/ui/frontend_ui_stack_adr.md` and `docs/ui/ui_implementation_handoff_v1.md` — accepted Runs/detail information architecture, semantic components, visual stack, and execution-versus-analysis presentation rules.
