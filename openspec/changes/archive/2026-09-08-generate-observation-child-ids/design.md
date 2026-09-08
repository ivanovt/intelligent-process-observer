## Context

See `proposal.md` for motivation and `specs/observation-management-ui/spec.md` for observable behavior. The three nested Observation editors currently expose writable ID inputs and initialize new child IDs as empty strings. Their working values remain editor-local until Apply, while opaque `clientKey` values own draft routing and replacement independently of domain IDs.

The public aggregate contract still requires valid, stable string IDs; Metric and Alert uniqueness remains type-local, and Relationship participants refer to applied Metric IDs. The change therefore belongs at the frontend draft/editor boundary and must not alter backend identity, persistence, or routing semantics.

UI Direction v1.2 retains manual identifier entry while adding read-only Data Sources visibility, so this behavior is an approved meaningful UX evolution to UI Direction v1.3 rather than a minor implementation adjustment. The mainline persistence models store Lens and Relationship IDs in 255-character columns even though the public validation contract currently expresses only their syntax; generation must honor the narrower end-to-end boundary.

## Goals / Non-Goals

**Goals:**

- Use one pure generator for consistent Metric, Alert, and Relationship ID syntax.
- Make generation deterministic under an injected or explicit timestamp so boundary behavior is easy to test.
- Preserve editor-local cancel/apply isolation and type-local collision rules.
- Keep generated and existing IDs stable after their first assignment.
- Keep every generated ID within the existing 255-character persistence boundary.

**Non-Goals:**

- Generate Observation IDs or change backend-generated aggregate identity.
- Change public ID syntax, uniqueness boundaries, child routes, persistence, or Relationship topology.
- Backfill or rewrite IDs of existing definitions or already-applied draft children.
- Add editable overrides, random UUIDs, transliteration libraries, or new dependencies.

## Decisions

### 1. Generate once on the first qualifying name blur

Each editor updates the human-readable name normally. On name blur, it generates an ID only when the trimmed name is non-empty and the editor-local ID is still empty. This lets the user finish the initial name before deriving a readable prefix. Subsequent blur events do nothing because the assigned ID is the stability guard. Existing draft children enter the editor with a non-empty ID and therefore follow the same preservation rule without a separate edit mode.

Alternative considered: regenerate on every name change. That would make the ID appear sooner, but it would couple stable identity to later display-name edits and could invalidate Relationship participant references. Generating from the first typed character was also rejected because it produces poor prefixes.

### 2. Use exact contract-safe normalization plus a compact base-36 timestamp

A pure helper accepts the name, child type, sibling IDs, and generation time. It applies built-in NFKD Unicode decomposition, removes combining marks, lowercases the result, collapses remaining sequences outside ASCII `a-z0-9` to underscores, and trims boundary underscores. For example, `Crème Pressure` becomes `creme_pressure`; scripts or symbols that leave no leading ASCII lowercase letter use the child-type fallback. It appends `generationTimeMilliseconds.toString(36)` as the compact timestamp-derived suffix.

The helper takes time as an argument; editor event handlers supply the current time, while tests supply a fixed value. This keeps runtime behavior simple and tests deterministic without adding an ID or date library.

Alternative considered: a formatted UTC timestamp. It is recognizable but substantially longer without improving the Observation-local identity contract. A UUID would avoid time coupling but would lose the requested readable name component and is unnecessary because the browser serializes only local aggregate children.

### 3. Enforce the persistence length boundary while resolving scoped collisions

The generator reserves room for the underscore and complete base-36 timestamp, truncating only the normalized prefix so the initial candidate is at most 255 characters. It compares that candidate with current sibling IDs from only the appropriate collection. On collision it appends `_2`, then increments until it finds an unused valid value; on each attempt it recalculates available prefix space so the timestamp and complete discriminator are never truncated. Metric generation reads Metric siblings, Alert generation reads Alert siblings, and Relationship generation reads Relationship siblings. This guarantees that a read-only generated value is locally usable and persistence-compatible while preserving accepted Metric/Alert cross-type equality.

Alternative considered: rely on existing Apply validation. That could leave the user with an uneditable invalid ID, so generation must avoid collisions before validation.

### 4. Version the accepted UI direction with the behavior

Implementation updates the current-direction declarations in `docs/ui/README.md`, `docs/ui/ui_implementation_handoff_v1.md`, `docs/ui/frontend_ui_stack_adr.md`, and `AGENTS.md` from v1.2 to v1.3. The handoff records generated read-only child identity as an intentional exception to the earlier manually editable controls. The visual stack, v1.2 screen set including Data Sources, aggregate draft ownership, UI authority order, and all domain semantics remain unchanged. Historical statements about v1.1 and v1.2 remain historical and do not need rewriting.

Alternative considered: treat generation as an accessibility or browser adjustment. It changes who owns identifier choice and is therefore too meaningful to fit the existing minor-adjustment allowance.

### 5. Keep the ID input focusable, copyable, and serialized normally

The existing ID input remains in the identity section but uses the HTML read-only state rather than the disabled state. Its description explains that it is generated from the initial name and remains stable. Read-only keeps the value available to assistive technology, selection/copy, validation targeting, and the unchanged draft serializer.

Alternative considered: hide the ID. The ID remains useful for Relationship configuration and troubleshooting, and hiding it would reduce transparency around the persisted aggregate identity.

## Risks / Trade-offs

- **[A generated ID is longer than a hand-authored ID]** → Use compact base-36 time and truncate only its readable prefix to honor the existing 255-character persistence boundary.
- **[A non-Latin or symbol-led name cannot provide a valid contract prefix]** → Use a type-specific fallback while retaining the timestamp-derived uniqueness component.
- **[Two generations can receive the same millisecond value]** → Check the relevant current collection and append a deterministic numeric discriminator, recalculating prefix space as needed.
- **[A generated local ID exists before Apply]** → Keep it only in editor-local state so Cancel preserves the aggregate byte-for-byte.

## Migration Plan

No data or API migration is required. Deploy the UI Direction v1.3 documentation and frontend behavior together with their tests. Rollback restores the v1.2 manual-ID guidance and writable fields; persisted definitions and current drafts remain contract-compatible because their ID shape is unchanged.

## Architecture References

- `docs/architecture/01_observation_lens_concept.md`: the design preserves stable Lens correlation, type-local Metric/Alert identity, and Metric-only Relationship participation.
- `docs/architecture/05_relationship_evaluator_concept.md`: Relationship IDs and participant Lens IDs remain unchanged contract values after generation.
- `docs/architecture/03_ADR_log.md` (ADR-161 and ADR-162): the generator respects accepted type-aware Lens identity and reuses the canonical Lens ID primitive without adding a discriminator to the domain model.
- `docs/architecture/03_ADR_log.md` (ADR-167): the v1.3 evolution preserves the accepted UI authority order and does not treat MagicPath parity as an implementation gate.
- `docs/ui/README.md`: the design follows the required explicit UI version evolution for a meaningful UX change.
- `docs/ui/ui_implementation_handoff_v1.md`: UI Direction v1.3 will retain the nested aggregate workflow and v1.2 Data Sources behavior while replacing manual child-ID entry with the approved generated, read-only interaction.
- `docs/ui/frontend_ui_stack_adr.md`: current-direction references will move to v1.3 without changing the ADR's accepted technology decision or its historical UI-version statements.
