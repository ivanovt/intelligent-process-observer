# Implementation Plan — add-prometheus-metric-provider

**Status:** APPROVED — EXECUTION BLOCKED
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-prometheus-metric-provider`
**Implementation branch:** `feature/add-prometheus-metric-provider`
**Human-approved planning SHA:** `75b97960704af790b2d8c3e8b6ce84a9e400151a`

## Approval state

The proposal, delta specifications, design, and tasks are human-approved inputs to this
planning pass. This implementation plan is not approved for execution. The complete
planning snapshot defined below must first be committed, independently reviewed at that
exact commit SHA, and explicitly human-approved at that same SHA before VS-01 may begin.

## Authority and constraints

This file describes how the approved change can be implemented. It does not redefine
the approved behavior. Accepted ADRs, normative architecture/contracts, and the approved
OpenSpec remain authoritative.

Approved change sources:

- `openspec/changes/add-prometheus-metric-provider/.openspec.yaml`
- `openspec/changes/add-prometheus-metric-provider/proposal.md`
- `openspec/changes/add-prometheus-metric-provider/design.md`
- `openspec/changes/add-prometheus-metric-provider/specs/prometheus-metric-provider/spec.md`
- `openspec/changes/add-prometheus-metric-provider/specs/metrics-analysis-pipeline/spec.md`
- `openspec/changes/add-prometheus-metric-provider/tasks.md`

Architecture and accepted-contract sources:

- `docs/architecture/README.md`
- `docs/architecture/01_observation_lens_concept.md`, especially the one-metric Lens
  boundary and distinct current, configured-reference, and History perspectives
- `docs/architecture/02_architecture_principles_and_runtime.md`, especially the
  deterministic Metrics pipeline and common terminal/usable semantics
- `docs/architecture/03_ADR_log.md`: ADR-003, ADR-045 through ADR-048, ADR-133 through
  ADR-135, and ADR-157
- `docs/architecture/04_pipeline_and_agent_concepts.md`, especially Metrics stages and
  the agent's immutable observational scope
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, especially typed
  failure, partial, and usability boundaries
- `docs/architecture/10_open_decisions_and_backlog.md`, treating Open/Deferred entries
  only as boundaries and recognizing that this approved change resolves only the listed
  production Prometheus transport details
- `openspec/specs/metrics-analysis-pipeline/spec.md`
- `docs/development-guide.md` and `docs/development-workflow.md`

Advisory source:

- `.agents/PROJECT_KNOWLEDGE.md` (currently contains no validated entries)

Repository constraints:

- Implement only a production Prometheus provider behind the existing
  `MetricSeriesProvider` port for the existing `adapter_type="prometheus"` scope.
- Keep `app.metrics` provider-neutral. Source lookup, production-only target validation,
  authentication, HTTPX transport, response decoding, deadlines, retries, and safe
  diagnostics remain under `app.infrastructure.prometheus` and application composition.
- Preserve global `Settings` and shared `PROMETHEUS_SOURCES` parsing. A source rejected
  only by production acquisition must not prevent startup or alter capabilities,
  Observation creation, or Metric preflight.
- Preserve the opaque PromQL and exact pipeline-supplied window. Do not shift, rewrite,
  aggregate, infer cadence, add `offset`/`lookback_delta`, or alter current/reference
  attribution.
- Reuse the existing `MetricProviderScope`, `MetricAnalysisWindow`, `MetricSample`, typed
  acquisition outcomes, Metrics pipeline preparation, analysis, result, History,
  persistence, and lifecycle semantics unchanged.
- Add no dependency. The approved implementation uses the existing `httpx`, Pydantic,
  `pydantic-settings`, Python, and `asyncio` stack.
- Add no public API, database schema/migration, persistence model, frontend, LensRun or
  ObservationRun creation path, Observation orchestration, scheduler, Metrics Agent/tool
  behavior, Metric result contract, History behavior, or new public reason code.
- Never require a live Prometheus endpoint or repository credential. Verification uses
  injected/mock transport, monotonic time, sleep, and cancellation-observable bodies.
- Do not modify approved OpenSpec or `docs/architecture/`. Do not archive, push, open a
  pull request, or merge during execution of this plan.

At the exact commit SHA approved after independent review, the approved OpenSpec content
and plan structure become the frozen execution baseline. Acceptance sources and
GIVEN/WHEN/THEN assertions provide normative traceability; task numbers are supplementary
traceability. A task checkbox becomes complete only after every owning slice portion has
passed its gate.

Execution uses `PLANNED -> READY -> IN_PROGRESS -> COMPLETE`; `BLOCKED` records a defined
stop/escalation. Default execution is sequential. Only the Coordinator may change
execution status, accepted commit SHAs, handoff paths, verification/review results,
deviation dispositions, and execution notes after approval.

## Planning-review snapshot, approval, and pre-execution readiness

### Establish the immutable review and approval anchor

Before the final independent slice-plan review and before human approval of this plan:

1. Confirm the current branch is `feature/add-prometheus-metric-provider` and inspect the
   complete index/worktree. Preserve unrelated roadmap files outside this feature
   execution boundary; exclude every roadmap sidecar, `Zone.Identifier`, and other
   unrelated artifact from both the planning commit and later feature commits.
2. Stage exactly this complete planning snapshot and no other path:

   ```text
   openspec/changes/add-prometheus-metric-provider/.openspec.yaml
   openspec/changes/add-prometheus-metric-provider/proposal.md
   openspec/changes/add-prometheus-metric-provider/design.md
   openspec/changes/add-prometheus-metric-provider/specs/**
   openspec/changes/add-prometheus-metric-provider/tasks.md
   openspec/changes/add-prometheus-metric-provider/implementation-plan.md
   ```

3. Audit the staged names, commit the snapshot on the feature branch, and resolve the
   immutable planning-review commit SHA:

   ```bash
   set -euo pipefail
   change_dir=openspec/changes/add-prometheus-metric-provider
   snapshot_audit_dir=$(mktemp -d)
   current_branch=$(git branch --show-current)
   test "$current_branch" = "feature/add-prometheus-metric-provider"
   {
     printf '%s\n' \
       "$change_dir/.openspec.yaml" \
       "$change_dir/design.md" \
       "$change_dir/implementation-plan.md" \
       "$change_dir/proposal.md" \
       "$change_dir/tasks.md"
     find "$change_dir/specs" -type f -print
   } | LC_ALL=C sort > "$snapshot_audit_dir/expected"
   git diff --cached --name-only | LC_ALL=C sort > "$snapshot_audit_dir/actual"
   if ! diff -u "$snapshot_audit_dir/expected" "$snapshot_audit_dir/actual"; then
     exit 1
   fi
   git diff --quiet
   git commit -m "docs: plan Prometheus metric provider implementation"
   planning_review_sha=$(git rev-parse HEAD)
   test -n "$planning_review_sha"
   git status --porcelain > "$snapshot_audit_dir/status"
   test ! -s "$snapshot_audit_dir/status"
   printf '%s\n' "$planning_review_sha"
   ```

4. The independent slice-plan reviewer records that exact SHA in its review report and
   reviews the tree at that SHA, not mutable worktree content. Human approval must
   explicitly identify the same reviewed SHA.
5. If `.openspec.yaml`, proposal, design, any file in the complete specs tree, task text
   or structure, or any frozen part of this plan changes after review, the old review and
   approval are invalid. Create a new complete planning snapshot commit, repeat independent
   review against the new SHA, and obtain renewed human approval of that exact SHA.

After human approval, the Coordinator may record the approved SHA only in the mutable
`Human-approved planning SHA` field above and in `Execution notes`. That metadata update
does not create a new planning baseline and may not alter any frozen content.

### Reproducible approved-artifact integrity audit

Set the exact human-approved SHA; never infer it from `HEAD`, a branch name, or a merge
base:

```bash
set -euo pipefail
approved_sha="${APPROVED_PLANNING_SHA:?set APPROVED_PLANNING_SHA}"
git cat-file -e "$approved_sha^{commit}"
change_dir=openspec/changes/add-prometheus-metric-provider
immutable_paths=(
  "$change_dir/.openspec.yaml"
  "$change_dir/proposal.md"
  "$change_dir/design.md"
  "$change_dir/specs"
)
```

Run every audit below both immediately before VS-01 delegation and during VS-04 final
conformance. These are approved-artifact integrity checks, not implementation-diff checks.
The fenced blocks are consecutive fragments of one Bash audit script, split only for
readability: concatenate and execute them in order in one process. Each fragment repeats
`set -euo pipefail` defensively. Do not continue with a later fragment after any non-zero
exit. The recorded gate result is the exit status of the one complete script, so no later
successful command can mask an earlier failure.

The immutable OpenSpec paths must be byte-for-byte identical in committed `HEAD`, index,
and worktree:

```bash
set -euo pipefail
if ! git diff --exit-code "$approved_sha" HEAD -- "${immutable_paths[@]}"; then exit 1; fi
if ! git diff --cached --exit-code "$approved_sha" -- "${immutable_paths[@]}"; then
  exit 1
fi
if ! git diff --exit-code "$approved_sha" -- "${immutable_paths[@]}"; then exit 1; fi
```

Audit `tasks.md` separately against committed `HEAD`, index, and worktree. Normalization
must prove identical wording, numbering, ordering, structure, whitespace, task count, and
absence of additions/removals; the raw comparison permits only forward `[ ] -> [x]`
transitions. Each observed transition is then reconciled mechanically to every owning
slice's accepted commit and handoff recorded in execution metadata.

```bash
set -euo pipefail
audit_dir=$(mktemp -d)
task_path="$change_dir/tasks.md"
git show "$approved_sha:$task_path" > "$audit_dir/tasks.baseline"
git show "HEAD:$task_path" > "$audit_dir/tasks.head"
git show ":$task_path" > "$audit_dir/tasks.index"
cp "$task_path" "$audit_dir/tasks.worktree"

for current in head index worktree; do
  sed -E 's/^- \[( |x)\] /- [STATE] /' "$audit_dir/tasks.baseline" \
    > "$audit_dir/tasks.baseline.normalized"
  sed -E 's/^- \[( |x)\] /- [STATE] /' "$audit_dir/tasks.$current" \
    > "$audit_dir/tasks.$current.normalized"
  if ! diff -u "$audit_dir/tasks.baseline.normalized" \
    "$audit_dir/tasks.$current.normalized"; then
    exit 1
  fi
  if ! awk '
    FILENAME == ARGV[1] { baseline[FNR] = $0; baseline_count = FNR; next }
    FILENAME == ARGV[2] {
      current_count = FNR
      if ($0 == baseline[FNR]) next
      expected = baseline[FNR]
      changed = sub(/^- \[ \] /, "- [x] ", expected)
      if (changed != 1 || $0 != expected) invalid = 1
    }
    END {
      if (baseline_count != current_count) invalid = 1
      exit invalid
    }
  ' "$audit_dir/tasks.baseline" "$audit_dir/tasks.$current"; then
    exit 1
  fi
done
```

Mechanically reconcile every checked task in the current worktree with the frozen task
ownership table and execution overview. Every owning slice must be `COMPLETE` and must
have non-placeholder accepted commit and handoff fields:

```bash
set -euo pipefail
python3 - "$task_path" "$change_dir/implementation-plan.md" <<'PY'
import re
import sys
from pathlib import Path

tasks_text = Path(sys.argv[1]).read_text()
plan_text = Path(sys.argv[2]).read_text()

checked = set(re.findall(r"^- \[x\] (\d+\.\d+)\b", tasks_text, re.MULTILINE))
overview = {}
in_overview = False
in_tasks = False
owners = {}
for line in plan_text.splitlines():
    if line == "## Execution overview":
        in_overview = True
        continue
    if in_overview and line.startswith("## "):
        in_overview = False
    if line == "### Task ownership":
        in_tasks = True
        continue
    if in_tasks and line.startswith("## "):
        in_tasks = False
    if in_overview and re.match(r"^\| VS-\d\d ", line):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        overview[cells[0]] = (cells[4], cells[5], cells[6])
    if in_tasks and re.match(r"^\| \d+\.\d+ ", line):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        task_id = cells[0].split(maxsplit=1)[0]
        owners[task_id] = set(re.findall(r"VS-\d\d", cells[1]))

for task_id in sorted(checked):
    if task_id not in owners or not owners[task_id]:
        raise SystemExit(f"checked task {task_id} has no explicit owning slice")
    for owner in owners[task_id]:
        status, commit, handoff = overview.get(owner, ("", "-", "-"))
        if status != "COMPLETE" or commit == "-" or handoff == "-":
            raise SystemExit(f"checked task {task_id} lacks accepted metadata for {owner}")
PY
```

Audit `implementation-plan.md` against committed `HEAD`, index, and worktree by producing
a frozen projection. Only the top-level `Status` and `Human-approved planning SHA`, the
execution overview's `Status`/`Commit`/`Handoff` cells, and all content below
`## Execution notes` are normalized as mutable. Every other byte—including graph, goals,
ownership, boundaries, risk, coverage, verification, context packs, and gates—must match.

```bash
set -euo pipefail
plan_path="$change_dir/implementation-plan.md"
git show "$approved_sha:$plan_path" > "$audit_dir/plan.baseline"
git show "HEAD:$plan_path" > "$audit_dir/plan.head"
git show ":$plan_path" > "$audit_dir/plan.index"
cp "$plan_path" "$audit_dir/plan.worktree"

frozen_plan() {
  awk '
    /^## Execution notes$/ { exit }
    /^\*\*Status:\*\*/ { print "**Status:** [MUTABLE]"; next }
    /^\*\*Human-approved planning SHA:\*\*/ {
      print "**Human-approved planning SHA:** [MUTABLE]"; next
    }
    /^\| VS-[0-9][0-9] / {
      split($0, cell, "|")
      print "|" cell[2] "|" cell[3] "|" cell[4] "|" cell[5] \
        "| [MUTABLE] | [MUTABLE] | [MUTABLE] |"
      next
    }
    { print }
  ' "$1"
}

frozen_plan "$audit_dir/plan.baseline" > "$audit_dir/plan.baseline.frozen"
for current in head index worktree; do
  frozen_plan "$audit_dir/plan.$current" > "$audit_dir/plan.$current.frozen"
  if ! diff -u "$audit_dir/plan.baseline.frozen" "$audit_dir/plan.$current.frozen"; then
    exit 1
  fi
done
```

Before VS-01, also require the expected branch, successful strict change validation, and
an empty index/worktree, including no untracked files:

```bash
set -euo pipefail
readiness_audit_dir=$(mktemp -d)
current_branch=$(git branch --show-current)
test "$current_branch" = "feature/add-prometheus-metric-provider"
openspec validate add-prometheus-metric-provider --strict
git status --porcelain > "$readiness_audit_dir/status"
test ! -s "$readiness_audit_dir/status"
```

Any failure is a Coordinator stop condition. It is not delegated to VS-01 and cannot be
waived by an implementer.

### Separate implementation-diff audit

Implementation scope is audited separately from approved-artifact integrity. During
VS-04 compare the human-approved planning SHA to implementation `HEAD`, inspect every
commit/path/diff, and classify production, test, documentation, task-state, and mutable
plan-metadata changes:

```bash
set -euo pipefail
git cat-file -e "$approved_sha^{commit}"
git log --oneline "$approved_sha"..HEAD
git diff --name-status "$approved_sha"..HEAD
git diff "$approved_sha"..HEAD
```

A merge-base-to-main diff may supplement this check but must not substitute for either
the approved-SHA implementation diff or the committed/index/worktree integrity audits.

## Slice graph

```text
VS-01 -> VS-02 -> VS-03 -> VS-04
```

## Execution overview

| Slice | Goal | Depends on | Risk | Status | Commit | Handoff |
|---|---|---|---|---|---|---|
| VS-01 | Source-safe transport-free walking skeleton through the existing Metric port | none | high-risk | COMPLETE | 1217266598aa5f20b902e9ae2edfe1da2ffed6c2 | `implementation/VS-01-handoff.md` |
| VS-02 | Complete bounded single-attempt request, mapping, and status classification | VS-01 | high-risk | COMPLETE | `99bce08`, `d01a104`, `0d35520`, `ee4d364` | `implementation/VS-02-handoff.md` |
| VS-03 | Hard deadlines, deterministic retries, and terminal resilience integration | VS-02 | high-risk | BLOCKED | - | - |
| VS-04 | Compatibility, operational documentation, and whole-change conformance | VS-03 | normal | PLANNED | - | - |

## Slice definitions

### VS-01 — Source-safe transport-free walking skeleton

**Behavioral goal:** Compose one source-aware production `MetricSeriesProvider` behind
the existing port without exposing a callable HTTP path yet. Exact source selection and
production-only target validation return typed zero-request outcomes, and an absent or
unknown source flows through the real composed provider and unchanged Metrics pipeline to
the existing minimal failed Metric result.

**OpenSpec coverage:** source-resolution requirement and its exact-ID, unavailable,
unsafe-target, and shared-consumer scenarios; composition requirement's port/domain
boundary scenario; modified pipeline's transport-free scenario; real-provider current-
unavailable portion of the failure-preservation scenario; tasks 1.1, 1.3, 1.4,
pre-transport portions of 2.1 and 3.5, configuration/zero-request portions of 1.2 and
4.1, current-unavailable portion of 4.5, complete production-valid and production-invalid
shared-surface regression task 4.6, and per-symbol
docstrings from 5.1.

**Dependencies:** none beyond the human-approved planning-SHA readiness gate.

**Vertical boundary:** compatible shared registry snapshot -> real source-aware provider
composition -> `acquire(scope, window)` -> exact source lookup -> production-only URL/
path/transport validation -> existing typed unavailable or failure with zero client/
request activity -> existing Metrics pipeline -> unchanged current-acquisition failure
and minimal failed Metric result. A valid selected source may be represented internally
for VS-02, but VS-01 exposes no callable real HTTP acquisition path.

**Expected code impact:**

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/infrastructure/prometheus/` | add production composition/configuration modules; minimally extend exports | Registry snapshot, exact selection, production-only URL/path validation, unavailable/invalid zero-request provider behavior; no HTTP request implementation |
| `backend/src/app/main.py::lifespan` | modify | Construct/expose the source-aware provider only as an injectable application dependency; start no execution |
| `backend/tests/test_prometheus_metric_provider_configuration.py` | add | Registry compatibility, source isolation, exhaustive URL/path allow/reject matrix, secret-safe pre-transport diagnostics, zero client/request evidence |
| `backend/tests/test_metric_analysis_pipeline.py` | modify narrowly | Real composed absent/unknown source -> port outcome -> current minimal failed result; retain fake-provider regressions |
| `backend/tests/test_health.py`, `test_observation_contracts.py`, `test_observation_api.py`, `test_prometheus_adapter.py` | modify only for focused regressions | Startup and existing source-consumer compatibility for a production-invalid shared source |

**Contracts consumed/changed:** consumes the existing settings credential variants and
`MetricSeriesProvider.acquire` input/outcome contracts unchanged. Production-private
selected-source/validated-target structures may be added. The preflight
`PrometheusQueryAdapter`, its exceptions/results, and public projections remain unchanged
and are not reused as the production provider.

**Non-goals:** any HTTP client/request, authentication application, valid response
mapping, step/form construction, body reading, status/error-envelope classification,
retries/backoff, deadlines/cancellation, reference acquisition, or analytical change.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS01-AC01 | Resolve source / exact ID and unavailable source | Absent registry, unknown ID, and two configured sentinel sources | Call `acquire` through the real composed provider | Absent/unknown return fixed safe `MetricSeriesUnavailable` with zero client/request activity and no fallback; source lookup is exact | unit + transport ledger | outcome/category and fail-on-client-construction assertions |
| VS01-AC02 | Unsafe selected target | Valid HTTPS/exact-loopback targets plus every rejected scheme, authority, host, query, fragment, and ambiguous path form | Select and validate only the requested configured source | Accepted source becomes a private validated selection for later transport; rejected source returns fixed safe failure with zero client/request activity; shared Settings construction is unchanged | parameterized unit + startup | exhaustive raw URL/path vectors and zero-construction ledger |
| VS01-AC03 | Current unavailable end to end | Absent registry and separately unknown source ID, real source-aware composition, existing Metrics dependencies, and a fail-on-transport seam | Inject that provider into `MetricAnalysisPipeline` and analyze current | `acquire()` returns `MetricSeriesUnavailable`; pipeline preserves existing current-unavailable/current-acquisition failure and minimal failed Metric result semantics; zero HTTP requests occur | service | explicit real composition -> port -> acquire -> pipeline/result assertions for both cases |
| VS01-AC04 | Production-invalid current outcome | Shared loading accepts the selected source but production-only validation rejects it | Call real provider directly and through current pipeline | Provider returns fixed `MetricSeriesAcquisitionFailure`, pipeline preserves its existing minimal failed result, and zero HTTP requests occur | service + transport ledger | provider and pipeline outcome assertions with fail-on-request seam |
| VS01-AC05 | Production-invalid shared-consumer compatibility | Production-invalid source accepted by shared settings | Start app; exercise capabilities, Observation creation, preflight, and production acquisition | Startup and existing public/preflight behavior remain compatible; only production acquisition rejects the source with zero requests from the production transport | API + service | lifespan/API/service/preflight regressions with separate transport ledgers |
| VS01-AC06 | Secret-safe pre-transport composition | Sentinel Bearer token and Basic username/password in selected and unselected sources | Load, resolve, reject invalid target, and inspect outcomes/logs/errors/repr/public projections | No diagnostic/output exposes token, password, Authorization, or configured username; internal shared credential representation is unchanged; no credential reaches a URL | unit + repository audit | sentinel scan and exact safe diagnostic snapshots |
| VS01-AC07 | Port-only composition | Constructed application state and source-aware provider | Inspect imports/types without starting a run | Provider satisfies `MetricSeriesProvider`; Metric modules import no settings/HTTPX/Prometheus response types; construction creates/advances no LensRun or ObservationRun | static audit + service | protocol-use test, import scan, lifecycle spy |
| VS01-AC08 | Production-valid shared-consumer compatibility | Valid production source configuration and fail-on-production-transport seam | Start app; exercise capabilities, Observation creation, and existing Metric preflight without calling production acquire | Startup succeeds; capabilities and creation retain their exact behavior; preflight retains its independent adapter, 15-second/no-retry policy, labels/warnings, and public error mapping; these existing surfaces create zero production-provider HTTP activity | API + service + transport ledger | valid-source lifespan/capabilities/create/preflight regression with separate preflight and fail-on-production ledgers |

**Counterexample guards:** URL vectors include exact IPv4/IPv6/hostname loopback versus
look-alikes, percent-encoding case variants, raw backslashes, repeated/interior slashes,
dot segments, whitespace/control/parser-normalized forms, and credentials in authority.
The production-invalid compatibility source contains otherwise valid credentials so
eager shared validation cannot pass. Current-unavailable tests instantiate the real
source-aware provider and execute `MetricAnalysisPipeline`; directly injecting a typed
outcome or a fake provider does not satisfy VS01-AC03. VS01-AC08 gives preflight its own
adapter ledger and makes the production transport fail on construction/use, so merely
sharing a client or silently invoking production acquisition cannot pass.

**Focused verification:** `cd backend && uv run pytest
tests/test_prometheus_metric_provider_configuration.py
tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py
tests/test_observation_contracts.py tests/test_observation_api.py tests/test_health.py -q`;
targeted Ruff and Ruff format checks for changed source/tests; `git diff --check`.

**Context pack:** root `AGENTS.md`; approved source-resolution, composition, current-
unavailable/failure-preservation, and modified provider-boundary requirements/scenarios;
design decisions on selected-source validation, infrastructure composition, and preflight
separation; ADR-003, ADR-045, ADR-048, ADR-133, ADR-157; architecture Metrics provider/
pipeline boundaries; current settings, preflight adapter/contracts, observation service/
API, lifespan, Metric contracts/port/pipeline/result builder, and focused tests.

**Handoff expectations:** VS01-AC01 through VS01-AC08 evidence; exact public/private
symbols; URL/path allow/reject table; client/request zero-activity ledgers; direct and
pipeline unavailable/failure results; app-state provider type; shared-consumer regressions;
separate production-valid and production-invalid startup/capabilities/create/preflight
results; confirmation task 4.6 is complete; secret/import/dependency audit; deviations;
focused commands; explicitly deferred HTTP
acquisition/mapping/resilience; shared-knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS01 evidence passes; absent/unknown source and selected invalid
source return the approved typed outcomes with zero transport; real composed current-
unavailable and invalid-source outcomes traverse the existing pipeline to unchanged
minimal failed Metric results; valid-source setup exposes no callable HTTP path; startup
and capabilities/creation/preflight remain compatible for both production-valid and
production-invalid shared sources with zero production transport activity; all of task
4.6 is proven in this slice; no domain/public/schema/dependency/orchestration change
appears; docstrings and focused checks pass; independent high-risk review returns
`SLICE REVIEW PASS`; one atomic implementation commit and handoff exist, followed by
Coordinator acceptance metadata.

### VS-02 — Safely bounded single-attempt Prometheus acquisition

**Behavioral goal:** Add one complete production HTTP attempt behind the VS-01 provider:
construct the exact authenticated range query, stream one bounded response, and classify
its complete result through a single-attempt internal outcome model. This slice owns all
interacting body/status/envelope/success branches, including proving that an oversized or
otherwise unusable body is terminal before an HTTP status that would be retry-eligible.

**OpenSpec coverage:** exact-query requirement except multi-attempt identity; complete
float-series mapping and excessive-response/warning requirements; one-attempt portions of
the deadline/failure requirement including strict error envelopes, retry-eligible status
classification, deterministic rejection, bare 503, body/status/success precedence, and
initial completion; composition verification through successful current/reference paths;
modified pipeline's zero/one/multiple-reference scenarios; tasks 1.2 credential HTTP
boundary, 2.1-2.5, one-attempt classification portion of 3.3, 4.1-4.4, successful/empty/
current-failure/reference-failure portions of 4.5,
and per-symbol docstrings from 5.1.

**Dependencies:** VS-01 accepted.

**Vertical boundary:** private validated selected source -> exact immutable logical
request and authentication -> one injected HTTPX attempt with redirects/proxy trust
disabled and normal TLS verification -> complete streamed body capped at 1 MiB -> ordered
single-attempt body/error-envelope/status/success classifier -> private available,
terminal timeout/failure, or retry-eligible classification -> existing public provider
outcome -> unchanged current or independently requested reference pipeline behavior.

**Expected code impact:** extend only production modules under
`backend/src/app/infrastructure/prometheus/`, add focused production-provider HTTP tests,
and add narrow adapter-backed current/reference tests in
`backend/tests/test_metric_analysis_pipeline.py`. The existing preflight adapter changes
only if a low-level infrastructure-private helper can be shared without altering its
independent contract.

**Contracts consumed/changed:** the public provider still returns only existing
`MetricSeriesAvailable`, `MetricSeriesAcquisitionFailure`, and
`MetricSeriesAcquisitionTimeout`. A private strict attempt result may distinguish
`available`, terminal `failure|timeout`, and `retry_eligible(status)` for VS-03. Prometheus
envelopes, labels, annotations, bodies, credentials, and transport objects remain private.
`MetricSample` intentionally admits non-finite values for existing preparation.

**Non-goals:** attempt/acquisition hard-deadline orchestration; HTTPX exception taxonomy;
sleep/backoff; retry admission; second/third attempts; retry exhaustion; changing sample
preparation, comparisons, result, History, agent, persistence, or preflight behavior.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS02-AC01 | Exact request target and resolution | All accepted root/prefix forms and approved fractional/boundary windows from 0.5s through 3600.001s | Build/send one request | Exactly one form POST targets `<origin><preserved-prefix>/api/v1/query_range`; query and RFC3339 bounds are exact; step matches every double-ceiling vector and inclusive cap; timeout=10s/limit=2 are present; no other field, offset, rewrite, redirect, or proxy trust appears | parameterized unit + HTTP boundary | target/form/client snapshots and task 4.2 table |
| VS02-AC02 | Authentication and credential safety | Bearer and Basic profiles with sentinel secrets/username, plus redirect response | Execute one attempt | Bearer header or preemptive Basic applies only to the exact target; redirects are not followed; TLS verifies; URL/outcomes/logs/errors omit all protected credential values and configured Basic username | HTTP boundary + audit | request-header ledger, redirect host ledger, sentinel leakage scan |
| VS02-AC03 | One valid float series | Strict matrix with string labels and ordered finite and non-finite float pairs | Decode/map | Existing available outcome contains UTC samples in provider order; `NaN/+Inf/-Inf` survive; labels/response do not cross the port; existing preparer alone filters/sorts/rejects | unit + service | exact provider tuple followed by unchanged preparation assertions |
| VS02-AC04 | Zero/multi/histogram/malformed mapping | Empty result; two series; native/mixed histogram; malformed labels, values, pairs, timestamps, numeric strings, envelope/result type | Classify one complete body | Empty is available; one valid series maps; every unrepresentable shape is terminal safe failure without merge, repair, coercion, or truncation | parameterized unit | exhaustive strict success-shape matrix |
| VS02-AC05 | Body/sample bounds and non-vacuous precedence | Exact/over 1 MiB declared and streamed bodies, exact 61/62 samples, and separately a complete bounded malformed body at 429/500/502/504 | Run the same single-attempt classifier | Exact caps succeed when otherwise valid; over-cap/62 are terminal failure; each bounded malformed retryable-status body yields private `retry_eligible`; the same status with an oversized/unusable body yields terminal failure, proving body precedence through interacting implemented branches | streaming HTTP boundary + internal classifier | paired per-status bounded-versus-oversized tests with body close and attempt-result assertions |
| VS02-AC06 | Success annotations | Empty/non-empty warnings and infos plus malformed fields | Classify one successful response | Non-empty warnings are terminal failure; infos do not affect data and text is discarded; malformed annotations fail; no text leaks | parameterized unit | complete success annotation matrix |
| VS02-AC07 | Strict error/status classification | Valid timeout/canceled error envelopes with valid annotations; missing/malformed required fields; other errors; bare/malformed 503; other non-success; malformed bounded success | Classify one attempt | Strict timeout/canceled is terminal timeout; 429/500/502/504 become private retry-eligible unless body rule won; valid other errors, bare/malformed 503, and other non-success are terminal failure; only success status reaches success validation | parameterized unit + HTTP boundary | full error-envelope/status/body decision table |
| VS02-AC08 | Deterministic rejection and leakage | Auth/query/contract/warning failures and provider-authored/error/sample/label sentinel content | Execute one attempt and inspect outcome/logs | Rejections are terminal, not retry-eligible; diagnostics are fixed/bounded and expose no query, URL, body, headers, exception/provider text, credentials, labels, or samples | unit + audit | fixed diagnostic inventory and sentinel scans |
| VS02-AC09 | Successful current/reference integration | Empty and one-series current; ordered equal-duration references including one terminal single-attempt failure | Run composed provider through existing pipeline | Empty current remains completed-insufficient; successful current/reference requests preserve exact bounds/equal resolution/configured order; failed reference alone is omitted with accepted partial; analytical contracts stay unchanged | service | real provider request ledger and exact result comparisons |

**Counterexample guards:** target tests preserve case/characters and reject any URL join or
decode behavior already validated by VS-01. Response tests reject label/value coercion,
boolean/non-finite timestamps, wrong pair containers/lengths, and histogram mixing.
VS02-AC05 pairs every retryable status with both a complete bounded malformed body and an
over-cap body and asserts different internal attempt variants; a test that merely observes
public failure, or runs before retry eligibility exists, cannot pass. References surround
a failed offset with successes to expose short-circuit/default/baseline behavior.

**Focused verification:** `cd backend && uv run pytest
tests/test_prometheus_metric_provider.py tests/test_prometheus_metric_provider_configuration.py
tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py -q`; targeted Ruff
and format checks; `git diff --check`.

**Context pack:** accepted VS-01 handoff; approved exact-query, mapping, warning/body,
one-attempt failure-table, composition, and modified Metrics scenarios; design decisions
on immutable request, authentication, resolution, series sentinel, bounded streaming,
strict envelopes, annotations, and classification order; ADR-003, ADR-133-135, ADR-157;
current Metric preprocessing/references/pipeline contracts/tests; VS-01 validated-source
and composition seams; existing preflight adapter only as a compatibility boundary.

**Handoff expectations:** VS02-AC01 through VS02-AC09 evidence; private attempt-result
variants; exact target/form/auth/client snapshots; step vectors; response and complete
single-attempt decision matrices; paired non-vacuous body/status precedence results;
current/reference results; cleanup and leakage audits; deviations; focused commands;
explicitly deferred deadlines/exceptions/retry orchestration; shared-knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS02 evidence passes; the full single-attempt body/envelope/status/
success classifier exists before precedence is claimed; bounded malformed retryable
statuses and oversized retryable-status bodies prove distinct interacting branches;
successful data is complete and bounded; target/auth/request/sample fidelity and
current/reference semantics hold; no resilience orchestration or excluded scope leaks in;
focused checks pass; independent high-risk review returns `SLICE REVIEW PASS`; one atomic
implementation commit and handoff exist, followed by Coordinator acceptance metadata.

### VS-03 — Deterministic resilience and typed failure mapping

**Behavioral goal:** Complete production acquisition with hard monotonic attempt/acquire
deadlines, cancellation-safe cleanup, exact HTTPX exception handling, and a retry
orchestrator that consumes VS-02's complete single-attempt classifications. Every public
acquisition terminates with the approved existing typed outcome, exact 1..3 attempt
behavior, and unchanged current/reference pipeline semantics.

**OpenSpec coverage:** deadline/failure scenarios for retry eligibility/admission,
initial/retry completion, exhaustion, HTTPX taxonomy, proven hard timeout, and final
current/reference failure semantics; logical-request-across-retries scenario; complete
production resilience integration over all VS-02 attempt variants; tasks 3.1, 3.2,
exception/deadline/retry-orchestration portions of 3.3, 3.4, transport-attempt portions
of 3.5, retry/deadline portions of 4.3/4.4, current timeout/final retry failure and
reference timeout/failure portions of 4.5, plus per-symbol docstrings from 5.1.

**Dependencies:** VS-02 accepted.

**Vertical boundary:** VS-02 immutable request and complete one-attempt function ->
injected monotonic 50-second acquire budget -> 15-second deadline around each request and
body read -> HTTPX exception classifier or VS-02 attempt result -> remaining-budget
admission -> exact fixed wait and up to two identical retries -> cancellation/resource
closure -> existing typed available/failure/timeout -> unchanged current failed or
reference partial result.

**Expected code impact:** extend the production provider's infrastructure-private
deadline, retry, clock/sleeper, exception-classifier, and orchestration seams plus focused
production-provider tests and narrow adapter-backed pipeline tests. VS-02 response/body/
status mapping is consumed, not reimplemented. Do not change Metric domain, pipeline,
result builder, persistence, or preflight policy.

**Contracts consumed/changed:** only existing `MetricSeriesAcquisitionFailure` and
`MetricSeriesAcquisitionTimeout` classifications are produced, with fixed bounded safe
diagnostics and optional safe status codes kept infrastructure-private where the existing
port cannot represent them. No new public/domain outcome or reason is introduced.

**Non-goals:** changing VS-02 request, authentication, body, envelope, annotation, sample,
or status classification; retrying timeout or any VS-02 terminal rejection; jitter/
Retry-After; proxy/redirect support; changing current/reference pipeline mapping;
Observation-level deadlines or concurrency.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS03-AC01 | Attempt/acquire hard deadlines | Hanging request, slow-progress body, retry waits, and cancellation-observable resources | Cross 15s attempt or 50s acquire deadline | Typed timeout wins, in-flight work is cancelled, response/client closes, and no work/wait continues after total deadline | deterministic clock + async service | injected deadline runner/clock/body ledgers |
| VS03-AC02 | Retry eligibility/count/identity | ConnectError and each VS-02 retry-eligible 429/500/502/504 result sequence succeeding on attempt 1, retry 1, retry 2, or never | Acquire | Exact attempt counts are 1/2/3/3 with waits 0.5/1.0, never a fourth; every attempt uses byte-identical logical request and same source/auth/configuration | parameterized HTTP boundary | complete attempt/form/auth/config snapshots and sleep ledger |
| VS03-AC03 | Retry admission | For ConnectError and each retryable status, remaining budgets just below/at/above wait+15s | Admit next retry | Insufficient budget returns timeout with no wait/request; sufficient budget waits exactly and retries; three actually executed eligible failures exhaust as failure | deterministic unit + HTTP boundary | boundary clock vectors for retry 1 and retry 2 |
| VS03-AC04 | HTTPX hierarchy | Timeout subclasses, ConnectError, remaining TransportError subclasses, and non-Transport request/client errors named by the spec | Classify each | Only ConnectError retries; timeout subclasses time out without retry; every other named class fails without retry; no generic transport retry branch exists | parameterized unit | hierarchy table including representative subclasses and exact counts |
| VS03-AC05 | Hard-deadline precedence | Deadline completion races an HTTPX exception | Observe attempt/acquire boundary | Hard local timeout classification wins and resources close, regardless of simultaneously observed exception | deterministic concurrency unit | controlled race/cancellation seam |
| VS03-AC06 | Terminal versus retry-eligible integration | Every VS-02 terminal attempt result and retry-eligible result | Run full acquisition orchestrator | Terminal outcomes perform no retry/sleep; only retry-eligible statuses enter admission; retry exhaustion becomes failure; no body/status/envelope policy is reclassified by the orchestrator | parameterized service | VS-02 variant-to-attempt-count/outcome matrix |
| VS03-AC07 | Pipeline failure preservation | Real provider timeout and terminal/retry-exhausted failure on current versus one configured reference | Run existing pipeline | Current produces existing minimal failed Metric result; reference alone is omitted and yields accepted `reference_unavailable/reference_periods` partial while usable current survives | service | real-provider injected current/reference matrix with result equality |

**Counterexample guards:** retries mix ConnectError and all VS-02 retry-eligible status
variants across attempts; admission tests use exact equality as fitting; race tests retain
an exception so catch order alone cannot fake deadline precedence. The orchestrator matrix
feeds VS-02 terminal body/envelope/warning/status results and asserts no sleep/additional
request, preventing a broad "retry any failure" branch.

**Focused verification:** focused production provider and Metrics pipeline tests,
including deterministic async cancellation/resource tests; targeted Ruff and format
checks; `git diff --check`.

**Context pack:** accepted VS-02 handoff and its attempt-result decision matrix; approved
deadline/retry/exception/current-reference scenarios; design decision on hard budgets,
retry admission, exhaustion, and ordered exception precedence; exact-query logical-request
identity; ADR-045, ADR-133-135, ADR-157; current typed provider outcomes and Metrics
pipeline mappings; HTTPX 0.28 exception hierarchy as used by the installed dependency.

**Handoff expectations:** VS03-AC01 through VS03-AC07 evidence; orchestration table linked
to VS-02 attempt variants; attempts/waits/budget traces; identical-request snapshots;
cancellation/cleanup and hard-deadline precedence proof; HTTPX taxonomy; final pipeline
outcomes; deviations; focused results; shared-knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS03 evidence passes; 15/50-second hard deadlines cover body
reads and waits; resources close on timeout/failure; retries occur only for ConnectError
or VS-02's retry-eligible statuses and only when admitted; every named exception and
terminal-versus-retry orchestration branch is tested; VS-02 classification remains
unchanged; logical request identity and secret-safe outcomes hold across attempts;
current/reference semantics remain unchanged; the slice remains bounded to orchestration
and its integration; focused checks pass; independent high-risk review returns
`SLICE REVIEW PASS`; one atomic implementation commit and handoff exist, followed by
Coordinator acceptance metadata.

### VS-04 — Compatibility, documentation, and whole-change conformance

**Behavioral goal:** Make the completed provider operationally understandable and prove
as a whole that it remains an infrastructure-only injected capability: shared startup,
capabilities, Observation creation, Metric preflight, fake-based pipeline tests, domain
imports, public contracts, persistence, and dependency/schema surfaces remain unchanged.

**OpenSpec coverage:** conformance rerun of every requirement/scenario already implemented
and owned by VS-01 through VS-03; documentation and final audit tasks 5.1-5.4 only. Tasks
4.5 and 4.6 must already be complete through their behavioral owning slices; VS-04 does
not implement or add missing coverage for them.

**Dependencies:** VS-03 accepted.

**Vertical boundary:** placeholder-only deployment configuration and developer guidance
-> application startup/composed provider -> mocked production current/reference runs and
existing public preflight/API/fake/persistence suites -> repository-wide static and
verification gates -> deployable, provider-neutral change with no new public execution
surface.

**Expected code impact:** `.env.example`, `docs/development-guide.md`, Coordinator-owned
task checkboxes and mutable execution metadata only. No production code or test code may
be added or changed in this slice. A discovered production/test gap stops VS-04 and
routes a targeted correction through VS-01, VS-02, or VS-03 ownership and the required
high-risk review before VS-04 restarts.

**Contracts consumed/changed:** documents and verifies existing contracts only. No
production or test contract changes. Public production-provider class/interface-method
docstrings must already have been added by their owning implementation slices; VS-04
audits them.

**Non-goals:** implementing or correcting production behavior/tests; live smoke test;
secrets in examples; production Metrics model selection; Observation execution/
orchestration; archive/PR/push; fixing an unrelated pre-existing failure.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS04-AC01 | Documentation task | Placeholder source configuration and approved production policy | Read deployment/developer docs | HTTPS/loopback and exact prefix grammar, auth/exclusions, secrets, resolution/limits/warnings, attempts/deadlines/retries/classification, lookback/staleness, and production-only validation are concise and exact without real credentials | documentation review + secret scan | `.env.example`/guide audit against task 5.1 checklist |
| VS04-AC02 | Shared behavior preservation | Production-valid and production-invalid shared sources | Run startup, capabilities, Observation create, and preflight suites | Existing outputs, 15-second/no-retry preflight, labels/warnings, and public error mapping remain compatible; production-invalid source affects only production acquire | API + service regression | focused existing and added tests with separate ledgers |
| VS04-AC03 | Provider-neutral pipeline and persistence | Existing fake provider matrix plus completed VS-01 through VS-03 real-provider tests | Rerun Metric tests and inspect modules/artifacts without editing them | Zero/one/multiple references remain independent; fake tests use no transport; all result variants and rollback behavior round-trip unchanged; no raw transport/provider data persists | service + persistence + static audit | existing completed test suites and import scan |
| VS04-AC04 | Scope/dependency/schema/API audit | Baseline-to-HEAD implementation diff and manifests/migrations/routes/contracts | Review change | No dependency, migration/schema, public API, Metric result/analysis, History, Agent, reference semantics, persistence, or Observation orchestration change exists | repository audit | diff/name-status, lock/manifest/migration/route/contract checks |
| VS04-AC05 | Final verification | Completed sequential slices and clean execution state | Run focused tests, strict OpenSpec validation, and `make check` | Every command passes accurately; approved artifacts remain intact; task ownership is reconciled; worktree is clean after accepted commits/metadata | repository gate | recorded commands, baseline integrity audit, task/plan mutable-only audit |

VS04-AC05 includes this separate final-completion assertion after the authorized
transition audit above. It fail-closes unless the approved snapshot, current `tasks.md`,
and frozen task ownership matrix contain the same 24 unique ordered task IDs; every
current task is checked; and every owner is `COMPLETE` with accepted commit and handoff
metadata:

```bash
set -euo pipefail
approved_sha="${APPROVED_PLANNING_SHA:?set APPROVED_PLANNING_SHA}"
git cat-file -e "$approved_sha^{commit}"
change_dir=openspec/changes/add-prometheus-metric-provider
final_task_audit_dir=$(mktemp -d)
git show "$approved_sha:$change_dir/tasks.md" > "$final_task_audit_dir/tasks.baseline"
cp "$change_dir/tasks.md" "$final_task_audit_dir/tasks.current"

python3 - \
  "$final_task_audit_dir/tasks.baseline" \
  "$final_task_audit_dir/tasks.current" \
  "$change_dir/implementation-plan.md" <<'PY'
import re
import sys
from pathlib import Path

TASK = re.compile(r"^- \[([ x])\] (\d+\.\d+)\b")


def task_entries(path: str) -> list[tuple[str, str]]:
    return [
        (match.group(2), match.group(1))
        for line in Path(path).read_text().splitlines()
        if (match := TASK.match(line))
    ]


baseline = task_entries(sys.argv[1])
current = task_entries(sys.argv[2])
if len(baseline) != 24 or len({task_id for task_id, _ in baseline}) != 24:
    raise SystemExit("approved snapshot must contain exactly 24 unique task IDs")
if [task_id for task_id, _ in current] != [task_id for task_id, _ in baseline]:
    raise SystemExit("current task IDs/count/order differ from approved snapshot")
if any(state != "x" for _, state in current):
    raise SystemExit("all 24 approved tasks must be checked at final conformance")

plan_lines = Path(sys.argv[3]).read_text().splitlines()
overview = {}
owners = {}
in_overview = False
in_ownership = False
for line in plan_lines:
    if line == "## Execution overview":
        in_overview = True
        continue
    if in_overview and line.startswith("## "):
        in_overview = False
    if line == "### Task ownership":
        in_ownership = True
        continue
    if in_ownership and line.startswith("## "):
        in_ownership = False
    if in_overview and re.match(r"^\| VS-\d\d ", line):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        overview[cells[0]] = (cells[4], cells[5], cells[6])
    if in_ownership and re.match(r"^\| \d+\.\d+ ", line):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        task_id = cells[0].split(maxsplit=1)[0]
        if task_id in owners:
            raise SystemExit(f"duplicate ownership row for task {task_id}")
        owners[task_id] = set(re.findall(r"VS-\d\d", cells[1]))

approved_ids = [task_id for task_id, _ in baseline]
if list(owners) != approved_ids:
    raise SystemExit("frozen ownership matrix task IDs/count/order are not exact")
for task_id in approved_ids:
    if not owners[task_id]:
        raise SystemExit(f"task {task_id} has no explicit owner")
    for owner in owners[task_id]:
        status, commit, handoff = overview.get(owner, ("", "-", "-"))
        if status != "COMPLETE" or commit == "-" or handoff == "-":
            raise SystemExit(
                f"task {task_id} owner {owner} lacks passed gate/accepted metadata"
            )
PY
```

After every approved-artifact and task audit succeeds, run the remaining final gate in a
single fail-fast shell. A successful exit means every listed command and assertion passed:

```bash
set -euo pipefail
final_gate_dir=$(mktemp -d)
current_branch=$(git branch --show-current)
test "$current_branch" = "feature/add-prometheus-metric-provider"
openspec validate add-prometheus-metric-provider --strict
make check
git diff --check
git status --porcelain > "$final_gate_dir/status"
test ! -s "$final_gate_dir/status"
```

**Counterexample guards:** compatibility runs use a production-invalid source that shared
Settings still accepts; preflight tests record attempts and warnings so replacing it with
the production policy fails; persistence tests include every Metric terminal result and
rollback path; static scans cover both imports and serialized artifacts; secret scan uses
sentinel values absent from placeholder docs.

**Focused verification:** in one fail-fast Coordinator gate, run the committed/index/
worktree immutable, task-transition, task-ownership, and frozen-plan audits above; the
24/24 final task assertion; focused provider/configuration/preflight/Metrics/integration
tests; `openspec validate add-prometheus-metric-provider --strict`; `make check`;
approved-SHA implementation-diff and scope audits; `git diff --check`; and the final clean
status assertion. Every shell block starts with `set -euo pipefail`, and loop comparisons
use explicit `if ! ...; then exit 1; fi` handling.

**Context pack:** accepted VS-03 handoff and all earlier handoffs; complete approved
OpenSpec; all architecture/ADR sources listed above; `.agents/PROJECT_KNOWLEDGE.md`;
development guide/workflow; root Makefile and manifests; full baseline-to-HEAD diff;
changed production/tests/docs and all focused existing regressions.

**Handoff expectations:** VS04-AC01 through VS04-AC05 evidence; documentation checklist;
public docstring audit; exact focused and full command results; regression counts;
approved-SHA committed/index/worktree artifact/task/plan integrity results; explicit
24/24 checked-task and all-owner acceptance result; dependency/schema/API/import/secret
audits; final clean status; deviations and shared-knowledge candidates; explicit note
that the change remains unarchived pending whole-change verification/review.

**Risk:** normal

**Completion gate:** VS04 evidence and all earlier acceptance IDs regress green without
production/test edits in VS-04;
documentation and docstrings are complete and secret-safe; task ownership is reconciled;
focused tests, strict OpenSpec validation, baseline implementation diff, approved-artifact
integrity, checkbox-only transition audit, exact 24/24 completion/ownership assertion,
mutable-only plan audit, scope/dependency/schema/API/secret audits, clean status, and
`make check` pass under fail-fast command execution. Any implementation/test gap is routed
back to its owning high-risk slice rather than fixed here. One atomic documentation/
conformance commit and handoff exist, followed by Coordinator acceptance metadata. The
change remains unarchived pending whole-change verification and independent implementation
review.

## Coverage matrix

Coverage target: **8 requirements, 45 acceptance scenarios, and 24 tasks**. A requirement
or task shared across slices completes only when every listed portion passes its owning
gate.

### Requirement ownership

| Approved requirement | Owning slice(s) | Verification |
|---|---|---|
| Resolve a server-managed Prometheus source without exposing credentials | VS-01, VS-02 | VS01-AC01/02/05/06/08; VS02-AC02 |
| Query the exact current or reference window through HTTP API v1 | VS-02, VS-03 | VS02-AC01/09; VS03-AC02 |
| Map one float series into the provider-neutral sample contract | VS-02 | VS02-AC03/04 |
| Fail closed on warning annotations or excessive Prometheus responses | VS-02 | VS02-AC05/06/08 |
| Bound acquisition time and map failures through existing typed outcomes | VS-01, VS-02, VS-03 | VS01-AC01-04; VS02-AC05/07/08; VS03-AC01-07 |
| Compose and verify the provider behind the existing Metric port | VS-01, VS-02, VS-03 | VS01-AC03/04/07; VS02-AC09; VS03-AC07 |
| Acquire metric series only through the internal provider boundary | VS-01, VS-02, VS-03 | VS01-AC03/07; VS02-AC09; VS03-AC07 |
| Persist terminal Metric outcome atomically through the existing repository | VS-04 | VS04-AC03/04 |

### Scenario ownership

| Approved scenario | Owning slice | Acceptance evidence |
|---|---|---|
| Resolve a configured source by exact ID | VS-01 | VS01-AC01/02 |
| Keep a Prometheus credential secret | VS-01, VS-02 | VS01-AC06; VS02-AC02/08 |
| Keep the internal Basic username compatible but out of failures | VS-01, VS-02 | VS01-AC06; VS02-AC02/08 |
| Report an unavailable source safely | VS-01 | VS01-AC01 |
| Reject an unsafe authenticated target | VS-01 | VS01-AC02/04 |
| Preserve shared source consumers for a production-invalid source | VS-01 | VS01-AC05 |
| Acquire the current window exactly | VS-02 | VS02-AC01 |
| Preserve one logical request across retries | VS-03 | VS03-AC02 |
| Construct exact root and prefixed targets | VS-02 | VS02-AC01 |
| Reject an ambiguous path before request construction | VS-01 | VS01-AC02 |
| Acquire a configured reference through the same operation | VS-02 | VS02-AC09 |
| Bound one hour to the accepted resolution | VS-02 | VS02-AC01 |
| Map one valid float series | VS-02 | VS02-AC03 |
| Preserve non-finite values for deterministic quality assessment | VS-02 | VS02-AC03 |
| Treat no series as successful empty acquisition | VS-02 | VS02-AC04/09 |
| Reject a multi-series or histogram result | VS-02 | VS02-AC04 |
| Reject an oversized response without truncation | VS-02 | VS02-AC05 |
| Reject a warning-annotated success response | VS-02 | VS02-AC06 |
| Keep informational annotations operational | VS-02 | VS02-AC06 |
| Reject malformed successful annotations | VS-02 | VS02-AC06 |
| Retry an eligible attempt outcome within the hard budget | VS-03 | VS03-AC02/03 |
| Reject a retry that cannot fit the remaining acquisition budget | VS-03 | VS03-AC03 |
| Admit a retry that fits the remaining acquisition budget | VS-03 | VS03-AC03 |
| Complete on the initial attempt | VS-02, VS-03 | VS02-AC01/03; VS03-AC02 |
| Complete on retry one | VS-03 | VS03-AC02 |
| Complete on retry two | VS-03 | VS03-AC02 |
| Exhaust all HTTP attempts | VS-03 | VS03-AC02/03 |
| Map the HTTPX exception hierarchy deterministically | VS-03 | VS03-AC04/05 |
| Do not retry a deterministic provider rejection | VS-03 | VS03-AC06 |
| Map a proven timeout without extending the acquisition budget | VS-02, VS-03 | VS02-AC07; VS03-AC01/05 |
| Require a strict timeout or canceled error envelope | VS-02 | VS02-AC07 |
| Reject an invalid error envelope as timeout proof | VS-02 | VS02-AC07 |
| Do not infer timeout from a bare HTTP 503 | VS-02 | VS02-AC07/08 |
| Let body-bound failure precede retriable status | VS-02 | VS02-AC05 |
| Classify a complete malformed body by status before success validation | VS-02 | VS02-AC05/07 |
| Preserve current and reference failure semantics | VS-01, VS-02, VS-03 | VS01-AC03/04; VS02-AC09; VS03-AC07 |
| Inject the real provider without domain coupling | VS-01 | VS01-AC03/04/07 |
| Verify provider integration without live credentials | VS-01, VS-02, VS-03 | VS01-AC03; VS02-AC01-09; VS03-AC01-07 |
| Acquire zero configured references | VS-02 | VS02-AC09 |
| Acquire one configured reference | VS-02 | VS02-AC09 |
| Acquire multiple references independently | VS-02 | VS02-AC09 |
| Test without provider transport | VS-01 | VS01-AC03/07 |
| Round-trip all Metric result variants | VS-04 | VS04-AC03 |
| Roll back persistence failure | VS-04 | VS04-AC03 |
| Avoid transport, model, and framework coupling | VS-01, VS-04 | VS01-AC07; VS04-AC03/04 |

### Task ownership

| OpenSpec task | Owning slice(s) | Verification |
|---|---|---|
| 1.1 Preserve shared loading; selected-source production validation | VS-01 | VS01-AC02/05/08 |
| 1.2 Production boundary and credential safety tests | VS-01, VS-02 | VS01-AC02/06; VS02-AC02/08 |
| 1.3 Source-aware provider composer/resolver | VS-01 | VS01-AC01/02/07 |
| 1.4 Lifespan/state port-only wiring | VS-01 | VS01-AC03/07 |
| 2.1 Exact bounded range request and path grammar | VS-01, VS-02, VS-03 | VS01-AC01/02/04; VS02-AC01; VS03-AC02 |
| 2.2 Bounded response streaming and cleanup | VS-02, VS-03 | VS02-AC05; VS03-AC01 |
| 2.3 Strict success/matrix/sample mapping | VS-02 | VS02-AC03-05 |
| 2.4 Preserve samples for deterministic preparation | VS-02 | VS02-AC03 |
| 2.5 Warning/info and diagnostic leakage policy | VS-02 | VS02-AC06-08 |
| 3.1 Hard attempt/acquire deadlines and cleanup | VS-03 | VS03-AC01/05 |
| 3.2 Exact retries and remaining-budget admission | VS-03 | VS03-AC02/03 |
| 3.3 Ordered classification table and safe diagnostics | VS-02, VS-03 | VS02-AC05-08; VS03-AC01/04-06 |
| 3.4 Retry/deadline/precedence tests | VS-03 | VS03-AC01-06 |
| 3.5 Exact acquisition-attempt tests | VS-01, VS-02, VS-03 | VS01-AC01-04; VS02-AC01; VS03-AC02/03 |
| 4.1 Exact request-target tests | VS-01, VS-02 | VS01-AC02; VS02-AC01 |
| 4.2 Deterministic-step boundary tests | VS-02 | VS02-AC01 |
| 4.3 HTTP/auth/current-reference boundary tests | VS-02, VS-03 | VS02-AC01/02/09; VS03-AC02 |
| 4.4 Response/error/annotation/body matrix | VS-02, VS-03 | VS02-AC03-08; VS03-AC04-06 |
| 4.5 Injected Metrics pipeline tests | VS-01, VS-02, VS-03 | VS01-AC03/04; VS02-AC09; VS03-AC07 |
| 4.6 Startup/capabilities/create/preflight regressions | VS-01 | VS01-AC05/08 |
| 5.1 Docstrings and developer/deployment documentation | VS-01, VS-02, VS-03, VS-04 | Per-slice gates; VS04-AC01 |
| 5.2 Scope/dependency/schema/semantics audit | VS-04 | VS04-AC03/04 |
| 5.3 Focused provider/configuration/preflight/pipeline tests | VS-01, VS-02, VS-03, VS-04 | Every slice gate; VS04-AC02/03/05 |
| 5.4 Strict OpenSpec validation and `make check` | VS-04 | VS04-AC05 |

## Frozen plan and mutable execution state

Frozen at the exact independently reviewed and explicitly human-approved planning SHA:

- the planning-review snapshot/approval protocol, human-approved SHA definition,
  pre-execution readiness protocol, approved-artifact
  integrity rule, and task checkbox-only rule;
- implementation branch, slice count/order/graph, goals, dependencies, vertical
  boundaries, risk classifications, and completion gates;
- acceptance IDs, approved sources, GIVEN/WHEN/THEN assertions, proof levels,
  counterexample guards, and planned ownership;
- requirement/scenario/task coverage matrices, expected code impact, contract boundaries,
  non-goals, context packs, and handoff expectations.

Mutable only by the Coordinator after approval:

- human-approved planning SHA and readiness/audit command results;
- `tasks.md` checkbox state only as `[ ] -> [x]`, after every owning slice portion passes;
- plan and slice execution statuses;
- active assignments, accepted implementation/correction commit SHAs, and handoff paths;
- command results, evidence locations, reviewer/verifier outcomes, deviation dispositions,
  shared-knowledge disposition, and exact stop/escalation records;
- execution notes that do not add or alter requirements, proof levels, dependencies,
  boundaries, or design.

A later slice may detect a regression but may not silently take ownership of missing
earlier behavior. A code-path change inside the same approved vertical boundary may be
recorded as a local deviation; a source conflict, new behavior, missing dependency
approval, contract/schema/API change, or slice-structure problem stops execution for
re-planning, independent review, and renewed human approval.

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements,
acceptance obligations, proof-level changes, or redesign decisions here.

- Planning record (2026-09-03): branch `feature/add-prometheus-metric-provider` initially
  pointed to `ff813a6`; the approved change artifacts and revised draft plan required one
  complete planning-review snapshot commit before the next independent review. No
  production code or tests were changed during planning. The reviewer must record the
  resulting exact SHA, and human approval must identify that same SHA. The Coordinator
  records it in mutable metadata only after approval.
- Default execution order is VS-01 through VS-04 with no concurrent slice dispatch.
- VS-01 through VS-03 require fresh independent high-risk slice review before
  Coordinator acceptance. VS-04 is normal risk and still requires Coordinator evidence
  review.
- Every implementer uses a fresh context, reads the exact context pack and accepted
  predecessor handoff, runs focused verification/self-review, creates one atomic commit
  by default, and writes the repository-standard handoff.
- Readiness record (2026-09-03): the Coordinator executed the complete pre-VS-01
  approved-artifact committed/index/worktree, checkbox-transition, task-ownership, and
  frozen-plan audits against `75b97960704af790b2d8c3e8b6ce84a9e400151a`; strict OpenSpec
  validation, branch verification, and the required clean-status assertion passed before
  execution metadata was recorded.
- VS-01 active assignment (2026-09-03): delegated to a fresh Slice Implementer; no
  predecessor handoff is required.
- VS-01 acceptance (2026-09-03): focused gate independently reproduced as 148 passed,
  28 existing PostgreSQL-gated skips; targeted Ruff/format and diff checks passed.
  Independent high-risk review of `03fef65..6499d90` returned `SLICE REVIEW PASS` with
  no findings. Accepted implementation commit `1217266598aa5f20b902e9ae2edfe1da2ffed6c2`
  and handoff `implementation/VS-01-handoff.md`; no shared-knowledge candidates.
- VS-02 active assignment (2026-09-03): delegated to a fresh Slice Implementer after
  accepted VS-01 handoff and high-risk gate.
- VS-02 high-risk review (2026-09-04): `SLICE CHANGES REQUIRED` on MEDIUM evidence
  gaps only: incomplete approved deterministic-step vectors, incomplete per-status
  oversized-versus-bounded malformed precedence pairs, and incomplete required
  annotation/error matrix coverage. A fresh corrective implementer is active; VS-02
  remains `IN_PROGRESS` and VS-03 is not ready.
- VS-02 corrective re-review (2026-09-04): `SLICE CHANGES REQUIRED` on remaining MEDIUM
  evidence gaps only. Timeout/canceled proof must discriminate against every retryable
  status with independent valid warnings-only and infos-only envelopes; malformed infos
  must be covered on an error envelope. A fresh corrective implementer is active; VS-02
  remains `IN_PROGRESS` and VS-03 is not ready.
- VS-02 final review (2026-09-04): `SLICE CHANGES REQUIRED` on one remaining MEDIUM
  evidence gap only. VS02-AC09 requires empty-current completed-insufficient behavior
  through the real composed provider, not a fake provider. A fresh corrective implementer
  is active; VS-02 remains `IN_PROGRESS` and VS-03 is not ready.
- VS-02 acceptance (2026-09-04): focused gate independently reproduced as 193 passed,
  28 existing PostgreSQL-gated skips; targeted Ruff/format and diff checks passed.
  Initial high-risk review findings were corrected through bounded VS-02 evidence-only
  commits. The final fresh re-review returned `SLICE REVIEW PASS` with no findings;
  accepted code commits are `99bce0803fb8781151b085d06925d1edf3dacae2`,
  `d01a10477158d316b18eac43fc48abca5ddd01db`,
  `0d355201d94da59db062afbad794cbce96a98e67`, and
  `ee4d364bb95a954b84b93dd33f0203fa9d72cb1b`, with handoff
  `implementation/VS-02-handoff.md`. No shared-knowledge candidates.
- VS-03 active assignment (2026-09-04): delegated to a fresh Slice Implementer after
  accepted VS-02 handoff and final high-risk gate.
- VS-03 high-risk review (2026-09-04): `SLICE CHANGES REQUIRED` with HIGH findings that
  generic HTTPX request/client errors could escape typed provider outcomes and
  cancellation cleanup could exceed the hard deadline, plus a MEDIUM finding that retry
  admission anchored the acquisition budget too late. A fresh corrective implementer is
  active within the approved VS-03 resilience boundary; VS-03 remains `IN_PROGRESS` and
  VS-04 is not ready.
- VS-03 corrective re-review (2026-09-04): `SLICE CHANGES REQUIRED` with one remaining
  HIGH finding: a typed timeout may return while detached response/client cleanup is
  still running. A fresh corrective implementer is active to restore the approved
  resource-closure/no-post-deadline-work semantics without changing scope; VS-03 remains
  `IN_PROGRESS` and VS-04 is not ready.
- VS-03 stop/escalation (2026-09-04): `SLICE BLOCKED BY CONTRACT CONFLICT`. The approved
  hard 15-second attempt/50-second acquire deadline and no-post-deadline-work semantics
  require an absolute return bound, while the same approved gate requires cancellation-
  resistant response/client cleanup to complete before the typed timeout returns. For an
  arbitrary cleanup operation that catches cancellation and awaits an unbounded external
  operation, returning at the absolute deadline leaves cleanup active; awaiting closure
  exceeds the deadline. The approved sources impose neither a priority nor a bounded/
  cooperative transport-cleanup contract. Human source resolution is required before
  any further VS-03 correction, re-planning, re-review, or VS-04 dispatch.
