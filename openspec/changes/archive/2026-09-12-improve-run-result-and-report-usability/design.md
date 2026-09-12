## Context

See `proposal.md` for the observed usability defects. The backend already persists a strict structured analysis plus a deterministic Markdown report; the run-detail endpoint already returns all values needed for semantic Metric rendering and most evidence resolution. The current UI loses that structure by generically enumerating Metric evidence, reducing references to repeated source IDs, and displaying Markdown in a raw `<pre>` block.

The report renderer intentionally treats all model/source strings as untrusted, but its current reversible type encoding is optimized for machines rather than readers. This change must improve readability without allowing source text to own Markdown structure and without adding a Markdown library.

## Goals / Non-Goals

**Goals:**

- Make existing Metric, Analysis, and Report artifacts readable and inspectable from the unchanged run-detail response.
- Preserve exact persisted values and reference identities behind concise formatted presentation.
- Render the deterministic report subset safely with accessible semantic HTML and exact-copy access.
- Keep empty, unavailable, unknown, and explicit negative analytical states honest.

**Non-Goals:**

- Do not change analytical results, report-agent prose, overall-state selection, evidence/reference contracts, persistence, or APIs.
- Do not fetch current Observation definitions to recover Lens names that were not frozen into the run artifact.
- Do not infer why an optional Metric section is null or add an optional-tool execution history to the public result.
- Do not add charts, report export, arbitrary Markdown/HTML support, severity, confidence, recommendations, new navigation, or dependencies.
- Do not implement the separate `improve-observation-synthesis-quality` change.

## Decisions

### 1. Replace typed report literals with safe inline-code values

The deterministic renderer will format opaque identifiers as English-labeled inline code containing an exact reversible representation of the logical value. A small code-span encoder will represent structural control whitespace with visible escapes such as `\n`, preserve ordinary characters exactly, and choose a backtick fence longer than any backtick run in the value, so values remain inert and unambiguous without Python `ascii()` wrappers, type prefixes, or punctuation-wide escaping.

Locator segments will be rendered with conventional notation: safe identifier-like keys use dots, other keys use safely encoded bracketed strings, and integer indices use decimal brackets. Tests will prove exact segment preservation and containment of Markdown/HTML-like hostile values.

Model-authored presentation prose remains normalized and punctuation-escaped under renderer-owned blockquotes. This change does not allow the model to author headings, lists, links, or sections.

Alternative considered: remove escaping globally. Rejected because it would let untrusted model/source content alter document structure.

Alternative considered: keep the reversible typed encoding and hide it only in the browser. Rejected because copied Markdown is itself a user-facing artifact and should be readable outside the application.

### 2. Use explicit project-owned Metric presentation components

Run Detail will replace `Object.entries` rendering with explicit components for:

- current numerical evidence: mean, standard deviation, minimum, maximum, slope;
- current semantic state: trend direction/rate and variability;
- optional spike, oscillation, and stuck-signal sections;
- reference-period evidence and semantic comparison; and
- persisted History summary.

The primary title will use `result.identity.metric_ref` plus `unit`, both already frozen in the result. The Lens ID remains compact secondary text. This avoids joining against the mutable current Observation definition.

A shared run-detail number formatter will use a small bounded significant-digit policy, switch very small non-zero values to scientific notation, normalize negative zero, and never mutate source data. Symmetric relative change will be shown as a dimensionless value with an explicit label, together with current and reference means; it will not be multiplied and narrated as ordinary percentage increase.

Alternative considered: introduce a generic recursive JSON viewer. Rejected because it reproduces implementation structure instead of the accepted Metric semantics.

### 3. Resolve traceability locally with defensive path traversal

A pure frontend resolver will map `metric_result` references to the LensRun whose `id` equals `source_id`, and `relationship_evaluation` references to the matching relationship ID. It will traverse only own object properties and valid in-range array indices from the structured locator. Prototype keys, type mismatches, absent sources, and missing segments return an unavailable result rather than throwing.

Collapsed project-owned Evidence/Relationship controls will include a compact source label and locator. An accessible disclosure reveals exact source ID, full path, and a safely formatted scalar or compact structured value already present in the response. Knowledge chips remain separate and are not resolved as evidence.

Alternative considered: refetch provider data or current definitions. Rejected because it breaks run immutability, adds availability dependencies, and can display data different from the analyzed snapshot.

### 4. Parse only the safe renderer-owned Markdown subset

The frontend will use a small line-oriented parser owned by the Report feature. It recognizes renderer-produced ATX headings, paragraphs, blockquotes, unordered-list items, blank-line boundaries, and safe inline-code spans. Outside code spans it decodes only the standard backslash escapes emitted by the deterministic backend renderer, so escaped punctuation is displayed as prose while the persisted Markdown remains unchanged. It creates React elements with text children only; it never uses `dangerouslySetInnerHTML`, activates links, or interprets raw HTML.

Unrecognized constructs are retained as plain text in document order. Malformed inline-code fences fall back to text. The parser is intentionally not a general Markdown engine and adds no dependency. `Copy Markdown` continues to use the untouched persisted string.

Alternative considered: add `react-markdown` and a sanitizer. Rejected because the required subset is fixed and small, while dependency changes require separate approval and add unnecessary MVP surface.

Alternative considered: render a new report from `analysis` in the browser. Rejected because that would ignore the persisted report artifact and could diverge from its presentation prose.

This choice explicitly resolves the architecture backlog item for the MVP browser renderer. Implementation will record the decision in a new ADR entry: the browser renderer is project-owned, dependency-free, limited to the deterministic Markdown subset, inert for HTML/links/unsupported syntax, and never an analytical authority. Other report formats, export renderers, notifications, and a general-purpose Markdown engine remain open or deferred.

### 5. Synchronize architecture and version the accepted UI direction to v1.8

The architecture ADR log, open-decision backlog, README, and changelog will record the approved MVP browser-rendering decision before or with implementation. `docs/ui/README.md` and the living handoff will record v1.8 as a run-detail/report refinement: explicit Metric sections, bounded formatting, local traceability disclosure, safe formatted Markdown, exact copy, and meaning-oriented empty language. Information architecture and the existing six run-detail tabs remain unchanged.

## Risks / Trade-offs

- [A custom Markdown subset becomes a partial general parser] → Keep accepted constructs explicit, treat everything else as inert text, and test hostile/malformed input.
- [Readable identifiers weaken injection protection] → Use renderer-owned labels and safe code-span encoding; retain prose escaping and adversarial tests.
- [Formatted numbers hide meaningful precision] → Use bounded significant digits, preserve small non-zero slopes, and leave exact values unchanged in the API.
- [Local reference resolution encounters future source types] → Fail visibly as traceability unavailable and keep the finding/hypothesis visible.
- [Current run artifacts do not contain Lens display names] → Use frozen `metric_ref` rather than joining mutable definitions; an API snapshot enhancement requires a separate contract change.
- [Report and Analysis views remain partially repetitive] → This change improves presentation only; synthesis and narrative quality belong to the sequenced follow-up change.

## Migration Plan

1. Add backend renderer regression/adversarial tests, then implement readable safe identifiers, locators, and empty text.
2. Add pure frontend formatter, reference resolver, and safe Markdown-subset parser tests.
3. Replace the Metric, Analysis traceability, and Report views using project-owned semantic components.
4. Record the approved browser-rendering architecture decision and close only that open backlog item; update architecture package metadata.
5. Update UI Direction documentation to v1.8 and expand Run Detail tests for completed, empty, unavailable, hostile, and narrow-screen cases.
6. Run focused backend/frontend checks and `make check`.

No data migration or deployment configuration is required. Existing persisted reports remain readable through the parser's plain-text fallback; newly generated reports use the refined deterministic Markdown. Rollback is a code/UI documentation revert and does not alter stored analysis artifacts.

## Architecture References

- `docs/architecture/08_observation_analysis_result_contract.md`: the UI reads but does not reinterpret structured analytical artifacts.
- `docs/architecture/09_report_agent.md`: Markdown remains the persisted human-readable format and Report remains presentation-only.
- `docs/architecture/03_ADR_log.md`: ADR-086/087 retain the report envelope and separation; ADR-167 requires accepted UI versioning.
- `docs/architecture/10_open_decisions_and_backlog.md`: this change resolves only the MVP browser-renderer choice; export, notification, and other renderer decisions remain outside scope.
- `docs/ui/frontend_ui_stack_adr.md`: React, project-owned semantic components, and the existing stack are retained without a new dependency.
- `docs/ui/ui_implementation_handoff_v1.md`: v1.8 refines Run Detail presentation without changing its information architecture or semantic boundaries.

The design creates one explicitly approved architecture decision for the browser presentation adapter while leaving Markdown as the persisted artifact and all analytical ownership unchanged. It creates no new analytical meaning, persistence truth, provider access, export format, or notification behavior.
