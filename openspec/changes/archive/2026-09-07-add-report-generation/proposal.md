## Why

The MVP can now produce a validated `ObservationAnalysisResult`, but it cannot yet turn that machine-readable artifact into the human-readable report required by the normal Observation workflow. Report generation is the next roadmap feature because it provides the presentation boundary while preserving the analytical result as the sole source of truth.

## What Changes

- Add an English-language Report Generation capability that converts one validated `ObservationAnalysisResult` plus minimal Observation semantic context into one Markdown `ObservationReport`.
- Add a strict framework-neutral report request, output envelope, agent port, and typed execution outcome around the existing analysis-result contract.
- Use a bounded PydanticAI presentation adapter with no tools or retrieval capability, validate its source-keyed structured output, and construct all Markdown structure deterministically.
- Preserve observation and run identity, represent every input finding, hypothesis, limitation, and available traceability reference without adding analysis, recommendations, or certainty.
- Treat model-authored and source-authored text as plain untrusted content: deterministic code enforces structure, membership, identity, and traceability, while English semantic faithfulness remains an agent-instruction and evaluation obligation rather than a lexical runtime classifier.
- Keep exact Markdown headings and engineer/operator template variants outside the public contract; require readable English organization and semantic completeness instead.
- Keep persistence, ObservationRun lifecycle, top-level Observation execution, rendering, notification, localization, and public API behavior outside this change.

## Capabilities

### New Capabilities

- `report-generation`: Presentation-only generation and validation of an English Markdown `ObservationReport` from `ObservationAnalysisResult` and minimal Observation semantic context.

### Modified Capabilities

None.

## Impact

- Adds a focused backend report-generation package and a PydanticAI infrastructure adapter following existing agent integration patterns.
- Reuses the existing reasoning contracts, PydanticAI dependency, OpenRouter configuration/composition conventions, and persistence-compatible report envelope; no dependency or database migration is required.
- Adds unit, adapter, failure-boundary, adversarial presentation-evaluation, and in-memory integration tests.
- Does not add or change HTTP endpoints, persistence repository behavior, frontend behavior, or runtime lifecycle semantics.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, section 9 — Report Generation input/output boundary.
- `docs/architecture/08_observation_analysis_result_contract.md` — authoritative analytical input and traceability structure.
- `docs/architecture/09_report_agent.md` — Report Agent role, inputs, exclusions, responsibilities, and Markdown envelope.
- `docs/architecture/03_ADR_log.md`: ADR-050, ADR-085, ADR-086, ADR-087, and ADR-152.
- `docs/architecture/10_open_decisions_and_backlog.md`, section 6 — exact template variants remain open; English is fixed for this change by explicit user decision.
