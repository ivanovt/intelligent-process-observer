# Metric status correction handoff

Correction: C10 for approved tasks 3.3–3.4.

- The Metric adapter now rejects any non-`MetricPreTransactionAnalysis`, non-envelope terminal result, invalid Metric envelope, incomplete or mismatched assigned identity, and branch/status contradiction before opening the Metric terminal transaction.
- Validation matrix: producer analysis type; terminal-envelope type; Metric result type; complete and exact assigned identities; failure + completed contradiction; success + failed contradiction.
- Every rejected producer result becomes the assigned-context adapter failure `identity_mismatch/metric`; only the newly builder-produced failed artifact is persisted, with `mandatory_metric_analysis_failed`. The rejected producer artifact never reaches `persist_terminal` or persistence.
- History and terminal transaction error propagation remains outside the validation/normalization boundary.

Files changed:

- `backend/src/app/execution/adapters.py`
- `backend/tests/test_observation_execution_adapters.py`

Checks:

- `cd backend && uv run ruff check src/app/execution/adapters.py tests/test_observation_execution_adapters.py` — passed.
- `cd backend && uv run ruff format --check src/app/execution/adapters.py tests/test_observation_execution_adapters.py` — passed.
- `cd backend && uv run pytest tests/test_observation_execution_adapters.py tests/test_metric_analysis_pipeline.py` — 82 passed, 28 skipped.

Self-review: scope is limited to the assigned adapter and focused tests; no pipeline, result-builder, persistence, contract, migration, dependency, architecture, or OpenSpec task-state edit. No source-of-truth concern remains.

Final SHA: reported to the Coordinator with this handoff.

Shared knowledge candidates: none.
