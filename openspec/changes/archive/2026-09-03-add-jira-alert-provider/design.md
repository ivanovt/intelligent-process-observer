## Context

See [proposal.md](proposal.md) for motivation and the delta specifications for the
behavior contract. The completed Alerts Analysis Pipeline has a framework-neutral
`AlertProvider.acquire(scope, window)` port, application-owned lifecycle validation,
and no production composition point for Jira. Its only accepted provider identifier is
`jira_track_and_release`; the definition's opaque selector contains the provider-native
query, while the LensRun owns current/reference time scope.

This change resolves the deferred provider decisions as a deliberately narrow **Jira
Cloud issue-search** integration. It does not select Jira Service Management Operations
or the separate Opsgenie alert API. Atlassian's current official documentation verifies
that v2 and v3 expose the same operation collection, including enhanced JQL search, and
that v3's material addition is Atlassian Document Format support. This provider does not
request description or another ADF field, so it selects fixed REST API v2 and
`POST rest/api/2/search/jql` as the smallest compatible official contract. The internal
`jtr` behavior is corroborating deployment evidence only; it is not the normative basis
for the version decision.

The target deployment may provide a user-facing Jira site URL such as
`https://foo.atlassian.net/jira`. `/jira` is an accepted configuration input form but
is not part of the canonical REST or issue-navigation base; both root and `/jira`
inputs canonicalize to `https://foo.atlassian.net` for derived URLs. Atlassian
also distinguishes ordinary-user classic/unscoped tokens on site-specific URLs from
scoped tokens and official Service Accounts, which require the
`api.atlassian.com/ex/jira/{cloudId}` gateway. This MVP deliberately chooses a dedicated
ordinary Atlassian user account used operationally as a bot plus a classic/unscoped API
token and does not add gateway/Cloud-ID or OAuth lifecycle.

The repository already has `httpx`, `pydantic-settings`, secret types, and an
infrastructure HTTP adapter pattern. No dependency, database, or public API change is
needed.

## Goals / Non-Goals

**Goals:**

- Add a deterministic Jira Cloud infrastructure adapter that fulfills the existing port.
- Preserve exact provider-neutral lifecycle, current/reference, and failure semantics.
- Bound external response volume and retry work so the adapter cannot silently analyze a
  truncated result set.
- Make configuration, time, transport, and response behavior testable without Jira
  credentials or a live tenant.

**Non-Goals:**

- Jira Server/Data Center, Jira Service Management/Operations, Opsgenie, Forge, Connect,
  OAuth 3LO, token refresh, webhooks, writes, issue updates, or endpoint discovery.
- Scoped API tokens, official Atlassian Service Accounts, Atlassian API gateway routing,
  Cloud ID discovery, or bearer/scoped-token configuration.
- Custom Jira domains, Atlassian Government domains, arbitrary reverse-proxy paths, IP
  targets, non-Atlassian hosts, or a generic Jira dialect/version framework.
- Custom field mapping, description/ADF rendering, occurrence reconstruction,
  provider-independent severity mapping, query linting, query repair, or point-in-time
  historical state reconstruction.
- A new Alert Lens source/configuration ID, database migration, public API, runtime
  scheduler/orchestrator, LensRun creation path, agent/model production configuration,
  or any change to the Alert pipeline's analytical/result behavior.

## Decisions

### Select Jira Cloud REST v2 enhanced issue search as the only provider surface

The adapter calls the fixed site-specific path `/rest/api/2/search/jql` with POST JSON. It
requests only `summary`, `created`, `resolutiondate`, `status`, and `priority`; this
minimizes payload, avoids ADF description parsing, and covers the existing canonical
fields that are required or useful. Jira issue `key` becomes the record ID, `summary`
title, `created` lifecycle start, `resolutiondate` nullable end, `status.name` source
status, and `priority.name` `{type: "priority", value: ...}`. `source_ref` is built by
appending `/browse/<encoded-issue-key>` directly to the canonical pathless site origin,
independently of REST request construction. The key uses the existing strict UTF-8 URI
segment encoding with RFC 3986 unreserved bytes literal and uppercase `%HH` for every
other byte. Root and `/jira` configuration inputs therefore create the same
site-root navigation URL. Description and occurrence count remain absent, which invokes
the accepted downstream default of one occurrence and avoids inventing Jira aggregation
semantics.

This mapping is an approved MVP provider interpretation: Jira's `created` and REST
`fields.resolutiondate` are treated as the Alert lifecycle start and end for this
adapter, but Atlassian does not define a Jira issue as the system's Alert model. The
interpretation remains inside the provider adapter and does not redefine the canonical
Alert lifecycle contract.

This is a material product-boundary decision proposed for approval. The architecture
mentions an Opsgenie alert surface as deferred, but the canonical contract and current
implementation do not define its endpoint, identity, or lifecycle mapping. Supporting
it would be a distinct provider capability, not a fallback inside this adapter.

Atlassian documents `POST /rest/api/2/search/jql` as the v2 enhanced-search operation
with the same cursor request/response contract needed here. Its version documentation
states that v2 and v3 offer the same operation set and distinguishes v3 by ADF support.
Because this adapter uses only standard scalar/object issue fields and intentionally
omits description, v3 supplies no required capability. REST v2 is therefore the
explicit provider approval decision, not an inferred default from the internal client.

Alternative considered: retain REST v3 because it is the latest version. Rejected for
this bounded provider because its ADF capability is unused and would enlarge the
selected contract without benefit. Alternative considered: use the older
`/rest/api/2/search` offset API. Rejected because Atlassian identifies it as being
removed. Alternative considered: use a JSM/Opsgenie Alert API. Rejected for this change
because it has a different API and mapping contract that has not been approved.

### Keep optional Jira configuration raw until provider composition

Global `Settings` adds only a raw optional string value such as
`jira_alert_provider_raw: str | None`, populated from a serialized
`JIRA_ALERT_PROVIDER` environment value. Global Settings does not JSON-decode or bind it
to a strict Jira model. This ensures absent, malformed, or Jira-invalid optional
configuration cannot raise during `Settings()` construction.

The Jira composition factory exclusively owns JSON parsing and validation into an
internal strict `JiraAlertProviderSettings` containing `site_url`, non-empty `email`,
and a `SecretStr` non-empty `api_token`. Absence creates an unavailable provider with a
fixed `not_configured` diagnostic; any parse/validation error creates an unavailable
provider with fixed `configuration_invalid`. The factory never includes the raw value,
validation exception, token, or Authorization header in diagnostics or logs. A valid
profile constructs `HttpxJiraAlertProvider`. The committed `.env.example` documents
only the JSON shape and placeholders. No credential belongs in a Lens, repository
model, result, error, or log message.

The credential contract is a dedicated ordinary Atlassian user account used
operationally as a bot plus a classic/unscoped API token created for that account.
Authentication is preemptive Basic base64 of UTF-8 `email:token` against the
site-specific REST origin. Token strings do not reveal whether they are scoped, so the
classic/unscoped token type and ordinary-account ownership are deployment preconditions,
not runtime introspection. The configuration has no Cloud ID, gateway URL, scopes,
account-type selector, or OAuth fields.

Official Atlassian Service Accounts can create only scoped API tokens, and scoped tokens
for ordinary accounts also use the Atlassian API gateway. Supporting either would
require `api.atlassian.com/ex/jira/{cloudId}`, Cloud ID discovery/configuration, scopes,
and a second trusted-target policy, so both remain outside this capability.

Alternative considered: place `JiraAlertProviderSettings | None` directly in global
Pydantic Settings. Rejected because malformed optional JSON or fields would make
application startup fail before the provider factory could produce an unavailable
provider. Alternative considered: use an official Service Account or scoped token.
Rejected because it changes account lifecycle, routing, configuration, and credential
validation rather than being a drop-in replacement for the selected site-specific
classic-token contract.

### Derive one credential-safe site origin from every accepted Jira site URL

Parse the configured site URL before creating any authenticated client. Require HTTPS;
no userinfo, explicit port, query, or fragment; and a hostname matching exactly one
ASCII DNS label plus `.atlassian.net`. After case-normalizing the hostname for
comparison, the site label uses 1..63 ASCII alphanumeric/hyphen characters, begins and
ends alphanumeric, and cannot be an IP address. Accept only path `""`, `/`, `/jira`, or
`/jira/`. Reject every other host or path, including custom domains, Government hosts,
and arbitrary reverse-proxy prefixes.

Canonicalize both accepted user-facing path forms to the same site origin, with no path
or trailing slash:

```text
https://foo.atlassian.net       -> https://foo.atlassian.net
https://foo.atlassian.net/      -> https://foo.atlassian.net
https://foo.atlassian.net/jira  -> https://foo.atlassian.net
https://foo.atlassian.net/jira/ -> https://foo.atlassian.net
```

Construct enhanced search from that origin plus the fixed absolute path:

```text
https://foo.atlassian.net/rest/api/2/search/jql
```

The adapter must never construct
`https://foo.atlassian.net/jira/rest/api/2/search/jql`. The same canonical origin is
also used independently to build
`https://foo.atlassian.net/browse/<encoded-issue-key>`; the operator-supplied `/jira`
path is not preserved in REST or navigation output.

No authenticated client or request exists before validation and canonicalization
succeed. Redirect following is disabled, so a 3xx—including a cross-host redirect—is a
non-timeout provider error and credentials are never forwarded. Each admitted request
sends preemptive Basic authentication as base64 of the UTF-8 `email:api-token`
credential pair; credentials never appear in the request URL.

Deployment documentation makes complete provider visibility a precondition. The bot
must have Browse Projects and every applicable issue-level-security permission for the
full scope of every configured selector. Jira filters results to the authenticated
account's visibility and can therefore make missing permissions appear as a valid empty
or incomplete result rather than an authorization error. This limitation cannot be
reliably detected from one successful search response and is not represented as
analytical data.

Because Alert Lens source is a fixed provider discriminator rather than a source-profile
ID, one configured source is the only representation compatible with the accepted
definition. The composition root creates an unconfigured typed-outcome provider when
the optional raw settings are absent or invalid and a `HttpxJiraAlertProvider` only when
they are valid. This preserves local startup before a runtime dispatch capability
exists, while making a future injection failure map through the existing
current/reference paths.

Alternative considered: extend Alert Lens with a source ID/multiple Jira profiles.
Rejected because it changes the accepted definition contract and is not needed to
acquire real data from the one MVP provider. Alternative considered: OAuth 3LO. Rejected
because a scheduled process has no approved consent, callback, secure refresh-token
storage, or token-refresh lifecycle; this change makes no claim that bot basic auth is
the generally preferred Atlassian integration.

### Construct provider-owned time filtering without changing semantic scope

The adapter treats the stored selector as the immutable scope expression and constructs
one JQL expression for each supplied window:

```text
(<selector>) AND created < <end-ms>
AND (resolved IS EMPTY OR resolved > <start-ms>)
```

`resolved` is the documented JQL lifecycle-date field; the REST response field remains
`fields.resolutiondate`. `<start-ms>` and `<end-ms>` are unquoted UTC Unix epoch
milliseconds. Atlassian's JQL field documentation states that an unquoted number is
interpreted as milliseconds after epoch, which avoids a site-time-zone or
minute-precision conversion.

The start operand is `floor(window.start * 1000)` and the end operand is
`ceil(window.end * 1000)` after UTC epoch conversion. Flooring the lower bound and
ceiling the upper bound intentionally make Jira's millisecond query a candidate
superset when the application window has sub-millisecond precision. The existing
normalizer remains the final owner of exact strict overlap and rejects any extra
candidate admitted by the widened bounds. The time clauses are provider realization of
the existing LensRun `when` scope, not a rewrite of provider-owned `which` scope. No
lifecycle-status clause is introduced.

The same function is called for the pipeline-supplied current and same-duration
reference windows. It retains latest REST `resolutiondate` information, then the existing
normalizer independently applies strict overlap and duration semantics. A non-predicate
selector (notably an `ORDER BY` clause that cannot live inside parentheses) is sent as
constructed, rejected by Jira, and mapped as a query failure; the adapter does not
parse/repair opaque user JQL. This is compatible with the accepted rule against
automatic query rewriting, while avoiding an undocumented alternate scope.

Alternative considered: search the selector without time clauses and filter locally.
Rejected because a bounded response could omit old still-open records and could become
unbounded. Alternative considered: add time constraints to the definition query.
Rejected because time is owned by LensRun, not scope configuration.

### Use cursor pagination with a fail-closed volume bound

Each POST carries `maxResults: 100`; later pages carry the returned `nextPageToken` and
the identical selector/time/field request. A strict page decoder requires boolean
`isLast`. `isLast=false` requires a non-empty token not seen earlier in the same
acquisition; that token drives the next request. `isLast=true` terminates and must not
carry a non-empty continuation token. Missing, repeated, or contradictory pagination
state is an acquisition-level provider failure.

The adapter accepts at most 1,000 returned issues for one acquire call. Exactly 1,000
issues is successful only when the last page is terminal. It fails rather than returns
an incomplete success when a page would cross the cap or when a non-terminal page
follows the 1,000th issue. A response can return fewer than requested items because
Atlassian owns the per-operation maximum; only a consistent `isLast=true` envelope
terminates successfully.

This proposed 1,000-record cap is a correct-first MVP safety bound: it prevents a
plausible but silently incomplete AlertAnalysisResult. It does not introduce truncation
metadata because current result contracts lack it; operational diagnostics identify the
bounded-volume failure without raw response data.

Alternative considered: accept the first page. Rejected because it silently changes
record/occurrence evidence. Alternative considered: unlimited paging. Rejected because
it makes one LensRun unbounded and conflicts with the MVP's bounded-record direction.

### Classify request outcomes and bound the complete acquisition

One `acquire()` call has a hard 60-second monotonic deadline across all pages, complete
attempts, waits, and response-body reads. Every HTTP attempt has a separate hard
15-second monotonic deadline covering pool/connect, write, response headers, and the
complete body read. The provider owns these hard deadlines outside HTTPX phase timeout
configuration. HTTPX connect/read/write/pool timeouts remain optional defense in depth;
they cannot implement the normative wall-clock contract because, for example, a read
timeout limits inactivity between chunks rather than total response duration.

The asynchronous request/body-read operation remains cancellable by the deadline owner.
If either hard deadline expires while a request or body read is in flight, the provider
interrupts/cancels it, closes the response/transport resources, and returns typed
timeout. The design intentionally does not freeze a particular Python cancellation
primitive; tests assert elapsed monotonic behavior and cancellation/cleanup effects. A
new attempt starts only when a full 15 seconds remains in the acquire budget.

For one failed page request, the adapter retries at most twice after the initial attempt
for connection errors and HTTP 502/503/504/429 only. Read all raw `Retry-After` field
values rather than a convenience accessor that may combine duplicates. Exactly one
value is eligible: strip surrounding ASCII SP/HTAB only, require `^[0-9]+$`, parse
base-10, and require a value greater than zero. Leading zeros are accepted. Duplicate
fields, combined/comma-separated content, HTTP dates, signs, fractions, empty/zero, and
all other content are unusable.

A usable parsed delay through 15 seconds is the exact selected wait; a usable value
above 15 returns typed timeout without waiting. Missing or unusable headers and
connection failures select exactly 0.5 seconds before retry #1 and 1.0 second before
retry #2. There is no jitter. A retry is admitted only if the selected full wait plus a
subsequent hard 15-second attempt fits within the hard acquire deadline. Otherwise it
returns typed timeout without waiting. Requests are read-only and idempotent, so
admitted retries do not duplicate external mutations.

Authentication/authorization/query errors, redirects, malformed JSON/envelopes,
pagination and volume violations, and configuration errors are not retried. Hard
attempt/acquire deadline expiry or an excessive usable `Retry-After` becomes
`AlertProviderTimeout`. Exhausted retryable transport/HTTP failures while time remains,
and other non-timeout acquisition-level failures, become `AlertProviderFailure`. The
unconfigured composition uses `AlertProviderUnavailable`. Existing pipeline behavior is
intentionally reused: current timeout -> `current_query_timeout`, all other current
provider outcomes -> `current_query_failed`, and non-current failures/timeouts ->
unavailable reference comparisons. Diagnostics use a fixed safe category and status
code where useful, not Jira response text, URLs containing sensitive data, headers, or
token values.

Individual Jira issues are mapped independently. A missing key or other required
canonical field produces a minimal canonical-mappable dictionary with that field
missing or invalid, not a failed acquisition. The provider discards all unrequested Jira
fields, so it does not pass full raw payloads across the port. Existing normalization
then rejects the malformed item through `invalid_records` and preserves any usable
records in the same page/acquisition.

Alternative considered: return provider exceptions directly. Rejected because it would
make reference semantics rely on transport details and bypass the port's typed contract.
Alternative considered: retry all 4xx or deadlines. Rejected because invalid JQL and
credentials are not transient, and repeating a deadline can exceed the fixed
acquisition bound. Alternative considered: honor any positive `Retry-After`. Rejected
because provider-directed waits must not exceed the domain integration's bounded
execution budget.

### Keep source selection in composition, not the analytical pipeline

Introduce a small infrastructure package for Jira settings, request/response mapping,
and the port implementation. A composition/factory function validates that the scope's
source is `jira_track_and_release`, chooses configured or unconfigured provider, and
is the only construction point exposed to the application runtime. `main` may retain
that provider on application state for future dispatch; it must not create a LensRun or
invoke the pipeline. The domain `app.alerts` package remains free of `httpx`, settings,
and Jira imports.

Tests use an injected async HTTP transport/client seam, monotonic clock, sleeper, and
cancellation-observable slow/chunked bodies. They prove complete-attempt and
complete-acquire hard deadlines, cleanup of an interrupted in-flight body read, retry
admission, provider/injection boundaries, and existing pipeline typed-outcome
integration; no live Jira call is a test prerequisite.

Alternative considered: embed HTTP access in `AlertAnalysisPipeline`. Rejected because
it violates ADR-090 and makes deterministic pipeline tests dependent on production
configuration.

## Risks / Trade-offs

- [Jira Cloud endpoint/response contracts can evolve] → pin behavior to official links
  below, isolate response decoding in one adapter, and use mocked response-contract tests.
- [Enhanced JQL search is eventually consistent] → document that recent creation or
  resolution changes can be absent/stale; treat this as a provider limitation, not an
  error/partial reason/retry trigger. Do not use `reconcileIssues` because a JQL Lens
  does not start from a complete known missing-issue ID set.
- [JQL selector with `ORDER BY` cannot be safely embedded as a predicate] → fail as a
  provider query error without modifying the stored opaque selector; document this
  operational configuration constraint.
- [A current query can exceed the cap] → fail closed rather than publish a misleading
  truncated analysis; calibrate a later approved cap/aggregation feature from usage.
- [Jira permissions can silently reduce visible results] → require complete selector-
  scope permissions as a deployment precondition and document the limitation.
- [A classic/unscoped ordinary-user token has broader credential risk than a scoped
  token or OAuth] → dedicate a least-privilege ordinary account to bot operation, keep
  credentials secret, and constrain requests to the validated site-specific REST origin;
  gateway/scoped/Service-Account support requires a separate approved capability.
- [HTTPX phase timeouts allow indefinite slow progress across chunks] → enforce separate
  hard monotonic attempt/acquire deadlines around the complete async request and body
  read, with cancellation and cleanup verified independently of HTTPX timeout settings.
- [Jira issue timestamps are an application interpretation of Alert lifecycle] → make
  the approved MVP mapping explicit inside this adapter; support for a different alert
  data model remains a separate approval.

## Migration Plan

1. Deploy the optional configuration model and infrastructure adapter with no database
   migration and no required environment change.
2. Set the dedicated ordinary-user email, classic/unscoped token, and accepted Jira site
   URL only in the target deployment/local environment; root or `/jira` input derives
   the same site-root REST origin.
3. Compose the provider into the existing/future runtime dispatch path; unconfigured
   environments retain a typed unavailable provider.
4. Roll back by removing provider composition and configuration. No runtime artifact or
   schema rewrite is needed; already-created provider-neutral results remain readable.

## Open Questions

None that can be safely deferred within this task breakdown. Approval must explicitly
accept the material Jira Cloud REST v2 endpoint, site-URL-to-REST-origin policy,
dedicated ordinary-user/classic-token authentication, issue-field/lifecycle mapping,
hard 15/60-second deadlines, exact Retry-After grammar/retry policy, millisecond-bound
conversion, and 1,000-record cap decisions above before implementation. Jira
JSM/Opsgenie, OAuth, scoped-token, official Service-Account, gateway/Cloud-ID,
custom-domain, or Government support would change the approach and requires a separate
change.

## Architecture References

- `docs/architecture/13_alert_lens_and_analysis_concept.md` — source selector, lifecycle
  overlap, latest-known reference lifecycle, duration, and canonical record semantics.
- `docs/architecture/14_alerts_analysis_pipeline_detailed.md` and
  `19_alert_provider_adapter.md` — adapter ownership, strict scope boundary, and
  current/reference failure mapping.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — usable versus
  failed Alert outcomes and reference partial behavior.
- `docs/architecture/03_ADR_log.md` — ADR-090 through ADR-098 and ADR-102 through
  ADR-105, especially provider neutrality, which/when ownership, overlap, and no
  provider-importance normalization.
- `docs/architecture/10_open_decisions_and_backlog.md` — provider API, mapping,
  authentication, retries, timeouts, and volume policy were intentionally deferred.
- `openspec/specs/alerts-analysis-pipeline/spec.md` — existing injected port and
  unchanged analytical/result contract.

## Official Atlassian Documentation Verified on 2026-09-02

- [Jira Cloud platform REST API v2 issue search](https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-issue-search/)
  — `POST /rest/api/2/search/jql`, permissions, `jql`, fields, `maxResults`,
  `nextPageToken`, `isLast`, and eventual-consistency notice.
- [Jira Cloud REST API v2 version](https://developer.atlassian.com/cloud/jira/platform/rest/v2/)
  and [REST API v3 version](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro)
  — the versions expose the same operation collection; v3 adds ADF support for rich
  text fields not requested by this provider.
- [Search and Reconcile](https://developer.atlassian.com/cloud/jira/platform/search-and-reconcile/)
  — reconciliation requires known issue IDs from writes/webhooks; this JQL-defined Lens
  population does not have such a complete input set.
- [Jira Cloud JQL fields](https://support.atlassian.com/jira-software-cloud/docs/jql-fields/)
  — documented `resolved` syntax/`resolutionDate` alias, date operators, `IS EMPTY`,
  and unquoted epoch-millisecond operands.
- [Jira Cloud rate limiting](https://developer.atlassian.com/cloud/jira/platform/rate-limiting/)
  — HTTP 429, `Retry-After`, and backoff guidance.
- [Jira Cloud basic authentication](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/)
  — Atlassian account email plus API token and account-permission behavior.
- [API tokens for an ordinary Atlassian account](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)
  — unscoped tokens use site-specific URLs; scoped tokens require
  `api.atlassian.com/ex/jira/{cloudId}`.
- [API tokens for official Service Accounts](https://support.atlassian.com/user-management/docs/manage-api-tokens-for-service-accounts/)
  — Service Account tokens are scoped and use the Atlassian API gateway/Cloud ID.
- [Security for other integrations](https://developer.atlassian.com/cloud/jira/platform/security-for-other-integrations/)
  — OAuth 3LO recommendation and bot/script limitation of basic API-token auth.
- [HTTPX timeout behavior](https://www.python-httpx.org/advanced/timeouts/)
  — connect/read/write/pool phase timeouts, including per-chunk read inactivity rather
  than a complete-request wall-clock deadline.
