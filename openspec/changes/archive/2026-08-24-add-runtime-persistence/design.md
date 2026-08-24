## Context

See `proposal.md` for motivation and `specs/runtime-persistence/spec.md` for required behavior. The existing backend already has one asynchronous SQLAlchemy persistence package, a common declarative base, PostgreSQL JSONB support, Alembic migrations, and persisted Observation, Metric Lens, and Relationship definition tables. There is currently no runtime storage.

The runtime contracts require structured artifacts, common Lens lifecycle metadata, type-specific analytical payloads, and explicit treatment of failed/non-usable LensRuns. They do not require a runtime API, execution engine, retry/replay behavior, provider adapters, or analytical payload producers in this change.

## Goals / Non-Goals

**Goals:**

- Add the smallest relational runtime aggregate that can be queried and integrity-checked independently of definitions.
- Preserve accepted artifacts faithfully, including their type-specific JSON structure, contract-defined identity, version, provenance, and traceability fields.
- Enforce the distinct persistence and usability semantics of Metric, Alert, and Log results without creating Alert/Log placeholder results.
- Reuse the existing async SQLAlchemy session, models module, Alembic chain, and repository-style persistence boundary.

**Non-Goals:**

- Creating or dispatching runs, implementing state-machine orchestration, enforcing JOIN/gate behavior, or evaluating analytical content.
- Replacing or generalizing the existing definition persistence model, adding Alert/Log definitions, or changing the Observation definition API.
- Validating the full domain schema of Metric, Alert, Log, Relationship, or Observation-level payloads; their final contract owners remain later pipeline stages.
- Storing raw telemetry, raw provider payloads, operational log streams, retries, replays, scheduling records, or frontend/API representations.

## Decisions

### One runtime aggregate beside the definition aggregate

Add `observation_runs` and `lens_runs` tables beside the current definition tables. An ObservationRun has a foreign key to `observation_definitions`; a LensRun has a foreign key to its parent ObservationRun. Run records keep the stable Observation ID, Lens ID, Lens type, lifecycle state, timestamps, structured reason/failure metadata, and optional provenance/execution-context mappings.

ObservationRun lifecycle is `pending -> running -> completed | failed`. LensRun lifecycle is `pending -> running -> completed | partial | failed`, with `completed`, `partial`, and `failed` as its terminal states. A partial LensRun does not make the ObservationRun partial.

The existing definition persistence currently has only Metric Lens rows, while this foundation must support the accepted Alert and Log artifacts. Therefore, LensRun identity is stored as the immutable `(observation_id, lens_id, lens_type)` execution correlation rather than introducing a new polymorphic definition table or a second definition abstraction. The explicit relational path `artifact -> lens_run -> observation_run -> observation_definition`, unique run identities, and artifact cardinality constraints supply the query/integrity guarantees required now. A future approved Alert/Log definition change can add definition validation without altering the runtime artifact model.

Alternative considered: make LensRun reference the current `metric_lens_definitions` table. Rejected because it would hard-code the runtime foundation to Metric-only definitions and prevent the agreed Alert/Log artifacts from using the same persistence model.

### Shared Lens-result storage with type-specific persistence eligibility

Use one `lens_analysis_results` table with a result-type discriminator (`metric`, `alert`, `log`), a unique foreign key to `lens_runs`, and a JSONB payload that preserves the complete type-specific result contract. It stores the contract-defined result version for the versioned Metric, Alert, and Log result artifacts.

The persistence integrity requirements are:

- result type matches LensRun type;
- result identity matches the associated ObservationRun and LensRun;
- a Metric result status is `completed`, `partial`, or `failed` and matches the Metric LensRun status;
- an Alert or Log result status is `completed` or `partial` and matches the corresponding LensRun status; and
- there is at most one Lens analysis result row per LensRun.

A failed Metric result uses the accepted minimal failed contract and is retained for traceability; it is not a usable LensAnalysisResult. A failed Alert or Log LensRun has no result row. The implementation will apply the above integrity requirements at the minimal appropriate persistence boundary; this design does not pre-decide which requirements belong in database constraints, contract validation, repository validation, or a combination.

Alternative considered: one fully generic artifact table. Rejected because LensRun ownership, type-specific eligibility, and one-result cardinality would move essential integrity and query behavior into opaque JSONB.

Alternative considered: one table per Lens result type. Rejected because the shared correlation/integrity needs are the same, while type-specific payload schemas are intentionally versioned and evolving. A discriminator plus JSONB avoids premature database schemas without weakening run correlation.

### Separate Observation-level artifact storage without invented domain versions

Add separate artifact tables for `relationship_evaluations`, `observation_analysis_results`, and `observation_reports`. Each is related to its ObservationRun. Relationship evaluations retain their evaluated relationship ID and a complete self-contained payload, with zero or one row per `(observation_run_id, relationship_id)`. Observation analysis results retain their complete payload and the accepted `schema_version`, with zero or one row per ObservationRun. Observation reports retain the accepted envelope fields—Observation/ObservationRun correlation, generated time, Markdown format, and content—and have zero or one row per ObservationRun; a persisted report references the ObservationAnalysisResult that supplied it.

These cardinalities allow an ObservationRun to fail at the zero-usable-results gate before Relationship Evaluation, Observation Reasoning, and Report Generation. In that path, the runtime record and available Lens artifacts are persisted without fabricating an ObservationAnalysisResult or ObservationReport. Uniqueness constraints enforce at most one ObservationAnalysisResult and at most one ObservationReport per ObservationRun.

RelationshipEvaluation's exact serialized schema is still Open, so the persistence model preserves its self-contained payload without requiring a domain-level schema/version field. ObservationReport is a Markdown presentation artifact with a minimal metadata envelope, not a versioned domain schema. No internal storage-envelope version is introduced because it is unnecessary for this change.

### Contracts and retrieval stay internal

Introduce small internal Pydantic persistence-contract models for run envelopes and artifact persistence inputs/outputs. They validate persistence-owned lifecycle and cross-record correlation requirements; existing/future analytical Builders and Validators retain ownership of type-specific semantic payload validation. Repository methods persist one run/artifact at a time within the caller's async transaction and load an ObservationRun with all associations using eager loading.

No FastAPI routes, API transport models, or runtime service that instantiates executions are added. Tests call the internal persistence contract/repository boundary directly.

Alternative considered: expose CRUD endpoints now. Rejected because runtime execution and external lifecycle APIs are explicitly out of scope and would create a public contract before orchestration semantics exist.

### Schema migration and compatibility

Add one forward Alembic migration after `20260822_01`. It creates only the runtime tables, foreign keys, indexes, and cardinality constraints needed by this design. Existing definition rows need no backfill. Downgrade drops only these new runtime tables in dependency order.

The older architecture text describing database technology/schema as Open remains unchanged. This is a documentation synchronization item: the approved workspace stack and existing implementation already select PostgreSQL, async SQLAlchemy, Psycopg 3, and Alembic.

## Risks / Trade-offs

- [Future Alert/Log definition tables do not yet exist] → Keep LensRun's definition identity as an immutable runtime correlation and defer new definition foreign-key validation to the approved definition change that introduces those types.
- [JSONB payload evolution] → Preserve contract-defined result type/version where it exists and validate shared correlation fields before storage; domain producers own payload-version compatibility.
- [A failed Metric result could be mistaken for downstream evidence] → Persist its failed status and expose usability separately; tests verify it is non-usable.
- [A persistence layer can be misused to simulate execution] → Expose only record/store/load operations and omit orchestration, dispatch, retry, and producer behavior.
- [Run/artifact writes can become inconsistent if composed incorrectly] → Require each repository operation to use the caller's async transaction and test lifecycle, correlation, and cardinality integrity requirements.
- [Existing schema migration may already be deployed] → Add an additive migration only; no definition-table rewrite or data backfill is required.

## Migration Plan

1. Add internal run/artifact persistence contracts, SQLAlchemy models, repository operations, and focused tests.
2. Add and review an additive Alembic migration chained from `20260822_01`.
3. Apply the migration before any later runtime producer uses the persistence contract; no existing data requires migration.
4. On rollback, deploy code that no longer writes runtime data before downgrading the additive runtime tables. No production deletion or database reset is part of this change.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — definition/run separation and persisted LensRun history.
- `docs/architecture/02_architecture_principles_and_runtime.md` — deterministic lifecycle ownership, structured artifact boundaries, and persistence requirements.
- `docs/architecture/05_relationship_evaluator_concept.md` — self-contained RelationshipEvaluation identity/evidence.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — common Lens envelope, terminal/usable semantics, unavailable Lens handling, and persistence boundary.
- `docs/architecture/08_observation_analysis_result_contract.md` — Observation analysis identity and traceability.
- `docs/architecture/09_report_agent.md` — Markdown report envelope and presentation boundary.
- `docs/architecture/15_alert_analysis_result_contract.md` — usable Alert identity/provenance and failed-result exclusion.
- `docs/architecture/23_log_analysis_result_contract.md` — usable Log identity/provenance and failed-result exclusion.
- `docs/architecture/10_open_decisions_and_backlog.md` — RelationshipEvaluation serialization and report-template details remain open; persistence does not resolve them.
- `docs/architecture/11_glossary_and_naming.md` — names and lifecycle terminology.
- `docs/architecture/03_ADR_log.md` — ADR-035, ADR-037–039, ADR-054–059, ADR-066–068, ADR-085–087, ADR-116–121, ADR-135, and ADR-147–148.
