# C12/C13 envelope-integrity correction handoff

Implemented the bounded C12/C13 correction for collected terminal artifacts.

- C12: every adapter persistence-return path now correlates the returned
  `LensAnalysisResultModel.lens_run_id` to the assigned LensRun before rebuilding the
  envelope; returned ID, result type, terminal status, and payload-identity
  contradictions are rejected before collection.
- C13: `CollectedLensArtifact` is a recursively detached immutable snapshot of the
  just-persisted envelope. Nested mappings are read-only and sequences are tuples;
  it retains type, status, schema, complete identity, provenance, and payload. Its
  `to_persistence_envelope()` projection returns an independent mutable envelope for
  later JOIN/Relationship/reasoning consumers without persistence reload.
- Evidence covers source-model/source-envelope mutation, attempted nested snapshot
  mutation, a History-derived Metric terminal replacement returned by persistence,
  and corrupt persistence-return models.

Files changed:

- `backend/src/app/execution/contracts.py`
- `backend/src/app/execution/adapters.py`
- `backend/src/app/execution/__init__.py`
- `backend/tests/test_observation_execution_contracts.py`
- `backend/tests/test_observation_execution_adapters.py`

Checks: focused execution-contract/adapter/Metric/Alert tests — 142 passed, 28 skipped;
Ruff check and format check passed.

Scope/normative concerns: none.

Final SHA: reported to the Coordinator with the atomic commit.

Shared knowledge candidates: none.
