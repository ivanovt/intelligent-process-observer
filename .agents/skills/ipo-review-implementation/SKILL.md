---
name: ipo-review-implementation
description: Independently review the cumulative implementation of an approved OpenSpec change as a strict whole-change product-quality gate before archive and PR preparation. Use to assess behavior, architecture, contracts, code quality, tests, repository compatibility, and scope without re-auditing planning mechanics or historical slice proofs.
---

# IPO Review Implementation

Perform an independent, report-only whole-change review after an approved OpenSpec change has been applied and before it is archived.

Answer: Does the implemented change correctly and completely satisfy the approved behavior with acceptable code quality, tests, architecture conformance, and repository compatibility?

Prefer running this skill in a fresh reviewer session or isolated review context so the reviewer is not biased by implementation decisions made in the coding session.

## Guardrails

- Do not modify files.
- Do not fix findings.
- Do not edit OpenSpec artifacts.
- Do not modify architecture documents or ADRs.
- Do not create commits, push, open PRs, or archive the change.
- Do not broaden the review into style-only refactoring advice.
- Treat the approved OpenSpec artifacts as frozen behavior for this review.
- Treat architecture/ADRs as normative using `AGENTS.md` precedence.
- Treat the implementation plan and slice handoffs as supporting execution context, not normative behavior sources.
- Do not re-review planning or approval mechanics unless a concrete implementation problem depends on them.

Verification commands that do not intentionally change source are allowed. If a check cannot run because the local environment is unavailable, report it instead of guessing.

## Input and change selection

Use `$ARGUMENTS[0]` as the change id when supplied.
Use `$ARGUMENTS[1]` as the base branch when supplied; otherwise use `main`.

If the change is omitted, infer it only when unambiguous. Otherwise inspect `openspec list --json` and ask the user to select one.

Always state the selected change and base branch.

## Review procedure

### 1. Establish expected behavior

Use these primary authorities:

1. root `AGENTS.md`;
2. `docs/architecture/README.md`;
3. the complete approved OpenSpec change:
   - `proposal.md`;
   - all delta specs;
   - `design.md` when present;
   - `tasks.md`;
4. every relevant architecture/ADR/contract document listed in `Architecture References`; and
5. applicable repository contracts and conventions.

Do not assume the implementation is correct because tasks are checked off.

Evaluate the actual implementation and tests against these authorities.

Consult `implementation-plan.md` and slice handoffs only when they help explain implementation boundaries, execution decisions, or a concrete suspected defect. Do not treat them as normative behavior or re-review them as execution artifacts.

### 2. Establish the implementation diff

Inspect repository state and compare the feature branch against the merge base with the base branch.

Review all source, tests, migrations, configuration, and documentation changed by the implementation.

If the diff contains unrelated changes, report scope deviation explicitly.

Review the cumulative final state through normal Git history and the cumulative diff. Do not require reconstruction of every historical slice review, repeated approval-SHA verification, duplicate commit ledgers, content digests, or byte-level replay of accepted slices.

### 3. Gather proportionate engineering evidence

Normal review evidence includes:

- source inspection and the cumulative Git diff;
- focused and repository-wide tests;
- static, lint, and type checks;
- integration or database verification where relevant; and
- OpenSpec validation.

If the official `openspec-verify-change` workflow is installed, its result may be used as supporting evidence, but this skill must still perform an independent project-specific review.

Do not treat OpenSpec structural or verify output as proof of architecture correctness.

Do not require custom checksum/digest schemes, AST inventories, byte reconstruction, newline/token auditors, or repeated raw SHA anchors unless a concrete correctness, security, or integrity risk cannot reasonably be verified through normal engineering evidence. State that risk and why ordinary evidence is insufficient before requiring specialized machinery.

### 4. Review specification compliance

Review the whole implemented change for requirement completeness, behavioral correctness, public/domain contract correctness, architecture/ADR conformance, error and failure handling, applicable security/persistence/transport semantics, code quality and maintainability, meaningful test coverage, scope discipline, and documentation required by the approved change.

For every major requirement/scenario, determine whether the implementation is:

- covered;
- partially covered;
- not covered.

Check especially:

- lifecycle transitions;
- terminal/partial/failure semantics;
- absence versus empty-result semantics;
- type-specific contract differences;
- identity and correlation invariants;
- cardinality and uniqueness;
- version/provenance preservation where defined;
- API behavior when the change exposes a public API;
- bounded-agent/tool behavior when the change contains agentic execution.

### 5. Review architecture compliance

Check whether implementation preserves ownership boundaries such as:

- domain vs API vs persistence contracts;
- deterministic orchestration vs agentic reasoning;
- provider adapters vs analytical logic;
- persistence integrity vs domain semantic validation;
- Lens-local reasoning vs Observation-level reasoning;
- analysis vs presentation/reporting.

Report any implementation that silently resolves or contradicts an `Open`/`Deferred` architecture decision.

### 6. Review failure, security, and integration semantics when applicable

Inspect error propagation, partial and terminal failure behavior, retry/deadline/cancellation boundaries, credential and secret handling, authentication behavior, and external request/response/transport semantics when the approved change touches them.

Verify that failures are visible and correctly classified, secrets cannot leak through code, logs, errors, or client-visible configuration, and integration behavior matches the approved contract.

### 7. Review data and persistence integrity when applicable

When the change touches persistence, inspect:

- SQLAlchemy async/session usage;
- caller/repository transaction ownership;
- foreign-key and aggregate correlation integrity;
- redundant sources of truth;
- JSONB round-trip behavior;
- uniqueness/cardinality enforcement;
- migration upgrade compatibility and downgrade intent;
- fresh-session retrieval rather than fake in-memory round-trips;
- failure/rollback behavior;
- whether integration tests exercise real PostgreSQL when the requirement depends on database behavior.

Prefer minimal integrity design. Do not demand complex relational machinery when redundant columns can simply be removed.

### 8. Review tests

Determine whether tests genuinely prove the approved behavior rather than merely executing code paths.

Look for:

- missing negative/boundary cases;
- mocks/fakes that bypass the behavior being claimed;
- contract-invalid fixtures;
- migration tests that inspect metadata but never exercise the migration;
- missing fresh-session/database round-trips;
- missing mismatch/uniqueness/cardinality cases;
- tests that encode non-normative vocabulary or shapes.

Require meaningful verification, not maximum verification. A persistence feature needs real database/integration evidence where behavior depends on PostgreSQL; a transport feature needs relevant request, error, retry, and deadline coverage; a small configuration feature may be sufficiently demonstrated by focused tests plus repository checks. Do not demand unrelated broad test expansion.

### 9. Review documentation quality

Apply the code-documentation rules in `AGENTS.md`.

Check that:

- non-trivial public classes/functions have concise useful docstrings/comments;
- architecture-sensitive invariants are understandable near the enforcing code;
- comments explain why rather than narrating obvious code;
- comments/docstrings do not contradict the approved spec or architecture;
- implementation-specific decisions that reviewers should know are documented appropriately.

Missing documentation is a finding only when it materially impairs understanding of non-trivial public or architecture-sensitive code.

### 10. Review unnecessary complexity and scope

Report:

- new abstractions without a current requirement;
- new dependencies without approval;
- framework/stack changes outside scope;
- unrelated refactors mixed into the feature;
- code that implements future/deferred behavior prematurely.

Do not report ordinary stylistic preferences.

## Defect classification

Classify the defect itself, not the historical slice that introduced it.

### Bounded correction candidate

Use when the finding can be corrected within approved behavior and existing architecture/contracts, ownership, dependencies, and semantic boundaries. Examples include a narrow implementation bug, missing focused regression coverage, or a non-behavioral conformance issue.

Report the finding normally and identify it as a bounded correction candidate. The Coordinator decides whether to route it through the bounded correction path.

### Structural or normative escalation

Use when satisfying the approved change requires changing OpenSpec behavior, architecture/ADRs, a public/domain contract, schema or dependencies, or lifecycle/security/concurrency semantics.

State clearly that structural triage and re-planning are required. Do not perform either correction type yourself.

## Finding severity

Use:

- `BLOCKER` — unsafe to proceed; architecture/contract conflict, destructive risk, or missing decision blocks correctness;
- `HIGH` — significant correctness, data-integrity, contract, or security defect;
- `MEDIUM` — meaningful correctness risk, integration/test gap, boundary violation, or maintainability defect that should be fixed before archive;
- `LOW` — minor documentation/local quality issue that does not block archive unless the user chooses stricter policy.

Severity reflects actual impact and likelihood, not which slice introduced the issue, the feature's historical risk, or how late the defect was found. Do not promote a small documentation or conformance issue to `MEDIUM` or `HIGH` merely because final review found it, and do not downgrade a substantive defect because its correction is narrow.

## Output format

Report findings only. Do not fix them.

Order findings by severity. For each finding, report:

```text
ID: IR-001
Severity: BLOCKER | HIGH | MEDIUM | LOW
Location: path:line or smallest useful symbol
Requirement:
Problem:
Why it matters:
Correction route: BOUNDED CORRECTION CANDIDATE | STRUCTURAL/NORMATIVE ESCALATION | N/A
Suggested direction:
```

Then provide a compact summary:

```text
## Reviewed change
<change and base branch>

## Requirement and architecture coverage concerns
- None
or
- ...

## Verification evidence inspected
- commands/checks run and outcomes
- checks that could not be run

## Final disposition
READY
| CHANGES REQUIRED

## Required-change routing
- Bounded correction candidates: ...
- Structural/normative escalations: ...
```

Use only `READY` or `CHANGES REQUIRED`. `READY` requires no unresolved `BLOCKER`, `HIGH`, or `MEDIUM` finding. Keep `LOW` findings visible; they may remain non-blocking under repository policy or be routed as bounded corrections.

Do not reproduce large plan sections, SHA histories, or handoff contents unless needed to explain a concrete finding.
