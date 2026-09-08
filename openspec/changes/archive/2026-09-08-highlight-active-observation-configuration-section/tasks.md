## 1. Active Section Navigation

- [x] 1.1 Add local active-section state and animation-frame-coalesced scroll/resize tracking for the five Create Observation sections, including top and document-bottom handling.
- [x] 1.2 Connect native section-anchor activation to the active state and render exactly one token-styled link with `aria-current="location"`.

## 2. Verification

- [x] 2.1 Add focused component tests for the initial General state, immediate click selection, geometry-driven scroll changes, Review selection at the bottom, and accessible current-state exposure.
- [x] 2.2 Run the existing aggregate-flow regressions, frontend lint, frontend production build, and `git diff --check`.
- [x] 2.3 Run `make check` as the final local verification before archive or pull-request preparation.
