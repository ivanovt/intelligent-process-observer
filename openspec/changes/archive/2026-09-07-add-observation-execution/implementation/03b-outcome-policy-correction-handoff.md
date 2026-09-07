# Outcome and policy correction handoff

Findings addressed: C6 and C7 (both MEDIUM).

Behavior:

- Initialized completed and failed outcomes now reject non-UUID `observation_run_id`; failed outcomes also reject a non-`ExecutionReason` reason, while retaining fixed discriminator/status values and dataclass immutability.
- Invalid negative, zero, and boolean `max_parallel_lens_runs` values return the exact pre-initialization `invalid_execution_request` rejection; a positive value remains accepted.

Files changed:

- `backend/src/app/execution/contracts.py`
- `backend/tests/test_observation_execution_contracts.py`

Verification:

- `git diff --check`
- `cd backend && uv run ruff check src/app/execution/contracts.py tests/test_observation_execution_contracts.py`
- `cd backend && uv run ruff format --check src/app/execution/contracts.py tests/test_observation_execution_contracts.py`
- `cd backend && uv run pytest tests/test_observation_execution_contracts.py` — 22 passed

Scope/normative concerns: none. No dependencies, migrations, OpenSpec task metadata, or architecture artifacts changed. Final commit SHA is reported directly to the Coordinator because including a commit's own final object ID in this tracked handoff would change that ID.

Shared knowledge candidates: none.
