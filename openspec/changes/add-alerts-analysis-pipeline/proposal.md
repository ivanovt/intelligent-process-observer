## Why

Alert Lens definitions and runtime persistence can already represent an Alert LensRun, but the system has no internal pipeline that turns one already-created run into its accepted, usable AlertAnalysisResult. This change makes the accepted deterministic acquisition/analysis boundary and bounded Alert Analysis Agent executable without coupling it to a Jira transport or a production model provider.

## What Changes

- Add the internal, provider-transport-free Alerts Analysis Pipeline for one already-running Alert LensRun.
- Add strict AlertAnalysisResult 1.0 contracts, deterministic normalization and mandatory evidence analysis, the zero-record fast path, bounded optional tools, and deterministic result validation.
- Add framework-neutral Alert provider and Alert Analysis Agent ports, plus an injected-model PydanticAI infrastructure adapter with no production model selection.
- Persist completed and partial Alert artifacts atomically with the existing terminal LensRun transition; preserve failed Alert result absence.
- Define the canonical `alert://` evidence-reference grammar and strict agent-completion versus result-builder failure boundary, alongside the previously proposed partial-reason and builder-failure mappings.

## Capabilities

### New Capabilities

- `alerts-analysis-pipeline`: Analyze a single already-created Alert LensRun into a validated, persisted completed or partial AlertAnalysisResult, or a failed LensRun without an Alert result.

### Modified Capabilities

- None.

## Impact

- Affected code: new internal backend Alert domain/application package, one infrastructure-only PydanticAI Alert adapter, and bounded reuse of the existing runtime persistence repository.
- Affected persistence: existing LensRun and LensAnalysisResult artifact boundary only; no new table, migration, public endpoint, or definition schema.
- Dependencies: none added; the accepted `pydantic-ai-slim` dependency already exists and remains confined to infrastructure.
- Architecture references: `docs/architecture/02_architecture_principles_and_runtime.md`, `03_ADR_log.md` (ADR-089--132 and ADR-152), `04_pipeline_and_agent_concepts.md`, `06_runtime_contracts_and_execution_semantics.md`, `10_open_decisions_and_backlog.md`, `13_alert_lens_and_analysis_concept.md` through `20_alert_analytical_tools.md`; `openspec/specs/observation-definition-api/spec.md` and `openspec/specs/runtime-persistence/spec.md`.
