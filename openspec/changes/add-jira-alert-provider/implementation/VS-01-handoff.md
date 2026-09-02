# VS-01 Handoff — Credential-safe composition and empty walking skeleton

## Implemented behavior

- `Settings` retains optional `JIRA_ALERT_PROVIDER` as raw text; parsing remains Jira-owned.
- The source-isolated resolver rejects non-Jira sources before configuration parsing or provider construction. For the accepted `jira_track_and_release` source it returns either an `UnavailableAlertProvider` (`not_configured` or `configuration_invalid`) or `HttpxJiraAlertProvider`.
- The real provider validates/canonicalizes only accepted Jira Cloud site URLs, sends one redirect-disabled REST v2 enhanced-search POST with preemptive Basic authentication, and completes a terminal empty page as `AlertRecordsAvailable`.
- This walking skeleton fails closed for non-empty, non-terminal, malformed, redirected, and other non-success responses. Mapping, paging, deadlines, and retries remain VS-02 through VS-05 work.

## OpenSpec scenarios covered

VS01-AC01 through VS01-AC07 at their VS-01 configuration, composition, empty-request, redirect, and zero-record-pipeline boundaries.

## Important files/contracts

- `app.core.settings.Settings`; new Jira-private configuration, adapter, and composition modules under `app.infrastructure.jira`.
- Existing `AlertProvider`, typed provider outcomes, and injected `AlertAnalysisPipeline` are consumed unchanged.

## Verification

`cd backend && uv run ruff check ...` — passed.

`cd backend && uv run ruff format --check ...` — passed.

`cd backend && uv run pytest tests/test_jira_alert_provider.py tests/test_jira_alert_provider_configuration.py tests/test_health.py tests/test_alert_analysis_pipeline.py` — 53 passed.

`git diff --check` — passed.

## Downstream invariants

The raw configuration is parsed only after source selection; all application-used Jira resolutions are provider objects, never typed outcomes. The `/jira` browser path never enters derived REST targets. Credentials are generated only for the request Authorization header and never included in diagnostics.

## Known limitations within approved scope

Only terminal empty pages are successful in this slice. Non-empty records, pagination, deadlines, retries, and comprehensive response mapping are intentionally deferred to the following approved slices.

Commit SHA: `HEAD` (resolve as the commit containing this handoff).

Plan change requested: none.

Shared knowledge candidates: none.
