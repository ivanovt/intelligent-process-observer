# Lifecycle persistence handoff

## Tasks

- 1.1 Add the `cancelled` runtime lifecycle state and validation.
- 1.2 Reject cancelled LensRun artifacts while preserving terminal retrieval semantics.

## Files

- `backend/src/app/infrastructure/persistence/runtime_contracts.py`
- `backend/src/app/infrastructure/persistence/repository.py`
- `backend/tests/test_runtime_persistence.py`

## Behavior

- ObservationRuns may transition from `running` to `cancelled`; LensRuns may transition from `pending` or `running` to `cancelled`.
- Cancellation requires a structured reason with code `execution_cancelled`, is terminal, and is non-usable.
- A cancelled LensRun rejects any new analysis artifact. Aggregate retrieval continues eager-loading all persisted child and Observation-level artifacts without creating placeholders or filtering terminal state.

## Verification

- `uv run pytest tests/test_runtime_persistence.py` — 15 passed.
- `uv run ruff check src/app/infrastructure/persistence/runtime_contracts.py src/app/infrastructure/persistence/repository.py src/app/infrastructure/persistence/alert_runtime.py tests/test_runtime_persistence.py` — passed.
- `uv run ruff format --check src/app/infrastructure/persistence/runtime_contracts.py src/app/infrastructure/persistence/repository.py src/app/infrastructure/persistence/alert_runtime.py tests/test_runtime_persistence.py` — passed.
- Self-reviewed the complete owned implementation diff against `89bfe7f`; no ownership or contract issues found.

## Risks / notes

- No migration is required: runtime status columns are string-backed.
- This does not add the aggregate cancellation operation from task 1.3.
- `alert_runtime.py` requires no code change because Alert terminal outcomes remain limited to completed, partial, and failed; top-level cancellation uses the runtime repository directly.

## Commit

- `2ebc0051edc4dde571aa8281145dea547e583d9b` (`feat: support cancelled runtime lifecycle`)
