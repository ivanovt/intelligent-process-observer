## Context

See `proposal.md` for motivation. The Metrics Analysis Pipeline is implemented and
accepts `MetricProviderScope(adapter_type="prometheus", source_id, query)` plus an exact
`MetricAnalysisWindow` through the framework-neutral `MetricSeriesProvider.acquire`
port. It already derives and independently requests the current and every configured
reference window, maps typed provider outcomes into accepted terminal/partial behavior,
and validates all returned samples deterministically.

The repository also has a server-managed `PROMETHEUS_SOURCES` registry and an
`HttpxPrometheusQueryAdapter`, but that adapter serves only the public non-persisting
Metric Lens preflight operation. It raises preflight-specific exceptions and returns
labels/warnings, so it does not satisfy the production pipeline port. This change may
reuse small infrastructure-only request/decoding primitives, but it must preserve the
canonical preflight contract, including its independent 15-second/no-retry behavior.
It must also preserve compatible shared source loading, application startup,
capabilities projection, and Observation creation. Stricter production-provider
validation therefore belongs after source selection inside production acquisition, not
in global Settings or the shared registry model.

Official Prometheus behavior used by this design:

- The stable API is under `/api/v1`; range queries support GET or form-encoded POST,
  require `query`, inclusive `start`, inclusive `end`, and `step`, and accept optional
  `timeout`, `limit`, and `lookback_delta`: [Prometheus HTTP API — range queries](https://prometheus.io/docs/prometheus/latest/querying/api/#range-queries).
- Success/error envelopes, HTTP `400`/`422`/`503`, and successful data accompanied by
  `warnings` or `infos` are documented by the [HTTP API format overview](https://prometheus.io/docs/prometheus/latest/querying/api/#format-overview).
- Matrix results can carry float `values`, native `histograms`, or both, and special
  float values are encoded as strings: [expression query result formats](https://prometheus.io/docs/prometheus/latest/querying/api/#expression-query-result-formats).
- A range query evaluates PromQL independently at equally spaced timestamps; normal
  selector lookup uses the newest sample within the configured/default lookback and
  honors staleness: [Prometheus querying basics](https://prometheus.io/docs/prometheus/latest/querying/basics/).
- Prometheus supports TLS and HTTP Basic authentication, and Basic credentials without
  TLS are exposed in cleartext: [Prometheus security model](https://prometheus.io/docs/operating/security/).
- A deployment can expose Prometheus behind an external URL path prefix:
  [Prometheus command-line configuration](https://prometheus.io/docs/prometheus/latest/command-line/prometheus/).
- HTTPX distinguishes timeout, network, protocol, proxy, decoding, redirect, URL, and
  stream-state failures through its documented
  [exception hierarchy](https://www.python-httpx.org/exceptions/).

## Goals / Non-Goals

**Goals:**

- Implement the existing single-series provider port with deterministic, bounded
  Prometheus API v1 behavior for any exact window supplied by the pipeline.
- Keep credentials and trusted endpoint selection in server-side infrastructure.
- Detect response shapes that cannot be represented honestly by the existing dataset
  contract instead of silently merging, truncating, or accepting incomplete data.
- Make request, time, volume, retry, and resource-cleanup bounds deterministic and
  independently testable.
- Expose a composed source-aware provider at the application boundary without creating
  new Observation execution/orchestration behavior.

**Non-Goals:**

- Changing Metric provider/domain contracts, sample preparation, statistics,
  deterministic semantics, reference comparisons, History, agent behavior, result
  building, persistence, or public APIs.
- Adding expected-cadence/gap analysis, Prometheus metadata discovery, query rewriting,
  automatic aggregation, recording rules, remote read/write, exemplar support, native
  histogram conversion, or provider SDKs.
- Adding unauthenticated production sources, custom CA/mTLS, OAuth, cloud-vendor request
  signing, proxy configuration, dynamic secret discovery/rotation, or source health
  monitoring.
- Adding top-level Observation orchestration or invoking a live Prometheus instance in
  automated tests.

## Decisions

### Reuse the existing source registry but harden the outbound trust boundary

The production provider resolves the exact `source_id` from the already-established
server-managed source registry without changing Settings validation or the shared model.
Only after the production `MetricSeriesProvider` selects a source does it validate the
URL and transport policy. Thus a source that remains usable by capabilities,
Observation creation, and preflight can be rejected for production acquisition without
breaking startup or those existing public behaviors. An unknown source returns
`MetricSeriesUnavailable` with zero HTTP attempts; a selected configured source
rejected by production-only validation returns `MetricSeriesAcquisitionFailure` with
zero HTTP attempts.

The provider supports only the existing discriminated Bearer and Basic credential
models. **Secret credential material** means exactly the Bearer token and Basic-auth
password. The Basic username is not secret credential material and remains in the
existing internal model; this change does not alter model representation merely to hide
it internally. The external safety boundary is stricter: diagnostics, logs, errors,
public output, and failure messages omit the Bearer token, Basic password,
Authorization header, and configured Basic username. There is no separate provider
configuration store or Lens-owned credential reference.

The selected base URL accepts HTTPS and loopback-only HTTP and has no
userinfo/query/fragment. The path accepts only empty or `/` for no prefix, or one or
more non-empty `/`-separated segments containing only ASCII RFC 3986 unreserved
characters (`ALPHA`, `DIGIT`, `-`, `.`, `_`, `~`). A segment cannot equal `.` or `..`.
One trailing slash is removed; all other accepted segment bytes are preserved exactly.
The validated origin is exactly scheme, host, and optional port with no path. Repeated
`//`, empty interior segments, backslashes, every percent-encoded byte
(including encoded separators/dot segments), and other ambiguous parser forms are
rejected. The target is formed without URL joining or decoding as
`<validated origin><normalized prefix>/api/v1/query_range`. Redirects and
environment-derived proxies are disabled and normal certificate verification remains
enabled.

Alternative considered: create another serialized provider setting like Jira. Rejected
because Prometheus sources and secret types are already canonical repository behavior
and are also used by Metric preflight. Alternative considered: strengthen the shared
source model. Rejected because that would regress startup and established public source
consumers for a production-only concern. Alternative considered: accept arbitrary HTTP
targets, path encodings, or redirects. Rejected because every configured source carries
credentials, official documentation warns that Basic authentication over HTTP is
cleartext, and ambiguous path normalization could change the credential-bearing target.

### Use one immutable range-query payload with explicit resolution and a series sentinel

Each port acquisition first executes a pre-transport phase. An absent/unknown source
returns unavailable with zero attempts; a selected source that fails production-only
validation returns failure with zero attempts. Only a successfully resolved and
validated source enters the transport phase.

The transport phase prepares one immutable logical request for the unchanged PromQL at
`<validated-origin><normalized-prefix>/api/v1/query_range`. It performs one initial HTTP
attempt and zero, one, or two admitted retries, for exactly 1..3 attempts and never a
fourth. Every attempt emits exactly one form-encoded POST and reuses identical query,
RFC 3339 UTC `start`/`end`, step, source/provider selection, authentication, and
configuration. This preserves the exact pipeline window without float timestamp
roundoff; retries cannot rewrite, broaden, shift, or otherwise modify it. The provider
sends the fixed server evaluation `timeout=10s`, omits `lookback_delta` so
deployment-owned Prometheus staleness semantics apply, and never adds a PromQL `offset`;
references are separate acquisitions over the exact windows already derived by the
pipeline.

The step is `max(1, ceil(ceil(duration_seconds) / 60))` integer seconds. Thus a 60-minute
window uses 60 seconds, equal-duration current/reference windows use equal resolution,
and the inclusive range has no more than 61 requested evaluation timestamps. The
provider sends `limit=2`: because the Lens contract requires exactly one series, a
limit of two bounds the returned series while retaining enough information to reject
every multi-series result. This is intentionally not a user-configurable tuning surface
for the MVP.

Parameterized boundary tests include sub-second and fractional windows and durations
immediately below, exactly at, and immediately above minute/60-divisor boundaries,
including one hour. Each case asserts the exact step, byte-for-byte start/end form
values, and `floor(duration / step) + 1 <= 61`; this distinguishes the double-ceiling
policy from floor or integer-truncation implementations.

Attempt tests separately prove unavailable source and production-invalid source at zero
attempts, then transport success on the initial request, retry #1, retry #2, and
exhaustion at exact counts of one, two, three, and three. Every multi-attempt case
compares the complete logical payload and selected source/authentication identity, not
only the query string.

Alternative considered: reuse raw scrape timestamps. Rejected because `query_range`
evaluates at explicit steps and the existing preflight already establishes range-query
semantics. Alternative considered: configure step per Lens. Rejected because that would
change the public Metric definition and analytical comparability. Alternative
considered: `limit=1`. Rejected because silent server truncation would make a
multi-series query look valid.

### Translate only a complete single float series

The adapter validates `status=success`, `resultType=matrix`, a result array, and strict
matrix members. Zero series becomes `MetricSeriesAvailable(samples=())`, so the
existing quality policy—not transport—owns the insufficient-data outcome. Exactly one
series maps each `[timestamp, "value"]` pair to the current `MetricSample`. More than
one series, native histograms, mixed float/histogram data, or malformed required fields
return acquisition failure.

Float strings intentionally include `NaN`, `+Inf`, and `-Inf`; the provider port already
admits them and deterministic preparation owns their removal and quality effect. Labels
are shape-validated and discarded. Sample order, duplicates, and window membership are
not repaired: decoded samples cross unchanged so the existing preparer retains sole
ownership of sorting and malformed-series rejection.

Alternative considered: merge multiple series or extract a native histogram statistic.
Rejected because either action invents metric semantics outside the stored PromQL and
violates the one-metric-series contract. Alternative considered: make zero series
unavailable. Rejected because a complete empty provider response is data and the
existing pipeline has an explicit completed-insufficient variant.

### Fail closed when warning annotations cannot be represented

The HTTP layer streams and limits each body to 1 MiB, including early rejection from a
larger declared content length, and validates at most 61 samples for the accepted
series. It never returns a truncated successful dataset. The series sentinel bounds a
valid response to at most two series before rejection.

Prometheus documents `warnings` as non-inhibiting errors that can accompany returned
data, but does not guarantee that every warning means partially collected data. Failing
closed on every non-empty warnings array is therefore an explicit conservative
project/provider policy: `MetricSeriesAvailable` cannot represent or qualify warning
annotations, and the pipeline's partial reasons do not include them. Valid `infos` are
handled by the already-approved provider policy: their count may be bounded operational
telemetry, but their provider-authored text is discarded. Raw bodies, errors, labels,
annotation text, queries, URLs, and samples never enter port diagnostics or persistence.

That warning policy applies only to a valid `status="success"` data envelope. Error
envelopes validate optional warnings/infos as string arrays, but those annotations do
not override a valid primary `timeout|canceled` classification and do not turn another
error into the successful-data warning policy. Malformed annotation fields make either
envelope contract-invalid.

Alternative considered: accept data and discard warnings. Rejected because it can
publish an unqualified Metric analysis even though the provider supplied an annotation
the existing contract cannot express; this rejection does not assign one universal
meaning to Prometheus warnings.
Alternative considered: add warnings to the dataset/result contracts. Rejected because
that would redesign the provider-neutral and public analytical contracts.

### Apply hard local deadlines and narrow deterministic retries

Prometheus receives `timeout=10s` for query evaluation. The application separately owns
a hard monotonic 15-second execution/result deadline for the complete attempt and body
read, and a 50-second execution/result deadline for the observable `acquire()` call. The
latter contains the worst admitted three-attempt sequence:
`15 + 0.5 + 15 + 1.0 + 15 = 46.5` seconds plus local overhead. A retry is admitted only
when its selected wait and a complete attempt fit.

Deadline expiry commits the provider to the existing typed timeout result. It signals
cancellation and close to an in-flight response/client, but does not wait indefinitely
for cancellation-resistant cleanup: the execution/result deadline governs return, while
transport resource-cleanup lifetime is best-effort and separate. A late transport
completion is discarded and cannot start a retry, replace the committed timeout, or
mutate analytical, pipeline, Lens, runtime, or persistence state. To prevent detached
cleanup from accumulating, a private finite execution/resource capacity accounts for
both live acquisition work and cleanup that remains after timeout. Cleanup retains that
capacity until it terminates; capacity exhaustion fails a newly admitted acquisition
before transport through the existing typed acquisition-failure outcome with a fixed safe
diagnostic. This is an infrastructure-private safeguard, not a new public setting,
reason code, or provider-port contract.

Retry admission is itself terminal when the remaining acquisition budget is too small.
If an otherwise eligible retry cannot fit its selected 0.5/1.0-second wait plus a full
15-second next attempt, the provider returns timeout immediately, without sleeping and
without issuing another request. This applies identically to `ConnectError` and each
retryable HTTP status. It differs from exhaustion: when all three admitted attempts
actually run and the retryable condition persists through the third, the outcome is
failure.

Only `httpx.ConnectError` and HTTP `429`, `500`, `502`, or `504` are retried, at most
twice, with fixed 0.5/1.0-second waits and no jitter or `Retry-After` behavior. All
other HTTPX exceptions are non-retryable. The catch/classification order mirrors the
current official HTTPX hierarchy rather than relying on a generic transport category.

Classification uses one ordered decision table:

1. Hard local attempt/acquire deadline exhaustion is timeout and takes precedence over
   any simultaneously observed HTTPX exception.
2. HTTPX exceptions are matched most-specific first:
   - any `TimeoutException` (`ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, or
     `PoolTimeout`) is timeout without retry;
   - `ConnectError` uses the retry policy, becomes timeout without wait/request when
     remaining-budget admission rejects the next retry, and becomes failure when all
     admitted attempts are exhausted;
   - every other `TransportError`—including `ReadError`, `WriteError`, `CloseError`,
     `RemoteProtocolError`, `LocalProtocolError`, `ProxyError`, and
     `UnsupportedProtocol`—is failure without retry;
   - request/client errors outside `TransportError`, including `DecodingError`,
     `TooManyRedirects`, `InvalidURL`, and `StreamError`, are failure without retry.
3. Body acquisition without an HTTPX exception enforces the deadline and 1 MiB bound;
   deadline is timeout, while oversized or deterministically unusable body acquisition
   is failure before status classification.
4. With a complete bounded body, first validate the error envelope. It is valid only
   when the JSON object has `status="error"`, non-empty string `errorType`, non-empty
   string `error`, and string-array `warnings`/`infos` whenever either is present;
   `data` is optional. A valid exact `timeout|canceled` error type is timeout and valid
   annotations do not override it. Next, `429|500|502|504` uses the retry policy,
   including for a malformed envelope or valid other error type; remaining-budget
   rejection is timeout without wait/request, while actual exhaustion is failure. A
   valid other error type is failure. Bare/malformed `503` and every other non-success
   status are failure.
5. A successful status requires the complete success envelope/result contract. Its
   annotation fields must be string arrays when present; non-empty warnings trigger the
   project fail-closed policy, while infos alone are discarded.

Complete bounded malformed JSON is deliberately distinct from failed body acquisition.
On `429|500|502|504`, it follows the status retry branch; on `503` or another
non-success status, it fails without retry; on success, it fails success-envelope
validation. Conversely, an oversized body fails at rule 3 even when its HTTP status
would otherwise be retryable. A bare `503` is never treated as timeout merely because
Prometheus documents 503 for query timeout/abort: the same status can be emitted by a
proxy or intermediary, so timeout requires the valid Prometheus error envelope.

The exception taxonomy is exhaustive at the provider boundary: `ReadError`,
`WriteError`, protocol failures, decoding failures, redirect errors, URL errors, and
stream-state errors cannot fall through to an undefined retryable-transport rule.

Alternative considered: no retry, matching preflight. Rejected because production
analysis benefits from narrowly retrying idempotent reads while preflight's interactive
contract remains unchanged. Alternative considered: exponential jitter or
provider-directed waits. Rejected to keep the MVP deterministic and within a provable
budget. Alternative considered: retry query timeouts. Rejected because repeating an
already expensive query can amplify Prometheus load and exceed observation latency.

### Compose at infrastructure/application startup and test through injected seams

Add a source-aware provider implementation/composer in
`app.infrastructure.prometheus`. Application lifespan constructs it from validated
shared settings and exposes it for injection into the existing pipeline port, analogous
to the existing provider composition pattern. Construction retains the compatible
registry as loaded and does not apply the stricter production URL/transport rules;
those run only when `acquire` resolves its selected source. This does not start a
LensRun or add an Observation execution endpoint. The Metric package remains free of
settings, HTTPX, and Prometheus response contracts.

Keep preflight and production policy entry points distinct. Shared low-level parsing or
request construction is acceptable, but capabilities, Observation creation, and
preflight regression tests are mandatory regardless of whether any HTTP helper is
shared; they must prove compatible source loading and canonical public behavior did not
change. The production provider accepts injected HTTP transport/client construction,
monotonic clock, sleeper, and hard-deadline runner or equivalent seams. Tests use mocked
HTTP exchanges and cancellation-observable bodies to cover exact requests, all
response/mapping branches, bounds, retry admission, timeout commitment, discarded late
transport information, bounded cleanup capacity, composition, and pipeline
current/reference behavior.

Alternative considered: inject the preflight adapter directly into the pipeline.
Rejected because its exceptions/output are API-specific, it accepts a source profile
rather than `MetricProviderScope`, and its warning/retry semantics differ. Alternative
considered: resolve settings inside the domain pipeline. Rejected because it violates
the accepted provider-neutral boundary.

## Risks / Trade-offs

- [A valid PromQL expression may aggregate a very large underlying cardinality even
  though only one result series is returned] → retain the stored-query preflight,
  explicit 10-second server timeout, hard local deadlines, and operator responsibility;
  recommend recording rules for expensive expressions rather than inventing query
  rewriting.
- [Prometheus range evaluation and staleness can return fewer points than the requested
  grid] → preserve returned data and let the existing finite-sample quality contract
  decide good/degraded/insufficient; do not infer gaps without expected cadence.
- [Failing on warnings can reduce availability for deployments that accept
  warning-annotated query results] → retain the explicit conservative project policy;
  representing or qualifying those annotations would require a separately approved
  provider-neutral contract change.
- [A fixed 61-point resolution can smooth brief events or change results relative to a
  dashboard step] → make the policy explicit and identical for equal-duration current
  and reference windows; changing resolution later is a behavioral/spec decision.
- [A source accepted by shared configuration can be unusable for production acquisition]
  → validate only after production source resolution, return the typed failure without
  a request, preserve startup/capabilities/create/preflight behavior, and document the
  production-only HTTPS/path rules.
- [A 50-second bound applies independently to current and each sequential configured
  reference] → preserve accepted independent reference semantics; Observation-level
  concurrency or total Lens deadline remains outside this provider change.

## Migration Plan

1. Add production-only selected-source validation without changing shared Settings or
   registry loading; verify startup, capabilities, Observation creation, and preflight
   remain compatible even for a source rejected only by production acquisition.
2. Add the production port adapter and deterministic HTTP/deadline/retry seams while
   retaining the preflight entry point and its tests.
3. Add application composition and injected-pipeline verification. No database or
   public-API migration is required.
4. Document placeholder-only deployment configuration and operational limitations,
   then run focused checks, strict OpenSpec validation, and `make check`.
5. Roll back by reverting provider composition/adapter changes; definitions, LensRuns,
   Metric results, database schema, and stored source IDs require no data migration.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`: the provider receives one Metric
  Lens query and never introduces cross-metric or baseline semantics.
- `docs/architecture/02_architecture_principles_and_runtime.md` and
  `04_pipeline_and_agent_concepts.md`: acquisition remains a deterministic pipeline
  dependency; the Metrics Agent cannot access or change provider scope.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: typed current
  failures and independent reference incompleteness are reused unchanged.
- `docs/architecture/03_ADR_log.md`: ADR-003 and ADR-045–048 constrain single-metric,
  deterministic-pipeline, and immutable-agent scope; ADR-133–135 constrain exact
  independently acquired equal-duration references and preserve History separation;
  ADR-157 fixes unavailable-reference partial semantics and reason precedence.
- `openspec/specs/metrics-analysis-pipeline/spec.md`: the canonical provider-port,
  current acquisition failure, configured-reference omission/partial, diagnostic, and
  result rules remain authoritative for integration outcomes.
- `docs/architecture/10_open_decisions_and_backlog.md`: this design intentionally closes
  only the deferred production Prometheus transport, authentication, retry, timeout,
  mapping, and composition details named there; it does not close the separate
  production Metrics LLM/model decisions.
