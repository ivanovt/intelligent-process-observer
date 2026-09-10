## 1. Secret-safe capabilities contract

- [ ] 1.1 Add typed public Prometheus configuration and credential projection models to the definition-capabilities contract, with no token or password fields, and verify model validation covers both credential variants.
- [ ] 1.2 Map configured Prometheus settings field by field into the public projection while preserving source order, and verify focused backend contract/API tests assert exact Bearer and Basic JSON plus absence of secret keys, sentinel secret values, masked values, Authorization data, health, and diagnostics.
- [ ] 1.3 Preserve production provider behavior and its separate privacy boundaries, and verify provider tests still prove that connection configuration does not cross the provider port, production-invalid sources imply no health state in capabilities, and Basic usernames remain absent from logs, diagnostics, errors, failures, and public output outside the approved capabilities projection.

## 2. Data Sources disclosure UI

- [ ] 2.1 Update the frontend capabilities types and fixtures for the required typed configuration projection, and verify TypeScript compilation accepts both credential variants without making configuration optional.
- [ ] 2.2 Refactor each configured source into a compact-by-default card with an accessible independent expand/collapse control and a horizontally scrollable two-space-indented JSON code pane, and verify focused UI tests cover default collapse, `aria-expanded`/controlled-pane semantics, exact formatted content, independent disclosures, collapse, and zero disclosure-triggered requests or mutations.
- [ ] 2.3 Preserve the existing Data Sources loading, retry, empty, refresh, ordering, navigation, and Metric Lens availability behavior, and verify the existing page and Metric editor test suites remain green with the expanded response contract.

## 3. Documentation and verification

- [ ] 3.1 Advance `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` to UI Direction v1.6 and document the compact-default, secret-safe Prometheus configuration disclosure while retaining the trusted-environment and read-only lifecycle boundaries; verify no accepted UI text still forbids the newly approved endpoint, credential type, or Basic username visibility.
- [ ] 3.2 Run `openspec validate show-data-source-configuration --strict` and `make check`, resolve in-scope failures, and record both commands' successful results before archive or pull-request preparation.
