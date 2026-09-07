# Lifecycle correction handoff

## Corrections

- C1: Guard ObservationRun and LensRun transitions with a conditional persisted-state update; stale instances now fail without overwriting a committed terminal status or reason.
- C2: Restrict cancellation reasons to `execution_cancelled` with no component detail.

## Files

- `backend/src/app/infrastructure/persistence/runtime_contracts.py`
- `backend/src/app/infrastructure/persistence/repository.py`
- `backend/tests/test_runtime_persistence.py`
- `backend/tests/test_runtime_persistence_integration.py`

## Verification

- `uv run ruff check src/app/infrastructure/persistence/runtime_contracts.py src/app/infrastructure/persistence/repository.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run ruff format --check src/app/infrastructure/persistence/runtime_contracts.py src/app/infrastructure/persistence/repository.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run pytest tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py -q` — 17 passed, 30 skipped (PostgreSQL integration tests require `IPO_TEST_DATABASE_URL`).

## Notes

- No aggregate cancellation operation, migration, dependency, or OpenSpec task metadata was changed.
- The integration regression covers stale ObservationRun and LensRun instances against independently committed terminal state.
- Shared knowledge candidates: none.

## Commit

- `c2e3bc4ba7e042bb52b438d88ece9196aa55ff34` (`fix: guard runtime lifecycle transitions`)
