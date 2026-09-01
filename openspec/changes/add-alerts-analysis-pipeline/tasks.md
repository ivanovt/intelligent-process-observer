## 1. Alert execution and contract foundations

- [ ] 1.1 Create the internal `app.alerts` package with strict execution-context, provider-outcome, canonical-record, agent request/output, optional-tool outcome, and AlertAnalysisResult 1.0 models; preserve existing UUID/string runtime identity primitives and reject unknown/transient/provider fields.
- [ ] 1.2 Define framework-neutral Alert provider, Alert Analysis Agent, and optional-tool executor ports for one immutable existing running Alert LensRun; add focused contract tests for scope, controlled values, and excluded data.
- [ ] 1.3 Implement and test current/reference window derivation, lifecycle-overlap filtering, canonical validity and unique canonical Alert IDs, normalized active/resolved/unknown status, and typed acquisition outcomes without Jira transport or field-mapping code; reject every member of duplicate-ID collision sets through the existing invalid-record paths.

## 2. Deterministic current and reference analysis

- [ ] 2.1 Implement the pure Deterministic Alert Analyzer and test effective occurrence defaults, record-based status distribution, active/resolved durations, finite unrounded duration statistics, native provider-importance aggregation, and zero-record omissions.
- [ ] 2.2 Implement independent configured-reference preparation and occurrence comparison; test same-duration backward windows, configured-order preservation, strict direction, raw-reference exclusion, and unavailable/malformed/all-invalid offset omission.
- [ ] 2.3 Implement typed current/reference failure and incompleteness outcomes; test current query error/timeout, usable invalid-record subset, all-invalid current failure, successful empty current response, and all-reference-unavailable partial behavior.

## 3. Bounded optional Alert tools

- [ ] 3.1 Implement the run-local optional-tool registry and ledger with exactly the three accepted tool names, empty-object input admission, repeated permitted use, unknown/scope-expanding rejection, and an all-outcome maximum of ten attempts.
- [ ] 3.2 Implement and test recurrence concentration, including missing occurrence defaults, zero-total non-applicability, and lexical tie output.
- [ ] 3.3 Implement and test duration outlier analysis with the approved `(n-1)*p` interpolation, minimum-eight boundary, strict high-side IQR threshold, and non-applicable outcome.
- [ ] 3.4 Implement and test reference-pattern analysis with the two-successful-comparison minimum, unique dominant-direction calculation, and mixed tie handling.

## 4. Alert agent boundary

- [ ] 4.1 Implement the strict bounded Alert agent request/output projection and application-owned optional-tool execution mapping; test excluded query/provider/reference/cross-Lens/knowledge data and strict completion rejection of `none`, invalid controlled values, unknown/missing fields, and malformed findings as `agent_failed` before the builder.
- [ ] 4.2 Implement `PydanticAIAlertAnalysisAgent` as an injected-model infrastructure adapter using the existing dependency only; enforce no corrective validation/model retries and the domain-owned ten-call budget, without a production model/provider default.
- [ ] 4.3 Add deterministic adapter tests using fake/function models for zero calls, repeated permitted calls, call #10, rejected unregistered or over-budget requests, valid completion, `none` and other invalid controlled completion values, unknown/missing completion fields, malformed findings, agent error, agent timeout, and optional failed/timeout continuation.

## 5. Strict Alert result construction

- [ ] 5.1 Implement the deterministic AlertAnalysisResult builder as the sole completed/partial constructor, including exact envelope, section omission rules, zero-record fixed output, controlled overall-importance invariant, unsuccessful optional trace projection, and persistence envelope correlation.
- [ ] 5.2 Implement and test the canonical ASCII `alert://` grammar and exact-one resolution against final current records, aggregates, and successful comparisons: UTF-8/RFC 3986 segment encoding, reserved characters, Unicode, uppercase escapes, percent-encoded-unreserved rejection, malformed/incomplete/lowercase escapes, invalid UTF-8, query/fragment, exact path shapes, optional-section absence, and ambiguous/duplicate targets; ensure transient-tool-derived findings cite only persisted underlying evidence.
- [ ] 5.3 Implement and test terminal reason mapping: `invalid_records/current_normalization` over `reference_unavailable/reference_periods`, current acquisition failures, mandatory analyzer failure, malformed/contract-invalid agent completion as `agent_failed`, required agent timeout, and final contextual/result invariants as `result_validation_failed/alert_result_builder`.
- [ ] 5.4 Add exhaustive builder tests for strict unknown-field rejection, identity/time/provenance correlation, lifecycle/count/duration/comparison invariants, zero-record omissions, native importance preservation, and failed-Alert artifact absence.

## 6. Pipeline and existing runtime-persistence integration

- [ ] 6.1 Implement the Alerts Analysis Pipeline for one already-running immutable Alert LensRun with the approved deterministic stage order, zero-record gate, and no Observation/LensRun creation or scope mutation.
- [ ] 6.2 Compose terminal LensRun advancement and at-most-one completed/partial Alert artifact persistence through the existing caller-owned runtime transaction; do not add a repository, table, or migration.
- [ ] 6.3 Add repository/pipeline integration tests for completed and partial status/reason correlation, failed Alert result absence, mismatched artifact rejection, and rollback/propagation on flush or commit failure.

## 7. Verification and documentation

- [ ] 7.1 Add concise public-class/interface docstrings and developer-facing documentation for injection/composition boundaries, explicitly preserving deferred Jira transport and production-model configuration.
- [ ] 7.2 Run focused backend contract, deterministic-analysis, tool, agent-adapter, builder, pipeline, and PostgreSQL persistence tests; report failures accurately.
- [ ] 7.3 Run `openspec validate add-alerts-analysis-pipeline --strict` and `make check`; do not archive, push, create a pull request, or add Jira/model-provider integration in this change.
