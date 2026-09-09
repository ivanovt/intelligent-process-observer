## 1. Relationship action rail

- [x] 1.1 Restructure the Relationship editor so `Cancel`, `Apply changes`, and Rule semantics share one responsive action-and-guidance rail while preserving the existing page heading and validation-summary flow.
- [x] 1.2 Apply wide-layout sticky positioning beneath the application shell and a narrow-layout normal-flow ordering that keeps the rail readable without covering or compressing form controls.

## 2. Descriptor row controls

- [x] 2.1 Replace When and Expect row `Remove` text actions with compact Lucide icon-only project `Button` controls that retain section-specific accessible names, focus behavior, and existing removal callbacks.
- [x] 2.2 Replace the link-like `Add condition` and `Add expectation` controls with compact secondary project `Button` controls, preserving visible labels, accessible button semantics, and existing row defaults.

## 3. Verification

- [x] 3.1 Update Relationship editor component tests to cover the grouped rail, accessible icon-removal controls, button-styled add actions, and unchanged add/remove/cancel/apply behavior including no child HTTP writes.
- [x] 3.2 Manually verify a long Relationship form at wide and narrow viewport sizes for sticky visibility, shell clearance, source order, keyboard focus visibility, and absence of content overlap.
- [x] 3.3 Run `make check` and resolve any failures within the approved change scope.
