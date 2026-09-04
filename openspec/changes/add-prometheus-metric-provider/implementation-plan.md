# Implementation Plan — add-prometheus-metric-provider

**Status:** DRAFT — READY FOR FOCUSED INDEPENDENT REVIEW
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-prometheus-metric-provider`
**Implementation branch:** `feature/add-prometheus-metric-provider`

## Authority and proportional governance

This plan describes execution; it does not redefine behavior. The approved OpenSpec,
accepted ADRs, normative architecture/contracts, repository governance, and accepted
implementation remain authoritative.

Verification rigor is proportional to change risk. A narrow non-behavioral documentation
correction does not require the same re-planning and proof machinery as a change to runtime
behavior, contracts, persistence, dependencies, lifecycle semantics, or architecture.

Structural re-planning is required only when remaining work changes approved normative
behavior, slice ownership/dependencies, public contracts, persistence/lifecycle semantics,
architecture, dependencies, or material implementation scope.

Relevant sources are the complete approved change, `openspec/specs/metrics-analysis-pipeline/spec.md`,
the architecture references named in the approved proposal/design, root `AGENTS.md`, the
development guide/workflow, and `.agents/PROJECT_KNOWLEDGE.md` as advisory knowledge.

## Execution anchors

These are the only retained Git anchors. They identify accepted recovery points; Git and
the handoffs/review records contain the detailed history.

| Accepted phase | Anchor | Handoff | Purpose |
|---|---|---|---|
| VS-01 | `fc6558d06133ea82903e2e1241a4cf781f86d45c` | `implementation/VS-01-handoff.md` | Accepted source-safe composition |
| VS-02 | `81270d9537329eea0477254094ef9fcdce6f17e6` | `implementation/VS-02-handoff.md` | Accepted bounded single-attempt acquisition |
| VS-03 | `7baae2b4d3e05c55ba2ae8d5a82f2cc03f630a9a` | `implementation/VS-03-handoff.md` | Accepted execution state and correction baseline |

VS-01, VS-02, and VS-03 are independently reviewed, accepted, and frozen. This plan does
not reopen, rewrite, or re-execute them.

## Remaining graph

```text
VS-01 accepted/frozen
  -> VS-02 accepted/frozen
  -> VS-03 accepted/frozen
  -> C-01 bounded non-behavioral docstring correction
  -> FINAL non-corrective conformance
```

Execution is sequential.

## Execution overview

| Phase | Goal | Depends on | Risk | Status | Commit | Handoff/review |
|---|---|---|---|---|---|---|
| VS-01 | Source-safe transport-free provider composition | none | accepted high-risk | COMPLETE | see anchor | accepted |
| VS-02 | Bounded single-attempt acquisition and classification | VS-01 | accepted high-risk | COMPLETE | see anchor | accepted |
| VS-03 | Deadlines, retries, state-inert cleanup, bounded capacity | VS-02 | accepted high-risk | COMPLETE | see anchor | accepted |
| C-01 | Add two missing public provider-port docstrings | VS-03 | non-behavioral correction | PLANNED | - | `implementation/C-01-handoff.md` |
| FINAL | Standard final conformance and implementation review | C-01 | normal | PLANNED | - | final review record |

## Accepted implementation summary

- **VS-01:** accepted source selection, production-only validation, zero-request typed
  outcomes, application composition, and provider-to-pipeline integration.
- **VS-02:** accepted request/authentication behavior, response bounds and mapping,
  warning policy, and single-attempt classification.
- **VS-03:** accepted 15-second attempt and 50-second acquisition result deadlines,
  timeout commitment, cancellation/close signalling, state-inert late cleanup, finite
  active-plus-cleanup capacity, retries, and current/reference integration.

Detailed evidence remains in the handoffs and Git history.

## Remaining execution

### C-01 — Metric provider-port docstring conformance

**Classification:** non-behavioral conformance correction

**Behavioral goal:** Add meaningful, concise docstrings to the existing public
`MetricSeriesProvider` protocol and its public `acquire` interface method.

**OpenSpec coverage:** the remaining public class/interface-method documentation portion
of task 5.1. No functional requirement or scenario changes.

**Dependencies:** accepted VS-03; use its execution anchor as the correction baseline.

**Vertical boundary:** accepted `backend/src/app/metrics/ports.py` -> two docstrings ->
unchanged interface/runtime behavior -> focused checks and independent correction review.

**Expected code impact:** only the two docstrings in
`backend/src/app/metrics/ports.py`, plus `implementation/C-01-handoff.md` and concise
Coordinator status updates.

**Contracts consumed/changed:** documents the existing provider-neutral protocol. No
signature, annotation, type, public API, serialized contract, or behavior changes.

**Non-goals:** refactoring, unrelated formatting, tests, imports, executable statements,
or any provider, pipeline, analysis, reference, History, agent, persistence, lifecycle,
API, schema, dependency, OpenSpec, or architecture change.

**Focused verification:**

- Inspect the complete correction commit diff from the VS-03 execution anchor.
- Confirm the only production file is `backend/src/app/metrics/ports.py` and its intended
  production diff contains only the two docstring additions.
- Confirm no signature, annotation, import, executable statement, or runtime behavior was
  intentionally changed.
- Confirm no tests, approved OpenSpec, architecture, dependencies, configuration, or
  unrelated source changed in the corrective implementation.
- Run Python compilation and targeted Ruff lint/format checks for `ports.py`.
- Run `git diff --check`.
- Obtain fresh independent review of the narrow correction diff.

Normal Git diff inspection is sufficient. Do not add a custom source parser, byte-level
verifier, or metadata-validation framework.

**Context pack:** root documentation rules; this plan; accepted VS-03 anchor;
`backend/src/app/metrics/ports.py`; accepted handoffs as regression boundaries; historical
`implementation/VS-04-handoff.md` identifying the conformance defect.

**Handoff expectations:** `implementation/C-01-handoff.md` records the correction commit,
the two docstrings, changed-file summary, focused checks, independent review result, and
confirmation of no intentional behavior/signature/type change.

**Risk:** normal; documentation-only and non-behavioral

**Completion gate:** both docstrings are meaningful; the correction diff is clean and
limited to those additions; focused compile/lint/format and diff checks pass; independent
review confirms the correction is non-behavioral and in scope; one correction commit and
handoff are accepted by the Coordinator.

No further vertical-slice design review is required for the docstring content after this
simplified plan is approved.

### FINAL — Non-corrective repository conformance

**Behavioral goal:** Verify the complete change with repository-standard tooling and
independent review without implementing or correcting behavior.

**OpenSpec coverage:** final verification of every approved requirement/scenario and tasks
5.1–5.4.

**Dependencies:** accepted C-01 correction.

**Vertical boundary:** accepted implementation/correction -> standard checks -> independent
implementation review -> archive-readiness or explicit stop.

**Expected code impact:** developer/deployment documentation authorized by task 5.1, task
checkbox updates after owning work is accepted, and concise Coordinator status only. No
production or test behavior changes.

**Contracts consumed/changed:** none.

**Non-goals:** fixing defects, changing tests to obtain a pass, or altering approved
behavior, contracts, persistence, lifecycle, dependencies, or architecture.

**Focused verification:**

- Reconcile all 24 approved task checkboxes with accepted work.
- Run `openspec validate add-prometheus-metric-provider --strict`.
- Run `make check`.
- Run database-enabled verification when required and available; report unavailable or
  skipped checks accurately.
- Run official OpenSpec verification when installed.
- Run fresh `ipo-review-implementation` review of the complete change.
- Inspect final Git status and diff for scope and cleanliness.

**Context pack:** complete approved OpenSpec and architecture references; accepted
handoffs; C-01 handoff/review; complete current diff; repository development workflow.

**Handoff expectations:** concise final record containing task state, command results,
database-verification status, review findings/dispositions, scope summary, and archive-
readiness or stop reason.

**Risk:** normal; verification only

**Completion gate:** all tasks reconcile; strict OpenSpec validation and `make check`
pass; required database verification is passed or accurately dispositioned; final review
has no unresolved `BLOCKER`, `HIGH`, or `MEDIUM` finding; Git state/diff is clean and in
scope; no substantive behavior changed during FINAL.

If final review finds a substantive defect, stop for human triage. Do not repair it inside
FINAL. `LOW` findings follow existing repository governance.

## Coverage matrix

### Requirement ownership

| Approved requirement | Accepted owner | Final verification |
|---|---|---|
| Resolve a server-managed Prometheus source without exposing credentials | VS-01/VS-02 | FINAL |
| Query the exact current or reference window through HTTP API v1 | VS-02/VS-03 | FINAL |
| Map one float series into the provider-neutral sample contract | VS-02 | FINAL |
| Fail closed on warning annotations or excessive Prometheus responses | VS-02 | FINAL |
| Bound acquisition time and map failures through existing typed outcomes | VS-03 | FINAL |
| Compose and verify the provider behind the existing Metric port | VS-01–VS-03 | FINAL |
| Acquire metric series only through the internal provider boundary | VS-01–VS-03 | FINAL |
| Persist terminal Metric outcome atomically through the existing repository | accepted Metrics pipeline | FINAL |

### Scenario ownership

Every approved scenario remains owned by its accepted implementation phase. The exact
scenario inventory is unchanged in the approved specs; FINAL re-runs it through standard
tests and review.

| Approved scenario group | Accepted owner |
|---|---|
| Source resolution, credential safety, unsafe targets, shared-consumer compatibility | VS-01/VS-02 |
| Exact current/reference request, target/path, resolution, and logical retry identity | VS-01–VS-03 |
| Float-series, empty/multiple-series, histogram, sample-fidelity mapping | VS-02 |
| Body/sample bounds, warnings, infos, malformed annotations | VS-02 |
| Retry eligibility/admission/counts/exhaustion and HTTPX taxonomy | VS-03 |
| Deadline commitment, error/status precedence, late cleanup, bounded capacity | VS-02/VS-03 |
| Current/reference failure and provider-neutral pipeline integration | VS-01–VS-03 |
| Zero/one/multiple reference and transport-free pipeline behavior | VS-01/VS-02 |
| Metric result round-trip, rollback, and coupling avoidance | accepted Metrics pipeline/VS-01–VS-03 |

### Task ownership

| Approved task | Owner/status |
|---|---|
| 1.1–1.4 | accepted VS-01 |
| 2.1–2.5 | accepted VS-02 |
| 3.1–3.5 | accepted VS-03 |
| 4.1–4.6 | accepted across VS-01–VS-03 |
| 5.1 | C-01 owns the two missing interface docstrings; FINAL completes documentation and reconciliation |
| 5.2 | FINAL |
| 5.3 | FINAL |
| 5.4 | FINAL |

## Frozen plan and mutable execution state

After focused independent review and explicit human approval, C-01 and FINAL ownership,
dependency, scope, and gates are frozen. VS-01–VS-03 remain accepted/frozen.

Coordinator bookkeeping is limited to phase status, accepted commit, handoff/review
record, verification result, stop reason, and approved task-checkbox transitions. Git,
handoffs, and review artifacts provide detailed traceability; this plan does not duplicate
them.

## Execution notes

- VS-01, VS-02, VS-03: complete, independently reviewed, accepted, and frozen.
- Historical final conformance: stopped correctly on the two missing provider-port
  docstrings; no correction was made there.
- C-01: planned; must not start before this simplified plan is reviewed and approved.
- FINAL: planned; starts only after C-01 acceptance.
