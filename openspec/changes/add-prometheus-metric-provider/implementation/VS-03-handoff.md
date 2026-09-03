# VS-03 Handoff

## Delivered

- Completed the private acquisition orchestrator behind the unchanged
  `MetricSeriesProvider` port. It consumes VS-02's immutable logical request and its
  complete attempt outcomes without changing request construction or response mapping.
- Added injected monotonic-clock, sleeper, and deadline-runner seams. The default
  runner enforces hard 50-second acquire and 15-second complete-attempt/body-read
  deadlines, cancels outstanding work, waits for cancellation cleanup, and gives the
  local deadline precedence over an exception raised during cancellation.
- Retries only `httpx.ConnectError` and VS-02's private retry-eligible
  `429|500|502|504` outcomes. At most three attempts run, with fixed waits `0.5` then
  `1.0` seconds; `Retry-After` is ignored. Admission requires the exact wait plus a
  new 15-second attempt to fit the remaining 50-second budget. Rejection is timeout;
  three executed eligible failures exhaust as failure.
- Maps HTTPX exceptions in the approved order: timeout subclasses are timeout without
  retry, only `ConnectError` is retry-eligible, and the named remaining transport,
  request/client, URL, and stream errors are terminal failures. Response/client async
  contexts close on cancellation and ordinary terminal paths.

## Acceptance evidence

| Coverage | Evidence |
|---|---|
| VS03-AC01 | Cancellation-observable streaming-body and client fakes prove a 15-second attempt deadline produces the typed timeout, cancels the body, and closes response/client. A separately controlled 50-second deadline cancels a retry wait with one request and no later work. |
| VS03-AC02 | Parameterized `ConnectError` and `429/500/502/504` sequences prove success on attempts 1/2/3 and exhaustion at exactly 1/2/3/3 requests, fixed wait ledgers, ignored `Retry-After`, and byte-identical method/URL/form/auth request snapshots. |
| VS03-AC03 | Parameterized ConnectError/status vectors prove the first retry's just-insufficient and exact-fit `0.5 + 15` boundary; the retry-two vector proves `1.0 + 15` admission rejection. No rejected retry sleeps or sends another request. |
| VS03-AC04 | The exact HTTPX hierarchy table covers `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, `ConnectError`, `ReadError`, `WriteError`, `CloseError`, protocol/proxy/unsupported errors, `DecodingError`, `TooManyRedirects`, `InvalidURL`, and `StreamError`. |
| VS03-AC05 | A cancellation race whose cancelled work raises `ConnectError` proves `_run_with_deadline` returns local timeout rather than retry eligibility. |
| VS03-AC06 | Private terminal available/failure/timeout variants prove no sleep/additional attempt. A private retry-eligible status proves three-attempt exhaustion as typed failure; VS-02's status/body mapping remains consumed unchanged. |
| VS03-AC07 | Real composed-provider pipeline tests prove a valid Prometheus timeout becomes the existing minimal failed current result, and a retry-exhausted reference alone leaves usable current data and produces the existing `reference_unavailable/reference_periods` partial result. |

## Files and verification

- Production: `backend/src/app/infrastructure/prometheus/composition.py`
- Tests: `backend/tests/test_prometheus_metric_provider_resilience.py` and focused
  additions to `backend/tests/test_metric_analysis_pipeline.py`
- `cd backend && uv run pytest tests/test_prometheus_metric_provider.py tests/test_prometheus_metric_provider_resilience.py tests/test_prometheus_metric_provider_configuration.py tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py -q` — **251 passed, 28 skipped** (existing PostgreSQL-gated skips).
- Targeted Ruff check and format check for changed provider/tests, plus
  `git diff --check` — **passed**.

## Downstream invariants and deferred scope

Public typed outcomes and current/reference pipeline semantics are unchanged. Every retry
reuses the same private logical request/source/auth/configuration; body/status/envelope
classification remains VS-02-owned. No Metric domain, pipeline, result, persistence,
preflight, Observation orchestration, migration, dependency, or frontend changes were
made.

Deferred scope remains unchanged: no jitter, `Retry-After`, proxy/redirect policy
change, Observation-level deadline, concurrency, or public retry diagnostics.

Implementation commits: `4baf129efeb84ba40c507934ad9e4451cf59b5b0` (bounded retry/deadline
orchestrator and tests), `5c35ae84e141169375faff4e7f1c909ccb774cbb` (strict hard-deadline
precedence at an exact completion boundary).

Plan change requested: none.

Shared knowledge candidates: none.
