## 1. Source configuration and safe composition

- [ ] 1.1 Preserve global Settings and shared `PROMETHEUS_SOURCES` loading unchanged;
  add stricter URL/transport validation only after the production
  `MetricSeriesProvider` resolves the selected configured source, returning failure
  with zero HTTP attempts when that production-only validation rejects it.
- [ ] 1.2 Add production-boundary and credential-safety tests covering valid HTTPS and
  loopback targets, every rejected URL component/host/scheme, absent and unknown
  sources, and proof that invalid selected targets send no request; define secret
  material as Bearer token/Basic password while also excluding Authorization and the
  configured Basic username from provider diagnostics, logs, errors, public output,
  and failure messages without changing the existing credential model for repr alone.
- [ ] 1.3 Add a source-aware Prometheus Metric provider composer/resolver that returns
  the existing typed unavailable outcome with zero HTTP attempts for absent/unknown
  sources, preserves the compatible loaded registry without eager production URL
  validation, resolves and validates only the source selected by `acquire`, returns
  failure with zero attempts for a selected production-invalid source, and never
  chooses a fallback.
- [ ] 1.4 Wire the composed provider into application lifespan/state only as an
  injectable `MetricSeriesProvider`; prove Metric domain/pipeline modules import no
  settings, HTTPX, or Prometheus response contracts and that composition starts no run
  or Observation orchestration.

## 2. Bounded Prometheus range acquisition

- [ ] 2.1 Implement the infrastructure-only production port adapter using form-encoded
  `POST <validated-origin><normalized-prefix>/api/v1/query_range`; terminate absent,
  unknown, or selected production-invalid sources in a pre-transport phase with zero
  attempts, then prepare one immutable logical request only for a transport-phase
  acquisition and make exactly one POST on each of its 1..3 attempts with identical
  source, authentication, configuration, unchanged PromQL, exact UTC RFC 3339 bounds,
  deterministic step, `timeout=10s`, `limit=2`, and no lookback/stats extras. Preserve
  verified TLS, disabled redirects/proxies, the exact path grammar, and rejection of
  ambiguous paths before any attempt.
- [ ] 2.2 Implement strict bounded response-body streaming with the 1 MiB cap and
  cancellation-safe resource cleanup; reject declared or observed over-cap responses
  without returning truncated data.
- [ ] 2.3 Implement strict success-envelope/matrix/label/sample validation and mapping
  to the unchanged `MetricSeriesAvailable` contract: zero series to empty available,
  exactly one float series to UTC samples, multi-series/native-histogram/malformed data
  to failure, and at most 61 samples.
- [ ] 2.4 Preserve decoded sample order, duplicate timestamps, window membership, and
  `NaN|+Inf|-Inf` values for existing deterministic preparation; discard labels and all
  raw Prometheus transport objects at the provider boundary.
- [ ] 2.5 Reject non-empty warnings under the explicit conservative project policy
  because the provider-neutral contract cannot represent or qualify them, without
  assigning one universal meaning to Prometheus warnings; treat valid infos only as
  bounded operational telemetry without retaining provider text, and ensure bodies,
  provider errors, annotations, labels, queries, URLs, and samples never enter outcomes,
  logs, persistence, or diagnostics.

## 3. Deadlines, retries, and typed outcome mapping

- [ ] 3.1 Implement injected monotonic hard deadlines of 15 seconds per complete
  request/body-read attempt and 50 seconds per complete acquire, including waits and
  every attempt; cancel in-flight work and close response/transport resources on expiry.
- [ ] 3.2 Implement at most two retries only for `httpx.ConnectError` and HTTP
  `429|500|502|504`, with exact no-jitter waits of 0.5 and 1.0 seconds and admission only
  when the complete wait plus a new 15-second attempt fits the acquire budget; do not
  honor provider-directed delays. If an otherwise eligible retry cannot fit, return
  timeout immediately with no sleep and no additional HTTP attempt; apply this rule
  identically to ConnectError and every retryable status.
- [ ] 3.3 Implement the exact ordered classification table: hard local deadlines first;
  then HTTPX exceptions in subclass order (`TimeoutException`, `ConnectError`, other
  `TransportError`, request/client errors outside `TransportError`); bounded/deadlined
  body acquisition; strict Prometheus error-envelope validation; proven
  timeout/canceled; status retry for `429|500|502|504`; valid other provider error;
  bare/malformed HTTP 503 and other non-success failure; then successful-status
  envelope/result and success-annotation validation. Use no undefined generic transport
  retry category and only fixed bounded diagnostic categories/status codes.
- [ ] 3.4 Add deterministic retry/deadline/precedence tests for exact attempt counts and
  waits, retry admission/rejection, in-flight request and slow-body cancellation,
  cleanup, and no work after 50 seconds; explicitly map `ConnectError` to retry,
  `ConnectTimeout`/`ReadTimeout` to timeout without retry, and `ReadError`, `WriteError`,
  `RemoteProtocolError`, and `DecodingError` to failure without retry, plus representative
  remaining named hierarchy categories and hard-deadline precedence over exceptions.
  Add near-deadline cases proving insufficient budget after ConnectError and each
  retryable status returns timeout with no sleep/request, sufficient budget admits the
  retry normally, and actual three-attempt exhaustion remains failure.
- [ ] 3.5 Add acquisition-attempt tests proving absent registry and unknown source each
  return unavailable with zero attempts, and a selected production-invalid source
  returns failure with zero attempts; success on attempt 1 uses one POST, success on
  retry #1 uses two, success on retry #2 uses three, and full retry exhaustion uses
  three and no fourth. For every retry compare identical PromQL, start, end, step,
  timeout, limit, target, source selection, authentication, and configuration.

## 4. Mapping and integration verification

- [ ] 4.1 Add exact request-target tests for empty and `/` root paths, their normalized
  forms, valid prefixes such as `/prometheus` and `/team.v1/_prom~etheus-2/metrics/`
  with exact accepted-segment preservation, and rejection before request of concrete
  repeated/empty/dot/backslash/encoding cases such as `/a//b`, `/a//`, `/./a`,
  `/a/../b`, `/a\\b`, `/%41`, `/%2F`, and `/%2e%2e`, plus uppercase/lowercase encoded
  separator or dot variants and other ambiguous path forms.
- [ ] 4.2 Add parameterized deterministic-step tests for sub-second and fractional
  windows and exact boundary cases including `0.5s -> 1`, `1.25s -> 1`,
  `59.999s -> 1`, `60s -> 1`, `60.001s -> 2`, `119.999s -> 2`, `120s -> 2`,
  `120.001s -> 3`, `3599.999s -> 60`, `3600s -> 60`, and
  `3600.001s -> 61`. For every case assert the exact expected step, exact start/end
  preservation, and `floor(duration / step) + 1 <= 61`, alongside unchanged
  POST/query/timeout/limit/no-lookback/no-stats request fields.
- [ ] 4.3 Add HTTP-boundary tests for Bearer/Basic authentication, exact root/prefixed
  targets, current/reference requests, equal-duration resolution, verified TLS, no
  environment proxy trust, no redirect following, and no credential forwarding.
- [ ] 4.4 Add response tests for empty/one/multiple series, finite and non-finite float
  strings, invalid timestamps/values/labels/pairs/envelopes/result types, native and
  mixed histograms, exact 61-sample success, 62-sample failure, exact body-cap success,
  declared/streamed over-cap failure, and absence of raw-data leakage. Add the complete
  error/annotation matrix: valid timeout; valid canceled; missing status; missing
  errorType; missing/empty error; malformed warnings; malformed infos; timeout with
  valid warnings; timeout with valid infos; bare 503; malformed 503; retryable status
  with malformed body; successful data with non-empty warnings; and successful data
  with infos only.
- [ ] 4.5 Add injected Metrics pipeline tests proving successful current acquisition,
  configured reference acquisition through the same provider, empty-series insufficient
  behavior, current unavailable/failure/timeout terminal mapping, reference-only partial
  mapping, and preservation of the provider-neutral Metric contracts and analytical
  results.
- [ ] 4.6 Regardless of whether HTTP helpers are shared, add mandatory regression tests
  proving application startup, capabilities output, Observation creation, and Metric
  preflight retain compatible shared-source behavior for both production-valid and
  production-invalid selected source URLs; preserve preflight's independent 15-second
  timeout, no-retry policy, labels/warnings projection, and public error mapping.

## 5. Documentation and final verification

- [ ] 5.1 Add concise public class/interface-method docstrings and developer/deployment
  documentation for placeholder-only source configuration, HTTPS/loopback policy,
  exact path-prefix grammar, production-only validation boundary, supported Bearer/Basic
  modes, secret-material terminology and external username suppression, excluded
  authentication/TLS/proxy modes, fixed resolution/limits, project-owned warning policy,
  exact zero-attempt pre-transport and 1..3-attempt transport/logical-request identity
  contract, budget-rejection timeout versus executed-retry exhaustion failure, ordered
  HTTPX exception and strict Prometheus error-envelope classification, hard deadlines,
  retries, and Prometheus lookback/staleness limitations without storing real credentials.
- [ ] 5.2 Verify no dependency, database schema/migration, public API,
  MetricAnalysisResult, deterministic analysis, History, Metrics Agent,
  reference-period semantics, or Observation orchestration changes were introduced.
- [ ] 5.3 Run focused Prometheus provider, configuration, preflight, Metrics pipeline,
  and integration tests; report every failure accurately.
- [ ] 5.4 Run `openspec validate add-prometheus-metric-provider --strict` and the
  repository `make check` as the final local gate. Do not archive, push, create a pull
  request, or begin Observation orchestration in this implementation pass.
