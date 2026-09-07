# C11 collected-envelope correction handoff

Implemented the approved collected persistence envelope required by strict JOIN.

- `CollectedLensOutcome` now carries an optional validated `LensAnalysisResultInput` and rejects contradictory Lens type, terminal status, assignment identity, Metric identity, reason, and artifact-absence combinations.
- Adapters reconstruct the envelope from the authoritative terminal `LensAnalysisResultModel` returned by persistence; this preserves any Metric History-derived replacement without a reload. Failed Alerts retain no artifact.
- Focused tests cover Metric completed-insufficient, partial, failed, Alert completed/partial/failed, wrapper failure, missing-artifact rules, and producer/persisted correlation.

Checks: `pytest tests/test_observation_execution_contracts.py tests/test_observation_execution_adapters.py tests/test_metric_analysis_pipeline.py tests/test_alert_analysis_pipeline.py` — 139 passed, 28 skipped; Ruff check and format check passed.

Risks/concerns: none. No architecture, OpenSpec task-state, dependency, migration, or persistence-semantic changes.

Final SHA: pending commit.

Shared knowledge candidates: none.
