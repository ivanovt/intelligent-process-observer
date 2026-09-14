## Context

See [proposal.md](proposal.md) for motivation and the delta specifications for acceptance behavior. The existing run-detail page already has independently accessible Evidence and Relationship disclosures and uses a two-column CSS grid for Summary cards. The report pipeline persists deterministic Markdown, while the browser renders only a dependency-free safe subset and copies the stored source unchanged.

## Goals / Non-Goals

**Goals:**

- Reduce visual noise around dense finding traceability without withholding any available evidence.
- Preserve compact Summary-card scanning when limitations are short.
- Improve factual scanability of generated reports through renderer-owned Markdown and safe semantic strong rendering.

**Non-Goals:**

- Change APIs, report data structures, source finding prose, analytical meaning, or traceability resolution.
- Fetch extra provider data, add a Markdown dependency, or support general Markdown.
- Retroactively rewrite persisted reports; only reports rendered after this change receive newly generated emphasis markup.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`: public run detail is a coherent durable projection; report generation remains a presentation artifact over approved analysis inputs only.
- `docs/ui/frontend_ui_stack_adr.md` (ADR-167): preserve accepted UI authority and project-owned components.
- `docs/ui/ui_implementation_handoff_v1.md`, Run Detail v1.8: reference disclosures are locally resolved from the immutable response, and report rendering is text-only, safe, dependency-free, and exact-copy.

The design neither changes the strict artifact contracts nor introduces state or lifecycle semantics.

## Decisions

### One collapsed `References` group per finding

The Analysis finding card will add a native, labelled `details` disclosure around its Evidence and Relationship controls. It starts closed. Existing per-reference disclosures remain the resolution and accessibility boundary inside it, so source label, compact ID, path, locally resolved value, and unavailable state behavior stay unchanged.

This uses native disclosure semantics rather than custom React state or a new primitive. It is keyboard-accessible, requires no dependency, and maintains the v1.8 on-demand inspection rule. A single flattened chip row was rejected because it recreates the visual density shown in the reported problem; collapsing all individual resolution details into one panel was rejected because users must still inspect references independently.

### Content-driven Summary cards

The Summary grid will align cards to the start of their grid area so the availability/limitations article keeps intrinsic height while the Key findings article grows independently. Responsive column behavior and card order remain unchanged.

This small layout-level change avoids a bespoke card variant and preserves the existing semantic warning presentation. Moving limitations below Key findings was rejected because it would alter the established Summary information order.

### Renderer-owned strong emphasis only

The backend deterministic report renderer will emit valid `**…**` markers only around factual tokens it itself owns, including displayed finding numbering and deterministic factual/traceability values. It will continue escaping model-authored presentation prose before that prose enters a renderer-owned blockquote. The safe frontend parser will recognize only balanced `**text**` spans alongside its existing inline-code parsing and construct `<strong>` elements from text children.

This keeps Markdown structure owned by deterministic code, avoids fragile browser heuristics over arbitrary model prose, and guarantees that copied Markdown is the persisted artifact. General Markdown parsing and server-side HTML rendering were rejected for safety and dependency scope reasons.

### Backward-compatible report display

Reports without valid emphasis markers remain readable exactly as they do today. Malformed or unsupported marker use remains inert visible text. Newly generated reports include the safe supported formatting; existing persisted report rows are not migrated or rewritten.

## Risks / Trade-offs

- [A collapsed group can conceal evidence at first glance] → The visible `References` summary provides an explicit affordance, and finding statements remain fully visible.
- [Nested native disclosures require clear labels] → Retain concise per-reference summaries and use the outer `References` label only for the collection.
- [Strong Markdown could be interpreted too broadly] → Parse only balanced renderer-owned syntax with text-only React children; leave malformed/raw content inert.
- [Only deterministic facts can be reliably emphasized] → Do not infer formatting from untrusted model prose; this preserves report safety and the analytical-content boundary.

## Migration Plan

1. Deploy frontend and renderer changes together; no database migration is needed.
2. Existing reports continue through the safe fallback parser and retain exact-copy behavior.
3. Roll back by reverting the code change; persisted reports remain valid plain Markdown and no stored data must be transformed.
