# VS-02 Handoff — mixed definition validation, ordering, and atomicity

Implemented behavior: Alert validation now rejects whitespace-only recognized strings,
duplicate/blank objectives, and invalid or duplicate direct reference offsets without
mutating accepted opaque strings. Metric and Alert IDs are independently unique; the same
ID is accepted across collections. Relationships continue to resolve participants solely
against Metric `lenses`, and Metric source lookup remains confined to Metric lenses.

Matrix/evidence: contract tests cover every accepted Alert field/default/extra behavior,
exact whitespace-bearing query preservation, ordered lists, each invalid Alert member,
type-local duplicate rejection, same-ID Metric/Alert acceptance, and Alert-only
Relationship participant rejection. API tests prove invalid Alert members fail before the
service is invoked. PostgreSQL coverage creates an ordered mixed aggregate, loads summary,
detail, and both equal-ID type-specific children, and asserts the hrefs differ. It also
uses a repository that raises after `flush`; the service transaction leaves Observation,
Metric, Alert, and Relationship table counts unchanged.

Important files: `backend/src/app/observations/contracts.py`, focused Observation contract,
API, and PostgreSQL integration tests. No migration, persistence ownership declaration,
runtime model/constraint, provider/capability/preflight behavior, or public route changed.

Verification:

- `uv run ruff check src/app/observations/contracts.py tests/test_observation_contracts.py tests/test_observation_api.py tests/test_runtime_persistence_integration.py` — passed.
- `uv run pytest tests/test_observation_contracts.py tests/test_observation_api.py` — 40 passed.
- `uv run pytest tests/test_runtime_persistence_integration.py::test_postgresql_mixed_definition_order_navigation_and_late_failure_are_atomic` — skipped because `IPO_TEST_DATABASE_URL` is not set locally; the test requires a disposable PostgreSQL database.
- `git diff --check` — passed.

Downstream constraints: preserve the VS-01 non-empty combined Lens invariant. VS-03 alone
owns Alert relationship cascade/delete-orphan and database cascade proof. VS-04 alone owns
LensRun type-aware uniqueness and migration downgrade behavior. Revision `20260901_01`
remains unreleased and no future-slice behavior was added.

Commit SHA: `HEAD`.

Plan change requested: none.

Shared knowledge candidates: none.
