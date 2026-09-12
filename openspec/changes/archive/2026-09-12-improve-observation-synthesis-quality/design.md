## Context

See `proposal.md` for the quality defects observed in run `b0ddf4df-f220-4955-8b87-36c3f10c8a4e`. The existing three-phase reasoning architecture and Report Agent contract are correct: findings are evidence-only, hypotheses are knowledge-grounded, overall state is knowledge-isolated, and reporting is presentation-only. The weakness is the minimal role guidance and lack of a focused qualitative evaluation rubric.

This change follows `improve-run-result-and-report-usability`. It assumes that change has landed before implementation so the completed run can be evaluated through readable Metric, traceability, and Report views. It must not absorb or duplicate renderer/frontend work.

## Goals / Non-Goals

**Goals:**

- Make finding formation use the analytical objective as relevance context while retaining catalog-only grounding.
- Prevent unsupported causal linkage and ordinary-percentage misuse of symmetric Metric comparison evidence.
- Encourage coherent findings without imposing count, ranking, taxonomy, or suppression rules.
- Make overall-state selection and the report's overall assessment evidence-sensitive rather than tautological.
- Establish deterministic guidance coverage plus a bounded private live-quality rubric.

**Non-Goals:**

- Do not change reasoning/report contracts, phases, input projections, evidence catalogs, builders, validators, persistence, APIs, or UI.
- Do not add a semantic repair model, retry, output filter, keyword blacklist, scoring framework, judge model, dataset service, telemetry platform, or dependency.
- Do not require an exact finding count, wording, order, severity, priority, confidence, recommendation, root cause, or causal classification.
- Do not change the Metric comparison formula or compute a conventional percentage in the agent.
- Do not implement a real knowledge backend or alter empty-hypothesis behavior.

## Decisions

### 1. Expand only the three role-owned instruction constants

The Observation Reasoning adapter will use explicit private constants for finding formation and overall-state determination; the Report adapter will refine its existing private system prompt. No prompt text enters settings, domain contracts, persistence, public APIs, or frontend configuration.

Finding guidance will:

- identify the analytical objective and semantic Lens metadata as relevance context, never evidence;
- require catalog references for every conclusion;
- distinguish direct objective evidence from auxiliary evidence;
- prohibit cross-Lens causal/confirming/contradicting claims without Relationship evidence;
- encourage one coherent statement when current, reference, and History evidence support the same conclusion, without setting a count limit;
- preserve materially distinct or conflicting conclusions; and
- define `relative_level_change` as the accepted symmetric dimensionless measure and prohibit ordinary-percentage wording.

Overall-state guidance will restate the accepted meanings and explicitly prohibit a finding-count shortcut. It will not add rationale to the strict output contract, which remains the single enum.

Report guidance will require `overall_assessment` to explain the supplied state using supplied findings/limitations, keep each source-keyed presentation complete and concise, avoid causal linkage absent from the source, and preserve symmetric comparison language.

Alternative considered: add fields for relevance, significance, rationale, or finding groups. Rejected because that would introduce new domain semantics and schema changes beyond the MVP contract.

### 2. Keep semantic quality out of deterministic runtime validation

Existing validators continue to enforce structure, exact source membership, evidence/reference grounding, state preservation, and absence of undeclared fields. They will not attempt to prove objective alignment, redundancy, semantic equivalence, or percentage meaning through keyword checks.

This follows the accepted report contract: arbitrary prose faithfulness is an instruction/evaluation concern. Exact tautologies or false percentage phrases may appear in evaluation fixtures, but no production blacklist will reject arbitrary model prose. A model quality failure remains visible in private traces and evaluation results; it is not silently rewritten, filtered, or retried.

Alternative considered: reject strings containing `%`, `cause`, or the state label. Rejected because legitimate evidence may contain those words and lexical rejection would claim semantic proof it cannot provide.

Alternative considered: add a second judge-model request. Rejected because it changes request budgets, cost, latency, failure semantics, and architecture.

### 3. Add a repository-owned scenario rubric without evaluation infrastructure

Focused adapter tests will capture model requests and assert that the relevant phase receives every required semantic instruction while other phases and budgets remain unchanged. Representative deterministic fixtures will document good and bad outputs for the accepted scenarios and exercise existing structural validation where applicable. Semantic rubric assertions remain scenario-specific test/documentation evidence, not imported production code.

The developer guide will define a compact rubric with these pass conditions:

- the directly relevant connectivity evidence is stated distinctly from auxiliary logging evidence;
- no unsupported causal/confirming relationship is asserted;
- mutually reinforcing current/reference/History facts are coherently presented without losing distinct contradictions;
- symmetric `relative_level_change` is not called ordinary percentage increase/decrease;
- overall state is plausible under the accepted meanings and not selected by count alone;
- report `overall_assessment` gives evidence-derived meaning beyond the enum label;
- each source item remains complete, and no recommendation, severity, confidence, probability, ranking, or root-cause certainty appears.

The rubric records PASS/FAIL per dimension, plus a short evidence-safe note. It does not create a scalar score, confidence measure, or persisted product artifact.

### 4. Require one trace-backed Home DEV evaluation before acceptance

With approved local credentials and development tracing, implementation will launch the Home DEV Observation over a completed representative window after the usability change is available. The evaluator will inspect the persisted analysis/report and private traces, recording only run ID and rubric outcomes in the implementation handoff.

A run is INCONCLUSIVE if the evidence does not exercise both direct connectivity and auxiliary logging comparison behavior, or if execution fails for an unrelated provider/configuration reason. An exercised violation is FAIL and must not be hidden by changing deterministic policies. PASS requires every rubric dimension applicable to the run. The live run remains outside `make check` and no trace content enters Git.

Alternative considered: make live OpenRouter evaluation part of CI. Rejected because network/model variability and credentials would make repository verification nondeterministic.

### 5. Preserve source boundaries and sequencing

Implementation may change only infrastructure-owned prompts, focused adapter/report/reasoning tests or evaluation fixtures, and developer evaluation documentation. It will not edit domain request/result models or executors/builders unless a discovered contradiction requires re-planning. The change starts from main only after `improve-run-result-and-report-usability` is merged; its UI/renderer behavior is consumed for manual review but not modified here.

## Risks / Trade-offs

- [Prompt guidance improves but cannot guarantee prose quality] → Require representative scenario coverage and one trace-backed live evaluation while retaining strict grounding validators.
- [Consolidation guidance accidentally hides distinct evidence] → Explicitly preserve conflicts/materially distinct conclusions and avoid numeric count targets.
- [Objective focus turns configured intent into evidence] → State repeatedly that objective/Lens metadata affect relevance only; every finding still requires catalog evidence.
- [A false percentage survives despite guidance] → Include the exact Home DEV counterexample and formula in prompts/tests/rubric; do not add unsafe lexical runtime validation.
- [Overall-state assessment remains subjective] → Anchor guidance to accepted state meanings and limitations while preserving agent ownership and no count invariant.
- [Changes overlap the earlier usability branch] → Require that change to merge first and keep all renderer/UI files outside this implementation scope.

## Migration Plan

1. Confirm `improve-run-result-and-report-usability` is present on the implementation base.
2. Add failing request-capture tests for finding, overall-state, and report guidance plus representative evaluation fixtures.
3. Refine the three private role instructions without changing contracts, budgets, or retries.
4. Add the bounded quality rubric and private trace-handling procedure to developer documentation.
5. Run focused reasoning/report/trace tests and the trace-backed Home DEV evaluation.
6. Run `make check` as the final local verification step.

No data migration, dependency, API transition, or configuration change is required. Rollback is a code/documentation revert; persisted results remain valid under the unchanged contracts.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md`: deterministic orchestration, evidence-only findings, bounded hypotheses, and separate presentation remain unchanged.
- `docs/architecture/07_observation_reasoning_agent.md`: the objective is admitted semantic context; findings remain evidence-grounded and overall state remains agent-owned.
- `docs/architecture/08_observation_analysis_result_contract.md`: no new field, ranking, severity, confidence, recommendation, or root-cause semantic is introduced.
- `docs/architecture/09_report_agent.md`: the Report Agent organizes a logical engineering narrative without new analysis.
- `docs/architecture/03_ADR_log.md`: ADR-087, ADR-152, ADR-169, and ADR-171 permit this bounded infrastructure-owned prompt/evaluation refinement.
- `docs/architecture/10_open_decisions_and_backlog.md`: the change resolves only the stated Home DEV quality cases; general prompt/model evaluation strategy remains open.

The design refines implementation-owned guidance and evaluation evidence inside accepted boundaries. It does not change the architecture package or silently decide a general evaluation framework.
