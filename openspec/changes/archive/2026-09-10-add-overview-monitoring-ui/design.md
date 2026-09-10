## Context

See `proposal.md` for motivation and `specs/overview-monitoring-ui/spec.md` for observable behavior.

The frontend already has an application shell, Observation list API, complete newest-first run-history API, coherent run-detail API, domain status badges, polling utilities, and a Runs screen. The root route currently redirects to `/observations`, while the Overview shell item is non-interactive. No backend overview projection exists, and adding one would duplicate data already available through accepted public contracts. Recharts is part of the accepted visual stack but is not installed yet; the proposal therefore requests explicit approval to add `recharts@^3.10.1` during implementation.

The main technical constraint is that definition metadata and compact run state come from two independent list requests, while persisted Observation-level finding statements exist only in run detail. The design therefore needs bounded detail loading and honest partial-data behavior without creating a second domain model.

## Goals / Non-Goals

**Goals:**

- Compose a deterministic read-only monitoring snapshot from existing public contracts.
- Keep analytical state, execution state, and data availability structurally independent.
- Bound finding-detail requests and reuse existing polling/terminal-regression protections.
- Keep data derivation testable through pure selectors separate from page rendering.
- Use existing frontend foundations and accepted visualization stack.

**Non-Goals:**

- A backend overview endpoint, new persistence projection, or API contract change.
- Launch, cancellation, retry, scheduling, edit, or delete behavior on Overview.
- Full historical analytics, configurable time ranges, pagination, or advanced table controls.
- New severity, confidence, urgency, recommendation, health, or root-cause semantics.
- Visual parity with or synchronization to the informative MagicPath canvas.

## Decisions

### 1. Compose the snapshot client-side from existing APIs

The Overview will request `GET /api/v1/observations` and `GET /api/v1/observation-runs` concurrently through the existing typed API modules. A pure projection layer will index newest-first runs by Observation ID, select the latest run, retain the first seven runs for row history, compute independent summary counts, and sort run-backed rows before never-run definitions.

This approach keeps the backend and persistence unchanged and makes every Overview value traceable to an accepted public field. A dedicated overview API was considered, but it would add a new contract and projection for an MVP data volume already served as complete non-paginated lists.

### 2. Maintain independent request state per source

Definition and run-history data will each retain `loading`, `data`, `error`, and `refreshing` state. Rendering selectors will use only successful snapshots, so a failed request is never represented by an empty array. Manual Refresh will start both requests, while automatic polling will refresh only run-derived state because definitions do not change as part of execution.

Keeping one all-or-nothing page request was considered, but it would hide usable definition context when runtime reads fail and hide operational run activity when definition refresh fails.

### 3. Reuse the established forward-only run merge and polling behavior

The Overview run-history loader will reuse or extract the existing sequential polling, active-run detection, and stable-identity merge rules from the Runs feature. There will be one in-flight history request at a time. Terminal summaries will not regress to an older `pending` or `running` snapshot, and the established final refresh after active-to-terminal transition will remain intact.

A separate Overview polling implementation was rejected because duplicate lifecycle logic would make the two monitoring screens disagree under fast completion or stale responses.

### 4. Bound Recent Findings to five analyzed run details

From the current history snapshot, the projection will select the first five summaries whose `analytical_state` is non-null. Their details will be requested concurrently, with request cancellation when the candidate identity set changes or the page unmounts. Successful details will be cached by stable run ID for the lifetime of the mounted page. Findings will be flattened in candidate-run order and persisted finding order, then limited to five.

One failed detail request will produce scoped incomplete/stale feedback while successful candidates remain usable. It will not turn missing detail into an empty finding list. Fetching every historical run detail was rejected as unbounded and unnecessary; a backend findings feed was rejected because it would expand the public API solely for this first Overview.

### 5. Keep view models semantic and minimal

The feature will define local display projections such as an Observation monitoring row, summary counts, recent finding item, and run-activity item. These are derived view models, not new domain contracts. They will retain source run and Observation identities and exact enum values rather than translating them into a combined health score.

No attention rank will be invented. Run-backed Observation rows will follow latest run creation order, which makes recency explicit without claiming that one combination of analytical and execution states is more severe than another.

### 6. Wrap Recharts in a project-owned Run Activity component

After the dependency proposal is approved, `RunActivityChart` will wrap Recharts and receive at most fourteen already-projected activity items. It will display them oldest-to-newest so time flows consistently. Exact execution-state tokens will control presentation. The component will also render a text legend and screen-reader-readable count summary; analytical state will not be an input.

A table library is unnecessary because the Overview needs neither sorting controls nor pagination. Raw feature-level Recharts usage was rejected to preserve the accepted project-owned chart boundary.

### 7. Extend routes without changing existing detail behavior

`/overview` will render the new page, `/` will redirect there, and the existing shell Overview item will become a `NavLink`. Existing `/observations`, `/runs`, and detail routes remain unchanged. Findings and latest-run actions will open the existing run-detail route; this change will not modify that screen to deep-link to a selected tab.

## Risks / Trade-offs

- **[Client-side list composition scales with complete MVP history]** → Keep projection linear, cap row history/activity/detail candidates, and defer pagination or a backend projection until the accepted API itself changes.
- **[Five analyzed runs may not include an older historical finding]** → Label the empty state with the exact bounded scope and provide a link to complete Runs history.
- **[Several detail requests can partially fail]** → Bound requests to five, preserve successful results, identify incomplete Recent Findings, and offer refresh without synthesizing absence.
- **[Two list snapshots are not transactionally atomic together]** → Treat each response as durable truth at its own read time, join only by stable IDs, and refresh active history; do not claim cross-endpoint snapshot atomicity.
- **[Overview and Runs could drift if polling logic is copied]** → Reuse or extract the existing polling and merge helpers and cover shared lifecycle behavior with tests.
- **[Dense rows may become hard to scan on narrow screens]** → Use responsive stacking and accessible compact history labels while retaining the same information and actions.

## Migration Plan

1. After explicit dependency approval, add `recharts@^3.10.1` and update the frontend lockfile.
2. Add the Overview feature and tests while leaving existing routes operational.
3. Activate `/overview` and change only the root redirect after the page is available.
4. Run the canonical frontend and repository checks.

Rollback consists of reverting the frontend change; no database, API, stored data, or dependency migration is involved.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: execution lifecycle is forward-only; missing or failed evidence remains unavailable rather than normal.
- `docs/architecture/08_observation_analysis_result_contract.md`: only persisted Observation findings are surfaced; hypotheses and knowledge remain distinct.
- `docs/architecture/03_ADR_log.md` ADR-167: accepted UI docs and this approved OpenSpec govern UI behavior while architecture/public contracts govern semantics.
- `docs/architecture/03_ADR_log.md` ADR-168: list/detail reads expose durable state and remain side-effect free; active execution is monitored by polling.
- `docs/architecture/03_ADR_log.md` ADR-170: the page remains within the trusted, unauthenticated single-user/internal MVP boundary.
- `docs/ui/frontend_ui_stack_adr.md`: existing React, semantic component, Recharts, and lightweight-list choices are retained; the only dependency addition activates the already accepted chart library.
- `docs/ui/ui_implementation_handoff_v1.md`: the required Overview areas, row fields, semantic tokens, and monitoring purpose are implemented without expanding into later monitoring screens.
