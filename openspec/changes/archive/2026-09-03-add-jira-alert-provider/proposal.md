## Why

The accepted Alerts Analysis Pipeline can analyze bounded Alert records but currently
only receives fake or injected provider implementations. A real Jira Track and Release
adapter is needed so an already-configured Alert Lens can acquire its current and
configured-reference evidence without leaking Jira transport semantics into the
provider-neutral pipeline.

## What Changes

- Add a Jira Cloud implementation behind the existing `AlertProvider` port for the
  accepted `jira_track_and_release` source.
- Define the verified Jira Cloud REST v2 enhanced-search surface, credential-safe
  site-URL-to-REST-origin handling, lifecycle-overlap JQL augmentation, field mapping, cursor
  pagination, bounded-volume handling, and current/reference acquisition behavior.
- Add server-side Jira source configuration and secret handling, plus explicit
  timeout, retry/backoff, HTTP-error, and transport-error mapping.
- Add application composition that resolves the configured source and injects the
  provider without changing the provider-neutral pipeline, analytical contracts,
  or Observation orchestration.
- Add provider-focused unit and HTTP-boundary integration verification using mocked
  Jira responses; no live tenant or repository credential is required.

## Capabilities

### New Capabilities

- `jira-alert-provider`: Acquire canonical-mappable Alert records from Jira Cloud for
  an immutable Alert LensRun through the existing provider-neutral boundary.

### Modified Capabilities

- `alerts-analysis-pipeline`: Permit a separately specified production Jira provider
  to be composed behind the existing injected AlertProvider port while preserving all
  pipeline and analytical semantics.

## Impact

- Affected areas: `app.core.settings`, a new `app.infrastructure.jira` adapter package,
  application composition, `.env.example`, and provider-focused tests.
- No public API, database schema, AlertAnalysisResult, deterministic analysis, agent,
  optional-tool, Lens definition, or Observation orchestration behavior changes.
- No dependency change is proposed: the repository already uses `httpx`.
- The implementation will require a configured Jira Cloud site URL, the email of a
  dedicated ordinary Atlassian user account used operationally as a bot, and that
  account's classic/unscoped API token only in local/deployment secret configuration.
  Accepted `/jira` input is removed when deriving the canonical site origin used
  independently for REST and issue-navigation URLs, and no credential is stored in
  source control.

## Architecture References

- `docs/architecture/13_alert_lens_and_analysis_concept.md` — immutable opaque selector,
  lifecycle-overlap, retrospective lifecycle, and canonical Alert semantics.
- `docs/architecture/14_alerts_analysis_pipeline_detailed.md` and
  `19_alert_provider_adapter.md` — provider adapter responsibility and failure boundary.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md` — current versus
  reference failure propagation and failed-result absence.
- `docs/architecture/03_ADR_log.md` — ADR-090 through ADR-098 and ADR-102 through
  ADR-105.
- `docs/development-guide.md` — existing injected Alert integration boundary.
