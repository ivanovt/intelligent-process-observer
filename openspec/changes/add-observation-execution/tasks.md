## 1. Extend Runtime Lifecycle Persistence

- [x] 1.1 Add `cancelled` to ObservationRun and LensRun status contracts, terminal/usability helpers, forward transition validation, required-reason validation, and public docstrings while preserving every existing lifecycle rule.
- [x] 1.2 Extend runtime persistence to reject artifacts for cancelled LensRuns and to preserve cancelled/terminal children and already committed Observation-level artifacts during retrieval.
- [x] 1.3 Add a transaction-owned guarded cancellation operation that terminalizes only pending/running children plus the running parent, rejects contradictory concurrent terminalization, and leaves commit/rollback ownership with the caller.
- [x] 1.4 Add focused lifecycle/repository unit tests and PostgreSQL integration tests for pending/running cancellation, terminal preservation, artifact rejection, exact `execution_cancelled` reasons, duplicate transition races, retrieval, and all-or-nothing rollback without adding an Alembic migration.

## 2. Define Execution Inputs, Snapshot, and Initialization

- [x] 2.1 Create the small `app.execution` package with strict immutable execution request, policy, snapshot, assignment, collected-outcome, and closed internal execution-outcome values plus narrow framework-neutral ports and required public docstrings. Model only `completed` and `failed` initialized-run outcomes with run IDs and terminal status/reason as applicable, and a no-run-ID pre-initialization `rejected` outcome; leave cancellation and persistence/infrastructure errors propagated.
- [x] 2.2 Implement request/policy validation and one-shot projection of a complete loaded Observation aggregate into a detached immutable Metric/Alert snapshot, returning only the exact controlled pre-initialization rejection codes for malformed request/policy, absent, invalid, empty, Log, or unsupported definitions before runtime creation.
- [x] 2.3 Implement canonical Lens ordering by literal type order `metric`, `alert` then lexical Lens ID, preserving Relationship definition order and keeping provider configuration out of reasoning/report semantic projections.
- [x] 2.4 Implement atomic initialization that loads the definition, creates one fresh ObservationRun and the exact type-aware LensRun graph, advances the parent to running, and rolls the entire transaction back before pipeline work on any error.
- [x] 2.5 Add focused tests for UTC window validation, snapshot isolation, definition-read count, the exact completed/failed/rejected internal outcome shapes and controlled preparation-code mapping, no-run-ID rejection, propagated cancellation/persistence failures, unsupported/absent input, equal cross-type Lens IDs, canonical ordering independent of presentation order, exact topology correlation, fresh identities, and initialization rollback.

## 3. Compose Type-Specific Lens Execution Adapters

- [ ] 3.1 Implement the Metric execution adapter that projects the assigned snapshot/runtime identity into the existing Metric context, runs only pre-terminalization provider/agent/deterministic analysis under the per-Lens deadline, then performs the accepted History read/analysis and terminal-result transaction outside that deadline without moving Metric semantics into the orchestrator. For wrapper `timeout`, `analysis_failed`, and `identity_mismatch`, use the existing Metric-owned builder and assigned context to create the minimal failed artifact with `mandatory_metric_analysis_failed` while retaining the wrapper reason on the LensRun.
- [ ] 3.2 Implement the Alert execution adapter that resolves the existing injected provider boundary, projects the exact Alert context, invokes pre-terminalization analysis under the per-Lens deadline, and atomically persists its terminal outcome in a deadline-exempt transaction under existing failed-artifact absence rules.
- [ ] 3.3 Add adapter-owned normalization for expiry of deadline-covered analytical work, unexpected non-persistence exceptions, and identity/status mismatch with controlled `timeout`, `analysis_failed`, and `identity_mismatch` reasons. For each normalized Metric failure, retain the LensRun reason and construct the type-correct minimal Metric artifact through the existing generic mandatory-analysis builder path (`mandatory_metric_analysis_failed`); retain Alert failed-result absence. Propagate Metric History and every terminal persistence failure as infrastructure errors.
- [ ] 3.4 Add focused adapter tests for exact context projection, running precondition, completed/partial/failed persistence, Metric History transaction ownership, Alert failed-result absence, the pre-terminalization-only deadline, History query/transaction and terminal-write failure propagation without timeout normalization, and each Metric wrapper failure mapping: exact LensRun reason plus assigned-context minimal artifact identity/window/provenance and `mandatory_metric_analysis_failed` fixed error. Cover unexpected failure, mismatched outcomes, safe reason content, rejected producer artifacts, and rollback on persistence failure.

## 4. Implement Bounded Fan-Out, Strict JOIN, and Usability Gate

- [ ] 4.1 Implement the fixed-size asyncio worker scheduler with canonical admission, independent sessions, durable pending-to-running admission, work-conserving slot reuse, a deadline limited to pre-terminalization analytical work after admission, deadline-exempt Metric History and terminal persistence, bounded active work, and canonical collected-result ordering.
- [ ] 4.2 Implement strict normal JOIN verification against the initialized topology and exact usable/unavailable classification for sufficient/partial Metrics, completed-insufficient/failed Metrics, and completed/partial/failed Alerts.
- [ ] 4.3 Implement the zero-usable gate that atomically fails the ObservationRun with `no_usable_lens_results/usable_results_gate`, preserves Lens artifacts, and prevents all Observation-level stages.
- [ ] 4.4 Add controllable asynchronous orchestration tests proving the concurrency ceiling, work-conserving non-batched admission, queue-time and terminal-transaction exclusion from deadlines, completion-order independence, one-Lens failure isolation, timeout terminalization only for deadline-covered analytical work, History/persistence-error propagation, strict no-early-continuation JOIN, degraded continuation, and zero-usable STOP.

## 5. Compose Observation-Level Evaluation, Reasoning, and Reporting

- [ ] 5.1 Invoke the existing Relationship Evaluator once after the gate with ordered frozen definitions and the complete admissible current-run artifact set; validate exact batch identity/cardinality/order and atomically persist all-or-none evaluations.
- [ ] 5.2 Build the exact accepted ObservationReasoningInput partition in canonical Lens order, preserving caller-unavailable reasons and the completed-insufficient Metric projection; invoke the existing executor and atomically persist only a valid correlated ObservationAnalysisResult.
- [ ] 5.3 Build the exact minimal ReportGenerationRequest from the committed analysis and frozen semantic context; invoke the existing executor and atomically persist a correlated Markdown report together with the parent completed transition.
- [ ] 5.4 Map Relationship, reasoning, and reporting failures to controlled parent reasons, preserving already committed artifacts and specifically retaining ObservationAnalysisResult with no report when report generation fails.
- [ ] 5.5 Add focused tests for empty/non-empty ordered Relationships, missing participant evidence, malformed evaluation batches, exact reasoning partitions, raw/config exclusion, reasoning failure and identity mismatch, report input isolation, successful completion, report failure after analysis, and final report/completion rollback.

## 6. Enforce Top-Level Failure, Cancellation, and Fresh-Run Boundaries

- [ ] 6.1 Implement the outer non-persistence failure boundary that stops admission, settles owned child work, preserves terminal children, fails unfinished LensRuns with `execution_aborted/<stage>`, fails the parent with `execution_failed/<stage>`, and starts no later stage.
- [ ] 6.2 Implement caller-cancellation handling that stops admission, cancels and settles active workers, performs non-detached shielded cancellation terminalization, preserves terminal children and committed artifacts, starts no later stage, and re-raises only after a definite commit or persistence failure.
- [ ] 6.3 Ensure the public internal execution entry point always begins at preparation with fresh ObservationRun/LensRun identities and exposes no resume, stage replay, automatic retry, idempotency, artifact reuse, or overlap-policy path.
- [ ] 6.4 Add focused cancellation tests during pending/running fan-out, reasoning, reporting, and final-transaction races; verify terminal preservation, cancelled retrieval, downstream STOP, no fabricated artifacts, cleanup commit ordering, cleanup rollback visibility, and no detached tasks.
- [ ] 6.5 Add tests for unexpected failures at each top-level stage, duplicate/contradictory completion attempts, persistence-error propagation without fabricated durability, and explicit re-runs creating new immutable runtime graphs after failed and cancelled runs.

## 7. Integration and Final Verification

- [ ] 7.1 Add PostgreSQL-backed end-to-end orchestration tests for all-completed success, mixed completed/partial/failed degradation, zero-usable failure, Relationship and reasoning persistence, analysis-preserving report failure, successful report-plus-completion, cancellation preservation, and exact aggregate retrieval.
- [ ] 7.2 Run the existing Metric, Alert, runtime persistence, Relationship Evaluation, knowledge retrieval, Observation Reasoning, and Report Generation test suites and correct only regressions caused within this change's approved scope.
- [ ] 7.3 Verify public execution classes/interfaces/methods have concise behavior-focused docstrings, architecture/framework boundaries remain import-safe, the migration head is unchanged, and no public API, frontend, dependency, Log, scheduler, notification, or retry/replay surface was introduced.
- [ ] 7.4 Run `make check` as the final local verification step and report every failure accurately before any archive or pull-request activity.

## Requirement Traceability

| Requirement | Tasks |
|---|---|
| Accept and freeze one predefined Observation execution scope | 2.1, 2.2, 2.5 |
| Create and correlate the complete runtime identity graph atomically | 2.4, 2.5, 7.1 |
| Dispatch Lens pipelines in deterministic bounded order | 2.3, 4.1, 4.4 |
| Invoke existing Metric and Alert pipelines through type-specific adapters | 3.1–3.4 |
| Enforce strict JOIN and classify the complete Lens outcome set | 4.2–4.4, 7.1 |
| Evaluate and persist Relationships deterministically before reasoning | 5.1, 5.5, 7.1 |
| Construct, invoke, and persist Observation Reasoning from the exact run partition | 5.2, 5.4, 5.5, 7.1 |
| Generate and persist a faithful report before successful completion | 5.3–5.5, 7.1 |
| Preserve forward-only, non-contradictory lifecycle ownership | 1.1–1.4, 6.1, 6.5 |
| Terminalize top-level cancellation without rewriting completed work | 1.2–1.4, 6.2, 6.4, 7.1 |
| Treat every retry, restart, and re-run as a fresh execution | 2.4, 6.3, 6.5 |
| Keep the MVP execution boundary intentionally small | 2.1, 3.1–3.2, 7.2–7.4 |
| Persist correlated runtime executions without duplicating definitions | 1.1, 2.4, 2.5 |
| Preserve cancelled runtime state without fabricating or deleting artifacts | 1.2–1.4, 6.2, 6.4, 7.1 |
