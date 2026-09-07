# C15/C16 fan-out test correction handoff

Implemented test-only evidence for OpenSpec tasks 4.1–4.2.

- C15 adds deterministic adapter-infrastructure and later-admission-commit failure cases. Event gates ensure an active sibling exists before failure; each case asserts original-error identity, sibling cancellation/settlement, independent sessions, no admission or invocation of the queued Lens, and zero active adapter work.
- C16 covers completed-good and partial/degraded Metrics, completed-insufficient and failed Metrics, completed/partial/failed Alerts, canonical partition order, failed-Metric traceability, failed-Alert artifact absence, and malformed topology/data-quality rejection.

Files changed: `backend/tests/test_observation_execution_fanout.py` only (plus this handoff).

Checks: focused fan-out plus execution contract/adapter tests — 49 passed; Ruff lint and format checks — passed; `git diff --check` — passed.

Scope/normative concerns: none. Shared knowledge candidates: none.

Final SHA: the atomic commit containing this handoff; reported to the Coordinator after creation.
