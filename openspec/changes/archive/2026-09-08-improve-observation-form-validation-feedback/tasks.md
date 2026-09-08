## 1. Shared Feedback Primitives

- [x] 1.1 Add semantic notice/error surface and border tokens, then extend `InlineNotice` with consistent `info`, `warning`, `error`, and `success` icons, styling, and roles.
- [x] 1.2 Enhance `Field` so invalid controls receive destructive border/focus styling and a concise `CircleAlert` message while retaining helper text and accessible descriptions without independent assertive announcements.
- [x] 1.3 Add a reusable focusable `ValidationSummary` that renders an ordered issue count and available field, section, or correction links.
- [x] 1.4 Add focused primitive tests covering every notice tone, invalid field styling and associations, summary semantics, and link rendering.

## 2. Create Observation Feedback

- [x] 2.1 Separate continuously computed pre-submit Review readiness from the latest explicit Create/API validation result, then normalize only explicit blocking paths into one ordered issue collection with General, Metric lenses, Alert lenses, Relationships, and Review ownership.
- [x] 2.2 Show and focus the validation summary after invalid Create attempts, retain field/child correction associations, and add independent issue-count badges to the sticky configuration navigation.
- [x] 2.3 Consolidate Definition Summary into mutually exclusive incomplete, blocking, and ready states without rendering the aggregate Lens requirement twice, and prevent live Review readiness from overriding retained explicit blocking state before revalidation.
- [x] 2.4 Add Create Observation tests for neutral pre-submit Review guidance, explicit-summary focus and counts, field and child links, section badges combined with active selection, duplicate-message removal, retained-until-revalidation errors, corrected-but-not-revalidated values showing no conflicting success, retained draft, and field-specific API rejection.

## 3. Nested Editor Feedback

- [x] 3.1 Add focused invalid-Apply summaries and focus behavior to Metric Lens and Alert Lens editors without changing validation, draft mutation, or request behavior.
- [x] 3.2 Add the same invalid-Apply summary to Relationship configuration and apply icon-plus-invalid treatments to participant and descriptor groups.
- [x] 3.3 Apply icon-plus-invalid treatment, persistent descriptions, programmatic error associations, and non-assertive field/group messages to Metric objective choices, shared Alert analysis objectives, shared reference periods, Relationship participants, and Relationship descriptor rows.
- [x] 3.4 Add nested-editor tests for summary focus/counts, every Field and repeatable/choice group association, retained-until-revalidation feedback, and unchanged Cancel/Apply/no-write behavior.

## 4. Observation Management Notice Audit

- [x] 4.1 Classify every existing Observation-management information, limitation, success, and transport-failure notice into the accepted semantic tones without changing message meaning, retry/correction actions, or draft retention.
- [x] 4.2 Add call-site regressions for list failure/retry, detail failure/retry, distinct not-found absence, capability failure/retry, empty Metric-source warning, unmapped create failure with retained draft, and successful-create confirmation.

## 5. Verification

- [x] 5.1 Run all frontend tests, ESLint, the frontend production build, strict change validation, and `git diff --check`.
- [x] 5.2 Run `make check` as the final local verification before archive or pull-request preparation.
