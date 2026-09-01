# VS-01 Handoff — Zero-record persisted walking skeleton

Implemented behavior: `AlertAnalysisPipeline` accepts one immutable `running` Alert
execution context, acquires only its frozen scope/window, normalizes a successful empty
response, produces zero mandatory evidence, skips the agent, and builds a strict completed
1.0 Alert artifact. `persist_alert_terminal` composes the existing runtime repository in
the caller-owned transaction; it advances the run, inserts the artifact, and flushes only.

OpenSpec scenarios covered: prepared-running-run (representative and non-running), empty
current acquisition, zero-record mandatory evidence/agent gate, strict empty result, and
completed persistence walking skeleton.

## Acceptance evidence

| ID | Boundary and command | Observable assertion and counterexample guard | Result |
|---|---|---|---|
| VS01-AC01 | Service: `cd backend && PYTHONPATH=src uv run pytest tests/test_alert_analysis_pipeline.py::test_running_context_is_the_only_pipeline_scope -q` | Provider receives exactly the context scope/window and the artifact preserves only its runtime identity; no agent call. A provider-derived or manufactured run cannot satisfy these assertions. PostgreSQL companion is in AC04. | passed |
| VS01-AC02 | Service: `cd backend && PYTHONPATH=src uv run pytest tests/test_alert_analysis_pipeline.py::test_alert_pipeline_rejects_every_non_running_status_before_acquisition -q` | Pending/completed/partial/failed values reject before provider/agent calls; no terminal outcome exists to persist. | passed |
| VS01-AC03 | Unit/service: `cd backend && PYTHONPATH=src uv run pytest tests/test_alert_contracts.py::test_zero_record_result_has_exact_sections tests/test_alert_analysis_pipeline.py::test_zero_record_path_skips_agent_and_builds_strict_result -q` | Exact zero activity/status counts, `findings=[]`, `overall_importance=none`, and omitted duration/provider-importance sections. The fail-on-call agent guards an incorrect gate. | passed |
| VS01-AC04 | PostgreSQL: `cd backend && IPO_TEST_DATABASE_URL="$IPO_ALERTS_TEST_DATABASE_URL" PYTHONPATH=src uv run pytest tests/test_runtime_persistence_integration.py::test_alert_zero_record_walking_skeleton_persists_completed_result -q` | Test asserts completed/no-reason run, one correlated Alert 1.0 artifact and pre-transaction phase order. `IPO_ALERTS_TEST_DATABASE_URL` was not configured; the test collected and skipped, so this required proof remains unexercised. | PENDING: database URL unavailable |

Technical verification: `test_foundational_alert_models_are_strict_and_preserve_runtime_identity`
passed. Focused suite: 5 passed. Nearby runtime regression: 14 passed. Full backend suite:
193 passed, 36 skipped. Ruff check and format check passed for all VS-01 files.

Important files/contracts changed: `app.alerts` strict contracts, provider/agent ports,
normalization, zero analyzer, builder and pipeline; persistence-only
`persist_alert_terminal`; focused service/unit/PostgreSQL tests.

Phase trace: `provider_acquisition -> current_normalization -> mandatory_analysis ->
zero_record_gate -> result_build -> transaction_open` (asserted by the PostgreSQL test).

Downstream invariants: the pipeline deliberately has no session/ORM import; no reference,
agent, optional-tool, partial, failed, non-zero, transport, or provider-mapping behavior
is implemented. Persistence never commits.

Deviation from change map: none.

Known limitation: PostgreSQL acceptance evidence requires a caller-provided
`IPO_TEST_DATABASE_URL`; Docker Compose showed a running PostgreSQL container but no
published host port and no repository database URL was configured.

Commit SHA: see the atomic implementation commit containing this handoff.

Plan change requested: none.

Shared knowledge candidates: none.
