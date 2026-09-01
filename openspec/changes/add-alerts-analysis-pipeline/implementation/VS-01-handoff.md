# VS-01 Handoff — Zero-record persisted walking skeleton

Implemented behavior: `AlertAnalysisPipeline` accepts one immutable `running` Alert
execution context, acquires only its frozen scope/window, normalizes a successful empty
response, produces zero mandatory evidence, skips the agent, and builds a strict completed
1.0 Alert artifact. `persist_alert_terminal` composes the existing runtime repository in
the caller-owned transaction; it advances the run, inserts the artifact, and flushes only.

OpenSpec scenarios covered: prepared-running-run (representative and non-running), empty
current acquisition, zero-record mandatory evidence/agent gate, strict empty result, and
completed persistence walking skeleton.

Correction finding addressed: `CompletedZeroAlertAnalysisResult` previously projected a
reduced nested `activity` shape. It now emits the full strict v1.0 zero-record result:
runtime identity, `lens_type`, completed status, analysis timestamp/window, minimal
provenance, top-level `alerts`, `alert_activity`, `status_distribution`, and
`comparisons`, with the required empty/none values and absent optional sections.

## Acceptance evidence

| ID | Boundary and command | Observable assertion and counterexample guard | Result |
|---|---|---|---|
| VS01-AC01 | Service: `cd backend && PYTHONPATH=src uv run pytest tests/test_alert_analysis_pipeline.py::test_running_context_is_the_only_pipeline_scope -q` | Provider receives exactly the context scope/window and the artifact preserves only its runtime identity; no agent call. A provider-derived or manufactured run cannot satisfy these assertions. PostgreSQL companion is in AC04. | passed |
| VS01-AC02 | Service: `cd backend && PYTHONPATH=src uv run pytest tests/test_alert_analysis_pipeline.py::test_alert_pipeline_rejects_every_non_running_status_before_acquisition -q` | Pending/completed/partial/failed values reject before provider/agent calls; no terminal outcome exists to persist. | passed |
| VS01-AC03 | Unit/service: `cd backend && uv run pytest tests/test_alert_contracts.py::test_zero_record_result_has_exact_sections tests/test_alert_analysis_pipeline.py::test_zero_record_path_skips_agent_and_builds_strict_result -q` | The unit test asserts the exact top-level v1.0 field set, full identity, timestamp/window aliases, `source_provider` provenance, normalized empty collections, zero activity/status distribution, and absent optional sections. The service test retains the fail-on-call agent guard. This rejects the prior reduced/nested shape. | passed |
| VS01-AC04 | PostgreSQL: `cd backend && IPO_TEST_DATABASE_URL="${IPO_ALERTS_TEST_DATABASE_URL:?set IPO_ALERTS_TEST_DATABASE_URL}" uv run pytest tests/test_runtime_persistence_integration.py::test_alert_zero_record_walking_skeleton_persists_completed_result -q` | Real PostgreSQL round trip passed: completed/no-reason run, one correlated Alert 1.0 artifact, full persisted identity/lifecycle/time/provenance and normalized empty sections, plus pre-transaction phase order. The assertions reject the prior reduced/nested shape. | passed |

Technical verification: `cd backend && uv run pytest tests/test_alert_contracts.py
tests/test_alert_analysis_pipeline.py -q` passed (5 passed). The PostgreSQL command in
VS01-AC04 passed (1 passed; Alembic emitted one existing deprecation warning). `uv run
ruff check src/app/alerts src/app/infrastructure/persistence/alert_runtime.py
tests/test_alert_contracts.py tests/test_alert_analysis_pipeline.py
tests/test_runtime_persistence_integration.py` and the matching `ruff format --check`
passed.

Local test-service provenance (ephemeral; no URL or credentials recorded): the AC04
command was run with the developer-provided `IPO_ALERTS_TEST_DATABASE_URL` exported into
the parameterized `IPO_TEST_DATABASE_URL` command context above. This is the canonical
rerunnable command; the local service value is intentionally not committed.

Important files/contracts changed: `CompletedZeroAlertAnalysisResult`,
`AlertResultProvenance`, and `AlertAnalysisWindow` now project contract-v1.0 names and
the required zero-record top-level sections; focused service/unit/PostgreSQL tests pin
that projection. The remaining VS-01 files and persistence seam are unchanged.

Phase trace: `provider_acquisition -> current_normalization -> mandatory_analysis ->
zero_record_gate -> result_build -> transaction_open` (asserted by the PostgreSQL test).

Downstream invariants: the pipeline deliberately has no session/ORM import; no reference,
agent, optional-tool, partial, failed, non-zero, transport, or provider-mapping behavior
is implemented. Persistence never commits.

Deviation from change map: none (PENDING Coordinator disposition: none required).

Known limitation: only the approved zero-record completed path is implemented; non-zero,
references, partial/failed, optional tools, transports, and adapters remain deferred.

Clean tree: verified after the corrective commit and rerunnable checks.

Commit SHA: final corrective commit; reported to the Coordinator after its final amend.

Plan change requested: none.

Shared knowledge candidates: none.
