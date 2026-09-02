## 1. Configuration and composition boundary

- [x] 1.1 Add only a raw optional serialized Jira provider value to global application
  Settings so absent or malformed Jira-specific configuration cannot fail Settings
  construction or unrelated application startup.
- [x] 1.2 Add the Jira composition-owned strict parser/validator and fixed safe
  `not_configured`/`configuration_invalid` unavailable providers; construct the real
  provider only for a complete valid site URL, dedicated ordinary Atlassian user email,
  and classic/unscoped secret API token, without exposing raw configuration, token,
  Authorization value, or validation details; add no scoped-token, Service-Account,
  Cloud-ID, gateway, or OAuth fields/discovery.
- [x] 1.3 Implement the exact credential-safe Jira Cloud site URL contract:
  HTTPS, one valid ASCII site label under `.atlassian.net`, no userinfo/port/query/
  fragment/IP, and only root or `/jira`; derive one pathless canonical site origin from
  every accepted form for independent REST and issue-navigation construction, disable
  redirects, and never forward credentials cross-host.
- [ ] 1.4 Document the placeholder-only `JIRA_ALERT_PROVIDER` serialized shape in
  `.env.example`, complete Browse Projects/issue-security visibility as a deployment
  precondition, silent permission-based omission, and enhanced-search eventual
  consistency; document the ordinary-user/classic-token model and excluded scoped-token,
  official Service-Account, gateway/Cloud-ID, and OAuth models; wire provider selection
  only behind the existing `AlertProvider` port.

## 2. Jira Cloud acquisition adapter

- [ ] 2.1 Implement the infrastructure-only Jira Cloud enhanced-search adapter using
  fixed site-root REST v2 target `/rest/api/2/search/jql`, preemptive Basic
  authentication for the selected ordinary-user classic token, the minimal approved
  field set, documented JQL field `resolved`, floor(start)/ceil(end)
  epoch-millisecond candidate bounds, and immutable scope/window values; strip accepted
  `/jira` from REST targeting, keep exact overlap filtering in existing normalization,
  and omit `reconcileIssues`.
- [ ] 2.2 Implement strict response decoding and Jira issue-to-provider-record mapping:
  key, summary, created, resolution date, source status, native priority, source
  reference, latest-known reference lifecycle, intentional description/occurrence
  omission, and minimal malformed individual records for existing `invalid_records`
  normalization; construct `source_ref` from the canonical site origin plus
  `/browse/<strictly-percent-encoded-key>` with no `/jira`; document the approved MVP
  lifecycle interpretation.
- [ ] 2.3 Implement cursor-token pagination with 100-item pages, a 1,000-record
  fail-closed cap, required boolean `isLast`, new non-empty token requirements for
  non-terminal pages, terminal-envelope consistency, and repeated-token detection.
- [ ] 2.4 Implement provider-owned hard monotonic deadlines of 15 seconds for the
  complete HTTP attempt/body read and 60 seconds for the complete acquire across pages,
  attempts, reads, and waits; ensure in-flight operations are cancellable and cleaned
  up, retain HTTPX phase timeouts only as defense in depth, and preserve typed timeout
  outcomes.
- [ ] 2.5 Implement maximum two retries per failed page request, exact single-value
  decimal `Retry-After` grammar and 15-second cap, exact no-jitter fallback waits of
  0.5/1.0 seconds, remaining-hard-deadline admission, non-timeout response-contract
  failure mapping, and secret-safe diagnostics.

## 3. Provider verification

- [ ] 3.1 Add deterministic HTTP-boundary tests for fixed REST v2, Basic authentication,
  exact requested fields and JQL `resolved` construction, floor-start/ceil-end
  current/reference bounds, sub-millisecond candidate-superset behavior, no status
  predicate, exact post-map overlap filtering, omitted `reconcileIssues`, and
  unsupported selector query-error mapping.
- [ ] 3.2 Add adapter tests for all mapped field combinations, malformed record and
  missing-key preservation through `invalid_records`, usable/malformed mixed pages,
  native priority/status preservation, source-reference safety, latest-known resolved
  reference records, and absence of full Jira payload leakage.
- [ ] 3.3 Add pagination and resilience tests for terminal/multi-page success, exact
  1,000-record terminal success, over-cap failure, `isLast`/token inconsistencies,
  missing/repeated tokens, malformed responses, slow-progress/chunked bodies,
  in-flight hard-attempt expiry, hard-acquire expiry across pages/retries, pre-attempt
  admission with insufficient budget, non-retryable errors, and retryable
  connection/502/503/504/429 failures.
- [ ] 3.4 Add deterministic retry tests for exactly one Retry-After value with SP/HTAB,
  positive decimal and leading-zero acceptance, empty/zero/signed/fractional/combined/
  duplicate/HTTP-date/non-decimal rejection, exact 15 accepted and 16 timed out,
  exact retry #1/#2 fallback waits, remaining-deadline admission/rejection, retry
  exhaustion, and non-timeout response-contract failures.
- [ ] 3.5 Add configuration, URL, composition, and injected-pipeline tests covering no
  configuration, malformed serialization, invalid URL, missing email, missing token,
  valid ordinary-user/classic-token composition, startup usability for every invalid
  optional-provider case, all accepted root/`/jira` trailing-slash input variants,
  rejected unsafe hosts/components/paths and gateway/Cloud-ID/scope configuration,
  canonical pathless site origin, exact
  `/rest/api/2/search/jql` target for root and `/jira` input, explicit proof that the
  `/jira/rest/api/2/search/jql` target is never used, identical
  `https://<site>.atlassian.net/browse/<strictly-percent-encoded-key>` source references
  for root and `/jira` inputs, cross-host redirect non-follow/no-credential-forwarding,
  preserved current failure and reference partial mapping, and no live Jira requirement.

## 4. Verification and handoff

- [ ] 4.1 Review public classes and interface methods for the repository docstring
  policy; update concise developer-facing site-URL/canonical-origin, source-reference,
  ordinary-user classic token, excluded gateway models, hard-deadline, Retry-After,
  permission, and eventual-consistency documentation.
- [ ] 4.2 Run focused Jira-provider, settings, Alert-pipeline, and integration tests;
  report failures accurately.
- [ ] 4.3 Run `openspec validate add-jira-alert-provider --strict` and `make check`.
  Do not archive, push, create a pull request, or add Jira JSM/Opsgenie/OAuth support
  in this change.
