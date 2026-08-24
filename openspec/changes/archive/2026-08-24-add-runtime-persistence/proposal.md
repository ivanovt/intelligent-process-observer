## Why

The existing persistence layer stores engineer-authored Observation, Lens, and Relationship definitions, but it cannot retain an execution's lifecycle or the structured artifacts later runtime stages need to consume. A small, queryable runtime persistence foundation is required before orchestration and analytical pipelines can be implemented without inventing a separate storage model per feature.

## What Changes

- Add internal persistence contracts and PostgreSQL-backed storage for `ObservationRun` (`pending -> running -> completed | failed`) and its `LensRun` records (`pending -> running -> completed | partial | failed`), including runtime identity, lifecycle state, timestamps, structured reason/failure metadata, and provenance/execution context.
- Persist one type-specific Lens analytical artifact per LensRun according to the accepted type-specific lifecycle policy: Metric results for `completed`, `partial`, and minimal `failed` outcomes; Alert and Log results only for `completed` or `partial` outcomes.
- Preserve the distinction between persistence eligibility and downstream usability: completed and partial Lens results are usable; a persisted failed MetricAnalysisResult is traceability data, not usable analytical evidence; failed Alert and Log LensRuns have no type-specific result artifact.
- Persist zero or more self-contained `RelationshipEvaluation` artifacts and at most one each of `ObservationAnalysisResult` and Markdown `ObservationReport` per ObservationRun for the MVP, preserving schema/version information only where the accepted artifact contract defines it.
- Provide internal retrieval that restores the runtime execution and correlations without confusing a missing artifact with an artifact that contains valid empty optional sections.
- Reuse the existing PostgreSQL, async SQLAlchemy, Psycopg 3, Alembic, and persistence-package foundation. No HTTP endpoint, orchestration, analytical pipeline, new dependency, or second persistence abstraction is introduced.

## Capabilities

### New Capabilities

- `runtime-persistence`: Store and retrieve runtime executions, their lifecycle state, and correlated analytical and presentation artifacts.

### Modified Capabilities

None.

## Impact

- Affected backend: persistence models, internal persistence contracts/repositories, Alembic migration, and persistence-focused tests.
- Existing definition tables and `ObservationRepository` remain the source for definition objects; this change adds runtime storage alongside them rather than duplicating definitions.
- Existing external API behavior is unchanged; the persistence contracts are internal foundations for later runtime changes.
- No dependency or architecture-document modification is proposed. The older architecture wording that calls database technology/schema open is a documentation synchronization issue: this change follows the approved workspace stack and the established PostgreSQL persistence layer.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — definition objects are distinct from runtime executions.
- `docs/architecture/02_architecture_principles_and_runtime.md` — runtime workflow, lifecycle boundaries, structured artifacts, and persistence boundary.
- `docs/architecture/05_relationship_evaluator_concept.md` — self-contained `RelationshipEvaluation` semantics.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — common Lens lifecycle envelope, usable/unavailable distinction, and persistence expectations.
- `docs/architecture/08_observation_analysis_result_contract.md` — versioned Observation-level analytical artifact and traceability fields.
- `docs/architecture/09_report_agent.md` — Markdown ObservationReport envelope and separation from analysis.
- `docs/architecture/15_alert_analysis_result_contract.md` — Alert result identity, provenance, lifecycle, and failed-result exclusion.
- `docs/architecture/23_log_analysis_result_contract.md` — Log result identity, provenance, lifecycle, and failed-result exclusion.
- `docs/architecture/10_open_decisions_and_backlog.md` — database/schema wording remains a documented synchronization item, not permission to change the approved stack.
- `docs/architecture/11_glossary_and_naming.md` — canonical runtime and artifact terminology.
- `docs/architecture/03_ADR_log.md` — ADR-035, ADR-037–039, ADR-054–059, ADR-066–068, ADR-085–087, ADR-116–121, ADR-135, and ADR-147–148.
