## 1. Typed Child ID Generation

- [x] 1.1 Replace timestamp-based Observation-child ID composition with the approved `metr|alrt|rel` prefix, normalized-name segment, and eight-character UUID-derived random part while preserving scoped collision discrimination and the 255-character limit; verify focused draft generator tests cover all three types, normalization/fallback, stability inputs, collisions, and long names.
- [x] 1.2 Update Metric Lens, Alert Lens, Relationship, and aggregate-flow test fixtures to inject or match random typed IDs and verify serialized payloads preserve those IDs without changing backend contracts.

## 2. Compact Identity Presentation

- [x] 2.1 Replace the separate read-only ID inputs in all three nested editors with accessible `(id: <value>)` metadata adjacent to Name, retain pre-generation guidance, and preserve existing IDs on reopen; verify focused component tests assert generated, blank, renamed, legacy, and cancelled states plus the absence of ID form controls.
- [x] 2.2 Check the three editor layouts at their existing desktop and narrow responsive breakpoints, correcting wrapping and overflow within the accepted visual system; verify the Name/ID identity remains readable without changing form semantics or adding controls.

## 3. UI Direction and Verification

- [x] 3.1 Advance `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` to UI Direction v1.5 with the typed generated-ID format, compact Name-associated presentation, legacy-ID preservation, and unchanged API/aggregate boundaries; verify documentation no longer prescribes a read-only ID input or timestamp component.
- [x] 3.2 Run focused frontend tests for Observation draft generation and all three nested editors, then run `make check`; report every result accurately and leave backend, persistence, dependencies, and architecture documents unchanged.
