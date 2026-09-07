## Why

The repository already provides independently tested definition loading, runtime persistence, Metric and Alert analysis, Relationship Evaluation, Observation Reasoning, and report generation, but it does not yet compose them into the deterministic top-level Observation workflow required by the architecture. This change supplies that control-plane capability so one immutable Observation execution can progress predictably from definition loading through durable terminal completion or a structured failure/cancellation outcome.

## What Changes

- Add an internal deterministic Observation execution orchestrator that loads one predefined Observation Definition once, fixes a run-scoped snapshot and time context, creates correlated ObservationRun and LensRun identities, and invokes the existing Metric and Alert pipelines.
- Enforce bounded work-conserving Lens fan-out, per-Lens deadlines, strict JOIN, and the usable-results gate without embedding Lens-specific analytical logic in the orchestrator.
- Invoke and persist deterministic Relationship Evaluations in definition order, then construct the existing strict Observation Reasoning input and invoke the reasoning capability only when at least one usable result exists.
- Persist a successful ObservationAnalysisResult before invoking the existing presentation-only report generator; persist a successful report and complete the ObservationRun, or fail the ObservationRun while preserving the committed analysis if report generation fails.
- Define structured top-level failure mapping, identity/correlation rejection, timeout handling, unexpected-failure containment, atomic persistence boundaries, and forward-only lifecycle enforcement.
- Add the accepted `cancelled` terminal status for ObservationRun and LensRun persistence. Cancellation preserves already terminal LensRuns and committed artifacts, marks only unfinished runs and the parent as cancelled, stops downstream work, and then propagates to the caller.
- Require every retry, restart, or re-run to create a fresh runtime aggregate; no existing run is resumable and this change introduces no automatic retry trigger, idempotency protocol, replay/artifact reuse, overlap policy, scheduler, or public execution endpoint.
- Keep Logs, UI, notifications, scheduling, ad-hoc Observation resolution, and autonomous scope expansion outside this MVP change.

## Capabilities

### New Capabilities

- `observation-execution`: Deterministic top-level orchestration of one predefined Metric/Alert Observation from immutable definition snapshot through fan-out, JOIN, reasoning, report persistence, and terminal lifecycle.

### Modified Capabilities

- `runtime-persistence`: Extend forward-only ObservationRun and LensRun lifecycle persistence with the accepted terminal `cancelled` state and cancellation-safe artifact preservation.

## Impact

- Backend application/domain composition will gain a framework-neutral Observation execution service and narrow ports/adapters to the existing definition, pipeline, evaluator, reasoning, reporting, and persistence capabilities.
- Existing runtime persistence contracts and lifecycle transition validation will admit `cancelled`; the current string-backed PostgreSQL columns require no schema migration.
- Focused unit/orchestration/failure-boundary tests and PostgreSQL integration tests will cover ordering, concurrency, correlation, transaction rollback, terminalization, and artifact preservation.
- No public API behavior, frontend behavior, dependency, database schema, architecture style, or provider/agent contract is added or changed beyond the accepted lifecycle extension.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — Definition-versus-run ownership and execution policy.
- `docs/architecture/02_architecture_principles_and_runtime.md` — top-level workflow, fan-out/JOIN, degradation, stage order, and persistence boundary.
- `docs/architecture/03_ADR_log.md` — ADR-043..ADR-068, ADR-085..ADR-088, ADR-152, ADR-161..ADR-165.
- `docs/architecture/04_pipeline_and_agent_concepts.md` — orchestrator and component responsibility boundaries.
- `docs/architecture/05_relationship_evaluator_concept.md` — deterministic Relationship Evaluation inputs and ordering semantics.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — lifecycle, usability, reasoning/report inputs, failure propagation, and persistence semantics.
- `docs/architecture/07_observation_reasoning_agent.md` — bounded Observation Reasoning boundary.
- `docs/architecture/08_observation_analysis_result_contract.md` — structured ObservationAnalysisResult contract.
- `docs/architecture/09_report_agent.md` — presentation-only report boundary.
- `docs/architecture/10_open_decisions_and_backlog.md` — exclusions for triggers, overlap, automatic retry, idempotency, replay, scheduling, and infrastructure choices.
