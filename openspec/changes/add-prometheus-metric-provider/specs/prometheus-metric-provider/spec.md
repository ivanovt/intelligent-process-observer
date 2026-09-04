## Purpose

Provide bounded, credential-safe Prometheus range-query acquisition for the existing
provider-neutral Metrics Analysis Pipeline without exposing transport details across
the Metric provider boundary.

## ADDED Requirements

### Requirement: Resolve a server-managed Prometheus source without exposing credentials

The system SHALL resolve the immutable Metric provider scope's `source_id` against the
existing server-managed `PROMETHEUS_SOURCES` registry. This change SHALL NOT make global
Settings construction or shared source-registry loading stricter and SHALL NOT alter
the existing capabilities response, Observation creation, or Metric preflight behavior.
Production-only URL and transport validation SHALL occur only after the
`MetricSeriesProvider` resolves the selected configured source for an acquisition.

A configured source SHALL retain its existing stable ID, human-readable name, base URL,
and exactly one existing credential mode: Bearer token or HTTP Basic username/password.
For this capability, **secret credential material** means exactly the Bearer token and
Basic-auth password. The existing Basic username is not secret credential material and
MAY remain in the existing internal configuration model. The provider SHALL send Bearer
credentials in `Authorization: Bearer <token>` or Basic credentials preemptively and
SHALL never put credentials in the URL. Provider diagnostics, logs, errors, public
output, and failure messages SHALL expose none of the Bearer token, Basic password,
Authorization header, or configured Basic username. This change SHALL NOT modify the
existing credential model merely to change its internal representation.

At production acquisition, the selected source base URL SHALL use HTTPS except that HTTP
MAY be used for the exact loopback hosts `localhost`, `127.0.0.1`, or `::1`. It SHALL
contain a host and SHALL contain no userinfo, query, or fragment. The provider SHALL
verify TLS by default, ignore process proxy environment variables, and not follow
redirects. Custom CA bundles, mutual TLS, OAuth, cloud-vendor signing, unauthenticated
sources, and proxy configuration are outside this capability.

Secret credential material SHALL be accepted only through local/deployment environment
configuration and SHALL NOT appear in an Observation definition, LensRun, Metric result,
public API response, committed example value, URL, log, error, failure message, or
diagnostic. An absent registry or unknown `source_id` SHALL yield the existing typed
unavailable provider outcome and SHALL NOT select a different or default source. A
configured source that shared loading accepts but production-only URL/transport
validation rejects SHALL yield `MetricSeriesAcquisitionFailure` with zero HTTP attempts;
application startup and all existing capabilities, Observation-creation, and
Metric-preflight behavior SHALL remain unchanged.

#### Scenario: Resolve a configured source by exact ID

- **GIVEN** the immutable provider scope names one valid configured Prometheus source
- **WHEN** Metric acquisition is composed
- **THEN** the provider uses only that source's normalized API target and credentials
- **AND** it does not expose the connection configuration across the provider port

#### Scenario: Keep a Prometheus credential secret

- **WHEN** a Bearer token or Basic password is supplied through deployment configuration
- **THEN** it is used only for the outbound Prometheus request
- **AND** no committed file, runtime artifact, public response, or diagnostic contains it

#### Scenario: Keep the internal Basic username compatible but out of failures

- **GIVEN** an existing configured source contains a Basic-auth username
- **WHEN** shared configuration is loaded and production acquisition is attempted
- **THEN** the existing internal credential model may retain that username unchanged
- **AND** provider diagnostics, logs, errors, public output, and failure messages expose neither that username nor any secret credential material

#### Scenario: Report an unavailable source safely

- **GIVEN** no source registry is configured or the requested `source_id` is absent
- **WHEN** the provider acquires a current or reference window
- **THEN** it returns the typed unavailable outcome with a fixed safe diagnostic category
- **AND** it performs zero HTTP attempts and selects no fallback source

#### Scenario: Reject an unsafe authenticated target

- **GIVEN** a source URL contains non-loopback HTTP, userinfo, no host, a query, or a fragment
- **WHEN** that configured source is selected for production Metric acquisition
- **THEN** zero HTTP attempts are performed
- **AND** acquisition returns `MetricSeriesAcquisitionFailure` with a fixed safe diagnostic

#### Scenario: Preserve shared source consumers for a production-invalid source

- **GIVEN** shared source loading accepts a configured source that production-only URL or transport validation rejects
- **WHEN** the application starts and capabilities, Observation creation, Metric preflight, and production Metric acquisition are exercised
- **THEN** startup succeeds and capabilities, creation, and preflight retain their existing behavior
- **AND** only production acquisition returns `MetricSeriesAcquisitionFailure` with zero HTTP attempts

### Requirement: Query the exact current or reference window through HTTP API v1

The production provider SHALL validate the selected base URL's path using this exact
grammar:

- an empty path or `/` means no prefix;
- otherwise the path contains one or more slash-separated non-empty segments;
- every segment contains only RFC 3986 unreserved characters: ASCII letters, digits,
  `-`, `.`, `_`, or `~`;
- no segment is exactly `.` or `..`;
- one trailing slash MAY be removed during normalization.

The validated origin SHALL be the URL's scheme, host, and optional port with no path.
The provider SHALL reject repeated `//`, empty interior segments, backslashes, every
percent-encoded path byte (including encoded separators or encoded dot segments), and
all other parser-dependent or ambiguous path forms. It SHALL preserve every accepted
prefix segment and character exactly after validation. Given the validated origin and
normalized prefix, the request target SHALL be constructed only as:

```text
<validated origin><normalized prefix>/api/v1/query_range
```

One provider-port acquisition SHALL have a pre-transport phase followed, only when
eligible, by a transport phase. In the pre-transport phase, an absent registry or
unknown source SHALL return `MetricSeriesUnavailable` with zero HTTP attempts. A
selected configured source rejected by production-only URL/transport validation SHALL
return `MetricSeriesAcquisitionFailure` with zero HTTP attempts.

Only an acquisition that resolves and validates its selected source SHALL reach the
transport phase. A transport-phase acquisition SHALL perform exactly one initial HTTP
attempt and, when admitted by the approved retry policy, retry #1 and retry #2; it SHALL
therefore perform exactly one through three HTTP attempts and SHALL never perform a
fourth. Each attempt SHALL send exactly one form-encoded HTTP `POST` to
`<validated origin><normalized prefix>/api/v1/query_range` and SHALL pass the scope's
opaque PromQL unchanged as `query`; the exact timezone-aware UTC window bounds as RFC
3339 `start` and `end`; an integer-seconds `step`; `timeout=10s`; and `limit=2`. It
SHALL omit `lookback_delta`, `stats`, and all other optional query parameters.

The provider SHALL determine one logical request for the acquisition before its initial
attempt. Every admitted retry SHALL use identical PromQL, `start`, `end`, `step`,
provider/source selection, authentication, and configuration. A retry SHALL NOT rewrite,
broaden, shift, normalize, or otherwise modify the query or window.

The step SHALL be calculated independently for every requested window as:

```text
duration_seconds = ceil(window.to - window.from in seconds)
step_seconds = max(1, ceil(duration_seconds / 60))
```

Prometheus evaluates both range endpoints inclusively, so this policy permits at most
61 requested evaluation timestamps. Equal-duration current and reference windows SHALL
therefore use the same step. The provider SHALL not shift a window, add a PromQL
`offset`, rewrite the selector, infer cadence, or compensate for Prometheus lookback or
staleness behavior. Current/reference identity and reference-offset correlation SHALL
remain owned by the existing pipeline.

#### Scenario: Acquire the current window exactly

- **GIVEN** an immutable scope, query, and current analysis window
- **WHEN** the provider executes acquisition
- **THEN** it posts the unchanged query and exact inclusive UTC start/end to API v1
- **AND** it adds no offset, lookback override, selector, or analysis behavior

#### Scenario: Preserve one logical request across retries

- **GIVEN** one transport-phase acquisition requires one or two admitted retries
- **WHEN** each HTTP attempt is recorded
- **THEN** the acquisition contains exactly one initial attempt followed by retry #1 and optionally retry #2
- **AND** every attempt contains exactly one POST with identical query, start, end, step, source, authentication, and configuration

#### Scenario: Construct exact root and prefixed targets

- **GIVEN** accepted source paths of empty, `/`, `/prometheus`, `/monitoring/prometheus`, and their single-trailing-slash variants
- **WHEN** production acquisition constructs the request target
- **THEN** empty and `/` target `<validated origin>/api/v1/query_range`
- **AND** each non-root form targets `<validated origin><preserved normalized prefix>/api/v1/query_range`

#### Scenario: Reject an ambiguous path before request construction

- **GIVEN** a source path contains repeated `//`, an empty interior segment, `.` or `..` as a segment, a backslash, any percent-encoded byte, an encoded separator, an encoded dot segment, or another parser-dependent form
- **WHEN** that source is selected for production acquisition
- **THEN** acquisition returns `MetricSeriesAcquisitionFailure` before sending a request
- **AND** no path decoding, segment rewriting, or ambiguous normalization occurs

#### Scenario: Acquire a configured reference through the same operation

- **GIVEN** the pipeline supplies an equal-duration reference window derived from one offset
- **WHEN** the provider executes acquisition
- **THEN** it sends the exact supplied reference bounds through the same range-query contract
- **AND** the equal-duration current and reference requests use the same resolution

#### Scenario: Bound one hour to the accepted resolution

- **GIVEN** an exact 60-minute requested window
- **WHEN** step is calculated
- **THEN** `step=60` seconds is sent
- **AND** no more than 61 inclusive evaluation timestamps are requested

### Requirement: Map one float series into the provider-neutral sample contract

The provider SHALL accept only a JSON success envelope whose `data.resultType` is
`matrix` and whose `data.result` is an array. It SHALL set `limit=2` so zero, exactly
one, and more-than-one result series remain distinguishable without accepting an
unbounded result set. Zero series SHALL map to a successful available dataset with no
samples, allowing the existing pipeline to determine `insufficient`. More than one
series SHALL map to typed provider failure because one Metric Lens observes one metric
series.

For exactly one series, `metric` SHALL be a string-to-string label object and `values`
SHALL be an array of exactly two-element timestamp/value pairs. Every timestamp SHALL be
a finite Prometheus Unix-seconds number convertible to timezone-aware UTC. Every value
SHALL be a string convertible to a Python float; `NaN`, `+Inf`, and `-Inf` SHALL remain
non-finite provider-neutral samples for the existing deterministic preparation policy.
Labels SHALL be validated and discarded rather than crossing the port. Native
histogram samples, absent/invalid `values`, invalid labels, invalid pairs, invalid
timestamps, and non-numeric value strings SHALL produce typed provider failure.

The provider SHALL preserve returned sample order and values without aggregating,
deduplicating, clamping, interpolating, or filtering them. Existing provider-neutral
preparation SHALL continue to sort samples, reject duplicates and samples outside the
inclusive requested window, remove non-finite values, and assess quality.

#### Scenario: Map one valid float series

- **GIVEN** Prometheus returns one matrix series containing valid float sample pairs
- **WHEN** the provider maps the response
- **THEN** it returns the existing available outcome with UTC timestamp/value samples
- **AND** no label set or Prometheus response object crosses the provider boundary

#### Scenario: Preserve non-finite values for deterministic quality assessment

- **GIVEN** one returned float series contains `NaN`, `+Inf`, or `-Inf`
- **WHEN** the provider maps its values
- **THEN** those values remain provider-neutral non-finite samples
- **AND** the existing Metric preparer alone removes them and determines data quality

#### Scenario: Treat no series as successful empty acquisition

- **GIVEN** Prometheus successfully returns an empty matrix result
- **WHEN** the provider maps the response
- **THEN** it returns an available dataset with zero samples
- **AND** the existing pipeline may complete with insufficient data rather than a provider failure

#### Scenario: Reject a multi-series or histogram result

- **GIVEN** the query returns two result series or any native histogram sample
- **WHEN** the provider validates the response
- **THEN** it returns typed provider failure
- **AND** it does not merge series or derive a float from a histogram

### Requirement: Fail closed on warning annotations or excessive Prometheus responses

One HTTP response body SHALL be limited to 1 MiB. A declared body length over the cap
or a streamed body that crosses the cap SHALL produce typed provider failure without
returning a truncated or partial success, regardless of HTTP status. On a successful
HTTP status, a one-series result SHALL contain at most 61 float samples, and a sample
count over the cap, invalid JSON, invalid success envelope, or unknown required success
structure SHALL produce typed provider failure. A complete bounded malformed body on a
non-success status SHALL instead follow the ordered status precedence defined below.

On a Prometheus `status="success"` envelope, `warnings` and `infos`, when present, SHALL
each be an array containing only strings. A malformed annotation field SHALL make the
success envelope contract-invalid. As a conservative project/provider policy, a valid
non-empty `warnings` array on a successful data envelope SHALL produce typed provider
failure because the existing provider-neutral dataset cannot represent or qualify
warning annotations. This policy SHALL NOT assert or depend on every Prometheus warning
meaning partially collected data. A valid `infos` array on a successful response MAY be
counted only as bounded operational telemetry under the approved provider policy; its
text SHALL be discarded and SHALL NOT cross the provider port or enter Metric results.
Raw response bodies, provider error text, warnings, infos, label sets, and rejected
samples SHALL NOT be persisted or placed in diagnostics.

#### Scenario: Reject an oversized response without truncation

- **GIVEN** a response body exceeds 1 MiB or one series contains more than 61 samples
- **WHEN** the provider enforces its acquisition bounds
- **THEN** it returns typed provider failure
- **AND** it returns no truncated available dataset

#### Scenario: Reject a warning-annotated success response

- **GIVEN** a success envelope includes one or more Prometheus warnings and usable data
- **WHEN** the provider applies its warning-annotation policy
- **THEN** project policy returns typed provider failure because warnings cannot be represented or qualified by the provider-neutral contract
- **AND** warning text does not cross the provider boundary or enter a diagnostic

#### Scenario: Keep informational annotations operational

- **GIVEN** a valid complete success envelope includes Prometheus infos
- **WHEN** the provider maps the response
- **THEN** the available dataset is determined only from the valid result data
- **AND** info text is neither persisted nor exposed across the provider port

#### Scenario: Reject malformed successful annotations

- **GIVEN** a successful data envelope contains `warnings` or `infos` that is not an array of strings
- **WHEN** the provider validates the success contract
- **THEN** it returns `MetricSeriesAcquisitionFailure`
- **AND** malformed annotation content is neither retained nor exposed

### Requirement: Bound acquisition time and map failures through existing typed outcomes

Each HTTP attempt, including the complete response-body read, SHALL have a hard
monotonic 15-second **execution/result deadline**. One provider-port acquisition,
including every attempt, body read, and retry wait, SHALL have a hard monotonic
50-second **execution/result deadline**. Those deadlines bound the observable return of
`MetricSeriesProvider.acquire()`, not the physical lifetime of arbitrary transport
resource cleanup. Deadline expiry SHALL commit the acquisition to the existing typed
timeout outcome. That commitment is final: no late response, body, error, exception, or
cleanup completion SHALL produce or replace a provider outcome, begin a retry, begin a
new HTTP attempt, or mutate analytical, pipeline, Lens, runtime, or persistence state.

On deadline commitment, the provider SHALL signal cancellation and close to the active
transport operation, discard all late transport information, and return the typed timeout
without waiting indefinitely for cancellation-resistant cleanup. Transport resource
cleanup MAY continue after that return only as best-effort cleanup; it is not execution
or analytical work and SHALL have no outcome/state authority. The provider SHALL account
for active acquisitions and post-timeout cleanup in one finite private execution/resource
capacity. A cleanup task SHALL retain its capacity until it terminates, so
cancellation-resistant cleanup cannot accumulate without bound; when capacity is
exhausted, the provider SHALL fail a newly admitted acquisition before transport with the
existing typed acquisition-failure outcome and a fixed safe diagnostic. This private
capacity policy SHALL add no public configuration, reason code, or provider-port field.

The provider SHALL retry an eligible failed read-only range request at most twice after
the initial attempt, stopping on success, a non-retryable outcome, retry exhaustion, or
insufficient remaining acquisition budget. It SHALL retry only `httpx.ConnectError` and
HTTP `429`, `500`, `502`, or `504`.
It SHALL wait exactly 0.5 seconds before retry one and 1.0 second before retry two, with
no jitter and no provider-directed delay. A retry SHALL begin only when its complete
wait and a new 15-second attempt fit inside the acquisition deadline.

When a retry would otherwise be eligible but the remaining hard acquisition budget is
insufficient for the selected retry wait plus one complete hard-bounded 15-second next
attempt, the provider SHALL return `MetricSeriesAcquisitionTimeout`. It SHALL perform no
retry wait and issue no additional HTTP attempt. This admission rule SHALL apply
identically after `httpx.ConnectError` and after HTTP `429`, `500`, `502`, or `504`.
It is distinct from retry exhaustion: budget rejection before an eligible next attempt
is timeout, while persistence of an eligible retry condition through the final allowed
attempt after all admitted attempts were actually executed is
`MetricSeriesAcquisitionFailure`.

For every attempt, classification SHALL follow this ordered decision table; a later
rule SHALL NOT override an earlier applicable rule:

1. Hard local attempt or acquisition deadline exhaustion SHALL commit and return
   `MetricSeriesAcquisitionTimeout`. This rule takes precedence over every HTTPX
   exception observed at the same boundary. It signals cancellation/close, discards late
   transport information, and prevents every later retry, HTTP attempt, or provider-state
   transition; best-effort cleanup has no authority to alter that committed outcome.
2. An HTTPX exception raised during request or body acquisition SHALL be classified in
   this exact subclass order:
   - any `httpx.TimeoutException`, including `ConnectTimeout`, `ReadTimeout`,
     `WriteTimeout`, and `PoolTimeout`, SHALL return
     `MetricSeriesAcquisitionTimeout` without retry;
   - `httpx.ConnectError` SHALL enter the approved retry path, and exhaustion SHALL
     return `MetricSeriesAcquisitionFailure`; an otherwise eligible retry rejected by
     the remaining-budget admission rule SHALL instead return
     `MetricSeriesAcquisitionTimeout` without waiting or attempting again;
   - any other `httpx.TransportError`, including `ReadError`, `WriteError`,
     `CloseError`, `RemoteProtocolError`, `LocalProtocolError`, `ProxyError`, and
     `UnsupportedProtocol`, SHALL return `MetricSeriesAcquisitionFailure` without
     retry;
   - any HTTPX request/client error outside `TransportError`, including
     `DecodingError`, `TooManyRedirects`, `InvalidURL`, and `StreamError`, SHALL return
     `MetricSeriesAcquisitionFailure` without retry.
3. Response-body acquisition without an HTTPX exception SHALL enforce the 1 MiB bound
   and hard deadline. A hard deadline while reading SHALL return
   `MetricSeriesAcquisitionTimeout`; an oversized or otherwise deterministically
   unusable body SHALL return `MetricSeriesAcquisitionFailure` without status-based
   retry.
4. After a complete bounded body is available, the provider SHALL first determine
   whether it is a valid Prometheus error envelope. A valid error envelope SHALL be a
   JSON object containing exact `status="error"`, a non-empty string `errorType`, and a
   non-empty string `error`. It MAY also contain `data`. When `warnings` or `infos` is
   present, that field SHALL be an array containing only strings; a malformed optional
   annotation field SHALL make the error envelope invalid. A body containing only
   `errorType`, or missing/malformed any required field, SHALL NOT prove Prometheus
   timeout or cancellation. Classification SHALL then proceed in this order:
   - a valid error envelope with exact `errorType="timeout"` or
     `errorType="canceled"` SHALL return `MetricSeriesAcquisitionTimeout`; valid
     warnings or infos on that envelope SHALL not override this classification;
   - HTTP `429`, `500`, `502`, or `504` SHALL enter the approved retry path unless a
     higher-precedence rule already applied, including when the complete bounded body
     is malformed or is a valid error envelope with another `errorType`; an otherwise
     eligible retry rejected by the remaining-budget admission rule SHALL return
     `MetricSeriesAcquisitionTimeout` without waiting or attempting again;
   - a valid error envelope with any other `errorType` SHALL return
     `MetricSeriesAcquisitionFailure`;
   - HTTP `503` without a valid timeout/canceled error envelope SHALL return
     `MetricSeriesAcquisitionFailure` and SHALL NOT be classified as timeout merely
     from its status code;
   - every other non-success HTTP status SHALL return
     `MetricSeriesAcquisitionFailure`.
5. A successful HTTP response SHALL require the approved Prometheus success
   envelope/result contract. A malformed or contract-invalid success envelope SHALL
   return `MetricSeriesAcquisitionFailure`. Only a successful data envelope applies the
   conservative non-empty-warning failure policy; infos on a valid successful response
   remain informational and are discarded.

A complete bounded but malformed body received with HTTP `429`, `500`, `502`, or `504`
SHALL follow the status retry rule because the higher-precedence deadline, transport,
and body-bound rules did not apply. The same malformed body with HTTP `503` or another
non-success status SHALL be failure without retry; with a successful HTTP status it
SHALL be a success-contract failure. Missing source configuration SHALL return typed
unavailable before this HTTP decision table is entered.

Provider diagnostics SHALL use only a fixed bounded category and, where useful, an HTTP
status code. They SHALL NOT contain the base URL, PromQL, response/provider error text,
headers, Bearer token, Basic password, Authorization header, configured Basic username,
exception text, stack trace, body content, label values, or sample values. Existing
pipeline semantics SHALL remain unchanged: any non-available current
outcome produces the accepted current-acquisition failed result, while a non-available
reference outcome omits only that comparison and contributes
`reference_unavailable/reference_periods` when current data is usable.

#### Scenario: Retry an eligible attempt outcome within the hard budget

- **GIVEN** `httpx.ConnectError` or a retryable HTTP status occurs and the complete wait plus attempt fits
- **WHEN** the provider applies resilience policy
- **THEN** it performs no more than two retries using exact waits of 0.5 and 1.0 seconds
- **AND** the same query, bounds, step, timeout, and limit are used on every attempt

#### Scenario: Reject a retry that cannot fit the remaining acquisition budget

- **GIVEN** `httpx.ConnectError` or HTTP `429`, `500`, `502`, or `504` makes a retry otherwise eligible but the selected wait plus one complete 15-second attempt does not fit the remaining acquisition budget
- **WHEN** retry admission is evaluated
- **THEN** the acquisition returns `MetricSeriesAcquisitionTimeout`
- **AND** it performs no retry wait and issues no additional HTTP attempt

#### Scenario: Admit a retry that fits the remaining acquisition budget

- **GIVEN** an eligible retry's selected wait plus one complete 15-second attempt fits the remaining acquisition budget
- **WHEN** retry admission is evaluated
- **THEN** the provider performs the selected fixed wait and issues the next HTTP attempt
- **AND** that attempt preserves the identical logical request

#### Scenario: Complete on the initial attempt

- **GIVEN** the initial HTTP attempt returns a valid successful response
- **WHEN** one acquisition completes
- **THEN** it performs exactly one HTTP attempt and one POST
- **AND** it performs no retry

#### Scenario: Complete on retry one

- **GIVEN** the initial attempt has an eligible retry outcome and retry #1 succeeds within budget
- **WHEN** one acquisition completes
- **THEN** it performs exactly two HTTP attempts and two POSTs
- **AND** both attempts use the identical logical request

#### Scenario: Complete on retry two

- **GIVEN** the initial attempt and retry #1 have eligible retry outcomes and retry #2 succeeds within budget
- **WHEN** one acquisition completes
- **THEN** it performs exactly three HTTP attempts and three POSTs
- **AND** all attempts use the identical logical request

#### Scenario: Exhaust all HTTP attempts

- **GIVEN** the initial attempt, retry #1, and retry #2 each have an eligible retry outcome and both retries fit the budget
- **WHEN** one acquisition exhausts its retry policy
- **THEN** it performs exactly three HTTP attempts and three POSTs
- **AND** it returns `MetricSeriesAcquisitionFailure` without a fourth attempt

#### Scenario: Map the HTTPX exception hierarchy deterministically

- **GIVEN** an HTTP attempt raises `ConnectError`, `ConnectTimeout`, `ReadTimeout`, `ReadError`, `WriteError`, `RemoteProtocolError`, or `DecodingError`
- **WHEN** the provider applies the ordered exception taxonomy
- **THEN** only `ConnectError` enters the retry path, both timeout subclasses return timeout without retry, and every listed remaining exception returns failure without retry
- **AND** no exception is classified through a generic retryable-transport rule

#### Scenario: Do not retry a deterministic provider rejection

- **GIVEN** Prometheus returns authentication, authorization, query, response-contract, warning, or bare HTTP 503 failure
- **WHEN** the provider maps the response
- **THEN** it performs no retry
- **AND** it returns a typed failure with a fixed secret-safe diagnostic

#### Scenario: Map a proven timeout without extending the acquisition budget

- **GIVEN** an attempt/acquisition deadline or a valid Prometheus timeout/canceled error envelope occurs
- **WHEN** acquisition terminates
- **THEN** it returns the existing typed timeout outcome
- **AND** no provider execution, retry wait, HTTP attempt, late transport outcome, or
  provider/pipeline/Lens/runtime state transition continues past the 50-second hard
  deadline; best-effort transport resource cleanup may continue only without outcome or
  state authority and within the provider's finite private capacity

#### Scenario: Bound post-timeout transport cleanup

- **GIVEN** a hard attempt or acquisition deadline commits an acquisition to timeout and
  its cancellation-resistant transport cleanup does not terminate immediately
- **WHEN** `MetricSeriesProvider.acquire()` returns its committed timeout
- **THEN** no late transport response, body, error, exception, retry, HTTP attempt, or
  provider/pipeline/Lens/runtime state transition can alter that result or begin
- **AND** cleanup may continue only as state-inert best-effort resource cleanup while it
  holds finite private execution/resource capacity
- **AND** capacity exhaustion rejects a newly admitted acquisition before transport with
  the existing typed acquisition-failure outcome and a fixed safe diagnostic

#### Scenario: Require a strict timeout or canceled error envelope

- **GIVEN** a complete bounded response contains a valid error envelope with exact `errorType="timeout"` or `errorType="canceled"`
- **WHEN** response classification executes
- **THEN** the provider returns `MetricSeriesAcquisitionTimeout`
- **AND** optional valid warnings or infos do not override that classification

#### Scenario: Reject an invalid error envelope as timeout proof

- **GIVEN** a purported error envelope is missing `status`, missing `errorType`, has a missing or empty `error`, contains only `errorType`, or has malformed `warnings` or `infos`
- **WHEN** response classification executes
- **THEN** it does not prove Prometheus timeout or cancellation
- **AND** the existing HTTP-status and successful-contract precedence determines the outcome

#### Scenario: Do not infer timeout from a bare HTTP 503

- **GIVEN** a complete bounded HTTP 503 response has no valid Prometheus timeout/canceled error envelope
- **WHEN** the ordered classification table is applied
- **THEN** the provider returns `MetricSeriesAcquisitionFailure` without retry
- **AND** it does not infer timeout from the status code alone

#### Scenario: Let body-bound failure precede retriable status

- **GIVEN** an HTTP `429`, `500`, `502`, or `504` response body exceeds 1 MiB
- **WHEN** response-body acquisition applies the ordered classification table
- **THEN** the provider returns `MetricSeriesAcquisitionFailure` without retry
- **AND** status-based retry does not override the earlier body-bound failure

#### Scenario: Classify a complete malformed body by status before success validation

- **GIVEN** a complete bounded malformed body is returned with a retriable, HTTP 503, other non-success, or successful status
- **WHEN** the ordered classification table is applied
- **THEN** a retriable status enters its approved retry path, while HTTP 503 and other non-success statuses fail without retry
- **AND** only a successful status reaches success-envelope validation and fails there

#### Scenario: Preserve current and reference failure semantics

- **GIVEN** the composed provider returns the same typed failure for a current request and one reference request
- **WHEN** each flows through the existing Metrics pipeline
- **THEN** the current path produces the accepted minimal failed Metric result
- **AND** the reference path preserves usable current analysis as partial with the accepted reference reason

### Requirement: Compose and verify the provider behind the existing Metric port

Application composition SHALL construct one source-aware Prometheus provider from the
server-managed registry and inject it only through the existing `MetricSeriesProvider`
port. Source selection, HTTP transport, authentication, response decoding, retry, and
deadlines SHALL remain in infrastructure. The Metric domain and pipeline SHALL not
import HTTP client or Prometheus transport types, and the provider SHALL not create or
advance LensRun or ObservationRun state.

Provider verification SHALL use injected/mock HTTP transport, monotonic clock, sleeper,
and cancellation-observable response bodies. It SHALL cover configuration and secret
safety, exact current/reference requests, response mapping and limits, typed failure and
timeout mapping, retry admission, resource cleanup, composition, and at least one
existing-pipeline current/reference integration path. No live Prometheus server,
credential, or network call SHALL be required by automated tests.

#### Scenario: Inject the real provider without domain coupling

- **GIVEN** application composition has a valid source registry
- **WHEN** a Metrics pipeline is constructed for execution
- **THEN** the production provider satisfies the unchanged framework-neutral port
- **AND** Metric domain modules contain no HTTP client, settings, or Prometheus response types

#### Scenario: Verify provider integration without live credentials

- **WHEN** automated provider-focused verification runs
- **THEN** deterministic test doubles exercise request, mapping, resilience, and pipeline boundaries
- **AND** no live Prometheus endpoint or repository secret is required
