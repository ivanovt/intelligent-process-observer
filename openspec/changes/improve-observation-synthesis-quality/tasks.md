## 1. Sequencing and evaluation cases

- [x] 1.1 Confirm the implementation base contains the archived/canonical results of `improve-run-result-and-report-usability` and verify no renderer/UI work is included in this change; stop for rebase rather than duplicating missing prerequisite behavior.
- [x] 1.2 Add representative evidence-safe evaluation fixtures for direct connectivity versus auxiliary logging evidence, absent Relationships, compatible and conflicting temporal evidence, symmetric relative change, stable-only findings, material limitations, and forbidden causal/severity/confidence/recommendation language; verify fixtures contain no provider query, credential, or private trace payload.

## 2. Objective-oriented finding guidance

- [x] 2.1 Add failing request-capture tests proving finding instructions treat the Observation objective/Lens metadata as relevance context only, require catalog grounding, distinguish direct and auxiliary evidence, prohibit unsupported cross-Lens linkage, consolidate compatible temporal evidence without a count target, and preserve conflicts.
- [x] 2.2 Add failing guidance/evaluation coverage for the exact symmetric `relative_level_change` formula and the Home DEV `2.28` versus `1.04` counterexample; verify ordinary “74.56% higher” wording is rejected by the scenario rubric without adding a production keyword validator.
- [x] 2.3 Refine the private finding instructions and verify existing finding freeze, unknown-reference rejection, no-knowledge input boundary, request count, failure mapping, and trace behavior remain unchanged.

## 3. Evidence-sensitive overall-state guidance

- [x] 3.1 Add failing request-capture and representative-case tests proving overall-state guidance uses accepted significance/evidence-availability meanings rather than finding count, including stable-only, notable auxiliary, and limitations-with-findings cases.
- [x] 3.2 Refine the private overall-state instructions without adding rationale fields or deterministic count invariants; verify the invocation remains knowledge-isolated, tool-free, single-request, and compatible with all three accepted states.

## 4. Informative Report Agent guidance

- [x] 4.1 Add failing report-adapter/evaluation tests for evidence-derived non-tautological `overall_assessment`, mixed direct/auxiliary evidence without causal linkage, concise exact source-key coverage, symmetric comparison preservation, uncertainty from supplied limitations, and hypothesis modality.
- [x] 4.2 Refine the private Report Agent instructions and verify exact source membership, unchanged overall state, renderer-owned Markdown structure, no tools/retries, safe failures, and the prohibition on new findings, recommendations, certainty, or root-cause claims remain enforced.

## 5. Trace-backed quality evaluation and verification

- [x] 5.1 Document the bounded PASS/FAIL/INCONCLUSIVE Home DEV synthesis rubric in the developer guide, including objective alignment, non-causal separation, consolidation without lost conflicts, comparison accuracy, state rationale, report usefulness, forbidden semantics, run-ID-only recording, and private trace handling; verify it introduces no scalar score or general evaluation framework.
- [x] 5.2 Run focused reasoning, report, production-composition, tracing, and evaluation-fixture tests and verify request budgets, deterministic validation, grounding, failures, and public artifacts remain unchanged.
- [x] 5.3 With approved local Home DEV/OpenRouter prerequisites, launch a representative completed window after the usability change, apply every applicable rubric dimension, and record only run ID plus dimension outcomes in the implementation handoff; treat unexercised direct/auxiliary evidence as INCONCLUSIVE and any exercised semantic violation as FAIL without weakening validators.
- [ ] 5.4 Run `make check` as the final local verification step and verify Ruff, backend tests, frontend lint/tests/build, and strict OpenSpec validation all pass before implementation review, archive, and pull-request preparation.
