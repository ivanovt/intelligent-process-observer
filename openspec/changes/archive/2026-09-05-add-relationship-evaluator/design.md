## Context

See `proposal.md` for motivation and `specs/relationship-evaluation/spec.md` for behavior.

The repository already has three relevant boundaries:

- validated Relationship definitions under the Observation aggregate;
- strict MetricAnalysisResult variants, where completed-sufficient and partial results carry `current_state`, completed-insufficient does not, and failed Metric results are traceability-only;
- generic runtime artifact persistence capable of storing a self-contained RelationshipEvaluation payload, although top-level Observation execution does not yet exist.

The architecture requires the evaluator to receive all Lens results, resolve Metric participants itself, remain deterministic and framework-neutral, and expose complete evidence to later Observation reasoning. The exact RelationshipEvaluation serialization was intentionally open; this change closes it at the implementation-specification level without editing architecture documents or assigning a schema version. The roadmap assigns strict JOIN and invocation/persistence coordination to the later `add-observation-execution` feature.

## Goals / Non-Goals

**Goals:**

- Establish one exact, strict RelationshipEvaluation domain contract suitable for later reasoning and persistence.
- Evaluate all supported condition and expectation descriptors using explicit three-valued logic.
- Consume the complete heterogeneous Lens result collection while keeping participant lookup and semantic extraction inside the evaluator.
- Keep output and ordering deterministic and make missing evidence auditable.
- Fit the existing modular-monolith contracts without adding a dependency or persistence model.

**Non-Goals:**

- Detecting JOIN completion or determining whether the post-JOIN usable-results gate passed.
- Loading definitions or runs, persisting results, or managing transactions and lifecycle transitions.
- Implementing Observation Reasoning, report generation, or a public execution endpoint.
- Supporting Alert/Log participants, optional Metric properties, reference/History rules, numerical/temporal rules, discovery, LLM, or RAG.
- Adding a RelationshipEvaluation schema version or changing existing Observation/API/persistence schemas.

## Decisions

### 1. Add a dedicated relationship domain module without moving existing definition contracts

Add a small `app.relationships` package containing the evaluation output contracts and deterministic evaluator. The evaluator consumes the existing validated Observation Relationship definition type rather than moving or duplicating the public definition contract in this feature.

This keeps aggregate ownership with Observations and limits the delta. Moving the Relationship definition types into a new shared package was considered, but it would create broad import churn without changing behavior. Defining a second evaluator-specific Relationship input was also rejected because it would duplicate the accepted rule DSL and create a mapping boundary the architecture explicitly does not assign to the orchestrator.

### 2. Consume existing complete runtime artifact envelopes and validate Metric payloads at the boundary

The evaluator accepts the complete collection of existing `LensAnalysisResultInput` envelopes. Before indexing participants, it requires every entry in a non-empty collection to share one exact `(identity.observation_id, identity.observation_run_id)` pair. It indexes only entries with `result_type=metric`, using `identity.lens_id`, and rejects duplicate Metric Lens IDs before ignoring other Lens types and unrelated Metric identities. For a matching Metric entry, the payload is validated against the existing strict MetricAnalysisResult variants before semantic access.

Only completed-sufficient and partial Metric variants provide available `current_state`. Completed-insufficient and failed Metric variants are valid inputs but provide unavailable relationship observations. A malformed Metric payload—including a current-state-bearing variant missing a mandatory descriptor—is a caller contract violation and rejects the batch; it is not silently converted into normal uncertainty. This makes architecture-level “missing descriptor” uncertainty concrete for the accepted MetricAnalysisResult 1.0 boundary as absence of current state in a valid variant, while preserving fail-closed handling of structurally invalid producer artifacts. An empty result collection is valid and makes every referenced observation unavailable.

The accepted MetricAnalysisResult 1.0 mandatory direction, rate, and variability vocabularies do not emit a literal `unknown`. The evaluation output therefore does not admit literal `unknown` as an observed descriptor. This does not change the architecture's uncertainty semantics: missing valid evidence is represented by `observed=null`, `match=null`, and the corresponding applicability/state outcome. A future change that adds literal unknown to mandatory Metric descriptors must explicitly extend this contract.

Passing only a preprojected participant map was rejected because ADR-060 assigns result resolution to the evaluator. Depending directly on ORM models was rejected because the domain capability must remain persistence-neutral.

### 3. Represent the output as strict discriminated variants

Use three strict output variants sharing identity and evidence fields:

- applicable: `applicability="applicable"` plus required `state`;
- not applicable: `applicability="not_applicable"` and no `state` field;
- unknown applicability: `applicability="unknown"` and no `state` field.

The public RelationshipEvaluation type is their discriminated union. Separate variants make illegal applicability/state combinations unrepresentable and ensure serialization omits `state` rather than emitting `state: null`. All public classes and interfaces receive concise behavior-focused docstrings as required by repository policy.

No `schema_version` is added because the accepted runtime-persistence specification explicitly preserves RelationshipEvaluation without inventing a domain-level version. Persistence correlation remains the responsibility of the existing ObservationRun parent and later execution integration.

### 4. Use property-specific evidence variants and explicit missing values

Flatten both rule sides into property-specific evidence items. Each item carries:

```text
lens_id
property
expected
observed
match
```

Use separate strict variants for `trend.direction`, `trend.rate`, and `variability.state` so each field admits only its own currently accepted Metric vocabulary. Available controlled values require Boolean `match`, and validators require it to equal the exact comparison result. A missing participant result or valid result variant without current state uses explicit `observed=null` and `match=null`. Literal `unknown` is rejected because no accepted MetricAnalysisResult 1.0 mandatory descriptor can produce it.

An alternative compact result containing only applicability/state was rejected because it would require downstream reconstruction from the mutable definition. Omitting unused-side evidence for non-applicable rules was rejected by the user-reviewed contract decision: every outcome remains complete and independently auditable.

### 5. Flatten evidence in a canonical order

For each side, walk `participants` in definition order and, for each participant, emit configured properties in this fixed order:

```text
trend.direction
trend.rate
variability.state
```

This avoids making dictionary insertion history part of the serialized contract while preserving the engineer-authored participant order. Conditions and expectations remain separate lists. The output contains only configured descriptors; it does not add evidence for supported but unconfigured properties.

### 6. Apply mismatch-dominant conjunction independently to each side

Each configured property yields `match`, `mismatch`, or `unknown` internally:

- exact available equality -> match;
- exact available inequality -> mismatch;
- no matching Metric result or a valid completed-insufficient/failed variant without current state -> unknown.

For conditions, any mismatch makes applicability `not_applicable`; otherwise any unknown makes it `unknown`; otherwise it is `applicable`. Empty conditions are `applicable`. For applicable expectations, any mismatch makes state `inconsistent`; otherwise any unknown makes it `uncertain`; otherwise it is `consistent`.

Mismatch dominance follows normal conjunction: one proven-false operand is enough to prove the conjunction false even when another operand is unavailable. Expectation evidence is still collected for non-applicable and unknown rules, but state is not calculated or serialized for those outcomes.

### 7. Keep evaluation pure and leave persistence adaptation trivial but external

The evaluator performs no I/O and returns validated domain models. The later Observation execution feature can serialize each model and place it into the existing `RelationshipEvaluationInput(relationship_id, payload)` persistence envelope inside its caller-owned transaction. This change does not add that adapter or call the repository because there is no post-JOIN runtime owner yet.

An interim partial orchestrator was rejected: it would pull JOIN, usable gating, loading, transactions, downstream continuation, and failure ownership from roadmap item #14 into this isolated capability.

### 8. Validate Relationship batch uniqueness at the evaluator boundary

Although persisted Observation aggregates already guarantee Relationship ID uniqueness, the evaluator's standalone public entry point receives an ordinary ordered collection of individually valid definitions. It therefore rejects duplicate Relationship IDs before evaluating any item. This preserves all-or-nothing batch behavior and guarantees that its output can later satisfy the existing `(observation_run_id, relationship_id)` persistence uniqueness constraint.

Relying only on upstream aggregate validation was rejected because the standalone component would otherwise admit an ambiguous input that its promised persistence-compatible output cannot represent.

## Risks / Trade-offs

- [The evaluator accepts generic artifact envelopes whose payload is dictionary-shaped] -> Revalidate matching Metric payloads through the existing strict domain result union before reading semantics; reject malformed producer output.
- [The result envelopes carry two correlated runtime identities] -> Validate both `observation_id` and `observation_run_id` as one batch pair before participant resolution.
- [Definition DTO ownership remains in the Observations module] -> Keep the dependency one-way from the new evaluator to the existing definition contract and defer any contract relocation until a demonstrated reuse need exists.
- [Complete evidence evaluates expectations even for rules that are not applicable] -> Treat this only as deterministic semantic lookup, never as an expectation state; omit `state` unless applicable.
- [Mismatch dominance can hide another unavailable descriptor at the summary level] -> Preserve every evidence item, including explicit null observations, so downstream consumers can see both facts.
- [The exact unversioned contract may evolve later] -> Keep strict models and tests centralized; any future property or schema change requires an explicit OpenSpec/architecture extension rather than permissive extras.

## Migration Plan

No database or data migration is required. Deploying the new package does not alter existing API or runtime behavior until a later caller invokes it. Rollback consists of removing the unused package and its tests; no persisted state or client contract requires repair.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`, section 10: Metric-only qualitative Relationships and current-state vocabulary.
- `docs/architecture/02_architecture_principles_and_runtime.md`, sections 4 and 11: stage placement and complete evaluator input.
- `docs/architecture/03_ADR_log.md`: ADR-010, ADR-053, ADR-060 through ADR-063, ADR-066, and ADR-088.
- `docs/architecture/04_pipeline_and_agent_concepts.md`, section 7: deterministic component boundary.
- `docs/architecture/05_relationship_evaluator_concept.md`: applicability, state, evidence, and non-responsibilities.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, sections 4, 5, 13, and 14: post-JOIN gate, uncertainty, and persistence boundary.
- `docs/architecture/07_observation_reasoning_agent.md`, sections 2.3 and 4: downstream self-contained evidence consumption.
- `docs/architecture/10_open_decisions_and_backlog.md`, section 4: exact serialization resolved by this design; deferred rule extensions remain excluded.

The design conforms by keeping evaluation deterministic, Metric-only, current-state-only, self-resolving, and free of orchestration, persistence, LLM, retrieval, or diagnostic responsibilities. MetricAnalysisResult 1.0 malformed payloads remain contract errors, while missing valid participant evidence follows the accepted unknown/uncertain semantics. No Open or Deferred capability is promoted into scope.
