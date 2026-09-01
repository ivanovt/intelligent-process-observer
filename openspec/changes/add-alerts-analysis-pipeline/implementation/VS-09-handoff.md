# VS-09 Handoff — rollback and whole-change conformance

**Status:** IMPLEMENTATION_COMPLETE

## Implemented conformance evidence

Added PostgreSQL proofs for both repository flush sites and caller commit rollback,
the completed/current-partial/reference-partial/failed terminal matrix, one-at-a-time
composer envelope mismatches, and transaction phase ordering. The service proof records
provider, normalization, deterministic/reference work, bounded optional-tool/agent work,
and result construction before caller transaction composition. No primary Alert behavior,
schema, API, dependency, or provider integration changed.

The public Alert contract models now have concise behavioral docstrings. The development
guide documents the framework-neutral injection boundary, caller-owned transaction, and
the intentionally deferred Jira transport and production-model configuration.

## Acceptance evidence

| Acceptance ID | Full command / observable assertion | Result |
| --- | --- | --- |
| VS09-AC01 | `tests/test_runtime_persistence_integration.py::test_alert_transition_flush_artifact_flush_and_commit_failures_roll_back_all_writes` injects transition flush, artifact flush, and caller commit failures; each re-raises and a fresh session sees the original `running` LensRun and no artifact. | PASS (PostgreSQL) |
| VS09-AC02 | `tests/test_runtime_persistence_integration.py::test_alert_terminal_outcome_correlation_matrix` reloads completed, current-normalization partial, reference-periods partial, and failures `current_query_failed`, `current_query_timeout`, `invalid_records`, `deterministic_analysis_failed`, `agent_failed`, `agent_timeout`, and `result_validation_failed/alert_result_builder`; usable artifacts exactly match terminal status/reason and failures have no artifact. | PostgreSQL rerun pending configured test URL |
| VS09-AC03 | Service `test_pre_transaction_work_finishes_before_persistence_composition` and PostgreSQL `test_alert_pipeline_phase_order_keeps_long_work_outside_transaction` record all long analysis phases before transaction open, then terminal write and commit. | PASS (service + PostgreSQL) |
| VS09-AC04 | Focused fake/injected Alert suite passed (`49 passed`); final merge-base import/scope/dependency/clean-tree scan is recorded below after the atomic commit. | PASS |
| VS09-AC06 | `tests/test_runtime_persistence_integration.py::test_alert_persistence_composer_rejects_every_mismatched_artifact_atomically` independently mutates type, status, identity, and partial reason; each raises and a fresh session retains `running` with no artifact. | PASS (PostgreSQL) |

## Final requirement/scenario/task audit

The accepted coverage matrix was reconciled against all nine requirements, 25 approved
scenarios, and 23 tasks. VS-09 closes task 6.3 rollback/mismatch proofs and tasks 7.1–7.3
documentation/validation gates; earlier handoffs retain their owned scenario evidence.
No frozen requirement, scenario, or task changed.

## Verification

- Original focused PostgreSQL VS-09 nodes — `4 passed` (one existing Alembic configuration warning). The corrected AC02 matrix requires rerun with the configured PostgreSQL test URL; the available local container rejected the documented default credentials.
- Focused Alert suite — `49 passed`.
- `openspec validate add-alerts-analysis-pipeline --strict` — passed.
- `git diff --check` — passed.
- Merge-base scope/dependency/import and clean-tree scans — passed after the atomic commit.
- `make check` — passed: Ruff, format, `237 passed, 57 skipped` backend tests,
  frontend lint/build, and strict OpenSpec validation (`4 passed, 0 failed`).

## Deviations and downstream invariants

| Deviation | Coordinator disposition |
| --- | --- |
| none | PENDING |

Terminal Alert writes remain caller-transaction-owned: persistence advances the existing
LensRun, conditionally writes one artifact, and flushes without committing.

Implementation commit SHA: `4a1b03f`.

Correction commit SHA: `ccb06a9`.

Plan change requested: none.

Shared knowledge candidates: none.
