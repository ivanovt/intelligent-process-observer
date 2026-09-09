## Context

See `proposal.md` for motivation and the five delta specs for observable behavior: `observation-execution`, `runtime-persistence`, `observation-run-api`, `observation-runs-ui`, and `production-agent-composition`. The repository already has durable ObservationRun/LensRun/artifact models, a framework-neutral orchestrator, provider and PydanticAI adapters, and internal coherent run retrieval. Production composition currently exposes only Observation Definition APIs, and the frontend has an inactive Runs navigation item with no runtime types or views.

The design must make a long-running workflow observable without adding a broker or distributed worker system. It must preserve the current caller-owned transaction boundaries, forward-only lifecycle, strict JOIN, type-aware Lens identity, safe failure reasons, cancellation behavior, and analytical/execution-state separation. Existing provider configuration and prompts must not cross the new public read boundary.

## Goals / Non-Goals

**Goals:**

- Reuse one orchestration implementation for synchronous internal execution and public detached launch.
- Return a durable run identity promptly, while making process ownership and shutdown behavior explicit.
- Provide small whitelisted public projections over already persisted runtime and analytical artifacts.
- Keep frontend list/filter/time-range/detail behavior easy to test without a new state, form, table, chart, or Markdown dependency.

**Non-Goals:**

- Durable distributed job delivery, multi-process task claiming, resumption, scheduling, cancellation UI, or retry of a prior run identity.
- Public mutation of execution policy or persisted runtime/artifact state.
- A final high-density analytical dashboard; the detail page is a semantic and component foundation for later refinement.
- Application authentication, authorization, user identity/audit attribution, or safe exposure to untrusted networks.

## Decisions

### 1. Split orchestration into initialize and continue operations behind one public manager

Refactor `ObservationExecutionOrchestrator` so its existing `execute(request, policy)` remains the framework-neutral end-to-end entry point but delegates to two reusable operations:

```text
initialize(request, policy)
  -> rejected preparation
  -> or committed InitializedObservationExecution

continue_execution(initialized, policy)
  -> existing fan-out, JOIN, relationships, reasoning, report, terminal outcome
```

A new application service, `ObservationRunManager`, owns the public launch lifecycle. It calls `initialize`, converts rejection/conflict outcomes at the API boundary, creates exactly one `asyncio.Task` for `continue_execution`, registers that task by run ID before returning, and consumes task results/exceptions in a done callback. It uses positive server-owned `ExecutionPolicy` settings with approved defaults `max_parallel_lens_runs=4` and `lens_deadline_seconds=300`, both environment-configurable and documented in `.env.example`.

The manager has explicit `ready`, `recovery_required`, and `shutting_down` states plus a monotonically increasing recovery generation guarded by one in-process state lock. Each public launch creates/registers a manager-owned initializer task and admission record `(admission_id, observation_id, generation)` under that lock before any database await. A preparation rejection or provably rolled-back transaction settles normally; cancellation, connection invalidation, commit error without a proven rollback, or another indeterminate transaction outcome requests recovery.

Initialization creates `ObservationRunAcceptanceSummary` from the initialized ORM/domain values in the committing transaction, including server-generated timestamps obtained through flush/returning, and detaches it before transaction exit. Its fixed launch-time fields are `status=running`, null reason/analysis/finish/duration, exact identity/window, and detail href.

After initialization commits, the task reacquires the state lock. If state remains `ready` at its captured generation, it atomically creates/registers the continuation and that immutable acceptance summary before removing the admission. If state/generation changed, it registers no continuation, releases no `202`, settles its session/admission, and leaves the committed run for reconciliation. The route serializes the captured object with no further database await. A very fast continuation may already be terminal, but the `202` remains an explicit acceptance-time representation; the immediate list poll supplies current durable truth.

The first recovery requester acquires the state lock, changes state to `recovery_required`, increments the generation, and closes admission. It cancels all registered older-generation initializers and continuations and awaits their completion plus transaction/session teardown. Only after their registries are empty may sequential reconciliation start, with one immediate attempt and five-second retries. Each attempt opens a fresh transaction, terminalizes every still-active record through the accepted cancellation operation, commits, and performs a fresh verification query. Only a verified empty active set returns the manager to `ready`. No initializer or analytical continuation is restarted. Later concurrent recovery requests join the same recovery task.

The FastAPI lifespan builds one production execution composition and manager. On graceful shutdown it moves to `shutting_down`, cancels and awaits all registered tasks, and does not complete while durable cancellation remains unverified. If an external supervisor hard-stops the process, the next startup owns recovery. On startup, before accepting requests, one reconciliation attempt must commit and verify no active record remains; failure raises from lifespan so the application never becomes ready. Normal runtime recovery continues retrying while the process remains alive.

This is explicitly a single-process MVP execution host consistent with plain Python/`asyncio`. The backend must be operated with one API process/worker while this capability is enabled. Startup reconciliation assumes sole task ownership and cannot distinguish a run owned by another live process. Multi-process deployment therefore remains unsupported until a separate durable ownership/lease or worker-coordination design is approved.

Alternatives considered:

- Keep the POST request open through terminal completion. This avoids task ownership but conflicts with prompt return-to-list behavior, makes client connection lifetime part of launch UX, and cannot return the running identity promptly.
- Use FastAPI `BackgroundTasks`. Its opaque lifecycle is a poor fit for tracked cancellation and awaiting shutdown.
- Add a broker/worker. This violates the approved modular-monolith MVP stack and is disproportionate to the feature.

### 2. Enforce same-Observation exclusion in PostgreSQL, not only in UI or memory

The manager maintains a lazily allocated per-Observation `asyncio.Lock` inside the single-process host. Launch acquires that lock, performs one durable active-run lookup, and—when none exists—keeps the lock through preparation and initialization commit. A found active row becomes a manager-owned `LaunchConflict(observation_run_id)` result distinct from `ObservationExecutionOutcome`; the API can safely return its stable identity even if the run terminalizes immediately afterward. Locks for different Observations remain independent and unused locks are removed after the guarded request.

Add a named PostgreSQL partial unique index on `observation_runs(observation_id)` where `status IN ('pending', 'running')` as defense in depth. Initialization remains one transaction, so an index loser rolls back the parent and all child inserts. After rollback the service performs exactly one active lookup: a found row becomes `LaunchConflict`; no row becomes `LaunchUnavailable(code="launch_admission_uncertain")` and requires a fresh client request. It never automatically retries initialization. Unrelated integrity failures remain infrastructure errors and enter the fail-closed recovery path where applicable. Although the database index is process-independent, it is only an overlap invariant and does not provide cross-process task ownership; it does not broaden the supported single-process deployment model.

The same Alembic revision adds a non-negative `position` column and unique `(observation_run_id, position)` constraint to `relationship_evaluations`. It first adds the column as nullable, backfills by joining each evaluation through its ObservationRun to the current immutable MVP Relationship definition with matching `relationship_id`, verifies every per-run ordinal set is unique and contiguous, and only then makes the column non-null. Any missing/ambiguous mapping aborts migration without guessing or changing analytical payloads. New evaluation-batch persistence enumerates the frozen definition order and writes the ordinal; detail ordering uses only the stored value.

Before creating the active-run index, the migration checks for duplicate active rows and aborts with an actionable message rather than rewriting historical state. Under the current application there is no public producer of active runs, so a clean database is expected. Startup reconciliation runs after migrations and before public launch availability.

Alternatives considered:

- UI-only disabling is race-prone and does not protect direct API callers.
- An in-memory lock alone does not cover direct persistence races or restart. The supported single process uses it for useful conflict identity, while the partial unique index remains the durable invariant.
- A broad unique constraint on Observation ID would incorrectly prevent immutable run history.
- Reconstruct Relationship order at read time from the current definition. That violates frozen-run independence and can drift after a future definition update; a persisted ordinal is the minimum stable projection.

### 3. Add a narrow run API with explicit summary and detail contracts

Create a dedicated run router/service rather than expanding Observation Definition response shapes:

```text
POST /api/v1/observation-runs
GET  /api/v1/observation-runs
GET  /api/v1/observation-runs/{observation_run_id}
```

`POST` accepts only concrete aware UTC timestamps. Time expressions remain a frontend interaction and never become a backend date-math language. The service validates the non-future finite window, invokes the manager, and returns `202` only after initialization commits.

`ObservationRunSummary` is shared by launch and list responses:

```text
id
observation: { id, name }
analysis_window: { from, to }
status
reason?
analytical_state?
created_at, started_at?, finished_at?, duration_seconds?
href
```

List retrieval joins the current immutable MVP Observation Definition only for identity/display name, orders by `created_at DESC, id DESC`, returns every row, and extracts `overall_state` only from a validated persisted ObservationAnalysisResult. It does not include full artifacts or accept pagination.

`ObservationRunDetail` embeds the summary plus ordered Lens run projections. The public response models import or wrap the exact existing domain types rather than restating them as permissive dictionaries:

| Detail member | Exact admitted contract |
|---|---|
| Metric `result` | schema-1.0 union of `CompletedSufficientMetricResult`, `CompletedInsufficientMetricResult`, `PartialMetricResult`, `FailedMetricResult` |
| Alert `result` | schema-1.0 union of `CompletedAlertAnalysisResult`, `PartialAlertAnalysisResult` |
| Relationship item | existing discriminated `RelationshipEvaluation`; persisted position orders the array but is not added to payload |
| Analysis | `ObservationAnalysisResult` schema 1.0 |
| Report | unversioned `ObservationReport` envelope |

The Alert result intentionally publishes all `CanonicalAlertRecord` fields—including provider-originated title/description, source status, provider importance, occurrence count, and `source_ref`—as operational evidence to the ADR-170 trusted operator. React renders every string as text/untrusted data. It does not publish `AlertProviderRecord`, malformed/rejected inputs, selectors/queries, transport responses, acquisition diagnostics, or successful optional-tool transient data.

LensRuns are ordered by canonical type/ID with run ID as a stable final tie-breaker; RelationshipEvaluations are ordered only by their persisted frozen-definition ordinal. Serialization uses strict Pydantic response models and whitelists the exact lifecycle/window fields named by the spec. It never serializes raw ORM objects, `execution_context`, provider configuration/query fields, credentials, prompts, task-registry data, or exception diagnostics. Stored domain payloads are revalidated and correlated before serialization; any invalid item fails the whole detail projection as safe `runtime_projection_invalid` rather than being dropped or exposed partially.

Alternatives considered:

- Put latest runtime data on Definition responses. That couples immutable configuration management to a separate runtime collection and does not serve cross-Observation history.
- Return raw persistence models/JSON. That risks leaking technical configuration and erases the public contract boundary.
- Create one endpoint per artifact. That adds request and routing complexity before the UI has an independent artifact-lifecycle need.

### 4. Extend repository reads without changing artifact ownership

Add focused repository operations for newest-first complete history, active-run lookup, startup reconciliation, and eager coherent detail loading. Summary retrieval is one ordered SQL statement selecting only required columns plus the analysis payload's `overall_state`.

Detail service opens a dedicated PostgreSQL `REPEATABLE READ`, read-only transaction before its first ORM query and keeps it through every `selectinload` query and response projection. This reuses the existing aggregate loader while ensuring parent, LensRun, Lens artifact, RelationshipEvaluation, ObservationAnalysisResult, and ObservationReport reads share one MVCC snapshot. It performs no writes and commits or rolls back before returning the detached strict response model. Default `READ COMMITTED` remains unchanged for ordinary write transactions.

Duration is derived only when timestamps make it truthful: `finished_at - started_at` for terminal runs or current display time minus `started_at` for active UI display. The API does not persist duration. Missing analysis remains `null`, including for early failure/cancellation. A failed report stage can therefore expose `status=failed` alongside a real analytical state.

Alternatives considered:

- Denormalize status/state/name into new columns. Existing data is already correlated and the MVP has no paging/scale requirement, so duplication and backfill are unjustified.
- Build one large JSON aggregation statement. It can provide one statement snapshot but duplicates validation/order logic in SQL and is harder to maintain for the broad first detail foundation.
- Reuse default `READ COMMITTED` across `selectinload` statements. It permits a terminal writer to commit between statements and expose a torn response.

### 5. Complete production agent and execution composition in application lifespan

Add role-specific `observation_metric_model` and `observation_alert_model` settings, each defaulting to the existing `openai/gpt-5.6-terra` value used by Reasoning and Report. Keep all four model settings independent even while defaults match. Add positive Metric/Alert model-request settings with defaults of 120 seconds and 12,288 output tokens. Extend the existing OpenRouter composition module to construct Metric and Alert PydanticAI models/adapters using the same API key and provider order/fallback policy already used by Reasoning and Report.

Promote the current Metric and Alert adapter prompt strings as their initial infrastructure-owned system prompts. Apply timeout/output bounds at each model request without changing the Metric four-request ceiling or top-level 300-second Lens deadline. Extend the Alert wrapper with an invocation-local request counter and admission state: at most eleven model requests, at most ten tool attempts, and after clean exhaustion exactly one remaining completion-only request. The wrapper removes domain tool availability for that final request and rejects any emitted tool call before registry execution or ledger insertion. For multi-call responses it admits calls in response order only through remaining capacity; an excess call causes policy failure and no continuation. No prompt/model setting becomes definition or run input.

Add one execution composition function that wires the database session factory, definition loader/repositories, Metric provider and pipeline, Alert provider resolver, Metric/Alert agents, Relationship Evaluator, Observation Reasoning executor, and Report executor into the orchestrator. Until a knowledge backend is separately approved, inject an `EmptyKnowledgeRetriever` that returns `()` for every valid request. This preserves the framework-neutral port and bounded retrieval behavior without selecting a store, index, embedding, ranking, or permission model; empty retrieval cannot validate a knowledge-grounded hypothesis. The route receives only the manager/service.

When `OPENROUTER_API_KEY` is absent, lifespan remains healthy and composition injects unavailable implementations behind all model agent ports. Metric/Alert adapters map those outcomes through existing partial/failed rules, and Observation Reasoning ultimately fails the run with its existing safe model-failure reason. The launch is still accepted and produces durable history as requested; no missing-credential fact or secret crosses the API. Configuration changes affect only future fresh launches after application restart.

Alternatives considered:

- Instantiate dependencies per request. That duplicates composition, makes task lifetime outlive request-owned objects, and complicates cleanup.
- Reject launch when the key is absent. The approved behavior is to retain a durable failed attempt, and provider availability may also change after launch.
- Share one model-name setting across roles. Separate settings preserve role evolution without adding another provider or leaking infrastructure into domain contracts.
- Select a real knowledge backend in this change. Knowledge storage/retrieval architecture remains explicitly Open, so the safe empty adapter avoids inventing that decision and is replaceable behind the existing port.

### 6. Keep frontend run state inside a bounded feature module

Add `frontend/src/features/runs/` with strict API types/client functions, pure projection/filter/time-range helpers, `RunsPage`, `RunDialog`, `RunDetailPage`, and small semantic subcomponents. Activate the shell's Runs `NavLink` and add `/runs` and `/runs/:observationRunId` routes. Reuse existing `Button`, `Field`, `Input`, `Select`, `InlineNotice`, and `PageHeader`; add only generic dialog/tab primitives actually required and keep run semantics in project-owned components.

`RunDialog` owns a separate abortable definition-request state machine on every open: `loading | error(lastError) | empty | success(definitions)`. It calls the existing list-definitions client independently of run history, preserves backend order, and uses history only to mark currently known active IDs. Retry replaces error state; close aborts and discards dialog request state; reopen fetches current definitions. Confirmation requires `success`, a selected non-active definition, and a valid resolved time range. Empty state links to `/observations/new`.

The list uses semantic list/table markup and lightweight rows, not TanStack Table. Filter state is one typed object with `observationId`, `status`, and `analyticalState`, and filtering is a pure ordered predicate pipeline. A neutral sentinel represents unavailable analysis. This structure allows another filter descriptor/predicate later without changing API items or row semantics.

Alternatives considered: add a server-state cache or table framework. Current full-list polling, three filters, and two routes do not justify either dependency.

### 7. Resolve time ranges with a closed client-side parser

Represent presets as data entries containing label and millisecond duration. The absolute parser accepts only exact trimmed tokens `now`, `now-15m`, and `now-1h`; it does not implement general Grafana grammar. Confirmation captures `now` once, resolves both endpoints against it, validates `from < to`, renders the concrete local/UTC range for review, and serializes ISO UTC values.

The initial selection is absolute `now-15m` to `now`. Choosing a preset updates the resolved preview without rewriting arbitrary text. No recently-used persistence is added. Pure tests inject the clock and cover every preset/token, shared-now resolution, invalid ordering, and rejection of lookalike or unsupported expressions.

Alternative considered: adopt a date-math package. Three exact expressions and fixed presets do not justify a dependency or a broader public language.

### 8. Poll active data sequentially and preserve the last successful snapshot

Use a feature-local polling hook based on `setTimeout` after each completed request, defaulting to five seconds. It never overlaps requests, aborts on unmount/route change, and polls only while the current successful list or detail is active. After the first response that observes a terminal-only list/detail, it performs one final refresh and then stops. Manual refresh uses the same loader.

Initial load and refresh state are separate. A refresh failure leaves last successful data rendered with a stale warning, preserving filters and selected detail tab. Only status text/targeted live regions are announced; list replacement does not force focus or repeatedly announce all rows.

Alternatives considered: fixed `setInterval` can overlap slow requests; WebSockets/server-sent events add a transport lifecycle without an MVP need; always-on polling wastes requests for immutable terminal history.

### 9. Build detail as semantic sections over durable artifacts

Use a `RunHeader` plus `Summary`, `Metrics`, `Alerts`, `Relationships`, `Analysis`, and `Report` tabs/sections. `ExecutionStatusBadge` and `AnalyticalStateBadge` remain independent. Summary derives counts only from returned LensRuns and labels unavailable evidence honestly.

Metric and Alert sections render accepted payload fields through type-specific feature components; no generic arbitrary JSON viewer is exposed. Relationship cards preserve applicability versus evaluation-state separation. Analysis uses project-owned `FindingCard`, `HypothesisCard`, `EvidenceChip`, `RelationshipChip`, `KnowledgeChip`, and `LimitationNotice` foundations. The report is displayed as readable preformatted Markdown with Copy Markdown using the browser clipboard API. UI Direction v1.4 explicitly defers file/PDF export and richer Markdown rendering, avoiding a parser dependency and unsafe HTML path in this foundation.

Empty, pending, failed-before-production, and genuinely empty artifact collections have distinct copy. Later specs may improve charts/layout without changing these API or semantic boundaries.

Alternative considered: render raw JSON for maximum coverage. It is less usable, leaks implementation shape, and weakens semantic separation.

### 10. Verify contracts at pure, API, persistence, lifecycle, and rendered boundaries

Backend tests cover strict request/response models, error mappings, task registration/result consumption, graceful shutdown, startup reconciliation, named-index races on PostgreSQL, newest-first ordering, missing/present artifacts, safe projection, and a composed launch-to-terminal flow with injected deterministic adapters. Existing orchestrator suites must continue proving synchronous `execute` behavior.

Launch tests include a continuation that terminalizes immediately after registration and assert that `202` uses the detached running acceptance summary without another persistence read, while the next list/detail request observes terminal state.

Alert adapter tests additionally count every model request, cover early completion, ten sequential tool calls plus final completion, a tool request in response eleven, a multi-call response crossing remaining capacity, model failure/invalid output accounting, no eleventh ledger entry, and proof that no twelfth request occurs.

Frontend tests cover initial/error/empty/stale states, combined filters, status/state independence, disabled active Observations, presets and closed expression parsing, request payload/call count, return-to-list behavior, active polling cleanup, detail progress, semantic section rendering, missing artifacts, and report copying. Tests use the existing Vitest/Testing Library setup and fake timers/injected clock; no dependency changes are required.

Launch-dialog tests independently cover definition loading, failure versus empty, Retry, abort/reopen, backend ordering, an Observation absent from all run history, known-active disabling, and confirmation gating.

### 11. Make the unauthenticated MVP trust boundary explicit

Do not add an identity model, auth middleware, token storage, login route, permission abstraction, CORS expansion, or rate-limiting dependency in this verification-focused change. Existing same-origin frontend requests call the API as one trusted operator.

Documentation and deployment examples must state that the backend is suitable only for local development or an operator-controlled internal network. Binding to `0.0.0.0` in the WSL development commands is a convenience for host access, not authorization; the host firewall/network must remain trusted. Any public-internet, shared untrusted LAN, or multi-user deployment requires a later approved authentication/authorization and admission-control design or an externally managed authenticated reverse proxy.

Alternative considered: add authentication now. It would require identity, secret/session lifecycle, authorization, and security acceptance criteria unrelated to validating Observation execution, so the user explicitly deferred it for the MVP.

## Risks / Trade-offs

- **[Risk] In-process tasks are not a distributed durable queue and cannot survive a hard process stop.** → Make the single-process MVP boundary explicit, durably cancel active orphans at startup, and require a fresh run identity after interruption.
- **[Risk] Starting a second application process would make sole-owner startup reconciliation unsafe.** → Document and test the one-process deployment constraint; defer multi-process operation until durable task ownership/leases are designed.
- **[Risk] Initialization commit may be indeterminate or may race with recovery.** → Register/fence every initializer before persistence, advance a monotonic recovery generation, recheck it after commit, await all older-generation session teardown before reconciliation, and never retry or return `202` for a fenced initializer.
- **[Risk] A persistence outage may prevent a detached task from terminalizing and leave a database row active.** → Enter global `recovery_required`, block every launch with safe `503`, quiesce all initializer/continuation work, retry only cancellation/reconciliation every five seconds, and restore readiness only after a durable empty-active verification; never retry analysis or fabricate terminal success.
- **[Risk] Graceful shutdown can remain incomplete during a prolonged database outage.** → Preserve truthful durability over a false successful shutdown; an external hard stop is recovered by the next startup, which remains unready until reconciliation commits.
- **[Risk] Full-history reads grow without bound.** → Accept this user-approved MVP behavior, keep the summary projection compact and indexed/orderable, and leave cursor pagination as a compatible later API/UI addition.
- **[Risk] The migration can fail if development data has overlapping active runs or a legacy RelationshipEvaluation cannot map uniquely to current definition order.** → Detect and report exact non-secret conflicting identities; do not guess order, delete rows, or rewrite analytical payloads automatically.
- **[Risk] A five-second poll can create unnecessary load with many clients.** → Poll only active views, sequence requests, stop at terminal state, and retain manual refresh.
- **[Risk] Detail publishes broad operational evidence, including provider-originated Alert text and source references.** → Limit access through ADR-170's trusted boundary, reuse exact strict versioned domain contracts, render strings as untrusted text, and exclude raw provider/configuration/diagnostic data.
- **[Risk] Plain preformatted Markdown is less polished than rendered Markdown.** → Preserve safe readable/copyable report access now and refine presentation later without adding a dependency in this foundation.
- **[Risk] Any network-reachable caller can launch costly work and read operational evidence because MVP has no authentication.** → Support only a trusted single-user/internal deployment, keep cross-origin access closed, document `0.0.0.0` development binding risk, and require a separate security change before untrusted exposure.

## Migration Plan

1. Confirm the worktree is on `feature/add-observation-run-management`; stop rather than write or commit this change directly on `main`.
2. Implement and test the orchestrator split and manager with no route enabled; preserve the existing end-to-end entry point.
3. Add the active-run partial unique index and RelationshipEvaluation ordinal migration. Abort on conflicting active rows or an unresolvable/non-contiguous ordinal backfill; otherwise preserve all historical payloads.
4. Add repository read/reconciliation operations, strict API contracts/service/router, approved server-owned policy settings, Metric/Alert model settings, unavailable model adapters, the empty KnowledgeRetriever, and production composition without adding or broadening authentication/CORS behavior.
5. Wire startup reconciliation and managed-task shutdown into FastAPI lifespan, then enable the run endpoints.
6. Add frontend routes, list/filters, launch dialog/time parser, polling, and detail semantic sections using the existing component system.
7. Run focused backend/frontend tests, migration upgrade checks, strict OpenSpec validation, and `make check`.

Rollback requires stopping the application so managed tasks cancel durably, reverting frontend/API/composition changes, and downgrading the migration to remove the active-run partial unique index plus the RelationshipEvaluation position uniqueness/check constraints and `position` column. Existing runtime rows and analytical payloads remain intact; downgrade removes only schema elements introduced by this change.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md`: the manager adapts only the trigger; the same deterministic stage graph, strict JOIN, usable-results gate, and top-level lifecycle owner remain intact.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: status, reason, forward transition, artifact availability, failure propagation, and cancellation rules govern API projections and restart handling.
- `docs/architecture/08_observation_analysis_result_contract.md`: detail preserves analytical state, findings, hypotheses, limitations, and reference types without additions.
- `docs/architecture/09_report_agent.md`: the UI treats the stored report as presentation-only and never derives new analysis from it.
- `docs/architecture/07_observation_reasoning_agent.md`: production composition preserves the injected, bounded KnowledgeRetriever boundary and uses an explicit empty adapter without selecting a real retrieval architecture.
- `docs/architecture/16_alert_analysis_agent.md`: Alert prompt, production model, request limits, and ten-tool budget follow the now synchronized component contract.
- `docs/architecture/03_ADR_log.md` ADR-152, ADR-164, ADR-165, ADR-168, ADR-169, and ADR-170: PydanticAI remains infrastructure-only; every fresh/recovered attempt gets a new identity; interrupted unfinished records are terminalized and never resumed; the server-owned execution/overlap and production Metric/Alert OpenRouter decisions are accepted; and the unauthenticated API is constrained to a trusted MVP deployment. ADR-166 and ADR-167 govern the reused frontend stack and UI authority.
- `docs/architecture/10_open_decisions_and_backlog.md` and `docs/architecture/12_CHANGELOG.md`: implementation removes only the decisions explicitly resolved here and records the architecture-package update.
- `docs/ui/frontend_ui_stack_adr.md` and `docs/ui/ui_implementation_handoff_v1.md`: routes, section vocabulary, status components, semantic separation, and visual organization follow accepted UI Direction v1.4; later refinement may evolve presentation through another approved change.
