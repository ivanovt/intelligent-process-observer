# C-02 Handoff

## Correction

- Disabled HTTPX's implicit client timers for production acquisitions, leaving the
  explicit 15-second complete-attempt runner as the sole observable attempt-timeout
  owner while preserving the 50-second acquisition deadline and typed classification.
- Moved private capacity admission to the validated transport lifecycle. One lease now
  spans every attempt and retry wait, releases on terminal lifecycle completion, and is
  retained until any detached cancellation-resistant attempt cleanup terminates.
- Kept capacity exhaustion before client construction/transport and preserved request,
  retry, deadline commitment, cancellation, late-result, and public-contract behavior.
- Commit identity: the atomic C-02 correction commit containing this handoff.

## Changed paths

- `backend/src/app/infrastructure/prometheus/composition.py`
- `backend/tests/test_prometheus_metric_provider_resilience.py`
- `openspec/changes/add-prometheus-metric-provider/implementation/C-02-handoff.md`

## Verification

- Focused resilience tests: **75 passed**.
- Prometheus provider, configuration, resilience, preflight, and Metric pipeline tests:
  **271 passed, 28 skipped**; skips are existing PostgreSQL-gated cases.
- Targeted Ruff lint and format checks: **passed**.
- `make check`: **passed** — Ruff lint/format, **541 backend tests passed with 57
  skipped**, frontend lint/build, and strict validation of all OpenSpec items.
- `openspec validate add-prometheus-metric-provider --strict` and `git diff --check`:
  **passed**.
- Full assigned delta self-review: **passed**.

No scope or normative concern remains. An unrelated concurrent `.gitignore` edit appeared
after the initially clean startup check; it was not created, altered, staged, or included
by C-02.

Plan change requested: none.

Shared knowledge candidates: none.
