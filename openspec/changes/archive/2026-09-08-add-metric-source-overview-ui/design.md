## Context

See `proposal.md` for motivation and `specs/metric-source-overview-ui/spec.md` for observable behavior.

The backend already accepts an ordered `PROMETHEUS_SOURCES` JSON array and projects safe `{id, name}` entries under the `prometheus` adapter through `GET /api/v1/observation-definition-capabilities`. `Settings` validates source-ID uniqueness, application composition constructs the production provider from the registry at startup, and the Metric Lens editor already offers all returned choices. The public response deliberately excludes endpoints and credentials.

The frontend shell contains a disabled `Data Sources` item but no route. The change is stacked on the Observation Management UI branch until PR #18 merges. UI Direction v1.1 does not include a Data Sources screen, and ADR-166 currently declares frozen v1.1 the visual/UX source of truth. The user has explicitly approved loosening that authority model, so a newer ADR must govern v1.2 and repository guidance must be reconciled consistently rather than silently overriding ADR-166.

## Goals / Non-Goals

**Goals:**

- Make the current server-managed Metric-source model understandable and visible without weakening its security boundary.
- Provide a useful empty-state path from missing sources to correct environment setup.
- Confirm multi-source behavior end to end using the existing capabilities contract and Metric editor.
- Fit the new screen into the established shell, token, icon, notice, loading, and retry patterns.

**Non-Goals:**

- Source CRUD, database persistence, dynamic reload, connection testing, health monitoring, or credential rotation.
- Returning base URLs, usernames, secrets, or credential metadata from the backend.
- Writing root `.env`, using `frontend/.env`, or placing secrets in `VITE_*` values.
- Supporting unauthenticated Prometheus, custom CA/mTLS, OAuth, cloud signing, proxies, or new provider types.
- Refactoring the backend source registry, capabilities endpoint, production provider, or Observation payload.

## Decisions

### 1. Treat Data Sources as a safe projection, not a resource lifecycle

Add `/data-sources` and convert only the existing Data Sources shell item to a `NavLink`. The page calls the existing capabilities endpoint and renders a project-owned lightweight list/card view. Each item shows only `Prometheus`, `name`, `id`, and explanatory availability copy. It does not call a detail endpoint because none exists and it does not synthesize connection status from presence in Settings.

Alternative considered: add source CRUD endpoints. That contradicts the selected MVP environment-only credential direction and requires unresolved secret storage and reload decisions.

### 2. Reuse the existing capabilities client and request-state pattern

The page consumes the existing typed `getDefinitionCapabilities` read and `useRequest` loading/error/retry behavior. This is intentionally a view of Observation-definition capability, not a new generic data-source API. Avoiding a premature shared API framework keeps the delta small; a future application-managed source resource may establish its own boundary.

The Metric Lens editor remains unchanged except for tests confirming that multiple returned sources stay selectable. No cross-page client cache is introduced, so Refresh performs a new abort-safe read and sees updated data after backend restart.

### 3. Make empty-state guidance operational but non-secret

The empty state contains:

- a concise explanation that configuration belongs in the backend root `.env` or deployment environment;
- the required `id`, `name`, `base_url`, and exactly-one-credential-shape fields;
- placeholder-only Bearer and Basic JSON examples matching `.env.example`;
- an explicit multiple-entry example or explanation;
- the sequence `change environment → restart backend → Refresh sources`;
- a warning never to commit real credentials or place them in frontend/Vite variables.

Examples use `.invalid` endpoints and obvious replacement tokens. They are static UI documentation and are never submitted or persisted.

Alternative considered: accept values in the browser and generate an environment string. Even without sending it to the backend, handling real credentials in client state and clipboard would blur the accepted boundary without providing true configuration persistence.

### 4. Add ADR-167 to make MagicPath an informative reference

Add ADR-167 to `docs/architecture/03_ADR_log.md`. It preserves ADR-166's accepted frontend stack and project-owned semantic-component decision while superseding its strict claim that frozen v1.1/MagicPath is the visual/UX source of truth.

ADR-167 establishes this authority order for UI work:

1. accepted domain/runtime architecture and public contracts remain authoritative for product semantics and API boundaries;
2. accepted `docs/ui/` direction/handoff plus approved OpenSpec changes govern UI behavior, information architecture, and intentional visual evolution;
3. MagicPath is an informative visual reference and synchronization target, not a parity requirement or implementation gate;
4. meaningful UI changes remain versioned and human-approved rather than arising from incidental code drift.

MagicPath synchronization may occur later but is optional and does not determine whether an approved UI change can be implemented or accepted. This rule applies consistently to existing and new screens; it is not a screen-14-only exception.

Update `docs/architecture/README.md` to the next package version and record the decision in `docs/architecture/12_CHANGELOG.md`. Historical ADR-166 and v1.1 archive text remain historical; newer ADR precedence supplies the supersession.

Alternative considered: amend UI docs only. That would conflict with ADR-166 under repository precedence and is therefore rejected.

### 5. Supersede v1.1 with an in-place living v1.2 handoff

Keep the existing filename `docs/ui/ui_implementation_handoff_v1.md` because it is the living major-v1 handoff, and update its internal title/status from v1.1 to v1.2. Add `14 Data Sources` and its read-only environment-managed semantics.

Reconcile every current authority pointer rather than renaming the file: update `docs/ui/README.md`, the current-version/authority language in `docs/ui/frontend_ui_stack_adr.md`, and the root `AGENTS.md` frozen-direction rules to v1.2 and ADR-167's non-binding MagicPath role while preserving the existing handoff path. Verify that the root `README.md` and any other current repository references still resolve to that unchanged path.

The v1.2 handoff remains the implementation-oriented UI contract. MagicPath may still guide look and feel, but no existing or new screen requires 1:1 parity or canvas synchronization for acceptance. This does not authorize changes to domain semantics, API behavior, or UI direction without the normal architecture/OpenSpec approval gates.

## Risks / Trade-offs

- **[Risk] Users may interpret a listed source as healthy.** → Label it “configured” or “available for Metric Lens configuration,” never online/healthy/connected.
- **[Risk] Static examples may be copied with placeholder values.** → Use `.invalid` hosts, explicit replacement wording, and a warning that examples are non-production.
- **[Risk] Restart requirements may be misunderstood as dynamic refresh.** → State that backend restart loads Settings; Refresh only re-reads the running backend afterward.
- **[Risk] Reusing an Observation-named endpoint couples the page to the current API surface.** → Keep the reuse explicit and narrow; do not create a second source representation merely for naming purity.
- **[Risk] A stacked branch can accidentally mix PR scopes.** → Keep this change on its own feature branch and rebase it onto `main` after PR #18 merges before opening its PR.
- **[Risk] Relaxing MagicPath authority could be misread as permission for unreviewed UI drift.** → ADR-167 keeps accepted UI docs/OpenSpec and human approval authoritative while making only the canvas reference non-binding.
- **[Risk] Partial v1.2 documentation updates could leave conflicting source-of-truth rules.** → Add the newer architecture ADR first, keep the handoff filename stable, update all current version/authority declarations together, and verify repository pointers.

## Migration Plan

1. Land or retain the Observation Management UI base from PR #18.
2. Add the Data Sources route/shell integration and safe capability-backed states.
3. Add environment setup guidance and multi-source integration tests.
4. Add ADR-167, increment the architecture package version, and update the architecture changelog.
5. Supersede v1.1 in place with consistent v1.2 UI documentation and repository instructions while preserving the living handoff path.
6. Run frontend verification and `make check`.

Rollback removes the route, page, navigation activation, tests, and v1.2 documentation update. No backend, data, or credential migration exists.

## Architecture References

- `docs/architecture/03_ADR_log.md`, ADR-166: stack decision retained; strict frozen-v1.1/MagicPath authority superseded by approved ADR-167.
- `docs/architecture/README.md` and `docs/architecture/12_CHANGELOG.md`: package version and decision history updated for ADR-167.
- `openspec/specs/prometheus-metric-provider/spec.md`: environment-only credentials, server-managed registry, trusted-target policy, and non-exposure boundaries remain unchanged.
- `openspec/specs/observation-definition-api/spec.md`: the existing safe capabilities response remains the only public source projection.
- `docs/ui/frontend_ui_stack_adr.md`: the screen uses the accepted project-owned React/Tailwind/Lucide patterns.
- `docs/ui/ui_implementation_handoff_v1.md`: retained as the living major-v1 file and versioned internally to v1.2 to add the screen and preserve all existing Observation Management constraints.
