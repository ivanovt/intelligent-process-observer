## 1. Human-readable deterministic reports

- [ ] 1.1 Add failing report-presentation tests for readable exact UUID/string identifiers, reversible control-whitespace representation, decimal locator paths, meaning-oriented empty hypotheses/limitations, and hostile identifier/locator containment; verify current typed encodings and empty copy fail the new expectations.
- [ ] 1.2 Implement safe inline-code identity/reference encoding and conventional locator formatting without weakening renderer-owned structure; verify all report presentation, policy, and adversarial tests pass and exact traceability membership is unchanged.

## 2. Semantic Metric result presentation

- [ ] 2.1 Add failing frontend tests for explicit numerical/semantic/optional Metric sections, formatted small non-zero slopes, metric-ref/unit identity, symmetric relative-change wording with both means, and honest null/unknown/absent states; verify no fixture can pass through generic object stringification.
- [ ] 2.2 Implement project-owned Metric result components and bounded number formatting using only the existing run-detail payload; verify `[object Object]`, literal null, false percentage interpretation, and mutable-definition joins are absent from the rendered view.
- [ ] 2.3 Add and verify responsive/accessibility coverage for Metric cards and optional-result groups, including text labels independent of color and readable narrow-screen ordering.

## 3. Inspectable analysis traceability

- [ ] 3.1 Add pure resolver tests for Metric and Relationship source lookup, own-property/array-index traversal, conventional locator labels, duplicate-source/different-locator distinction, and missing/hostile/prototype-key rejection.
- [ ] 3.2 Implement accessible project-owned Evidence and Relationship disclosure controls that show compact source/path labels and exact IDs/resolved values on demand; verify Knowledge references remain separate and unresolved references preserve their owning findings with explicit unavailable feedback.

## 4. Safe formatted Report view

- [ ] 4.1 Add failing parser/component tests for renderer-owned headings, paragraphs, blockquotes, lists, inline code, renderer-emitted backslash-escape display, exact persisted-copy behavior, malformed/unsupported fallback, raw HTML containment, and inert Markdown links.
- [ ] 4.2 Implement the dependency-free line-oriented safe Markdown subset renderer and replace the raw preformatted Report block; verify it uses text children only, preserves document order/content, supports legacy fallback, and never uses `dangerouslySetInnerHTML` or active links.
- [ ] 4.3 Replace persistence-oriented completed-state copy across Analysis/Report/empty run sections with accepted meaning-oriented language; verify empty, unavailable, active, failed, and cancelled states remain distinct.

## 5. Architecture, UI direction, and verification

- [ ] 5.1 Add the approved dependency-free safe browser-renderer decision to the architecture ADR log, close only the corresponding renderer item in the open-decision backlog, and update architecture README/changelog package metadata; verify Markdown persistence, report-agent boundaries, export, notifications, and other renderer decisions remain unchanged.
- [ ] 5.2 Update `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` to UI Direction v1.8 with the approved Metric, traceability, report-rendering, exact-copy, safety, and non-goal boundaries; verify no information architecture or domain semantics changed.
- [ ] 5.3 Run focused backend report tests and frontend Run Detail/formatter/resolver/parser tests, then inspect the completed run `b0ddf4df-f220-4955-8b87-36c3f10c8a4e` through the UI to verify readable values, traceability, empty language, and report formatting without exposing trace artifacts.
- [ ] 5.4 Run `make check` as the final local verification step and verify Ruff, backend tests, frontend lint/tests/build, and strict OpenSpec validation all pass before implementation review, archive, and pull-request preparation.
