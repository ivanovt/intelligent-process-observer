# Stale-child test correction handoff

## Correction

- C4 strengthens the PostgreSQL stale-child regression: the child is loaded with its parent, cancellation commits in a second session, and the stale child is then locally set to `completed` to match the candidate completed artifact.
- `no_autoflush` prevents the test setup from overwriting durable cancellation. The current refresh/lock rejects the cancelled durable state; rollback and reload prove no artifact was written.

## Files

- `backend/tests/test_runtime_persistence_integration.py`

## Verification

- `uv run pytest tests/test_runtime_persistence.py -q` — 19 passed.
- `uv run pytest tests/test_runtime_persistence_integration.py -q` — 33 skipped; `IPO_TEST_DATABASE_URL` is unavailable locally.
- `uv run ruff check tests/test_runtime_persistence_integration.py tests/test_runtime_persistence.py` — passed.
- `uv run ruff format --check tests/test_runtime_persistence_integration.py tests/test_runtime_persistence.py` — passed.

## Notes

- Test-only change; no scope or normative concern remains.
- Shared knowledge candidates: none.

## Commit

- `1cd0e0dc42ff0fdf17e5339fab486aebaa8d254a` (`test: strengthen stale cancelled artifact regression`)
