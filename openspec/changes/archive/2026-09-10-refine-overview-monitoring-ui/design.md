## Context

See `proposal.md` for motivation and `specs/overview-monitoring-refinement/spec.md` for observable behavior.

The prerequisite `add-overview-monitoring-ui` change already supplies correct client-side projections, independent definition/run request state, active-run polling, bounded Recent Findings retrieval, semantic badges, and a Recharts activity component. Its current presentation uses a `max-w-6xl` container, four large summary cards, one full-width stack of individually bordered Observation cards, and a two-column findings/activity region placed after that entire stack. With large definition sets, the insight sections therefore fall far below the initial viewport.

The supplied target screenshot is useful for density and hierarchy, but it also contains semantics the project does not support: ObservationRun `partial`, global time-range filtering, user identity, and non-finding entries inside Recent Findings. ADR-167 requires the refinement to adapt the visual idea to accepted contracts rather than copy it literally.

This is a stacked follow-up. Implementation must start from the accepted `add-overview-monitoring-ui` code and must not be archived ahead of its prerequisite capability.

## Goals / Non-Goals

**Goals:**

- Make the initial desktop viewport useful for high-volume monitoring.
- Increase information density without reducing status clarity or accessibility.
- Add locally derived no-findings and uncertain summary counts.
- Add deterministic client-side search without affecting other dashboard projections.
- Keep error and unavailable states honest but visually proportional to the remaining successful content.
- Reuse the existing data coordinator, projections, semantic components, and chart dependency.

**Non-Goals:**

- Changing backend APIs, projection failure policy, database records, or execution behavior.
- Adding a global dashboard time window or changing what “latest” means.
- Adding user identity, authentication, authorization, or personalization.
- Inventing Observation categories, health states, severities, confidence, or recommendations.
- Expanding Recent Findings beyond its existing candidate/detail bounds.
- Exact screenshot, MagicPath, or pixel parity.

## Decisions

### 1. Use a wider dashboard container and one primary content grid

The Overview root will expand from `max-w-6xl` to the existing Tailwind `max-w-7xl` scale. After the summary strip, one responsive grid will contain the Observation collection and the insights rail. At an appropriate wide breakpoint, the grid will use approximately a 2:1 primary-to-rail ratio; below it, sections will stack in the specified order.

The insights rail will contain Recent Findings followed by Run Activity. It will begin beside the Observation header and rows rather than after them. It will not be viewport-fixed: natural document flow is less fragile for short screens, zoom, and large error content while still solving the below-the-entire-list problem.

Keeping the current sequential layout was rejected because styling alone cannot keep insights visible with dozens of Observations. A fixed or permanently sticky rail was rejected because it can obscure long content and complicate narrow-height accessibility.

### 2. Split presentation into small project-owned Overview components

The large page composition will be separated into focused feature components such as a summary strip, searchable Observation collection, monitoring row, recent-run marker, and insights rail. These remain under the Overview feature or existing project-owned chart layer; they are not generic UI primitives or a second design system.

The desktop collection will remain a semantic list with a CSS-grid header and rows. This matches the existing lightweight-list direction and allows responsive stacked rows without introducing TanStack Table. Native table markup was considered, but preserving the same content as a compact narrow-screen card/list would require more complex duplicate rendering or layout overrides without adding needed table behavior.

### 3. Extend existing projections rather than derive state in JSX

`OverviewSummaryCounts` will add explicit `observationsWithNoSignificantFindings` and `observationsWithUncertainAnalysis` fields. The same latest-run selection used by the existing counts will own all analytical buckets, so absence is never converted to a value.

A pure search projection will accept the already ordered Overview rows and a query, normalize with `trim().toLocaleLowerCase()`, match name plus `description ?? ''`, and preserve input order. Summary, Recent Findings, and Run Activity continue using the unfiltered source projections.

Embedding filter/count logic directly in the page component was rejected because pure selectors are easier to test against semantic edge cases and keep domain-derived behavior out of markup.

### 4. Track client refresh receipt time inside the Overview coordinator

The Overview data coordinator will expose one optional `lastSuccessfulRefreshAt` value. It will advance from an injected/default client clock whenever either definitions or run history settles successfully, including automatic run polling. Failures will not advance it. The header will render the timestamp as `Last refreshed <localized time>` and make its client-receipt meaning clear in accessible text.

The shared Runs polling contract will not gain a backend timestamp or global snapshot concept. A server-generated freshness field was rejected because no backend change is needed and the timestamp is intentionally only local request feedback.

### 5. Make the six summary cards compact but semantically explicit

The summary will use six low-height cards with a large count, concise label, and an existing Lucide icon or status dot. Raw domain colors will come from existing analytical/execution tokens. Supplemental prose currently repeated under every large card will move to concise accessible labels/tooltips where useful.

The layout will use two columns on small widths, three at medium widths, and six only when the available content width can support readable labels. Counts remain text; icons and color never carry the value alone.

### 6. Use distinct, focusable recent-run markers

Recent-run markers will use unique visible icon/token combinations for `pending`, `running`, `completed`, `failed`, and `cancelled`; completed and cancelled will not share the same letter. Each marker will expose the full time/execution/analysis description through an accessible name and a keyboard-visible compact tooltip/detail treatment using existing primitives or project-owned CSS.

Markers remain informational rather than acting as hidden navigation controls. The explicit latest-run action remains the row's run navigation target.

### 7. Add visible bounded counts to Run Activity

The existing chart continues to receive at most fourteen projected runs. Beneath or beside it, a compact visible summary will show the represented total and exact counts for pending, running, completed, failed, and cancelled. These counts will reuse the same activity array as the bars and accessible summary so they cannot drift.

The target screenshot's `partial` count is intentionally replaced by exact supported statuses. The chart will not claim to represent a 24-hour period because its contract is newest-fourteen runs.

### 8. Preserve partial-failure behavior while reducing visual weight

Page-level loading/unavailable/stale notices will remain above the affected monitoring content, but spacing and typography will be tightened. Successfully loaded definitions stay visible and searchable when run history fails. Runtime-derived cards and rail sections continue to say `Unavailable`; no skeleton or decorative sample data will replace rejected durable state.

The local database records currently causing `runtime_projection_invalid` are operational input outside this change. Weakening projection validation or deleting local data was rejected because either would cross the approved scope and data-safety boundary.

## Risks / Trade-offs

- **[Dense desktop columns may truncate long generated names]** → Give the identity column flexible width, preserve full accessible text/title, and wrap or truncate only visual secondary content.
- **[Six cards can become cramped before the desktop breakpoint]** → Use progressive 2/3/6-column layout rather than forcing one line at every width.
- **[Responsive list markup is less inherently tabular than a native table]** → Keep explicit column headings, list semantics, stable field labels on narrow layouts, and focused accessibility tests.
- **[Last-refresh time could be mistaken for analysis freshness]** → Label it as client refresh receipt and never use it in analytical or execution derivation.
- **[Search over a stale definition snapshot remains stale]** → Preserve the existing stale warning and filter only what is truthfully loaded.
- **[The stacked branch could be archived out of order]** → Record the prerequisite explicitly and require `add-overview-monitoring-ui` to remain in the branch history or become canonical first.

## Migration Plan

1. Confirm the implementation branch contains the accepted `add-overview-monitoring-ui` base.
2. Extend pure projections and coordinator freshness state with focused tests.
3. Refactor the Overview presentation and Run Activity summary without changing API calls or polling behavior.
4. Verify desktop/narrow structure, keyboard behavior, semantic states, partial failure, and local search.
5. Run the canonical frontend checks and `make check`.

Rollback consists of reverting this presentation refinement. No database, API, dependency, or stored-data migration is involved.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: exact execution states and absence semantics remain unchanged; no ObservationRun `partial` is introduced.
- `docs/architecture/08_observation_analysis_result_contract.md`: Recent Findings remains limited to persisted Observation-level findings; hypotheses and knowledge remain separate.
- `docs/architecture/03_ADR_log.md` ADR-167: the screenshot informs density and hierarchy but cannot override accepted UI/domain semantics.
- `docs/architecture/03_ADR_log.md` ADR-168: the page continues to consume read-only durable run projections and existing polling behavior.
- `docs/architecture/03_ADR_log.md` ADR-170: no identity/authentication UI or broader access assumption is added.
- `docs/ui/frontend_ui_stack_adr.md`: existing React/Tailwind/Lucide/Recharts and lightweight project-owned components are reused without dependency changes.
- `docs/ui/ui_implementation_handoff_v1.md`: the refinement preserves the required Overview areas, status components, responsive behavior, and monitoring purpose.
- `add-overview-monitoring-ui`: the completed prerequisite remains the source for data-loading, failure, finding-bound, activity-bound, and navigation behavior.
