# C14 worker-cleanup correction handoff

Implemented C14 for the bounded fan-out worker lifecycle.

- A worker admission or adapter exception now immediately closes admission and requests
  cancellation of every active sibling; the scheduler then settles all owned workers
  before re-raising the original exception.
- Caller cancellation follows the same stop-and-settle path and is re-raised unchanged.
- The worker loop checks the shared stop state before a claim and after admission, so a
  failure cannot permit a later queued Lens to begin adapter execution.
- Fan-out tests now create a new session object for every admission. They prove a
  commit-exit failure leaves its own adapter uncalled, cancels/settles an active sibling,
  admits no later queued Lens, and leaves no active adapter work; caller cancellation is
  covered as well.

Files changed:

- `backend/src/app/execution/fanout.py`
- `backend/tests/test_observation_execution_fanout.py`

Checks: focused fan-out tests (5 passed); execution adapter/contract tests (42 passed);
Ruff lint and format checks; `git diff --check`.

Scope/normative concerns: none. No dependencies, migrations, task-state, or architecture
changes.

Final SHA: recorded in the accompanying atomic correction commit and reported to the
Coordinator.

Shared knowledge candidates: none.
