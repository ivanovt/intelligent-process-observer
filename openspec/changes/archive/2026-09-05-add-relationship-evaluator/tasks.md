## 1. RelationshipEvaluation Contracts

- [x] 1.1 Add the dedicated relationship package and strict property-specific evidence models for direction, rate, and variability, including exact current Metric 1.0 expected/observed vocabularies, explicit null unavailable representation, rejection of literal `unknown`, correlation validation, canonical serialization, and concise docstrings for every public contract class.
- [x] 1.2 Add strict applicable, not-applicable, and unknown RelationshipEvaluation variants so `state` is required only for `applicable`, semantic identity and both complete evidence lists are always present, extra fields are rejected, and no domain schema version is introduced.
- [x] 1.3 Add focused contract tests covering valid variants, absence of `state` on non-applicable serialization, explicit null unavailable evidence, rejection of literal `unknown`, not-classified rate evidence, invalid vocabulary, contradictory match values, and forbidden extra fields.

## 2. Complete-Collection Input Boundary

- [x] 2.1 Add all-or-nothing batch input validation/indexing over the complete LensAnalysisResult envelope collection, requiring one shared `(observation_id, observation_run_id)` pair, rejecting disagreement in either identity field and duplicate Metric Lens IDs, and permitting an empty collection.
- [x] 2.2 Validate matching Metric payloads against the existing strict MetricAnalysisResult variants; expose current state only from completed-sufficient and partial variants, and classify completed-insufficient and failed variants as unavailable relationship evidence.
- [x] 2.3 Add input-boundary tests proving non-Metric and unrelated results are ignored, same-ID non-Metric results do not satisfy Metric participants, disagreement in either batch identity field and duplicate Metric Lens IDs are rejected, malformed matching Metric payloads—including a missing mandatory descriptor—are rejected, and missing or valid non-usable participant results do not abort the batch.
- [x] 2.4 Reject duplicate Relationship IDs before any evaluation and test atomic rejection against individually valid duplicate definitions, while preserving valid definition order.

## 3. Deterministic Evidence Evaluation

- [x] 3.1 Implement fixed accessors for only `trend.direction`, `trend.rate`, and `variability.state`, with exact equality, reliable `not_classified` rate mismatch behavior, and no access to optional properties, reference periods, History, numerical evidence, or raw data.
- [x] 3.2 Flatten configured condition and expectation descriptors into complete evidence lists ordered by Relationship participant order and then `trend.direction`, `trend.rate`, `variability.state`, without emitting unconfigured properties.
- [x] 3.3 Add focused evidence tests for multi-participant and multi-property rules, canonical ordering independent of mapping insertion order, exact matches/mismatches, missing participant results, valid completed-insufficient/failed results without current state, and complete expectation evidence on non-applicable and unknown outcomes.

## 4. Applicability, State, and Batch Behavior

- [x] 4.1 Implement condition reduction with empty-condition applicability and mismatch-dominant conjunctive precedence across match, mismatch, and unknown evidence.
- [x] 4.2 Implement expectation reduction only for applicable Relationships, producing `consistent`, `inconsistent`, or `uncertain` with mismatch dominance while omitting state for other applicability outcomes.
- [x] 4.3 Implement the documented public evaluator interface with concise class and interface-method docstrings; return exactly one validated artifact per duplicate-free Relationship in order, return an empty batch for no Relationships, do not mutate inputs, and perform no I/O or runtime coordination.
- [x] 4.4 Add a table-driven semantic matrix covering all applicability/state outcomes, simultaneous mismatch and unavailable evidence, missing condition versus missing expectation evidence, ordered multi-Relationship batches, and all-evidence-unavailable batches; explicitly assert that supplied definitions and result envelopes are unchanged after both successful and rejected evaluation.

## 5. Compatibility and Verification

- [x] 5.1 Add a compatibility test showing every evaluation variant serializes into the existing generic `RelationshipEvaluationInput` payload without changing or invoking persistence, and run focused Observation, Metric contract, runtime persistence, and relationship test suites.
- [x] 5.2 Run `make check` and record any environment-dependent failures accurately before implementation review, archive, or pull-request preparation.
