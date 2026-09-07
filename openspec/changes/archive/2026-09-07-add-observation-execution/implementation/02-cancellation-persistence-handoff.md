# Cancellation persistence handoff

## Tasks

- 1.3 Add a guarded, caller-transaction-owned aggregate cancellation operation.
- 1.4 Add focused unit and PostgreSQL integration coverage for cancellation persistence.

## Files

- `backend/src/app/infrastructure/persistence/repository.py`
- `backend/tests/test_runtime_persistence.py`
- `backend/tests/test_runtime_persistence_integration.py`

## Behavior

- `cancel_observation_execution()` conditionally transitions only a running ObservationRun and its pending/running LensRuns to `cancelled` with the exact `{code: execution_cancelled, component: null}` reason and one terminal timestamp.
- The parent conditional update rejects stale or contradictory terminalization before any child update. Terminal children and their artifacts are not rewritten.
- The repository only executes SQL and updates the supplied parent instance; it never commits or rolls back.

## Verification

- `uv run ruff check src/app/infrastructure/persistence/repository.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run ruff format --check src/app/infrastructure/persistence/repository.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run pytest tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py -q` — 18 passed, 32 skipped.
- PostgreSQL run status: skipped because `IPO_TEST_DATABASE_URL` is unavailable. Added integration cases cover pending/running cancellation, completed/partial/failed/cancelled preservation, exact reasons/timestamps, cancelled artifact rejection and retrieval, rollback, and stale duplicate cancellation.

## Notes

- No migration, dependency, OpenSpec task metadata, or architecture document changed.
- The implementation follows the accepted conditional lifecycle updates from `c2e3bc4`.

## Commit

- `702fff688adccdf638c2e2600b0829189e079275` (`feat: add guarded runtime cancellation`)
