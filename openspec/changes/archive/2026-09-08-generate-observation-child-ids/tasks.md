## 1. ID Generation

- [x] 1.1 Add a pure Observation-child ID generator that applies the specified NFKD/combining-mark/ASCII normalization, type-specific fallbacks, and explicit base-36 millisecond timestamp; truncate only the prefix to preserve the 255-character limit while resolving collisions within a supplied sibling-ID set.
- [x] 1.2 Add focused unit tests for readable normalization, decomposable Latin diacritics, symbol/non-Latin fallbacks, contract-valid output, deterministic timestamps, exact 255-character boundaries, long-prefix collision discriminators, and type-scoped sibling inputs.

## 2. Nested Editor Integration

- [x] 2.1 Update the Metric Lens and Alert Lens editors to generate an ID on the first qualifying name blur, render the ID read-only, preserve it through later name edits and existing-child edits, and continue using the current type-local sibling collection.
- [x] 2.2 Update the Relationship editor with the same one-time read-only generation behavior using Relationship siblings, without changing participant or descriptor semantics.
- [x] 2.3 Update rendered editor and create-flow tests to cover blank-name behavior, initial generation, read-only presentation, stability after renaming/reopening, type-scoped collision handling, cancellation isolation, Apply behavior, and exact unchanged aggregate serialization boundaries.

## 3. UI Direction Documentation

- [x] 3.1 Update `docs/ui/README.md`, `docs/ui/ui_implementation_handoff_v1.md`, `docs/ui/frontend_ui_stack_adr.md`, and the current UI-direction guidance in `AGENTS.md` to identify UI Direction v1.2 and document generated, read-only, stable Metric Lens, Alert Lens, and Relationship IDs; preserve the accepted frontend stack, historical v1.1 introduction statements, and all existing semantic boundaries.

## 4. Verification

- [x] 4.1 Run focused frontend tests for the generator, all three nested editors, and the aggregate create flow, including 255-character and collision-after-truncation boundaries; resolve failures within the approved behavior.
- [x] 4.2 Run `make check` as the final local verification and report any failure accurately before archive or pull-request work.
