## Context

See `proposal.md` for motivation. Observation Definitions currently support aggregate create and read only. The backend stores Metric Lenses, Alert Lenses, and Relationships as ordered, delete-orphan children of one `ObservationModel`; the frontend maintains one create-only draft under `/observations/new` and its nested editor routes.

The accepted architecture already fixes two constraints needed by this change: definition updates use atomic snapshot/replacement semantics, and an initialized Observation Run uses an immutable in-memory snapshot that later definition mutations cannot change. Metric History is identity-scoped by `observation_id + lens_id`, so editing acquisition fields under the same public Lens ID intentionally retains History continuity.

## Goals / Non-Goals

**Goals:**

- Add one idempotent full-aggregate replacement boundary for an existing Observation.
- Reuse the established aggregate draft, validation, and nested-editor interactions for editing.
- Make add/edit/remove/reorder operations explicit in the client draft and persist them with one final request.
- Ensure a definition load observes either the aggregate before or after a concurrent replacement, never a mixture used to initialize a run.
- Preserve stable parent and persisted-child public identities while giving newly added children generated identities.

**Non-Goals:**

- Partial/PATCH semantics, per-child endpoints, soft deletion, restore, or Observation deletion.
- Definition revision history, audit logging, optimistic concurrency tokens, or merge/conflict UI.
- Changing Metric History eligibility or automatically detecting whether an edited query represents a different physical metric.
- Editing runtime records or changing an already initialized run.

## Decisions

### 1. Use `PUT` with the existing create-shaped aggregate body

Add `PUT /api/v1/observations/{observation_id}` with the same mutable fields and validation model as creation. `id`, `schema_version`, links, and runtime values remain response-only. A successful request returns the complete canonical definition with `200 OK`; repeating the same request produces the same represented configuration.

This matches the architecture's complete-snapshot ownership rule and avoids ambiguous omission semantics. `PATCH` was considered, but it would require field-specific merge rules and special collection operations that add contract surface without helping the required full-edit workflow.

### 2. Reconcile owned collections by public child identity inside one transaction

The service validates enabled Metric sources before mutation and opens one transaction. The repository locks and loads the target aggregate, returns not found before creating anything, updates parent scalars, and reconciles each ordered child collection:

- matching public IDs update the existing owned rows and position;
- new public IDs create owned rows;
- omitted public IDs are removed through delete-orphan ownership;
- the submitted order becomes the complete persisted order.

The full Pydantic aggregate validation occurs before repository mutation, while database or flush failures roll back the transaction. Reconciliation is preferred over delete-all/reinsert because it preserves internal row identities for retained public children and avoids transient uniqueness conflicts.

No schema migration is required: current tables already represent every mutable field, ordered position, aggregate foreign key, and delete-orphan relationship.

### 3. Serialize coherent definition loading against replacement

The target root row is acquired with an appropriate PostgreSQL row lock before replacement reconciliation. Complete definition loads that can overlap replacement—especially execution initialization—must hold a compatible read lock or otherwise use an equivalent coherent transaction snapshot while eager-loading all child collections. This makes a reader observe one side of the atomic replacement and prevents a multi-statement eager load from combining old parent values with new children.

This small locking boundary is preferable to introducing a revision store or globally changing transaction isolation. Definition reads and writes are low-frequency management operations, and active analytical execution does not retain a database lock after initialization has frozen its values.

### 4. Generalize the draft provider to explicit create and edit modes

The route tree gains `/observations/:observationId/edit` with nested `metric-lenses/:key`, `alert-lenses/:key`, and `relationships/:key` routes under the same provider boundary. The provider records its mode and target identity, can initialize from an `ObservationResponse`, and assigns UI-only `clientKey` values without changing public child IDs. The existing `/observations/new` behavior remains unchanged.

The aggregate form becomes a shared create/edit surface with mode-specific heading, breadcrumbs, primary action, submission call, cancellation destination, and success message. Existing field components, validation mapping, generated-ID behavior, and nested editors remain shared. Nested editors derive their return route from draft context instead of hard-coding `/observations/new`.

Separate copy-pasted edit forms were considered but rejected because they would allow validation and payload mapping to drift between create and update.

### 5. Add explicit collection actions without hidden topology repair

Each child card gains accessible Edit, Remove, Move up, and Move down controls when applicable; the existing Add actions remain. These operations only change the local ordered draft. Removing a Metric Lens does not mutate Relationships that reference it. Existing aggregate validation identifies each invalid Relationship and links the user back to its editor, preserving engineer-authored rule intent.

Persisted child IDs remain non-editable. Editing a retained Metric Lens therefore preserves its accepted History identity, even if other fields change. The Metric editor and removal affordance explain that users who intend a clean History boundary must remove the old Lens and add a new one, which receives a generated ID. Automatically regenerating IDs from changed fields was considered but rejected because the system cannot reliably infer semantic metric identity from provider-native configuration and silent regeneration would break references and continuity.

### 6. Keep update failure handling parallel to creation

Local validation blocks `Save changes` and uses the existing accessible issue summary, field association, section counts, and nested correction links. The update client maps backend field paths through the same mechanism as create. A save-time `404` has a distinct target-missing state; other validation or transport errors keep the complete draft. Success clears the draft and navigates to the read-only detail route with update confirmation.

The edit initialization request has independent loading, retryable error, and not-found states. A nested edit URL without a live matching draft returns to the parent edit route for canonical reload rather than constructing a partial draft.

## Risks / Trade-offs

- [Stable Lens IDs can join History across materially changed Metric configuration] → State this existing identity behavior in the edit UI and provide remove-plus-add as the explicit fresh-identity path.
- [Two editors can overwrite one another because no revision token is introduced] → Document last-successful-full-replacement behavior as an MVP limitation; keep optimistic concurrency as a later separately specified capability.
- [Collection reconciliation can accidentally retain omitted children or disturb order] → Cover mixed add/update/remove/reorder and transaction rollback with PostgreSQL integration tests for all three child collections.
- [Concurrent replacement can tear a multi-statement definition load] → Lock or snapshot the aggregate root for complete reads used by update and execution initialization, and add a focused concurrency/integration test where practical.
- [Shared create/edit UI can regress the established create flow] → Preserve create-route acceptance tests and add mode-specific tests around initialization, navigation, cancellation, payloads, and feedback.
- [Removing a Metric Lens can invalidate several Relationships] → Surface each invalid Relationship without silently repairing it; final save remains blocked until the draft is valid.

## Migration Plan

1. Deploy backend aggregate replacement support and its tests; no database migration is needed.
2. Deploy the frontend edit routes and controls after the endpoint is available.
3. Existing definitions require no data migration and become editable in place.
4. Rollback removes the frontend edit entry points and endpoint implementation; data written by replacement remains valid under the pre-change create/read schema.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`: conforms to Observation aggregate ownership, type-specific Lens collections, type-local IDs, Metric-only Relationships, and snapshot/replacement semantics.
- `docs/architecture/03_ADR_log.md` ADR-161 and ADR-163: retains dedicated owned child persistence, atomic mutation, physical removal of omitted Alert Lenses, and no standalone child lifecycle.
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: preserves forward-only immutable runtime records and keeps definition mutation outside runtime artifacts.
- `openspec/specs/observation-execution/spec.md`: keeps active runs isolated by loading and freezing one complete definition before runtime graph creation.
- `docs/ui/ui_implementation_handoff_v1.md` and `docs/ui/frontend_ui_stack_adr.md`: extends the existing Observation Management information architecture and project-owned component stack without adding unrelated controls or libraries.
