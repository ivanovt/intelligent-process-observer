## 1. Run-detail presentation

- [x] 1.1 Group each finding's Evidence and Relationship reference controls under a collapsed, accessible `References` disclosure, retaining individual local-resolution controls and empty-reference behavior; verify with focused RunDetailPage tests.
- [x] 1.2 Align Summary grid cards to their intrinsic content heights so a short availability/limitations card does not stretch beside Key findings; verify with a Summary layout regression test or DOM assertion.

## 2. Safe report emphasis

- [x] 2.1 Mark deterministic report finding numbers and renderer-owned factual values with valid strong Markdown while preserving escaped model prose and report content semantics; verify with report-presentation unit tests.
- [x] 2.2 Extend the dependency-free safe Markdown renderer to produce semantic strong text for valid emphasis and inert fallback for malformed input, preserving inline code and exact-copy behavior; verify with SafeMarkdownReport and RunDetailPage tests.

## 3. Verification

- [x] 3.1 Run targeted backend and frontend tests for report generation and run-detail presentation, then run `make check`; verify all commands pass before archive or pull request.
