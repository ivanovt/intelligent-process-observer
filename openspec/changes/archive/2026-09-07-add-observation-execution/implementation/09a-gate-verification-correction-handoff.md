# Gate verification correction handoff

Corrections C19/C20 for approved tasks 4.3–4.4:

- The usable-results gate now accepts initialized assignments plus collected outcomes, performs strict JOIN verification itself, and returns that verified nonzero partition without opening a parent transaction.
- For zero usable results, the gate owns one short session-factory transaction and returns the failed execution outcome only after its successful exit. Parent transition/transaction-exit errors propagate.
- Tests use builder-produced Lens outcomes, reject incomplete and reordered JOINs at the gate, prove degraded pass-through and zero STOP, normal failed-Lens isolation with queued work reaching JOIN, and deadline exclusion for queue delay and Metric History/terminal work.

Files changed:

- `backend/src/app/execution/gates.py`
- `backend/src/app/execution/__init__.py`
- `backend/tests/test_observation_execution_gate.py`
- `backend/tests/test_observation_execution_fanout.py`
- `backend/tests/test_observation_execution_adapters.py`

Verification:

- `cd backend && uv run pytest tests/test_observation_execution_gate.py tests/test_observation_execution_fanout.py tests/test_observation_execution_adapters.py -q` — 29 passed.
- `cd backend && uv run ruff check src/app/execution/gates.py src/app/execution/contracts.py src/app/execution/__init__.py tests/test_observation_execution_gate.py tests/test_observation_execution_fanout.py tests/test_observation_execution_adapters.py` — passed.
- `cd backend && uv run ruff format --check` for the same files — passed.
- `git diff --check` — passed.

Scope/normative concern: none. No production persistence, pipeline, initialization, or adapter code changed.

Final SHA: recorded after the atomic commit.

Shared knowledge candidates: none.
