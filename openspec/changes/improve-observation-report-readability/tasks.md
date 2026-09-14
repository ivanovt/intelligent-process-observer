## 1. Architecture boundary

- [x] 1.1 Confirm the report request and projector design admit only the exact UTC window approved by ADR-175, alongside existing semantic context; verify no full run snapshot, Lens result, or current-definition lookup crosses the Report Agent boundary.

## 2. Correlated report context

- [x] 2.1 Extend the strict report request with a reporting-owned exact UTC observed window and validate identity, UTC, and positive duration; verify focused request tests reject missing, non-UTC, reversed, zero-length, and undeclared input.
- [x] 2.2 Project the window from the immutable execution snapshot without a current-definition lookup or rounding; verify stage/projector tests preserve exact boundaries and the existing typed failure behavior.

## 3. Source-keyed presentation

- [ ] 3.1 Extend the strict presentation draft with a neutral English objective summary and source-keyed finding headings/order, including absent-objective behavior; verify exact-key, duplicate, unknown-field, blank-text, and source-coverage tests.
- [ ] 3.2 Refine the single-request Report Agent guidance and representative adversarial cases for objective-first assessment, material auxiliary events, conflicting references, uncertainty, no-significant-findings, concise finding prose, and possible explanations; verify no new analytical claim, ranking, recommendation, tool, retry, or second request is accepted.

## 4. Deterministic Markdown presentation

- [ ] 4.1 Render the readable header with neutral objective summary when supplied, exact UTC window, human analytical-state label, and short Observation ID excerpt; verify full identities, exact state, and generated time remain in technical details and no excerpt is treated as unique.
- [ ] 4.2 Render numbered, source-grounded finding headings and concise narratives in validated objective-first order, followed by distinct possible explanations and limitations; verify every source item appears once, supported-by finding-number mappings are exact, and empty collections remain honest.
- [ ] 4.3 Render a final technical appendix grouped by finding and exact source pair, with full source-ID mappings, every locator including repeated entries, and separate hypothesis knowledge references; verify multi-source, repeated-reference, and reordered-finding cases preserve exact ownership.
- [ ] 4.4 Replace blanket prose punctuation escaping with context-safe rendering inside deterministic Markdown structure; verify copied ordinary prose has no blanket backslashes and hostile Markdown, HTML-like text, links, backticks, and controls remain inert.

## 5. End-to-end compatibility

- [ ] 5.1 Verify representative completed reports for populated, empty, uncertain, and mixed-reference analyses through the report stage, including snapshot window correlation and unchanged report persistence/envelope behavior.
- [x] 5.2 Verify the existing browser safe-subset view renders the new headings, paragraphs, lists, and inline code safely and Copy Markdown still returns the exact persisted string; add focused frontend compatibility coverage only if the current tests do not cover the changed output.

## 6. Final local verification

- [ ] 6.1 Run `make check` and record its actual result before archive or pull-request preparation.
