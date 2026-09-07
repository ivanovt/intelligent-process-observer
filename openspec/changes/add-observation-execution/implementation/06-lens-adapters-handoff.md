# Lens adapters handoff

Tasks: approved implementation tasks 3.1 and 3.2 only.

Delivered boundary:

- `MetricLensExecutionAdapter` projects an immutable Metric assignment into the existing
  `MetricLensExecutionContext`, bounds only `MetricAnalysisPipeline.analyze`, then opens
  the caller-owned terminal transaction for the existing History/read-and-persist path.
- `AlertLensExecutionAdapter` resolves the injected provider for the immutable Alert scope,
  invokes the existing Alert pipeline under the Lens deadline, and uses
  `persist_alert_terminal` in the terminal transaction.
- Both adapters verify the expected durable running LensRun/parent correlation before a
  terminal write and return the existing compact collected terminal outcome.
- Focused tests cover normal completed, partial, and failed paths, exact context projection,
  Alert failed-artifact absence, and Metric analysis-before-terminal phase ordering.

Explicit remaining task 3.3 work:

- Normalize deadline expiry, unexpected non-persistence errors, and returned
  identity/lifecycle mismatches to the controlled wrapper reasons.
- Build the assigned-context minimal Metric failure artifact with
  `mandatory_metric_analysis_failed` for each wrapper failure; retain no Alert failed artifact.
- Preserve propagation of History and all terminal persistence failures while adding that
  normalization boundary.

Checks:

- `cd backend && uv run ruff check src/app/execution/adapters.py src/app/execution/__init__.py tests/test_observation_execution_adapters.py`
- `cd backend && uv run ruff format --check src/app/execution/adapters.py src/app/execution/__init__.py tests/test_observation_execution_adapters.py`
- `cd backend && uv run pytest tests/test_observation_execution_adapters.py tests/test_metric_analysis_pipeline.py tests/test_alert_analysis_pipeline.py` — 105 passed, 28 skipped
- `PYTHONPATH=src uv run python -c 'import app.execution'`

Final SHA: reported to the Coordinator immediately after the atomic commit containing this handoff.
