# VS-08 Handoff — injected PydanticAI Alert adapter

## Implemented behavior

`PydanticAIAlertAnalysisAgent` is an infrastructure-only, injected-model implementation
of the framework-neutral Alert agent port. It exposes the fixed three optional tools,
routes every framework-emitted call (including rejected unknown/non-empty/eleventh calls)
through the application-owned executor, and uses no default model, provider, network,
or retry configuration. Rejected calls are returned through a registered framework
handler so the next model turn is ordinary rather than a framework corrective retry.

## Acceptance evidence

| Acceptance ID | Boundary / assertion | Result |
| --- | --- | --- |
| VS08-AC01 | `test_valid_zero_call_completion_is_injected_and_bounded` | Exact request projection, injected function model, and zero-call completion pass. |
| VS08-AC02 | `test_repeated_calls_through_tenth_use_domain_executor` | Ordinals 1–10 and repeated calls are recorded by the domain ledger. |
| VS08-AC03 | `test_forbidden_requests_are_rejected_and_budget_rejection_then_completes` | Unregistered, non-empty, and eleventh requests reject before evaluator execution; each next ordinary completion succeeds. |
| VS08-AC04 | Adapter/pipeline failure tests and PostgreSQL `test_pydantic_ai_alerts_invalid_completion_error_and_timeout_are_terminal` | Invalid output/model error persist `agent_failed`; timeout persists `agent_timeout`; no artifact is stored. |
| VS08-AC05 | Adapter `test_optional_timeout_continues_to_valid_completion`; PostgreSQL `test_pydantic_ai_alerts_optional_timeout_continues_to_valid_result` | Timed-out optional execution remains non-terminal; the next completion persists a completed usable result with only the timeout tool/status trace. |
| VS08-AC06 | `test_instructions_preserve_lens_local_descriptive_boundary` | Instructions require deduplicated Lens-local descriptive findings and prohibit the specified scope expansions. |

## Verification

- `cd backend && uv run pytest tests/test_pydantic_ai_alerts_adapter.py tests/test_alert_analysis_pipeline.py -q` — 33 passed.
- `cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest tests/test_runtime_persistence_integration.py::test_pydantic_ai_alerts_invalid_completion_error_and_timeout_are_terminal tests/test_runtime_persistence_integration.py::test_pydantic_ai_alerts_optional_timeout_continues_to_valid_result -q` — 2 passed (one existing Alembic configuration warning).
- Ruff check/format and Alert import-boundary scan — passed.

## Deviations and invariants

Deviation from forecast change map: PostgreSQL proof was added to the existing runtime
integration suite, in addition to the planned adapter/pipeline tests. The adapter does
not own tool admission, result building, persistence, budgets, or terminal mapping.

Known limitations within approved scope: none.

Commit SHA: HEAD (atomic VS-08 implementation commit).

Plan change requested: none.

Shared knowledge candidates: PydanticAI can reject unknown/no-argument function calls
before a handler runs; preserving the domain rejection and ordinary continuation requires
the adapter to normalize only framework dispatch after the domain executor records the
original call.
