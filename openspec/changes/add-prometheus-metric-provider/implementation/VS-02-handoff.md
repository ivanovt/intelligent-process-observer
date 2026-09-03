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
| VS02-AC01 | Root/prefix and 0.5s, 60s, 60.001s, 3600s, 3600.001s request tests assert one form POST, exact URL/form, resolution, and no extra fields. |
| VS02-AC02 | Bearer/Basic request ledgers verify preemptive headers; redirect test makes one request; default-client test proves redirects/proxy environment off and TLS verification on. |
| VS02-AC03/04 | Strict matrix tests cover empty, single ordered finite/non-finite samples, two series, histogram presence, bad labels/pairs/timestamps/values, and 61/62 sample boundary. |
| VS02-AC05 | Exact 1 MiB body succeeds; declared and streamed over-cap bodies fail and close; complete malformed retryable status bodies yield private retry-eligible variants. |
| VS02-AC06/08 | Warning/annotation failures and sentinel audit prove fixed diagnostics omit provider text, labels, samples, URLs, and credentials. |
| VS02-AC07 | Classifier tests cover timeout precedence, malformed/bare 503 failure, and all retryable statuses. |
| VS02-AC09 | Real composed provider pipeline test records current plus ordered 1h/1d/1w windows, equal step `3`, successful surrounding references, and partial omission of the single failed reference. |

## Files and verification

- Production: `backend/src/app/infrastructure/prometheus/composition.py`
- Tests: `backend/tests/test_prometheus_metric_provider.py`, focused updates to
  `test_prometheus_metric_provider_configuration.py` and
  `test_metric_analysis_pipeline.py`.
- `cd backend && uv run pytest tests/test_prometheus_metric_provider.py tests/test_prometheus_metric_provider_configuration.py tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py -q` — **135 passed, 28 skipped** (existing PostgreSQL-gated tests).
- Targeted Ruff check/format, `openspec validate add-prometheus-metric-provider --strict`,
  and `git diff --check` — **passed**.

## Downstream invariants and deferred work

The public Metric port and pipeline contracts are unchanged. A VS-02 retry-eligible
attempt currently projects to fixed typed acquisition failure at the public boundary;
VS-03 must consume the private result for deadlines, HTTPX taxonomy, retry admission,
sleep, second/third attempts, and retry exhaustion. No hard deadline, retry, or sleep
was added here.

Implementation commit: `99bce0803fb8781151b085d06925d1edf3dacae2`

Plan change requested: none.

Shared knowledge candidates: none.
