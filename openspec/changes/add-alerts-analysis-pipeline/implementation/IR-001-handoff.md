# IR-001 Correction Handoff

## Implemented behavior

- `AlertFinding.evidence_refs` requires at least one item.
- The pipeline revalidates agent-supplied completion model instances through dumped data, so
  constructed or mutated empty-reference findings are rejected as `agent_failed` before the
  builder.
- The result builder independently rejects an empty-reference finding that bypasses model
  validation, preserving the contextual `result_validation_failed` /
  `alert_result_builder` mapping in the pipeline.

## Evidence

| Obligation | Exercised boundary and assertion | Result |
|---|---|---|
| Strict completion contract | `test_agent_request_and_completion_contracts_are_strict` constructs a finding with `evidence_refs=()` | `ValidationError` |
| Agent failure before builder | `test_required_agent_failures_are_rejected_before_builder` and `test_mutated_agent_completion_with_empty_evidence_refs_fails_before_builder` use raw and constructed empty-reference completions with a fail-on-use builder | artifact-free `agent_failed`; builder is not invoked |
| PydanticAI adapter boundary | `test_empty_finding_evidence_references_are_rejected_by_adapter` emits an empty-reference structured output | `UnexpectedModelBehavior`, one model call |
| Builder defense in depth | `test_builder_rejects_constructed_finding_without_evidence_references` passes model-constructed invalid objects to the builder | `ValueError` before construction/persistence |

## Verification

`cd backend && uv run pytest tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py tests/test_alert_result_builder.py tests/test_pydantic_ai_alerts_adapter.py -q` — 47 passed.

`cd backend && uv run ruff check src/app/alerts/contracts.py src/app/alerts/pipeline.py src/app/alerts/result_builder.py tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py tests/test_alert_result_builder.py tests/test_pydantic_ai_alerts_adapter.py` — passed.

`cd backend && uv run ruff format --check src/app/alerts/contracts.py src/app/alerts/pipeline.py src/app/alerts/result_builder.py tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py tests/test_alert_result_builder.py tests/test_pydantic_ai_alerts_adapter.py` — passed.

## Scope and follow-up

Important invariant: non-zero agent findings cannot be ungrounded at either the agent
boundary or builder boundary; valid zero-record results still use an empty findings list.

Known limitations within approved scope: none.

Deviations from forecast: none (Coordinator disposition: PENDING).

Plan change requested: none.

Shared knowledge candidates: none.

Commit SHA: `a81ff7d` (atomic IR-001 correction commit).
