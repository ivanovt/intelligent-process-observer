## 1. Current Main Reconciliation

- [x] 1.1 Merge current `origin/main`, inventory and resolve every overlapping production, test, specification, and governance file, preserve v1.2 Data Sources behavior/navigation and ADR-167 UI authority, verify the generated-ID implementation against the combined tree, and reopen any completed implementation task whose assumptions changed.

## 2. ID Generation

- [x] 2.1 Add a pure Observation-child ID generator that applies the specified NFKD/combining-mark/ASCII normalization, type-specific fallbacks, and explicit base-36 millisecond timestamp; truncate only the prefix to preserve the 255-character limit while resolving collisions within a supplied sibling-ID set.
- [x] 2.2 Add focused unit tests for readable normalization, decomposable Latin diacritics, symbol/non-Latin fallbacks, contract-valid output, deterministic timestamps, exact 255-character boundaries, long-prefix collision discriminators, and type-scoped sibling inputs.

## 3. Nested Editor Integration

- [x] 3.1 Update the Metric Lens and Alert Lens editors to generate an ID on the first qualifying name blur, render the ID read-only, preserve it through later name edits and existing-child edits, and continue using the current type-local sibling collection.
- [x] 3.2 Update the Relationship editor with the same one-time read-only generation behavior using Relationship siblings, without changing participant or descriptor semantics.
- [x] 3.3 Reconcile rendered editor and create-flow tests with current `main`, retaining coverage for blank-name behavior, initial generation, read-only presentation, stability after renaming/reopening, type-scoped collision handling, cancellation isolation, Apply behavior, and exact unchanged aggregate serialization boundaries.

## 4. UI Direction Documentation

- [x] 4.1 Update `docs/ui/README.md`, `docs/ui/ui_implementation_handoff_v1.md`, `docs/ui/frontend_ui_stack_adr.md`, and the current UI-direction guidance in `AGENTS.md` to identify UI Direction v1.3 and document generated, read-only, stable Metric Lens, Alert Lens, and Relationship IDs; preserve the accepted frontend stack, UI authority order, historical v1.1/v1.2 statements, Data Sources behavior, and all existing semantic boundaries.

## 5. Verification

- [x] 5.1 Run focused frontend tests for the generator, all three nested editors, and the aggregate create flow after current-main reconciliation, including 255-character and collision-after-truncation boundaries; resolve failures within the approved behavior.
- [x] 5.2 Run `make check` as the final local verification and report any failure accurately before re-archive and pull-request update work.
