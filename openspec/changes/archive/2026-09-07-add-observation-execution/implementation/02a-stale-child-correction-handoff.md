# Stale-child artifact correction handoff

## Finding and fix

- C3: A LensRun loaded before aggregate cancellation could retain a stale lifecycle state during artifact persistence.
- `persist_lens_analysis_result()` now refreshes and row-locks the LensRun's durable `status` and `reason` before validation. A durably cancelled child is therefore rejected before an artifact can be inserted.

## Files

- `backend/src/app/infrastructure/persistence/repository.py`
- `backend/tests/test_runtime_persistence.py`
- `backend/tests/test_runtime_persistence_integration.py`

## Tests and checks

- `uv run pytest tests/test_runtime_persistence.py -q` — 19 passed.
- `uv run pytest tests/test_runtime_persistence_integration.py -q` — 33 skipped; `IPO_TEST_DATABASE_URL` unavailable. The added PostgreSQL regression loads a child in one session, commits aggregate cancellation in another, and proves artifact insertion is rejected.
- `uv run ruff check src/app/infrastructure/persistence/repository.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run ruff format --check src/app/infrastructure/persistence/repository.py tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py` — passed.

## Notes

- Caller-owned transaction behavior is unchanged; the lifecycle refresh and lock participate in that transaction.
- No scope or normative concern remains.
- Shared knowledge candidates: none.

## Commit

- `6acac47f799ee44ffec672192968567e0316e86c` (`fix: guard stale cancelled lens artifacts`)
