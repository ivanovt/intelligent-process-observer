## 1. Runtime persistence contracts

- [x] 1.1 Define internal typed contracts for ObservationRun identity, lifecycle (`pending -> running -> completed | failed`), timestamps, structured reasons, and provenance/execution context.
- [x] 1.2 Define internal typed contracts for LensRun identity and lifecycle (`pending -> running -> completed | partial | failed`), including terminal and downstream-usability classification.
- [x] 1.3 Define internal artifact persistence contracts for Metric, Alert, and Log Lens results; support completed/partial Metric results and a minimal failed MetricAnalysisResult, and permit Alert/Log results only for completed/partial LensRuns.
- [x] 1.4 Define internal persistence contracts for `0..N` self-contained RelationshipEvaluations and `0..1` versioned ObservationAnalysisResults and Markdown ObservationReports, without assigning new domain schema versions where the accepted contracts do not define them.

## 2. Relational storage and migration

- [x] 2.1 Extend the existing SQLAlchemy persistence models with ObservationRun, LensRun, shared type-discriminated Lens analysis result, RelationshipEvaluation, ObservationAnalysisResult, and ObservationReport storage models and their `0..N`/`0..1` relationships and uniqueness constraints.
- [x] 2.2 Create an additive Alembic migration chained from `20260822_01` with the runtime tables, foreign keys, indexes, and uniqueness constraints required by the design, without altering existing definition persistence behavior.

## 3. Internal persistence operations

- [x] 3.1 Implement repository operations that persist and advance ObservationRun and LensRun records through their approved lifecycle directions within the existing async SQLAlchemy transaction/session boundary.
- [x] 3.2 Implement Lens-result persistence that preserves complete payloads and contract-defined versions where present, accepts failed minimal MetricAnalysisResults only for failed Metric LensRuns, and rejects Alert/Log results attached to failed LensRuns.
- [x] 3.3 Implement Observation-level artifact persistence that preserves `0..N` RelationshipEvaluation payloads and `0..1` ObservationAnalysisResult/ObservationReport artifacts, correlating a persisted report to its source analysis result without fabricating absent versions.
- [x] 3.4 Implement eager runtime-execution retrieval that returns correlated LensRuns and all available artifacts, preserves absence separately from empty optional sections, and exposes failed Metric results as non-usable.

## 4. Verification

- [x] 4.1 Add persistence-contract tests for ObservationRun lifecycle `pending -> running -> completed | failed` and LensRun lifecycle `pending -> running -> completed | partial | failed`.
- [x] 4.2 Add tests for completed and partial Metric result persistence, failed minimal MetricAnalysisResult persistence/retrieval, and failed Metric results being non-usable downstream evidence.
- [x] 4.3 Add tests for failed Alert LensRuns with no AlertAnalysisResult, failed Log LensRuns with no LogAnalysisResult, and rejection of Alert/Log results attached to failed LensRuns.
- [x] 4.4 Add tests for identity/type/status mismatch rejection and for the distinction between a missing artifact and a valid artifact with empty optional sections.
- [x] 4.5 Add repository/integration tests for self-contained RelationshipEvaluation, versioned ObservationAnalysisResult, and Markdown ObservationReport retrieval with the MVP cardinality rules.
- [x] 4.6 Add repository/integration coverage for an early-failed ObservationRun with available Lens artifacts but no ObservationAnalysisResult or ObservationReport.
- [x] 4.7 Add migration coverage or schema assertions for the new runtime relationships and uniqueness constraints.
- [x] 4.8 Run `make check` and resolve all reported failures before archive or pull-request preparation.
