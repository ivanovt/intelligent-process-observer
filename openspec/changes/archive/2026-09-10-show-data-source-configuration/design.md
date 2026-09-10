## Context

See `proposal.md` for motivation. The existing capabilities endpoint projects each configured `PrometheusSourceSettings` to only `id` and `name`, and the Data Sources page renders that response as a read-only ordered list. The requested detail view crosses the backend/frontend contract and deliberately changes both the accepted UI rule and the Prometheus provider contract that currently keep endpoints and Basic-auth usernames out of public output.

The application remains unauthenticated under ADR-170 and is supported only in a trusted single-user/internal environment. That deployment boundary permits trusted operators to inspect non-secret operational configuration, but it does not permit any credential secret to enter a public response or frontend state.

## Goals / Non-Goals

**Goals:**

- Define one stable, typed API representation of the current Prometheus environment entry with secret fields and rejected unsafe URL values omitted.
- Keep the compact source summary as the default scan-friendly view.
- Make per-source configuration disclosure accessible and independent.
- Make secret and unsafe-URL exclusion structurally testable at the serialization boundary and in rendered UI tests.

**Non-Goals:**

- Returning raw `PROMETHEUS_SOURCES` text or generic settings dumps.
- Showing bearer tokens or Basic-auth passwords, including masked/redacted representations.
- Adding authentication, authorization, source CRUD, environment mutation, connection testing, health state, or diagnostics.
- Adding Jira or another provider to the Data Sources screen.
- Changing the environment schema, Metric Lens selection contract, refresh semantics, or dependencies.

## Decisions

### 1. Use an explicit typed safe projection at the backend boundary

`CapabilitySource` will gain a required `configuration` object with a Prometheus-specific discriminated credential projection and an optional `base_url` member:

```json
{
  "id": "primary",
  "name": "Primary metrics",
  "base_url": "https://prometheus.example.invalid",
  "credentials": {
    "type": "bearer_token"
  }
}
```

or:

```json
{
  "id": "secondary",
  "name": "Secondary metrics",
  "base_url": "https://secondary.example.invalid",
  "credentials": {
    "type": "basic_auth",
    "username": "observe-reader"
  }
}
```

The projection will be constructed field by field from validated settings. Token and password fields will not exist on the public DTO, so normal response serialization cannot emit either real values or Pydantic masked secret strings. The outer `id` and `name` remain unchanged for existing Metric Lens consumers; duplicating them inside `configuration` intentionally makes the JSON pane represent one complete environment entry after secret removal.

Before including `base_url`, the projection will apply the same pure target rules used by production Prometheus validation. If the complete configured string passes, the exact original value is included. If it fails for any reason—including userinfo, query, fragment, malformed authority, unsafe scheme/host, control characters, or invalid path—the member is omitted during HTTP serialization. The rejected string is never normalized, redacted, logged, or returned, and the response adds no explanation or status. The source still appears because shared settings and capability availability remain intentionally tolerant; this confidentiality gate is not a health or production-validity result.

The safe-target predicate will be shared by the capabilities projection and acquisition validation rather than duplicated. Acquisition remains authoritative and repeats validation at the time the provider resolves a source, so capabilities neither cache nor confer production validity.

Alternative considered: return the raw settings model with serialization exclusions. Rejected because exclusions are easier to regress when settings evolve and can emit masked secret placeholders instead of proving that secret fields are absent.

Alternative considered: expose a generic dictionary containing every field except a denylist. Rejected because a future settings field could become public accidentally. New fields require an explicit public-contract decision and DTO update.

Alternative considered: return every configured `base_url` verbatim. Rejected because tolerant shared settings accept production-invalid URLs containing userinfo or query data, which can embed secrets.

Alternative considered: sanitize or replace an unsafe URL. Rejected because a transformed value is not the configured value, placeholders conflict with the requested JSON semantics, and either approach can disclose rejected input characteristics. Omitting the member fails closed without changing startup behavior.

Alternative considered: make shared Settings reject every production-invalid URL. Rejected because it would make optional source configuration fail global application startup and would change the accepted tolerant composition boundary.

### 2. Keep one capabilities request and disclose locally

The existing capabilities response will carry the configuration projection. Expanding a source will be local UI state and will not fetch a second detail endpoint. This keeps current loading, retry, refresh, ordering, and request cancellation behavior intact and avoids a new source-resource lifecycle implication.

Alternative considered: add a source-detail endpoint loaded on expansion. Rejected because the source list is already small environment configuration, a second endpoint adds contract and failure-state complexity, and it provides no stronger secret boundary than the required backend projection.

### 3. Render a semantic disclosure around a read-only JSON code block

Each source row/card will retain its current summary and add a button labeled for configuration visibility. The button will use `aria-expanded` and `aria-controls` for its source-specific pane. The pane will render `JSON.stringify(configuration, null, 2)` inside a `<pre><code>` container with horizontal overflow. Each card owns its expanded state so disclosures do not affect one another.

The UI will render the typed API projection directly rather than reconstructing credentials or applying a frontend redaction pass. Frontend filtering would be defense in depth at most, not the security boundary, because any returned secret would already be browser-visible.

Alternative considered: render labeled fields. Rejected for this initial iteration because the requested JSON mirrors the environment structure, is compact, and avoids bespoke layouts for the two credential variants.

### 4. Treat this as an additive response evolution within the existing internal client pair

The new `configuration` member is required in the updated backend and frontend types, while its `base_url` member is optional to represent fail-closed omission. The repository deploys the paired backend/frontend as one modular monolith, so implementation and verification will update both sides atomically. Existing `id`, `name`, adapter grouping, and ordering remain unchanged.

Alternative considered: make `configuration` optional for rolling compatibility. Rejected because this MVP has no independently versioned frontend/backend deployment contract and optionality would add an unsupported partial-detail state.

## Architecture References

- `docs/architecture/03_ADR_log.md`, ADR-167: the approved OpenSpec change intentionally evolves Data Sources UI behavior while public contracts remain authoritative. MagicPath parity is not required.
- `docs/architecture/03_ADR_log.md`, ADR-170: endpoint and username visibility is limited to the supported trusted operator environment; no browser-visible credential secret is introduced.
- `docs/ui/frontend_ui_stack_adr.md`: the design uses the existing React/Tailwind stack and needs no new UI dependency.
- `docs/ui/ui_implementation_handoff_v1.md`, Data Sources: environment ownership, read-only lifecycle, source ordering, and restart-then-refresh behavior remain intact. This approved delta replaces only the narrower visibility rule for non-secret configuration.
- `openspec/specs/observation-definition-api/spec.md` and `openspec/specs/metric-source-overview-ui/spec.md`: the delta files update the affected public API and UI requirements without changing Observation ownership or Metric Lens selection semantics.
- `openspec/specs/prometheus-metric-provider/spec.md`: the provider delta permits Basic username only in the approved capabilities projection while retaining secret-material, provider-port, diagnostic, failure, target-validation, and acquisition boundaries.

No unresolved Open or Deferred architecture decision is selected by this design.

## Risks / Trade-offs

- [The base URL or Basic-auth username may still be operationally sensitive] → Limit support to ADR-170's trusted environment, keep details collapsed by default, and document the expanded public contract explicitly.
- [A future settings field could contain a secret and leak through serialization] → Use allowlisted public DTOs rather than settings serialization or denylist-based dictionary filtering; require an explicit contract update for each new projected field.
- [A production-invalid URL may contain credential-like content outside declared credential fields] → Include the exact URL only after the complete value passes the shared production-safe target rules; otherwise omit the member and rejected value entirely.
- [Consumers could mistake URL inclusion or omission for a health result] → Return no validity reason or status, document the confidentiality-only purpose, and keep authoritative validation inside acquisition.
- [Secrets could appear in frontend fixtures or snapshots even if production projection is safe] → Use unmistakable sentinel secrets in backend tests and assert that both secret keys and values are absent from serialized output; keep frontend fixtures secret-free.
- [Long URLs or names can overflow the card] → Use a horizontally scrollable code container while preserving wrapping behavior in the compact summary.
- [The same `id` and `name` appear in both summary and JSON] → Accept the duplication because the detail pane represents the complete secret-removed environment entry and can be read independently.

## Migration Plan

1. Add and verify the typed public projection, shared safe-target serialization gate, and service mapping without changing environment parsing or acquisition authority.
2. Update the paired frontend contract, disclosure rendering, and interaction tests.
3. Advance the living UI handoff and index to v1.6, replacing the obsolete endpoint/username prohibition with the approved secret-safe disclosure rule.
4. Run repository checks and strict OpenSpec validation.

No database or environment migration is required. Rollback consists of reverting the paired API/UI change; existing environment configuration remains valid throughout.
