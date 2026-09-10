## 1. Backend Aggregate Replacement

- [x] 1.1 Add the `PUT /api/v1/observations/{observation_id}` route and service boundary using the validated create-shaped aggregate body, and verify API tests cover `200`, response identity preservation, `404`, and request-field rejection.
- [x] 1.2 Implement transaction-owned repository reconciliation for Observation metadata and all ordered Metric Lens, Alert Lens, and Relationship collections by public child ID, and verify PostgreSQL integration tests cover retained, added, removed, and reordered children without orphan rows.
- [x] 1.3 Add coherent definition read/write locking or equivalent snapshot behavior for replacement and execution initialization, and verify focused integration tests show a run receives either the complete pre-update or complete post-update aggregate.
- [x] 1.4 Verify atomic rollback when source validation, aggregate validation, or persistence fails and confirm tests leave the complete pre-update definition unchanged.
- [x] 1.5 Run the focused backend Observation API, persistence, and execution-initialization test suites and verify all existing create/read/run behavior still passes.

## 2. Frontend Draft and Routing Foundation

- [x] 2.1 Add the typed aggregate update client call and reusable response-to-draft hydration that strips links/runtime-only values while preserving domain order and public child IDs; verify unit tests assert the exact `PUT` URL, method, and payload.
- [x] 2.2 Generalize the draft provider for create and edit modes, matching target identity, canonical initialization, child removal, and ordered movement; verify reducer/provider tests cover initialization, add/edit/remove/reorder, clearing, and unchanged create defaults.
- [x] 2.3 Add `/observations/:observationId/edit` and its nested child routes, make nested editors derive their parent return route from context, and verify routing tests cover Apply, Cancel, browser back, refresh/direct-entry recovery, and zero nested HTTP writes.

## 3. Observation Editing Experience

- [x] 3.1 Add distinct Edit actions to definition rows and read-only detail, and verify UI tests navigate the correct Observation identity without adding Delete or runtime controls.
- [x] 3.2 Build the shared mode-aware aggregate form and edit initialization states, and verify tests cover loading, retryable failure, not found, exact persisted draft population, top-level cancellation, and create-flow regression behavior.
- [x] 3.3 Add accessible Edit, Remove, Move up, and Move down controls for all supported child collections, preserve existing IDs, and show the Metric History identity guidance; verify interaction tests cover full-field editing, order, new generated IDs, retained legacy IDs, and explicit removal.
- [x] 3.4 Keep Relationships unchanged when a referenced Metric Lens is removed and surface linked validation errors, and verify no update request is sent until every affected Relationship is repaired or removed.
- [x] 3.5 Implement final `Save changes` validation, one-request submission, field-path error mapping, draft retention, save-time not-found handling, and success navigation/confirmation; verify tests assert no standalone child calls and no create fallback.

## 4. Integrated Verification

- [x] 4.1 Run focused frontend Observation tests plus production build and verify the complete create flow and new full-edit flow both pass.
- [x] 4.2 Run strict OpenSpec validation for `enable-observation-editing` and verify both modified capability deltas remain structurally valid.
- [x] 4.3 Run `make check` as the final local gate and report every failure accurately before archive or pull-request preparation.
