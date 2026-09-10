## 1. Secret-safe capabilities contract

- [ ] 1.1 Add typed public Prometheus configuration and credential projection models with optional `base_url` and no token or password fields, and verify model validation covers both credential variants plus serialized omission of an absent URL.
- [ ] 1.2 Map configured Prometheus settings field by field into the public projection while preserving source order; include the exact `base_url` only after the complete value passes the shared production-safe target rules, and verify focused contract/API tests assert exact safe Bearer and Basic JSON plus absence of secret keys, sentinel secret values, masked values, Authorization data, health, and diagnostics.
- [ ] 1.3 Preserve tolerant shared settings and authoritative production provider behavior while reusing the target rules as a serialization confidentiality gate, and verify real HTTP responses omit `base_url` and the complete rejected value for userinfo/password, query, fragment, malformed, and otherwise unsafe targets while provider tests still prove unchanged acquisition, port, log, diagnostic, error, failure, and Basic-username privacy boundaries.

## 2. Data Sources disclosure UI

- [ ] 2.1 Update the frontend capabilities types and fixtures for the required typed configuration projection with optional `base_url`, and verify TypeScript compilation accepts both credential variants and configurations with or without the URL without making the configuration object optional.
- [ ] 2.2 Refactor each configured source into a compact-by-default card with an accessible independent expand/collapse control and a horizontally scrollable two-space-indented JSON code pane, and verify focused UI tests cover default collapse, `aria-expanded`/controlled-pane semantics, exact formatted content with safe URL inclusion and unsafe URL omission, no fabricated replacement/status, independent disclosures, collapse, and zero disclosure-triggered requests or mutations.
- [ ] 2.3 Preserve the existing Data Sources loading, retry, empty, refresh, ordering, navigation, and Metric Lens availability behavior, and verify the existing page and Metric editor test suites remain green with the expanded response contract.

## 3. Documentation and verification

- [ ] 3.1 Advance `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` to UI Direction v1.6 and document the compact-default, secret-safe Prometheus configuration disclosure, including conditional safe URL inclusion and fail-closed omission without health inference, while retaining the trusted-environment and read-only lifecycle boundaries; verify no accepted UI text contradicts the revised visibility rule.
- [ ] 3.2 Run `openspec validate show-data-source-configuration --strict` and `make check`, resolve in-scope failures, and record both commands' successful results before archive or pull-request preparation.
