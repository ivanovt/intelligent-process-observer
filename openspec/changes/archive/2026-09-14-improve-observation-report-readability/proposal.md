## Why

Generated reports bury the engineering assessment beneath repeated source IDs and locator paths. A support engineer should be able to understand how the observed evidence answers the Observation objective, find each finding quickly, and inspect complete traceability only when needed. Copied Markdown should remain readable as a standalone artifact.

## What Changes

- Present an objective-first, evidence-only opening assessment that states the supplied analytical state in human language, uses available current and configured reference values without calling them a baseline, and briefly notes material auxiliary observed events. Preserve uncertainty and material contrasts without adding severity, causes, or recommendations.
- Present every finding once in the opening's order, with a short subject-and-observed-event heading and concise current-observation-first prose. Use report-local finding numbers for reading; retain exact source finding IDs in the reference appendix.
- Keep possible explanations separate and explicitly unconfirmed, with readable links to supporting finding numbers. Keep analysis limitations distinct and describe empty collections honestly.
- Move exact evidence and knowledge references to a final technical appendix. Group evidence by finding and source so source type and exact source ID appear once per group, while retaining every exact locator and the mapping to source finding IDs. Keep knowledge provenance distinct from observational evidence.
- Make the report header human-oriented: a neutral English summary of the Observation objective, the exact observed window start and end in UTC, and a short Observation ID excerpt. Preserve full Observation/run IDs, exact source overall state, and generation time in technical details. The short excerpt is for orientation, not a uniqueness guarantee.
- Make ordinary copied Markdown prose readable without blanket backslash escaping, while retaining deterministic ownership of document structure and inert rendering of untrusted content.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `report-generation`: Revise the report input/presentation and Markdown behavior for objective-led reading, exact observed-window context, source-faithful finding order, end-of-report traceability, and readable safe copied content.

## Architecture References

- `docs/architecture/08_observation_analysis_result_contract.md` — source analytical state, findings, hypotheses, limitations, and traceability semantics remain unchanged.
- `docs/architecture/09_report_agent.md`; ADR-085, ADR-086, ADR-087, and ADR-175 in `docs/architecture/03_ADR_log.md` — preserve presentation-only generation and the minimal input boundary. ADR-175 explicitly admits only the immutable UTC ObservationRun analysis window as additional report context.
- ADR-012 in `docs/architecture/03_ADR_log.md` and `docs/architecture/01_observation_lens_concept.md` — configured reference periods and persisted History are not baselines.
- ADR-172 in `docs/architecture/03_ADR_log.md` — persisted Markdown and exact Copy Markdown remain the artifact boundary; output stays within the accepted safe browser subset.
- `docs/architecture/10_open_decisions_and_backlog.md` — this change does not establish engineer/operator template variants or a fixed public Markdown schema.

## Impact

The report request/presentation contracts, execution-to-report projection, deterministic Markdown renderer, Report Agent guidance, and focused backend tests will change. Existing persisted reports remain immutable and are not rewritten. The browser continues to display persisted Markdown and copy its exact content; no new API, database migration, dependency, renderer framework, analytical field, or provider data access is proposed. The approved window-input decision is recorded in ADR-175 and the Report Agent architecture contract.
