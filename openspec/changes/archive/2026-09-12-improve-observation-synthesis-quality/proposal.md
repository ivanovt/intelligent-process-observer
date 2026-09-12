## Why

The successful Home DEV run produced valid grounded artifacts, but its analytical narrative did not answer the configured objective clearly: stable Connected Devices evidence and a separate pod logging spike became five repetitive findings, the overall assessment merely restated the enum, and the symmetric relative-change measure was incorrectly described as an ordinary percentage increase. The reasoning and report presentation guidance need focused quality criteria while preserving strict evidence, knowledge, and lifecycle boundaries.

## What Changes

- Refine finding-formation guidance so the Observation analytical objective focuses selection and synthesis without becoming evidence or permitting unsupported conclusions.
- Require findings to distinguish direct evidence about the objective from other notable Lens evidence and to avoid causal or cross-Lens linkage when no Relationship evidence supports it.
- Encourage coherent consolidation of related current/reference/history evidence instead of mechanically producing one finding per field, while preserving all cited evidence and avoiding ranking or severity semantics.
- Explicitly define `relative_level_change` for reasoning as the accepted symmetric dimensionless comparison; agent-authored prose must not present it as ordinary percentage increase/decrease and should prefer the underlying current/reference means when explaining large changes.
- Refine overall-state guidance so the enum is selected from evidence significance and availability rather than finding count, with no new state or hard count invariant.
- Refine Report Agent guidance so `overall_assessment` explains the selected state using only supplied findings and limitations, rather than paraphrasing the enum, and source-item presentations remain concise without losing meaning or certainty.
- Add deterministic prompt/request tests, adversarial scripted output tests, and a trace-backed Home DEV evaluation rubric for objective alignment, non-causal separation, symmetric-change accuracy, consolidation, and informative overall assessment.
- Preserve current structured contracts, evidence references, knowledge grounding, zero-retry/request budgets, failure semantics, presentation-only Report boundaries, and the prohibition on severity, confidence, recommendations, probability, ranking, and root-cause claims.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `observation-reasoning`: Add objective-oriented, non-redundant, comparison-semantics-aware finding and overall-state guidance with evaluation scenarios.
- `report-generation`: Require an informative evidence-derived overall assessment and concise faithful item presentation without adding analysis.

## Impact

- Affected backend areas: Observation finding and overall-state adapter guidance, Report Agent guidance, focused tests/evaluation fixtures, and developer evaluation documentation.
- No public API, Pydantic/domain schema, persisted artifact, retrieval behavior, model default, dependency, timeout, token limit, request budget, lifecycle, or UI implementation change.
- Implementation is sequenced after `improve-run-result-and-report-usability` is merged so live evaluation uses the refined report/run-detail presentation and avoids overlapping report tests/documentation.
- The change operationalizes the already deferred prompt/evaluation refinement area without selecting general evaluation infrastructure or a new model.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md` — Observation-level synthesis, findings-before-knowledge, and reasoning/report separation.
- `docs/architecture/07_observation_reasoning_agent.md` — evidence-only findings, analytical objective context, optional hypotheses, and overall-state semantics.
- `docs/architecture/08_observation_analysis_result_contract.md` — minimal findings/hypotheses/limitations contract and excluded ranking/severity semantics.
- `docs/architecture/09_report_agent.md` — logical engineering narrative and presentation-only responsibility.
- `docs/architecture/03_ADR_log.md` — ADR-087 (Report Agent boundary), ADR-152 (PydanticAI infrastructure adapter), ADR-169 (role-specific production prompts and later refinement), and ADR-171 (trace-backed troubleshooting).
- `docs/architecture/10_open_decisions_and_backlog.md` — broader prompt/model evaluation tuning remains open beyond this bounded approved refinement.
