# VS-01 Handoff

## Delivered

- Added `PrometheusMetricSeriesProvider`, composed from the shared source snapshot into
  `app.state.metric_series_provider` behind the unchanged `MetricSeriesProvider` port.
- Exact missing-source lookup returns `MetricSeriesUnavailable`; selected sources with
  production-invalid targets return `MetricSeriesAcquisitionFailure`. Both use fixed,
  secret-safe diagnostics and execute no transport work.
- Valid sources reach only a private VS-02 transport placeholder and expose no HTTP
  client/request path. Existing preflight remains `HttpxPrometheusQueryAdapter` and is
  not reused by the production provider.

## Acceptance evidence

| Evidence | Result |
|---|---|
| VS01-AC01 | Absent/unknown IDs return `prometheus_source_unavailable`; two-source test proves exact lookup and no fallback. |
| VS01-AC02 / AC04 | Selected production-invalid targets return `prometheus_source_invalid`; validation runs after compatible Settings loading. |
| VS01-AC03 | Real composed absent/unknown provider traverses `MetricAnalysisPipeline` to the unchanged minimal `current_metric_acquisition_failed` result. |
| VS01-AC05 / AC08 | Valid and production-invalid sources both pass lifespan, capabilities, creation source resolution, and independent preflight regression coverage; task 4.6 coverage is complete for this slice. |
| VS01-AC06 | Bearer token, Basic password, Basic username, and `Authorization` are absent from outcomes/provider repr; no credential is used in target validation. |
| VS01-AC07 | Provider is port-typed, application composition starts no run, and `app.metrics` remains free of settings/HTTPX/Prometheus imports. |

## Target and activity ledgers

| Production target form | VS-01 result |
|---|---|
| `https://host`, root, accepted unreserved prefix, HTTPS IPv4 | validated private target; fixed transport-placeholder failure |
| `http://localhost`, `http://127.0.0.1`, `http://[::1]` | validated private target; fixed transport-placeholder failure |
| non-loopback HTTP, userinfo, absent host, query/fragment, invalid port | fixed invalid-target failure |
| repeated/dot/empty path segments, backslash, any percent encoding, whitespace/control | fixed invalid-target failure |
| absent or unknown source | fixed unavailable outcome |

Every VS-01 outcome above has zero client construction and zero requests: this slice has
no HTTP/client import or callable transport path. The valid/invalid shared-consumer test
also keeps preflight on a separate adapter ledger.

## Files and verification

- Production: `backend/src/app/infrastructure/prometheus/configuration.py`,
  `composition.py`, `__init__.py`, and `backend/src/app/main.py`.
- Tests: `backend/tests/test_prometheus_metric_provider_configuration.py` and focused
  real-provider additions to `test_metric_analysis_pipeline.py`.
- `cd backend && uv run pytest tests/test_prometheus_metric_provider_configuration.py tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py tests/test_observation_contracts.py tests/test_observation_api.py tests/test_health.py -q` — **148 passed, 28 skipped** (existing PostgreSQL-gated tests).
- Targeted `ruff check`, `ruff format --check`, `openspec validate add-prometheus-metric-provider --strict`, and `git diff --check` — **passed**.

## Downstream invariants and deferred work

Settings parsing and preflight behavior are unchanged; only the selected source is
production-validated. `MetricSeriesProvider` diagnostics remain internal and pipeline
failure/result semantics are unchanged. VS-02 owns HTTP construction, authentication,
request mapping, and response handling; VS-03 owns deadlines/retries/resilience.

Implementation commit: `1217266598aa5f20b902e9ae2edfe1da2ffed6c2`

Plan change requested: none.

Shared knowledge candidates: none.
