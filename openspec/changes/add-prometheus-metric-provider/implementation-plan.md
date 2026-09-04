# Implementation Plan — add-prometheus-metric-provider

**Status:** EXECUTION STOPPED — FINAL BLOCKED BY REPOSITORY-STATE PREREQUISITE
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

## Prometheus feature-delta scope

Git inspection identifies these project-wide workflow changes in the current branch
history:

- `.agents/skills/ipo-high-risk-slice-reviewer/SKILL.md`
- `.agents/skills/ipo-implementation-coordinator/SKILL.md`
- `.agents/skills/ipo-implementation-planner/SKILL.md`
- `.agents/skills/ipo-review-implementation/SKILL.md`
- `.agents/skills/ipo-slice-implementer/SKILL.md`
- `.agents/skills/ipo-slice-plan-reviewer/SKILL.md`

These files define reusable project planning, coordination, implementation, and review
workflows. They are not implementation of `add-prometheus-metric-provider`, do not satisfy
any Prometheus OpenSpec task, and are not part of the Prometheus feature delta. They retain
their own independent commits/history and must not be assigned to C-01 or FINAL.

Before FINAL starts, the repository topology must provide a clean Prometheus review base:
the reusable workflow-skill changes must already be independently integrated into or
otherwise established on the repository branch used as the Prometheus review base, and the
Prometheus feature branch must be synchronized with that base through the normal repository
workflow. The exact Git operation is outside this implementation plan; this plan does not
choose rebase, merge, or another synchronization mechanism.

Once that repository-state precondition is satisfied, FINAL reviews the complete
Prometheus-attributable feature delta against the synchronized base. If any workflow-skill
change or other unrelated workflow/governance edit remains in that feature delta, FINAL
must stop for repository/scope disposition. It must not ignore or subtract unrelated files
silently, and it must not integrate those changes itself.

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
  -> C-01 bounded documentation-conformance correction
  -> FINAL non-corrective conformance
```

Execution is sequential.

The clean-review-base condition above is an external repository-state prerequisite to
FINAL. It is not a Prometheus implementation phase and adds no node to this graph.

## Execution overview

| Phase | Goal | Depends on | Risk | Status | Commit | Handoff/review |
|---|---|---|---|---|---|---|
| VS-01 | Source-safe transport-free provider composition | none | accepted high-risk | COMPLETE | see anchor | accepted |
| VS-02 | Bounded single-attempt acquisition and classification | VS-01 | accepted high-risk | COMPLETE | see anchor | accepted |
| VS-03 | Deadlines, retries, state-inert cleanup, bounded capacity | VS-02 | accepted high-risk | COMPLETE | see anchor | accepted |
| C-01 | Complete all remaining task 5.1 documentation conformance | VS-03 | normal | COMPLETE | `028a8d5` | handoff accepted; independent review `ACCEPT` |
| FINAL | Standard final conformance and implementation review | C-01 | normal | BLOCKED | - | clean synchronized review base prerequisite unsatisfied |

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

### C-01 — Task 5.1 documentation conformance

**Classification:** bounded non-behavioral conformance correction

**Behavioral goal:** Complete all remaining documentation-only implementation required by
task 5.1 without changing runtime behavior, contracts, dependencies, architecture, or
approved OpenSpec semantics.

**OpenSpec coverage:** all remaining work in task 5.1. No functional requirement or
scenario changes.

**Dependencies:** accepted VS-03. Its historical execution anchor identifies the accepted
feature state only; C-01 scope is defined by its own atomic correction and exact owned paths,
not by a cumulative diff to that older anchor.

**Vertical boundary:** accepted provider and configuration behavior -> public provider-port
docstrings plus placeholder-only environment and developer/deployment guidance -> unchanged
interfaces and runtime behavior -> focused checks and independent correction review.

**Remaining task 5.1 inventory and exact ownership:**

| Path | Remaining gap | C-01 intended change |
|---|---|---|
| `backend/src/app/metrics/ports.py` | The public `MetricSeriesProvider` protocol and its public `acquire` interface method have no docstrings. | Add one concise behavior-focused docstring to the protocol and one to `acquire`; change no other production-source content. |
| `.env.example` | The existing `PROMETHEUS_SOURCES` example is only a minimal Bearer shape and does not fully establish placeholder-only local/deployment use or both supported credential shapes. | Keep the setting optional and add safe placeholder-only configuration guidance/examples for the required source fields and supported Bearer-token and Basic-auth shapes; store no real credential. |
| `docs/development-guide.md` | It has no production Prometheus Metric provider configuration or operational guidance. | Add developer/deployment guidance covering the complete approved task 5.1 configuration, safety, request, limit, classification, deadline/retry, and Prometheus-semantics topics listed below, without prescribing implementation changes. |
| `docs/metrics-analysis-developer-boundaries.md` | It still calls the production Prometheus provider future work. | Update that stale developer boundary to describe the implemented infrastructure provider behind the unchanged `MetricSeriesProvider` port and direct configuration/operations readers to the development guide; retain the provider-neutral domain boundary. |
| `openspec/changes/add-prometheus-metric-provider/implementation/C-01-handoff.md` | No correction handoff exists. | Record the atomic correction, changed paths, task 5.1 content review, checks, review result, and confirmation that the production-source delta is docstring-only. |

The production `PrometheusMetricSeriesProvider` class and its public `acquire` method in
`backend/src/app/infrastructure/prometheus/composition.py` already have concise public
docstrings. They require no C-01 edit. No task 5.1 implementation change is required in
`README.md`, `docs/development-workflow.md`, `frontend/.env.example`, or deployment/runtime
configuration code.

The developer/deployment documentation must cover the approved behavior at this level,
without prescribing exact prose:

- `PROMETHEUS_SOURCES` is optional; each configured source provides the required stable
  ID, display name, base URL, and exactly one supported Bearer-token or Basic-auth
  credential shape through local/deployment environment configuration. Examples remain
  placeholders and never contain a real token, password, or deployment profile.
- Secret credential material means the Bearer token and Basic-auth password. The Basic
  username remains compatible in the internal model but, together with the token,
  password, and Authorization value, is excluded from diagnostics, logs, errors, public
  output, and failure messages.
- Production acquisition accepts HTTPS and exact loopback-only HTTP, requires a host and
  forbids userinfo/query/fragment. An empty path or `/` means no prefix; otherwise the
  prefix has non-empty slash-separated ASCII RFC 3986 unreserved segments, no `.` or `..`
  segment, and at most one removable trailing slash. Repeated/empty segments,
  backslashes, and every percent-encoded path byte are rejected. The provider uses normal
  TLS verification with redirects and proxy-environment use off, and excludes
  unauthenticated sources, custom CA/mTLS, OAuth, cloud signing, and proxy configuration.
- Shared Settings loading is unchanged. The stricter target policy runs only after the
  production provider selects a source: absent/unknown sources and selected invalid
  sources perform zero HTTP attempts with their approved typed outcomes, while startup,
  capabilities, Observation creation, and the separately owned 15-second/no-retry Metric
  preflight behavior remain unchanged.
- An eligible transport acquisition creates one immutable logical range request and sends
  one through three identical form POST attempts to the exact API-v1 target. The guide
  records exact-window/opaque-query preservation, fixed `timeout=10s`, `limit=2`, omitted
  `lookback_delta`/`stats`/offset, step
  `max(1, ceil(ceil(window duration in seconds) / 60))`, inclusive maximum of 61
  evaluation timestamps and accepted samples, one-series boundary, and 1 MiB response
  cap.
- Non-empty success warnings fail closed under project policy; valid infos are discarded.
  The ordered outcome guidance distinguishes hard local deadlines, HTTPX timeout,
  `ConnectError`, other transport/client failures, body acquisition/bounds, strict
  Prometheus error-envelope proof, retryable statuses, bare/malformed 503, and success-
  contract validation without exposing provider-authored or credential-bearing data.
- Each complete attempt has a hard 15-second execution/result deadline and `acquire` has
  a hard 50-second execution/result deadline. Only `ConnectError` and HTTP
  `429|500|502|504` are eligible for at most two retries with fixed 0.5/1.0-second waits.
  Insufficient budget for the wait plus a full next attempt is timeout with no wait or
  request; three actually executed eligible attempts exhausting the policy is failure.
  A committed timeout cannot be changed by late transport work; best-effort cleanup is
  state-inert and held within finite private capacity.
- Prometheus evaluates each range timestamp using its deployment lookback/staleness
  behavior. The provider neither overrides nor compensates for it, so returned points may
  be fewer than the requested grid and the existing Metrics quality policy evaluates the
  resulting samples; operators remain responsible for suitable queries/recording rules.

**Contracts consumed/changed:** documents the existing provider-neutral protocol. No
signature, annotation, type, public API, serialized contract, or behavior changes.

**Production-source boundary:** C-01 may change only the two required docstrings in
`backend/src/app/metrics/ports.py`. It may not change executable statements, signatures,
annotations, imports, runtime behavior, provider selection, Prometheus request semantics,
retry/deadline/cancellation/capacity behavior, Settings behavior, or dependencies.

**Non-goals:** exact-prose mandates, refactoring, unrelated formatting, tests, or any
provider, pipeline, analysis, reference, History, agent, persistence, lifecycle, API,
schema, dependency, OpenSpec requirement/spec/design/task text, architecture, ADR, skill,
or behavior change.

**Focused verification:**

- Inspect the complete C-01 atomic diff and review every changed line.
- Confirm that atomic diff contains only the explicitly owned C-01 paths and contains no
  `.agents/skills/ipo-*` or other unrelated workflow/governance file.
- Review all C-01 documentation content against every clause of task 5.1 and the approved
  OpenSpec behavior summarized above.
- Confirm the only production file is `backend/src/app/metrics/ports.py` and its production
  diff contains only the two docstring additions.
- Confirm no signature, annotation, import, executable statement, or runtime behavior was
  changed.
- Confirm no tests, approved OpenSpec requirement/spec/design/task text, architecture,
  ADRs, skills, dependencies, runtime configuration behavior, or unrelated source changed.
- Run targeted Ruff lint and formatting checks for `backend/src/app/metrics/ports.py`.
- Run strict validation for `add-prometheus-metric-provider` and focused repository
  documentation/static checks applicable to the changed files.
- Run `git diff --check`.
- Obtain fresh independent review of the narrow correction diff.

Normal Git diff inspection is sufficient. Do not add a custom source parser, byte-level
verifier, or metadata-validation framework.

**Context pack:** root documentation rules; task 5.1 and the approved change; this plan;
accepted VS-03 anchor and handoffs as regression boundaries; historical
`implementation/VS-04-handoff.md`; all five exact C-01-owned paths above; existing
production-provider docstrings as already-satisfied evidence.

**Handoff expectations:** `implementation/C-01-handoff.md` records the correction commit,
the two public-port docstrings, exact documentation paths/content covered, changed-file
summary, focused checks, independent review result, and confirmation of no behavior,
signature, annotation, import, executable-statement, Settings, or dependency change.

**Risk:** normal; documentation-only and non-behavioral

**Completion gate:** both docstrings are meaningful; `.env.example` is placeholder-only and
documents both approved credential shapes; the developer/deployment guide covers every
task 5.1 topic; the stale developer-boundary note is current; the complete atomic diff is
limited to the exact owned paths and the production-source delta contains only the two
docstrings; relevant lint/format, strict OpenSpec, documentation/static, and diff checks
pass; independent review confirms the correction is non-behavioral and in scope; one
correction commit and handoff are accepted by the Coordinator.

No separate docstring and developer-documentation slices are required. The owned changes
are one cohesive documentation-only correction and can be implemented and reviewed
together after this plan is approved.

### FINAL — Non-corrective repository conformance

**Behavioral goal:** Verify the complete change with repository-standard tooling and
independent review without implementing or correcting behavior.

**OpenSpec coverage:** final verification of every approved requirement/scenario and tasks
5.1–5.4.

**Dependencies:** accepted C-01 correction.

**Repository-state precondition:** the reusable workflow-skill changes listed in
`Prometheus feature-delta scope` are established on the repository branch used as the
review base, and the Prometheus feature branch is synchronized with that base according to
the normal repository workflow. FINAL does not perform that integration. If this condition
is not true, FINAL remains blocked pending repository/scope disposition.

**Vertical boundary:** accepted implementation/correction -> standard checks -> independent
implementation review -> archive-readiness or explicit stop.

**Expected code impact:** no implementation, test, or developer/deployment documentation
creation or editing. Only task-checkbox reconciliation after owning work is accepted,
concise Coordinator execution metadata, and the final verification/review record are
permitted.

**Contracts consumed/changed:** none.

**Non-goals:** creating, completing, or correcting production code, tests, configuration
examples, developer/deployment documentation, or any approved behavior, contract,
persistence, lifecycle, dependency, architecture, ADR, or OpenSpec semantics.

**Focused verification:**

- Reconcile all 24 approved task checkboxes with accepted work.
- Run `openspec validate add-prometheus-metric-provider --strict`.
- Run `make check`.
- Run database-enabled verification when required and available; report unavailable or
  skipped checks accurately.
- Run official OpenSpec verification when installed.
- Resolve the appropriate synchronized repository review base through normal Git topology,
  then inspect the complete feature diff and confirm it contains only changes attributable
  to `add-prometheus-metric-provider`.
- Run fresh `ipo-review-implementation` review of that complete Prometheus feature delta.
- Inspect final Git status and diff for scope and cleanliness; stop for repository/scope
  disposition if any unrelated workflow/governance change remains in the feature delta.

**Context pack:** complete approved OpenSpec and architecture references; accepted
handoffs; C-01 handoff/review; complete current diff; repository development workflow.

**Handoff expectations:** concise final record containing task state, command results,
database-verification status, review findings/dispositions, scope summary, and archive-
readiness or stop reason.

**Risk:** normal; verification only

**Completion gate:** all tasks reconcile; strict OpenSpec validation and `make check`
pass; required database verification is passed or accurately dispositioned; final review
has no unresolved `BLOCKER`, `HIGH`, or `MEDIUM` finding; Git state/diff is clean and in
scope against the synchronized repository base; no unrelated workflow/governance edit is
present in the Prometheus feature delta; no substantive behavior changed during FINAL.

If FINAL finds any missing implementation or required documentation, stop and route it
through the appropriate bounded correction or escalation path. Do not repair it inside
FINAL. Substantive findings require human triage; `LOW` findings follow existing repository
governance.

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
| 5.1 | C-01 owns all remaining documentation implementation; FINAL verifies/reconciles completion only |
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
- Historical final conformance: stopped correctly on the task 5.1 documentation gap and
  recorded the two missing provider-port docstrings; no correction was made there.
- C-01: complete at `028a8d5`; focused verification passed, the compact handoff is
  accepted, independent correction review returned `ACCEPT` with no findings, and no
  shared-knowledge candidate was proposed.
- FINAL: not started. Repository inspection after C-01 found that the six reusable
  `.agents/skills/ipo-*` workflow changes listed in `Prometheus feature-delta scope`
  exist only on `feature/add-prometheus-metric-provider` and remain in its delta against
  `main`; the feature branch therefore does not yet have the required synchronized clean
  Prometheus review base. Stop pending explicit repository/base synchronization outside
  C-01; do not resolve this prerequisite implicitly inside FINAL.
