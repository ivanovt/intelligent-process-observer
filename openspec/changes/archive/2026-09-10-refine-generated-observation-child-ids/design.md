## Context

See `proposal.md` for motivation. Observation Management already generates child IDs in editor-local state when the initial non-empty Name field loses focus. The shared generator currently combines a normalized name with a base-36 millisecond timestamp, while each editor renders the result in a separate read-only input. The public API accepts the broader `^[a-z][a-z0-9_-]*$` grammar, limits persisted values to 255 characters, and scopes Metric and Alert uniqueness separately.

This change is an intentional UI Direction update but does not require a public API or persistence migration. Existing draft values may predate the new format and must remain opaque, stable identities.

## Goals / Non-Goals

**Goals:**

- Give every newly UI-generated child ID an immediately recognizable type prefix.
- Retain a readable normalized-name component and a compact random collision-resistant component.
- Reduce form hierarchy by presenting generated identity as metadata associated with Name rather than as a form input.
- Keep generation deterministic under injected test randomness and preserve current stability, length, uniqueness, cancellation, and aggregate-draft boundaries.

**Non-Goals:**

- Enforcing typed prefixes in backend request validation or changing canonical API identity semantics.
- Rewriting existing IDs, updating persisted Observations, or changing runtime identity references.
- Changing Observation IDs, LensRun IDs, findings, hypotheses, or other identity families.
- Adding copy controls, editable overrides, new dependencies, standalone child operations, or server-side ID generation.

## Decisions

### 1. Generate typed IDs only for new UI draft children

The shared generator will map the existing child kinds to fixed prefixes: `metric -> metr`, `alert -> alrt`, and `relationship -> rel`. It will construct `<prefix>_<normalized-name>_<random-part>` and retain the existing rule that generation occurs only when the editor-local value has no ID.

This keeps the improvement at the boundary the user is changing and avoids a breaking API restriction. Tightening backend validation was considered but rejected because accepted contracts permit broader IDs and existing callers or persisted definitions may use them.

### 2. Use eight UUID-derived lowercase hexadecimal characters as the random part

The generator will accept or obtain browser-provided randomness from `crypto.randomUUID()`, remove separators, and use eight lowercase hexadecimal characters. Tests will inject a known random value rather than mock wall-clock time. Eight characters keep the identifier compact; the existing explicit collision loop remains the correctness backstop within the relevant collection.

Keeping the timestamp was considered but rejected because it does not satisfy the requested random component and exposes creation-time information. Embedding a full UUID was considered but rejected as visually noisy for secondary UI metadata.

### 3. Preserve normalization, scoped collision handling, and the 255-character bound

The existing Unicode decomposition and ASCII-safe slug normalization remains. A normalized name without a leading ASCII letter becomes `item`, since the type is already represented separately. Length calculation reserves space for the type prefix, separators, complete random part, and any `_N` collision discriminator, truncating only the name segment.

Collision lookup remains type-local for Metric and Alert Lenses and collection-local for Relationships. Typed prefixes make cross-type collisions unlikely, but they do not redefine the backend's accepted type-local identity semantics.

### 4. Render identity metadata with the Name field, not as a disabled control

Each editor will give Name the available identity-row width and render the generated or preserved value as subdued text adjacent to the Name label, formatted `(id: <value>)`. The text remains selectable and is part of the accessible label/guidance structure; it is not focusable as a redundant input. Before generation, helper text explains that an ID is created after the initial non-empty name is entered.

A disabled input was considered but rejected because it still presents metadata as a form field and may reduce readability or selectability. Hiding the ID entirely was rejected because the ID remains useful traceability information in Relationship participant selection and runtime artifacts.

### 5. Update UI Direction to v1.5 without changing architecture documents

`docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` will record the typed composition and compact metadata presentation as UI Direction v1.5. Architecture documents remain unchanged because aggregate ownership, public identity grammar, uniqueness, and runtime identity are preserved.

## Risks / Trade-offs

- [Eight hexadecimal characters can collide] → Keep same-collection collision detection and numeric discrimination; tests cover repeated random output.
- [Legacy and new IDs look different] → Treat IDs as opaque after generation and explicitly preserve legacy values without reformatting.
- [Removing the input can weaken discoverability or accessibility] → Keep visible `(id: ...)` text adjacent to Name, maintain generation guidance, and assert accessible text and absence of an editable ID control.
- [Very long names could displace fixed components] → Calculate the name budget after reserving all fixed components and collision suffixes, preserving the 255-character contract.

## Migration Plan

Deploy the frontend and UI documentation together. No database or API migration is required. Existing Observations and already-applied draft children retain their IDs; only IDs first generated by the updated UI use the new format. Rollback restores the prior generator and presentation for future draft children without changing identities already persisted under either format.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md` — preserves aggregate ownership, type-local Lens identity, and type-aware runtime correlation.
- `docs/architecture/03_ADR_log.md` (ADR-167) — applies the accepted authority order by versioning the intentional UI evolution through `docs/ui/` and OpenSpec without changing domain contracts.
- `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` — current UI Direction v1.4 and generated-child identity presentation to be advanced to v1.5.
