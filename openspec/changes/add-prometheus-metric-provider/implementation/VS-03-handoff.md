# VS-03 Handoff

## Delivered

- The provider keeps the approved 15-second complete-attempt and 50-second acquire
  result boundaries, commits the existing typed timeout at either boundary, and signals
  cancellation without waiting for cancellation-resistant cleanup.
- Detached attempt cleanup is state-inert. Its completed late result, exception, or
  close outcome is consumed only to avoid an unobserved task exception; it cannot retry,
  issue a request, alter a provider outcome, or affect pipeline/runtime state.
- A private per-provider finite transport capacity now covers live HTTP attempt work and
  detached cleanup. Saturation returns the existing fixed-safe acquisition failure before
  client construction; the slot is released only from the cancelled attempt task's
  `finally`, after cleanup terminates.
- The VS-02 request/body/status classifier is unchanged. Retries remain only
  `ConnectError` and `429|500|502|504`, with at most three attempts, waits `0.5/1.0`,
  and admission only if `wait + 15` fits the 50-second anchor.

## Acceptance evidence

| Coverage | Evidence |
|---|---|
| VS03-AC01 | Cancellation-observable hanging body/client tests prove the attempt timeout is returned while client cleanup remains blocked; cancellation and response/client closure are signalled. The retry-wait test proves the 50-second boundary cancels the wait with one request. |
| VS03-AC02/03 | Parameterized ConnectError and every retryable-status vectors retain exact `1/2/3/3` requests, `0.5/1.0` waits, byte-identical request snapshots, and no-request/no-wait budget rejection. Retry two separately proves just-insufficient `34.000001` versus exact-fit `34.0` (remaining `1.0 + 15.0`): equality performs the `1.0` wait and the third request. |
| VS03-AC04/06 | The HTTPX hierarchy table leaves only ConnectError retry-eligible. Terminal VS-02 attempt variants neither sleep nor retry; three executed eligible attempts exhaust as typed failure. |
| VS03-AC05/08 | Controlled late available and ConnectError outcomes released after timeout leave the committed timeout, call count, and sleep ledger unchanged. A real-provider current-success/reference-timeout pipeline test persists its accepted reference-partial Lens outcome before cancellation-resistant client close is released; the late close raises `httpx.CloseError`, yet request/sleep ledgers, provider capacity, analysis, Lens state, and persisted artifact remain unchanged. |
| VS03-AC07 | Existing real-provider pipeline tests retain current timeout -> minimal failed result and retry-exhausted reference -> usable current partial result. |
| VS03-AC09 | With test-only private capacity one, a hung attempt returns timeout, a second valid acquisition fails before client construction, and a successful later acquisition is admitted only after cleanup releases its slot. A separate active-stream test fills that same shared capacity before any deadline; the saturated acquisition has zero client constructions and zero requests, while release of active work admits the later acquisition. |

## Verification

- `cd backend && uv run pytest tests/test_prometheus_metric_provider_resilience.py tests/test_prometheus_metric_provider.py tests/test_prometheus_metric_provider_configuration.py tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py -q` — **268 passed, 28 skipped** (the skips are existing PostgreSQL-gated tests).
- Targeted Ruff check, Ruff format check, and `git diff --check` — **passed**.
- Cumulative accepted-VS-02 audit with `VS03_REVIEW_TIP=9e5d80d7d520f37cabd843092c8b3712c4d5afac` — **passed**.

## Cumulative review inventory

- Accepted VS-02 baseline: `81270d9537329eea0477254094ef9fcdce6f17e6`.
- Existing unaccepted VS-03 production/test commits: `4baf129efeb84ba40c507934ad9e4451cf59b5b0`, `5c35ae84e141169375faff4e7f1c909ccb774cbb`, `3a3ef1b6e865afb257ab6ba72052cc80415a3acb`, and `71566e0b7b98251cd40f58361659ff52b76379df`.
- Later VS-03 corrections: `290fd968fe673838fc6b8dcff14311870c0128a1`, `9ecc0f5bdbf5407b6df3ba35c4d83f3c5af4b0e3`, `201d6180b90914e6ae9ee130635c3d5e13b27b0d`, and `9e5d80d7d520f37cabd843092c8b3712c4d5afac`.
- Audited candidate review tip: `9e5d80d7d520f37cabd843092c8b3712c4d5afac`.
- Complete production/test name-status: `M backend/src/app/infrastructure/prometheus/composition.py`; `M backend/tests/test_metric_analysis_pipeline.py`; `A backend/tests/test_prometheus_metric_provider_resilience.py`.
- Cumulative `production-test.diff` SHA-256: `0d77d5458efce23f5cc7f1c9b9544155c77a812771cd1821b4c8afea83c26f9c`.

This handoff is metadata-only and necessarily follows the audited implementation commit;
the Coordinator/reviewer must rerun the required audit at its exact final review tip.
The production/test name-status set and digest must remain unchanged unless another
approved VS-03 correction is made.

## Scope and follow-up

VS-01 source resolution and VS-02 request, mapping, and status behavior remain unchanged.
No Metric domain, pipeline, public port/outcome, runtime, persistence, schema,
dependency, preflight, API, or frontend behavior changed.

Plan change requested: none.

Shared knowledge candidates: none.
