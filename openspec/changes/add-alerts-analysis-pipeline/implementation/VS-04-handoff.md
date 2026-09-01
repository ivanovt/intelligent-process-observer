# VS-04 Handoff — mandatory failure terminal outcomes

**Status:** IMPLEMENTATION_COMPLETE
**Commit:** `HEAD` (the atomic focused VS-04 correction containing this handoff)

## Implemented behavior

The Alert pipeline maps typed/thrown current failures, all-invalid or non-empty
out-of-window current data, deterministic analyzer failures, and required-agent failures
to artifact-free failed terminal outcomes. The persistence projection omits an absent
structured-reason component rather than storing JSON `null`. The deterministic-analysis
PostgreSQL fixture now supplies a strictly in-window record and proves the injected
analyzer was called before its forced failure. The persistence seam advances a failed
LensRun without inserting an Alert result; usable outcomes retain their existing artifact
path.

## OpenSpec coverage

Mandatory current, normalization, deterministic-analysis, required-agent, and failed-Alert
absence scenarios for tasks 2.3, 4.1 (failure portions), 5.3, 5.4, 6.1-6.3, and 7.2.

## Acceptance evidence

| Acceptance ID | Exercised proof level | Full command / node | Observable assertions | Counterexample guard | Result |
|---|---|---|---|---|---|
| VS04-AC01 | service; PostgreSQL collected | `tests/test_alert_analysis_pipeline.py::test_current_acquisition_failures_map_exact_reason_and_stop`; `tests/test_runtime_persistence_integration.py::test_current_acquisition_failures_persist_exact_reason_without_artifact` | Typed/thrown error maps `current_query_failed`; typed/thrown timeout maps `current_query_timeout`; no artifact. | Fail-on-call agent/builder; distinct fixtures prevent generic mapping. | service PASS; PostgreSQL SKIPPED (URL unset) |
| VS04-AC02 | service; PostgreSQL collected | `tests/test_alert_analysis_pipeline.py::test_all_invalid_current_stops_before_analysis`; `tests/test_runtime_persistence_integration.py::test_all_invalid_current_fails_without_artifact` | Malformed and duplicate-only current records fail `invalid_records/current_normalization`; no later stage/artifact. | Raising analyzer, agent, and builder doubles. | service PASS; PostgreSQL SKIPPED (URL unset) |
| VS04-AC03 | service; PostgreSQL collected | `tests/test_alert_analysis_pipeline.py::test_mandatory_analysis_failure_stops_agent_and_builder`; `tests/test_runtime_persistence_integration.py::test_mandatory_analysis_failure_is_terminal_without_artifact` | A 00:30Z record lies strictly within the 00:00Z–01:00Z window; the injected analyzer is called exactly once, then its error maps `deterministic_analysis_failed`; no agent, builder, or artifact. | Analyzer-call assertion; fail-on-call agent/builder. | service PASS; PostgreSQL SKIPPED (no URL/service) |
| VS04-AC04 | service | `tests/test_alert_analysis_pipeline.py::test_required_agent_failures_are_rejected_before_builder` | Agent error and malformed/invalid completion map `agent_failed`; timeout maps `agent_timeout`; builder is bypassed. | Fail-on-use builder. | PASS |
| VS04-AC05 | PostgreSQL collected | `tests/test_runtime_persistence_integration.py::test_every_mandatory_alert_failure_has_no_result_artifact` | Every mandatory reason survives on one failed LensRun with zero artifacts. | Artifact relation is asserted `None`, never only empty payload. | SKIPPED (URL unset) |
| VS04-AC06 | service; PostgreSQL collected | `tests/test_alert_analysis_pipeline.py::test_nonempty_all_out_of_scope_differs_from_empty_success`; `tests/test_runtime_persistence_integration.py::test_nonempty_all_out_of_scope_fails_while_empty_response_completes` | Non-empty/no-usable fails `invalid_records/current_normalization`; empty response remains completed with an artifact. | Direct contrasting fixtures and artifact-presence assertions. | service PASS; PostgreSQL SKIPPED (URL unset) |

## Important changes / downstream invariants

`AlertTerminalOutcome` permits only artifact-free failed outcomes, while completed and
partial outcomes still require artifacts. `persist_alert_terminal` therefore inserts an
artifact only for usable outcomes. `RuntimePersistenceRepository._reason_payload` is the
common durable structured-reason projection and uses `exclude_none=True`; producer-side
contracts retain `component` as optional. Provider, analysis, agent, and persistence
errors are kept distinct; infrastructure errors are not remapped.

## Plan guidance deviations

| Deviation | Evidence / rationale | Coordinator disposition |
|---|---|---|
| Added `RuntimePersistenceRepository._reason_payload` and its unit regression test outside the forecast map. | This existing common durable projection, rather than the Alert pipeline contract, owned serialization of optional `component`; the narrow change preserves every producer's approved payload shape. | PENDING |

## Verification

- `cd backend && uv run pytest tests/test_runtime_persistence.py tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py -q` — 38 passed.
- Focused PostgreSQL command from the VS-04 plan (all five listed nodes) — 5 collected nodes skipped because no `IPO_TEST_DATABASE_URL` is configured and `docker compose ps` reported no service.
- `cd backend && uv run ruff check src/app/alerts src/app/infrastructure/persistence tests/test_runtime_persistence.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.
- `cd backend && uv run ruff format --check src/app/alerts src/app/infrastructure/persistence tests/test_runtime_persistence.py tests/test_alert_analysis_pipeline.py tests/test_runtime_persistence_integration.py` — passed.

## Known limitations within approved scope

Builder contextual/URI failures, optional tools, adapter translation, and transaction
rollback fault injection remain deferred to their assigned slices.

PostgreSQL execution remains unproven in this workspace: the focused five nodes were
collected but skipped because no local service or test URL is available.

## Plan change requested

none

## Shared knowledge candidates

none
