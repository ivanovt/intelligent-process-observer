# VS-04 Handoff — type-aware LensRun identity and guarded rollback

Implemented the final LensRun identity as `(observation_run_id, lens_type, lens_id)`.
The ORM and revision `20260901_01` now use
`uq_lens_runs_observation_run_id_lens_type_lens_id`; the predecessor key is
`lens_runs_observation_run_id_lens_id_key`.

PostgreSQL coverage proves same-ID Metric and Alert LensRuns coexist and retrieve by
their distinct types, while a duplicate same-type insert raises `IntegrityError` and
leaves both accepted rows intact. Existing completed and failed lifecycle retrieval is
covered in that path and the established runtime lifecycle suite remains green.

The final revision drops the old key before creating the type-aware key. Its downgrade
first queries for cross-type same-ID runs and raises before any DDL when found; the test
verifies the upgraded constraint, runtime rows, and Alert definition remain. After those
duplicate runtime rows are removed, the test proves the safe rollback restores the old
key and drops Alert storage, then upgrades back to the final structure.

Verification:

- `IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55435/ipo uv run pytest tests/test_runtime_persistence.py tests/test_runtime_persistence_integration.py -q` — 21 passed.
- `openspec validate add-alert-lens-definition --strict` — passed.
- `git diff --check` — passed.
- `IPO_TEST_DATABASE_URL=postgresql+psycopg://ipo:ipo@localhost:55435/ipo make check` — 223 passed; frontend lint/build and strict validation passed.

Scope audit: no dependencies, routes, providers, pipeline code, frontend code, or plan
artifacts changed. The disposable PostgreSQL container was used only for verification.

Commit SHA: `HEAD` (the atomic VS-04 commit containing this handoff).

Plan change requested: none.

Shared knowledge candidates: none.
