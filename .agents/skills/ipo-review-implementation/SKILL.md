---
name: ipo-review-implementation
description: Independently review an implemented OpenSpec change against its approved plan, Intelligent Process Observer architecture, tests, migrations, and documentation before archive and PR preparation.
argument-hint: "[change-id] [base-branch]"
---

# IPO Review Implementation

Perform an independent, report-only implementation review after an approved OpenSpec change has been applied and before it is archived.

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

Verification commands that do not intentionally change source are allowed. If a check cannot run because the local environment is unavailable, report it instead of guessing.

## Input and change selection

Use `$ARGUMENTS[0]` as the change id when supplied.
Use `$ARGUMENTS[1]` as the base branch when supplied; otherwise use `main`.

If the change is omitted, infer it only when unambiguous. Otherwise inspect `openspec list --json` and ask the user to select one.

Always state the selected change and base branch.

## Review procedure

### 1. Establish expected behavior

Read:

1. root `AGENTS.md`;
2. `docs/architecture/README.md`;
3. the complete approved OpenSpec change:
   - `proposal.md`;
   - all delta specs;
   - `design.md` when present;
   - `tasks.md`;
4. every relevant architecture/ADR/contract document listed in `Architecture References`.

Do not assume the implementation is correct because tasks are checked off.

### 2. Establish the implementation diff

Inspect repository state and compare the feature branch against the merge base with the base branch.

Review all source, tests, migrations, configuration, and documentation changed by the implementation.

If the diff contains unrelated changes, report scope deviation explicitly.

### 3. Use OpenSpec verification as supporting evidence

If the official `openspec-verify-change` workflow is installed, its result may be used as supporting evidence, but this skill must still perform an independent project-specific review.

Do not treat OpenSpec structural or verify output as proof of architecture correctness.

### 4. Review specification compliance

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

### 6. Review data and persistence integrity when applicable

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

### 7. Review tests

Determine whether tests genuinely prove the approved behavior rather than merely executing code paths.

Look for:

- missing negative/boundary cases;
- mocks/fakes that bypass the behavior being claimed;
- contract-invalid fixtures;
- migration tests that inspect metadata but never exercise the migration;
- missing fresh-session/database round-trips;
- missing mismatch/uniqueness/cardinality cases;
- tests that encode non-normative vocabulary or shapes.

### 8. Review documentation quality

Apply the code-documentation rules in `AGENTS.md`.

Check that:

- non-trivial public classes/functions have concise useful docstrings/comments;
- architecture-sensitive invariants are understandable near the enforcing code;
- comments explain why rather than narrating obvious code;
- comments/docstrings do not contradict the approved spec or architecture;
- implementation-specific decisions that reviewers should know are documented appropriately.

Missing documentation is a finding only when it materially impairs understanding of non-trivial public or architecture-sensitive code.

### 9. Review unnecessary complexity and scope

Report:

- new abstractions without a current requirement;
- new dependencies without approval;
- framework/stack changes outside scope;
- unrelated refactors mixed into the feature;
- code that implements future/deferred behavior prematurely.

Do not report ordinary stylistic preferences.

## Finding severity

Use:

- `BLOCKER` — unsafe to proceed; architecture/contract conflict, destructive risk, or missing decision blocks correctness;
- `HIGH` — significant correctness, data-integrity, contract, or security defect;
- `MEDIUM` — meaningful correctness risk, integration/test gap, boundary violation, or maintainability defect that should be fixed before archive;
- `LOW` — minor documentation/local quality issue that does not block archive unless the user chooses stricter policy.

## Output format

Report findings only. Do not fix them.

For each finding:

```text
ID: IR-001
Severity: BLOCKER | HIGH | MEDIUM | LOW
Location: path:line or smallest useful symbol
Requirement:
Problem:
Why it matters:
Suggested direction:
```

Then provide:

```text
## Requirement coverage
<major requirement> — Covered | Partially covered | Not covered

## Test coverage gaps
- ...

## Documentation gaps
- None
or
- ...

## Scope deviations
- None
or
- ...

## Verification evidence
- commands/checks run and outcomes
- checks that could not be run

## Final assessment
READY
| READY WITH MINOR FIXES
| CHANGES REQUIRED
```

`READY` requires no unresolved BLOCKER/HIGH/MEDIUM finding. LOW findings may remain if they are explicitly accepted for later cleanup.
