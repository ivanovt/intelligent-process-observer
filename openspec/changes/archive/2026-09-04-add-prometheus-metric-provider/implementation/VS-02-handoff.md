# VS-02 Handoff

## Delivered

- Replaced the valid-target transport placeholder with one injected HTTPX range-query
  attempt behind the unchanged `MetricSeriesProvider` port.
- Builds immutable form POSTs to the validated root/prefix target with opaque PromQL,
  UTC RFC 3339 bounds, double-ceiling step, `timeout=10s`, and `limit=2` only.
- Uses preemptive Bearer/Basic authentication, normal TLS verification,
  `follow_redirects=False`, and `trust_env=False`.
- Streams and closes each response/client, rejects declared or streamed bodies over
  1 MiB, then strictly classifies bounded bodies. Private attempt results distinguish
  available, terminal failure/timeout, and retry-eligible `429|500|502|504` responses.
- Maps only zero or one strict float matrix series; preserves order and non-finite float
  values, discards labels/annotation text, and fails closed on warning annotations,
  malformed shapes, histograms, multi-series responses, and more than 61 samples.

## Acceptance evidence

| Coverage | Evidence |
|---|---|
| VS02-AC01 | Root/prefix request tests cover every approved double-ceiling vector: `0.5`, `1.25`, `59.999`, `60`, `60.001`, `119.999`, `120`, `120.001`, `3599.999`, `3600`, and `3600.001` seconds. Each asserts the exact one-POST path, form, RFC 3339 start/end, step, and `floor(duration / step) + 1 <= 61`. |
| VS02-AC02 | Bearer/Basic request ledgers verify preemptive headers; redirect test makes one request; default-client test proves redirects/proxy environment off and TLS verification on. |
| VS02-AC03/04 | Strict matrix tests cover empty, single ordered finite/non-finite samples, two series, histogram presence, bad labels/pairs/timestamps/values, and 61/62 sample boundary. |
| VS02-AC05 | Exact 1 MiB body succeeds. For each `429`, `500`, `502`, and `504`, the same status's bounded malformed body yields private `retry_eligible`, while a declared over-cap body yields private terminal failure and closes its stream. The existing streamed over-cap `504` case also closes, proving both body-bound paths precede status. |
| VS02-AC06/08 | Valid successful `infos` preserve available data while discarding text. Valid non-empty warnings and every malformed success annotation form fail closed; sentinel assertions prove annotations, provider errors, labels, samples, URLs, and credentials do not enter outcomes. |
| VS02-AC07 | Strict matrix parameterizes both valid `timeout` and `canceled` envelopes over each retryable `429`/`500`/`502`/`504` status with separately warnings-only and infos-only valid annotation forms; every case yields private `_AttemptTimeout`, proving timeout/canceled wins over retry eligibility. It also covers absent/malformed `status`, `errorType`, or `error` including empty values; string-but-not-`error` statuses; malformed warning/infos error annotations (which yield terminal failure at `503` and retry eligibility at each retryable status); bare/malformed `503`; non-retryable `400`/`422`/`501`; and retryable statuses with a valid non-timeout error. All resulting private/public outcomes are fixed and omit provider text. |
| VS02-AC09 | A real composed-provider mock-transport pipeline test records exactly one empty-current request and proves an empty matrix reaches the existing pipeline as available-but-insufficient, producing the completed-insufficient result. The existing composition regression records current plus ordered 1h/1d/1w windows, equal step `3`, successful surrounding references, and partial omission of the single failed reference. |

## Files and verification

- Production: `backend/src/app/infrastructure/prometheus/composition.py`
- Tests: `backend/tests/test_prometheus_metric_provider.py`, focused updates to
  `test_prometheus_metric_provider_configuration.py` and
  `test_metric_analysis_pipeline.py`.
- `cd backend && uv run pytest tests/test_prometheus_metric_provider.py tests/test_prometheus_metric_provider_configuration.py tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py -q` — **193 passed, 28 skipped** (existing PostgreSQL-gated tests).
- Targeted Ruff check and format check for the provider/focused VS-02 tests, and
  `git diff --check` — **passed**.

## Downstream invariants and deferred work

The public Metric port and pipeline contracts are unchanged. A VS-02 retry-eligible
attempt currently projects to fixed typed acquisition failure at the public boundary;
VS-03 must consume the private result for deadlines, HTTPX taxonomy, retry admission,
sleep, second/third attempts, and retry exhaustion. No hard deadline, retry, or sleep
was added here.

Initial implementation commit: `99bce0803fb8781151b085d06925d1edf3dacae2`

Evidence correction commit: `d01a10477158d316b18eac43fc48abca5ddd01db`

Final error-envelope evidence correction: `0d355201d94da59db062afbad794cbce96a98e67`

Empty-current composed-provider evidence correction: `ee4d364bb95a954b84b93dd33f0203fa9d72cb1b` (this atomic correction commit).

Plan change requested: none.

Shared knowledge candidates: none.
