## Purpose

Provide a bounded Jira Cloud Alert acquisition integration that supplies the existing
provider-neutral Alert pipeline with canonical-mappable records for current and
configured-reference windows without exposing Jira transport or credentials to it.

## ADDED Requirements

### Requirement: Configure one ordinary-user Jira Cloud bot integration without repository secrets

The system SHALL support one optional server-side Jira Cloud source configuration for
the accepted `jira_track_and_release` Alert source. Global application settings SHALL
retain the optional serialized Jira provider configuration as raw provider-owned input;
the Jira composition boundary SHALL parse and validate it separately. Jira
configuration absence or any Jira-specific parse/validation error SHALL NOT make global
Settings construction fail, prevent application startup, or impair unrelated
functionality. The composition boundary SHALL construct the real provider only from a
valid complete configuration and SHALL otherwise construct/report an unavailable
provider with a fixed safe `not_configured` or `configuration_invalid` diagnostic
category.

A valid configuration SHALL contain a credential-safe Jira Cloud site URL, the
non-empty email of a dedicated ordinary Atlassian user account used operationally as a
bot, and that account's non-empty classic/unscoped API token. The account SHALL NOT be
described or configured as an official Atlassian Service Account. The email and token
SHALL be secret values read only from deployment/local environment configuration; they
SHALL NOT be persisted in an Observation definition, a LensRun, an Alert result, a log
diagnostic, an API response, `.env.example`, or any committed repository file. A
configuration diagnostic SHALL NOT contain the raw serialized configuration, API token,
Basic authentication value, or provider validation/exception text that could reproduce
secret input.

The configured Jira site URL SHALL satisfy all of these rules:

- scheme is exactly HTTPS;
- hostname is exactly `<site>.atlassian.net`, where `<site>` is one non-empty ASCII DNS
  label of 1..63 characters, begins and ends with an alphanumeric character, and
  otherwise contains only alphanumeric characters or `-`;
- userinfo and explicit ports are absent;
- query and fragment are absent;
- path is exactly empty, `/`, `/jira`, or `/jira/`;
- an IP-address host, non-Atlassian host, additional hostname label, or any other path is
  invalid.

After validation, the provider SHALL derive one canonical Jira Cloud site origin exactly
`https://<site>.atlassian.net`, with no path or trailing slash, regardless of whether
the accepted input path was root or `/jira`. It SHALL use that origin independently as
the base for both REST targets and issue-navigation `source_ref` values. The
operator-supplied `/jira` path SHALL NOT be part of either canonical base and SHALL NOT
be preserved in any derived URL.

The provider SHALL normalize only accepted trailing-slash variants before deriving the
canonical origin. Custom Jira domains, Atlassian Government domains, arbitrary
reverse-proxy paths, and non-Atlassian hosts SHALL NOT be supported.

The configuration contract SHALL be limited to site-specific Jira Cloud Basic
authentication by the dedicated ordinary user account and its classic/unscoped API
token. Scoped API tokens, official Atlassian Service Accounts,
`api.atlassian.com/ex/jira/{cloudId}` routing, Cloud ID discovery, OAuth 2.0,
Jira Server/Data Center, Jira Service Management/Operations (including Opsgenie) Alert
APIs, Connect, and Forge authentication SHALL NOT be supported by this change. Scoped
tokens and official Service Accounts require the Atlassian API gateway and would add a
different trusted target, Cloud ID, scopes, and credential lifecycle. After site URL
validation succeeds, the provider SHALL authenticate with
`Authorization: Basic <base64(UTF-8(email + ":" + api-token))>` and SHALL NOT put
credentials in the URL or wait for an authentication challenge. Authenticated requests
SHALL NOT follow redirects. Because token strings do not identify whether they are
scoped, supplying a classic/unscoped token from an ordinary account is a deployment
precondition rather than a provider introspection capability.

As a deployment precondition, the dedicated ordinary user account MUST have Browse
Projects permission and every applicable issue-level-security permission needed to see
the complete issue population selected by every configured Alert Lens. Jira MAY
silently omit issues that the account cannot view, so insufficient permissions can
otherwise appear to the system as a valid empty or incomplete acquisition rather than
an authentication or authorization error.

#### Scenario: Keep a configured token secret

- **WHEN** the application receives a Jira Cloud API token through local or deployment
  configuration
- **THEN** it uses the token only for server-to-Jira authentication
- **AND** no committed example, runtime artifact, public API response, or diagnostic
  contains the token

#### Scenario: Preserve an unconfigured local environment

- **GIVEN** no Jira source configuration is supplied
- **WHEN** an Alert provider is requested for a Jira Alert Lens
- **THEN** the injected provider reports an unavailable acquisition outcome
- **AND** application startup and non-Alert functionality remain usable

#### Scenario: Tolerate malformed optional Jira configuration

- **GIVEN** serialized Jira configuration is malformed, has an invalid base URL, or is
  missing its email or API token
- **WHEN** global application settings and provider composition are created
- **THEN** application startup and unrelated functionality remain usable
- **AND** Jira provider composition produces a safe `configuration_invalid`
  unavailable provider without exposing configuration or authentication material

#### Scenario: Compose a valid Jira provider

- **GIVEN** a valid accepted Jira Cloud site URL, dedicated ordinary account email, and
  classic/unscoped API token
- **WHEN** Jira provider composition validates the raw optional configuration
- **THEN** it constructs the real Jira Alert provider
- **AND** it derives the same canonical site origin for REST and navigation from either
  root or `/jira` input

#### Scenario: Exclude gateway-based account and token models

- **GIVEN** a deployment has only a scoped token or official Atlassian Service Account
- **WHEN** the Jira provider configuration is prepared
- **THEN** that credential model is unsupported by this capability
- **AND** the provider performs no Cloud ID discovery or `api.atlassian.com` request

#### Scenario: Reject an unsafe Jira target

- **GIVEN** Jira configuration contains HTTP, userinfo, an explicit port, query,
  fragment, IP address, non-Atlassian host, invalid site label, or unsupported path
- **WHEN** Jira provider composition validates the configuration
- **THEN** it produces a safe `configuration_invalid` unavailable provider
- **AND** it sends no authentication material to the configured target

#### Scenario: Require complete selector-scope visibility

- **GIVEN** a dedicated ordinary Atlassian user account is configured for Alert acquisition
- **WHEN** the deployment is prepared for an Alert Lens selector
- **THEN** the account has Browse Projects and applicable issue-level-security access
  for the complete selector scope
- **AND** operator documentation warns that Jira can silently omit inaccessible issues

### Requirement: Query Jira Cloud issues through the verified enhanced JQL search surface

For each immutable acquisition window, the system SHALL call Jira Cloud REST API v2
enhanced search at the fixed site-specific path `/rest/api/2/search/jql`, basic
authentication, JSON request body, and only the fields required for canonical mapping:
`summary`, `created`, `resolutiondate`, `status`, and `priority`. REST API v2 is the
approved provider version for this capability. The provider SHALL construct the target
from the canonical site-root REST origin, never from the accepted input/navigation
`/jira` path. Both accepted input forms SHALL produce the same target:

```text
configured https://foo.atlassian.net
-> REST origin https://foo.atlassian.net
-> target https://foo.atlassian.net/rest/api/2/search/jql

configured https://foo.atlassian.net/jira
-> REST origin https://foo.atlassian.net
-> target https://foo.atlassian.net/rest/api/2/search/jql
```

The provider SHALL NOT target
`https://foo.atlassian.net/jira/rest/api/2/search/jql`.

The provider SHALL use the provider-native selector unchanged as the scope expression
and SHALL add only the application-owned lifecycle time predicate:

```text
(<selector>) AND created < <window-end-epoch-milliseconds>
AND (resolved IS EMPTY OR resolved > <window-start-epoch-milliseconds>)
```

The numeric timestamp operands SHALL be UTC Unix epoch milliseconds. The adapter SHALL
calculate the start operand by flooring `window.start` to an epoch-millisecond integer
and the end operand by ceiling `window.end` to an epoch-millisecond integer. These
bounds SHALL make the provider query a safe candidate superset for sub-millisecond
windows. The adapter SHALL not add a lifecycle-status predicate, modify selector terms,
infer a different scope, or issue any provider query requested by an agent or optional
tool. A selector that cannot be used as a parenthesized JQL predicate (for example, one
containing a trailing `ORDER BY` clause) SHALL receive Jira's query-error treatment;
this change SHALL not parse, repair, or rewrite it.

The same construction SHALL be used for current and pipeline-derived same-duration
reference windows. The adapter SHALL additionally preserve the exact canonical
lifecycle-overlap rule after receiving Jira data; provider-side time filtering SHALL
never replace application-owned validation.

#### Scenario: Acquire an alert spanning the start boundary

- **GIVEN** a configured selector and a Jira issue created before a window ends whose
  resolution date is after the window begins
- **WHEN** the provider acquires that window
- **THEN** its request includes the lifecycle-overlap predicate without a status filter
- **AND** the mapped record remains available for the pipeline's canonical overlap check

#### Scenario: Remove the accepted browser path from the REST target

- **GIVEN** the configured Jira site URL is `https://foo.atlassian.net/jira`
- **WHEN** the provider executes enhanced search
- **THEN** the exact REST target is
  `https://foo.atlassian.net/rest/api/2/search/jql`
- **AND** it does not target `https://foo.atlassian.net/jira/rest/api/2/search/jql`

#### Scenario: Do not follow a cross-host redirect

- **GIVEN** the trusted site-specific REST target returns a redirect to another host
- **WHEN** the authenticated provider receives the response
- **THEN** it does not follow the redirect or forward credentials
- **AND** it returns a non-timeout provider failure through the existing mapping

#### Scenario: Treat a selector sort clause as a provider query error

- **GIVEN** a stored opaque selector that is not a parenthesizable JQL predicate
- **WHEN** Jira rejects the composed search expression
- **THEN** current acquisition is reported as provider failure
- **AND** reference acquisition is reported as unavailable without altering the selector

#### Scenario: Preserve overlap candidates at sub-millisecond bounds

- **GIVEN** an acquisition window whose start or end is between two epoch-millisecond
  instants
- **WHEN** the provider constructs the lifecycle JQL
- **THEN** it floors the start operand and ceils the end operand
- **AND** records admitted only by the wider candidate bounds are retained or rejected
  by the existing application-owned exact lifecycle-overlap filter after mapping

#### Scenario: Treat enhanced-search staleness as a provider limitation

- **GIVEN** Jira enhanced search returns a successful but temporarily stale or missing
  view of a recent issue creation or resolution change
- **WHEN** the provider completes the acquisition
- **THEN** it treats the returned issue population as a successful provider response
- **AND** eventual consistency creates no provider error, partial-result reason, or
  retry beyond the normal retry contract

The provider SHALL NOT send `reconcileIssues`. An Alert Lens begins with a JQL-defined
population and does not possess a complete known issue-ID set that could identify
potentially missing issues for reconciliation.

### Requirement: Exhaust cursor pages within a bounded provider volume

The provider SHALL request pages of at most 100 issues and SHALL require each successful
page envelope to contain a boolean `isLast`. When `isLast=false`, the page SHALL contain
a non-empty `nextPageToken` that has not appeared in any earlier page of the same
acquisition, and the provider SHALL request the next page with that token. When
`isLast=true`, pagination SHALL terminate and the page SHALL NOT contain a non-empty
continuation token. A missing or repeated token on a non-terminal page, a continuation
token on a terminal page, a missing or non-boolean `isLast`, or any other inconsistent
pagination envelope SHALL return a typed provider failure.

The provider SHALL accumulate at most 1,000 issues for one current or reference
acquisition. Exactly 1,000 issues on a terminal page SHALL be a successful bounded
result. A page that would raise the accumulated count above 1,000, or a non-terminal
page after the 1,000th accumulated issue, SHALL return a typed provider failure. The
provider SHALL NOT return a truncated successful record set.

#### Scenario: Follow cursor pagination

- **GIVEN** Jira returns a non-empty `nextPageToken` with the first search page
- **WHEN** the provider acquires the window
- **THEN** it requests the next page with that token and the same composed JQL and fields
- **AND** it returns records from all pages before the terminal page within the cap

#### Scenario: Reject an inconsistent non-terminal page

- **GIVEN** Jira returns `isLast=false` without a non-empty new continuation token
- **WHEN** the provider validates the pagination envelope
- **THEN** it returns a typed provider failure
- **AND** it returns no truncated successful record set

#### Scenario: Reject unbounded result volume

- **GIVEN** Jira indicates more than 1,000 matching issues for one acquisition
- **WHEN** the provider reaches the configured cap
- **THEN** it returns a typed provider failure rather than a partial successful set
- **AND** the Alert pipeline applies its existing current/reference failure semantics

### Requirement: Map Jira issue lifecycle fields faithfully to provider-neutral records

For every successfully decoded Jira issue, the provider SHALL map `key` to canonical
record ID, `fields.summary` to title, `fields.created` to `started_at`,
`fields.resolutiondate` to nullable `ended_at`, `fields.status.name` to source status,
and `fields.priority.name` to optional provider importance with exact type `priority`.
It SHALL construct optional `source_ref` independently from the canonical site origin
as `https://<site>.atlassian.net/browse/<encoded-key>`. The issue key SHALL be UTF-8
encoded as one URI path segment using the existing strict percent-encoding rule: only
RFC 3986 unreserved bytes remain literal and every other byte uses uppercase `%HH`.
Both root and `/jira` configuration inputs SHALL produce the same `source_ref`; `/jira`
SHALL NOT appear in it. It SHALL omit description and occurrence count because the
selected Jira issue-search surface supplies no provider-native occurrence value and
Jira rich text descriptions are not required by the accepted canonical record contract.

Using Jira issue `created` and REST `fields.resolutiondate` as `started_at` and
`ended_at` SHALL be the approved MVP provider interpretation for this adapter; Atlassian
does not define Jira issues as the system's Alert model. Missing, malformed, or
non-object individual issue fields, including a missing or unusable `key`, SHALL be
preserved as individual minimal canonical-mappable raw/provider records with the
corresponding canonical field missing or invalid. The adapter SHALL NOT include the full
Jira payload in those records. Existing application-owned normalization SHALL reject
each malformed record through `invalid_records`, preserving any usable records in the
same acquisition. A malformed individual issue SHALL NOT by itself cause typed provider
acquisition failure. Provider failure SHALL be reserved for response-envelope,
transport, authentication/authorization, query, pagination, volume, or other
acquisition-level failures.

The provider SHALL preserve Jira's latest returned resolution date for reference
windows and SHALL not reconstruct historical Jira state.

#### Scenario: Preserve native status and priority

- **GIVEN** a Jira issue with status name `In Progress` and priority name `Highest`
- **WHEN** the provider maps the search response
- **THEN** the record retains `In Progress` as source status and `{type: priority,
  value: Highest}` as provider importance
- **AND** it does not map either value to a global severity vocabulary

#### Scenario: Use the latest resolution information for a reference issue

- **GIVEN** an issue overlaps a configured reference window and was resolved after that
  window
- **WHEN** the provider maps the latest Jira search response
- **THEN** the record carries the returned later resolution timestamp
- **AND** the pipeline can use the accepted full-lifecycle duration semantics

#### Scenario: Preserve a malformed issue for normalization

- **GIVEN** a successful Jira page contains one usable issue and one issue without a
  usable key or another required canonical field
- **WHEN** the provider maps the page
- **THEN** it returns the usable record and a minimal malformed individual record
- **AND** existing normalization rejects only the malformed record through
  `invalid_records`

#### Scenario: Construct the same canonical source reference from every accepted input path

- **GIVEN** equivalent configurations using `https://foo.atlassian.net` and
  `https://foo.atlassian.net/jira` and an issue key requiring strict segment encoding
- **WHEN** the provider maps that issue from either configuration
- **THEN** both records use
  `https://foo.atlassian.net/browse/<percent-encoded-issue-key>` as `source_ref`
- **AND** neither source reference contains `/jira/`

### Requirement: Map Jira failures, deadlines, and retriable responses consistently

One `acquire()` call SHALL have a hard 60-second wall-clock deadline measured with a
monotonic clock. Every complete HTTP attempt SHALL have its own hard 15-second
monotonic deadline. The hard attempt deadline SHALL cover connection/pool wait, request
write, response headers, and complete response-body read. The hard acquire deadline
SHALL cover all pages, complete attempts, retry waits, and response-body reads. HTTPX
connect/read/write/pool phase timeouts MAY provide defense in depth but SHALL NOT be the
normative owner or substitute for either hard deadline; in particular, HTTPX read
timeouts measure inactivity between chunks rather than total attempt duration.

The provider SHALL make an in-flight request/body-read operation interruptible or
cancellable when either remaining hard deadline expires, without prescribing a
specific Python cancellation primitive. Before starting any first or retry attempt, at
least 15 seconds SHALL remain in the hard acquire deadline; otherwise acquisition SHALL
return the typed timeout outcome without starting that attempt.

For each failed page request, the provider SHALL retry at most twice after its initial
attempt and only for connection failures, HTTP 502, 503, 504, or HTTP 429. A usable
`Retry-After` delay SHALL consist of exactly one header field value. The provider SHALL
strip only optional surrounding ASCII space (`SP`) and horizontal tab (`HTAB`); the
remaining content SHALL match `^[0-9]+$`, parse as a base-10 integer, and be strictly
greater than zero. Thus `1`, `15`, ` 5 `, and `005` are syntactically usable, while an
empty value, `0`, `+5`, `-1`, `1.5`, an HTTP-date, other non-decimal content, a
comma-separated/combined value, or duplicate header fields is unusable.

For a 429 or retryable 5xx response with a usable `Retry-After`, the provider SHALL use
the parsed integer as the exact wait when it is at most 15 seconds. A usable value above
15 seconds SHALL immediately return the typed timeout outcome. A missing or
syntactically unusable `Retry-After`, and any retriable connection failure, SHALL use
the exact fallback wait of 0.5 seconds before retry #1 or 1.0 second before retry #2;
no jitter SHALL be applied. A retry SHALL start only when the selected complete wait
plus a subsequent hard 15-second attempt fits within the remaining hard acquire
deadline; otherwise acquisition SHALL return the typed timeout outcome without waiting
or starting the retry.

The provider SHALL not retry hard attempt-deadline expiration, HTTP 400, 401, 403, 404,
another non-retriable response, malformed JSON, malformed expected response shape,
pagination inconsistency, volume violation, cross-host redirect, or an
acquisition-level mapping error. Hard attempt-deadline expiration, a usable
`Retry-After` above 15 seconds, or hard acquire-deadline exhaustion SHALL return the
existing typed timeout outcome. Exhausted retryable connection or HTTP failures while
time remains, and every other non-timeout transport, authentication, authorization,
query, rate, decode, response-envelope, pagination, volume, redirect, or configuration
failure SHALL return the existing typed provider failure/unavailable outcome without
provider body or credential text in its diagnostic. Malformed individual issues remain
record-level normalization input rather than acquisition failures.

The existing pipeline SHALL continue to map current timeout to
`current_query_timeout`, current non-timeout failure to `current_query_failed`, and a
reference failure/timeout to partial `reference_unavailable` when current analysis is
usable.

#### Scenario: Respect Jira rate limiting

- **GIVEN** Jira returns HTTP 429 with `Retry-After: 3`
- **WHEN** the retry budget remains
- **THEN** the provider waits exactly three seconds before the retry
- **AND** it does not expose the response body as a pipeline diagnostic

#### Scenario: Apply exact fallback retry waits

- **GIVEN** retry #1 or retry #2 is admitted after a retriable failure without a usable
  `Retry-After`
- **WHEN** the provider waits before the retry
- **THEN** it waits exactly 0.5 seconds for retry #1 or exactly 1.0 second for retry #2
- **AND** it uses that exact wait for remaining-deadline admission

#### Scenario: Parse Retry-After with the exact grammar

- **GIVEN** a retriable response supplies exactly one `Retry-After` value
- **WHEN** surrounding ASCII SP/HTAB is stripped and the remainder is a positive
  decimal integer such as `005`
- **THEN** the provider parses it as base-10 integer `5` and uses exactly five seconds
  subject to the deadline and 15-second maximum
- **AND** an empty, zero, signed, fractional, combined, duplicate, HTTP-date, or other
  non-decimal value instead uses the deterministic fallback wait

#### Scenario: Reject an excessive Retry-After within the typed timeout path

- **GIVEN** Jira returns a retryable response with `Retry-After: 16`
- **WHEN** the provider evaluates the retry
- **THEN** it returns the typed timeout outcome without waiting or retrying
- **AND** the existing Alert pipeline applies its current or reference timeout mapping

#### Scenario: Refuse a retry that cannot fit the total deadline

- **GIVEN** a retryable response and less remaining acquire time than its complete wait
  plus one 15-second attempt
- **WHEN** the provider evaluates the retry
- **THEN** it returns the typed timeout outcome without waiting or starting the retry
- **AND** the acquisition completes within its 60-second total deadline

#### Scenario: Interrupt a slow-progress response at the hard attempt deadline

- **GIVEN** a Jira response continues yielding body chunks often enough to avoid an
  HTTPX read-inactivity timeout
- **WHEN** the complete attempt reaches 15 seconds
- **THEN** the provider interrupts/cancels the in-flight request and body read
- **AND** it returns the typed timeout outcome

#### Scenario: Exhaust the hard acquire deadline across pages and retries

- **GIVEN** successful and retryable page activity cumulatively reaches the 60-second
  hard acquire deadline
- **WHEN** an attempt, body read, or retry wait is still in progress
- **THEN** the provider interrupts/cancels the in-flight operation and returns the typed
  timeout outcome
- **AND** no additional page or retry attempt starts

#### Scenario: Preserve a current deadline distinction

- **GIVEN** every attempt for a current Jira search reaches the request deadline
- **WHEN** provider acquisition terminates
- **THEN** it returns the typed timeout outcome
- **AND** the existing Alert pipeline makes the LensRun fail as `current_query_timeout`

#### Scenario: Degrade only an unavailable reference

- **GIVEN** current Jira acquisition succeeds and one configured reference request
  exhausts retryable failures
- **WHEN** reference processing completes
- **THEN** that offset supplies no comparison
- **AND** the existing Alert pipeline retains usable current analysis as partial
  `reference_unavailable`

### Requirement: Compose the real provider only behind the existing AlertProvider boundary

The application SHALL resolve the Jira provider only for the accepted
`jira_track_and_release` source and inject it through the existing `AlertProvider`
boundary. The provider SHALL receive only immutable source scope and window values and
return only existing typed acquisition outcomes. It SHALL NOT change AlertAnalysisResult,
deterministic analysis, normalization ownership, optional tools, the Alert Analysis
Agent, Observation orchestration, LensRun creation, or terminal persistence semantics.

Provider-focused verification SHALL use deterministic configuration and mocked Jira
HTTP responses to cover authentication headers, exact request construction, current
and reference windows, multipage success, the cap, field mapping, failures, timeouts,
retries, and secret redaction. It SHALL NOT require a live Jira tenant or credentials.

#### Scenario: Keep the pipeline provider-neutral

- **GIVEN** the Jira provider is injected into an existing Alert pipeline invocation
- **WHEN** it returns canonical-mappable records for current and reference windows
- **THEN** the pipeline follows its existing normalization, deterministic-analysis,
  partial-result, and persistence behavior
- **AND** no Jira object, raw payload, credential, or transport detail reaches the
  agent or AlertAnalysisResult
