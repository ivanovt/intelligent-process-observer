# Implementation Plan — add-prometheus-metric-provider

**Status:** APPROVED — EXECUTION IN PROGRESS
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-prometheus-metric-provider`
**Implementation branch:** `feature/add-prometheus-metric-provider`
**Human-approved planning SHA:** `b24e82bdf80893a93e313836666fdb1e4840ef37`
**Human-approved deadline/cleanup source revision:** `2180c7d14862187635de21d716f27f6b3b9ff93f`
**Accepted VS-02 execution baseline SHA:** `81270d9537329eea0477254094ef9fcdce6f17e6`
**Replacement planning-review SHA:** pending

## Approval state

VS-01 and VS-02 are accepted execution history and remain unchanged. The proposal,
delta specifications, design, and tasks, including the human-approved deadline/cleanup
revision at `2180c7d14862187635de21d716f27f6b3b9ff93f`, are approved inputs to this
re-planning pass. This corrected implementation plan is not approved for VS-03 or
VS-04 execution. The replacement planning snapshot defined below must be committed,
independently reviewed at that exact SHA, and explicitly human-approved at that same SHA
before VS-03 may resume.

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
- approved deadline/cleanup clarification commit
  `2180c7d14862187635de21d716f27f6b3b9ff93f`

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

At the exact replacement planning commit SHA approved after independent review, the
approved OpenSpec content and plan structure become the frozen normative planning
baseline. It is not the implementation-diff baseline. The separate resumed implementation
baseline is the accepted VS-02 execution tip recorded above. Acceptance sources and
GIVEN/WHEN/THEN assertions provide normative traceability; task numbers are supplementary
traceability. A task checkbox becomes complete only after every owning slice portion has
passed its gate.

Execution uses `PLANNED -> READY -> IN_PROGRESS -> COMPLETE`; `BLOCKED` records a defined
stop/escalation. Default execution is sequential. Only the Coordinator may change
execution status, accepted commit SHAs, handoff paths, verification/review results,
deviation dispositions, and execution notes after approval.

## Planning-review snapshot, approval, and pre-execution readiness

### Establish the immutable review and approval anchor

Before the independent review and human approval of this corrected plan:

1. Confirm the current branch is `feature/add-prometheus-metric-provider` and inspect the
   complete index/worktree. Preserve unrelated roadmap files outside this feature
   execution boundary; exclude every roadmap sidecar, `Zone.Identifier`, and other
   unrelated artifact from both the planning commit and later feature commits.
2. The original full planning snapshot is historical execution evidence. For this
   correction, verify that the parent tree contains the approved source revision
   `2180c7d14862187635de21d716f27f6b3b9ff93f`, then stage exactly the corrected plan
   and no other path:

   ```text
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
   git merge-base --is-ancestor \
     2180c7d14862187635de21d716f27f6b3b9ff93f HEAD
   printf '%s\n' "$change_dir/implementation-plan.md" \
     > "$snapshot_audit_dir/expected"
   git diff --cached --name-only | LC_ALL=C sort > "$snapshot_audit_dir/actual"
   if ! diff -u "$snapshot_audit_dir/expected" "$snapshot_audit_dir/actual"; then
     exit 1
   fi
   git diff --quiet
   git commit -m "docs: replan Prometheus deadline cleanup"
   planning_review_sha=$(git rev-parse HEAD)
   test -n "$planning_review_sha"
   git status --porcelain > "$snapshot_audit_dir/status"
   test ! -s "$snapshot_audit_dir/status"
   printf '%s\n' "$planning_review_sha"
   ```

4. The independent slice-plan reviewer records that exact SHA in its review report and
   reviews the tree at that SHA, not mutable worktree content. Human approval must
   explicitly identify the same reviewed SHA.
5. If the approved source revision, task text/structure, or any frozen part of this plan
   changes after review, the review and approval are invalid. Create a new planning
   snapshot commit, repeat independent review against the new SHA, and obtain renewed
   human approval of that exact SHA.

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

Run every audit below both immediately before VS-03 delegation and during VS-04 final
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

Before VS-03 resume, also require the expected branch, successful strict change
validation, and an empty index/worktree, including no untracked files:

```bash
set -euo pipefail
readiness_audit_dir=$(mktemp -d)
current_branch=$(git branch --show-current)
test "$current_branch" = "feature/add-prometheus-metric-provider"
openspec validate add-prometheus-metric-provider --strict
git status --porcelain > "$readiness_audit_dir/status"
test ! -s "$readiness_audit_dir/status"
```

Before delegation, the Coordinator must also run the cumulative implementation audit in
the next section with `VS03_REVIEW_TIP` set to the exact human-approved replacement
planning SHA. This records the pre-existing unaccepted VS-03 production/test inventory
from accepted VS-02 tip `81270d9537329eea0477254094ef9fcdce6f17e6` through the resume
point. It is resume-scope evidence, not VS-03 acceptance; the final reviewer reruns the
same audit through the later candidate tip.

Any failure is a Coordinator stop condition. It is not delegated to resumed VS-03 and
cannot be waived by an implementer.

### Separate planning and resumed-implementation baselines

The replacement human-approved planning SHA governs normative artifact and frozen-plan
integrity only. It MUST NOT be used to determine implementation scope because its
ancestry already contains unaccepted VS-03 production/test work.

The resumed implementation baseline is the exact last accepted VS-02 execution tip from
Coordinator metadata:

```text
81270d9537329eea0477254094ef9fcdce6f17e6
```

The already-present unaccepted VS-03 production/test commits are:

```text
4baf129efeb84ba40c507934ad9e4451cf59b5b0
5c35ae84e141169375faff4e7f1c909ccb774cbb
3a3ef1b6e865afb257ab6ba72052cc80415a3acb
71566e0b7b98251cd40f58361659ff52b76379df
```

This is the existing inclusive VS-03 implementation history from first production commit
`4baf129` through current production tip `71566e0`, including interleaved handoff/review
metadata. None is accepted. Replacement-plan and OpenSpec-clarification commits later in
the ancestry do not narrow or reset the implementation scope.

For every resumed VS-03 handoff, correction re-review, and final high-risk review, set the
exact candidate tip and run this fail-closed cumulative audit. It reviews all repository
changes and separately materializes every production/test change since accepted VS-02;
therefore every later VS-03 correction is automatically added to the same cumulative
scope:

```bash
set -euo pipefail
accepted_vs02_sha=81270d9537329eea0477254094ef9fcdce6f17e6
vs03_review_tip="${VS03_REVIEW_TIP:?set VS03_REVIEW_TIP}"
review_audit_dir=$(mktemp -d)
production_test_paths=(backend/src backend/tests frontend/src)
existing_unaccepted_vs03_commits=(
  4baf129efeb84ba40c507934ad9e4451cf59b5b0
  5c35ae84e141169375faff4e7f1c909ccb774cbb
  3a3ef1b6e865afb257ab6ba72052cc80415a3acb
  71566e0b7b98251cd40f58361659ff52b76379df
)

git cat-file -e "$accepted_vs02_sha^{commit}"
git cat-file -e "$vs03_review_tip^{commit}"
git merge-base --is-ancestor "$accepted_vs02_sha" "$vs03_review_tip"
for commit in "${existing_unaccepted_vs03_commits[@]}"; do
  git cat-file -e "$commit^{commit}"
  git merge-base --is-ancestor "$accepted_vs02_sha" "$commit"
  git merge-base --is-ancestor "$commit" "$vs03_review_tip"
done

git log --reverse --format='%H %s' \
  "$accepted_vs02_sha".."$vs03_review_tip" \
  > "$review_audit_dir/all-commits.txt"
git diff --name-status "$accepted_vs02_sha" "$vs03_review_tip" \
  > "$review_audit_dir/all-paths.txt"
git diff --binary "$accepted_vs02_sha" "$vs03_review_tip" \
  > "$review_audit_dir/all.diff"

git log --reverse --format='%H %s' \
  "$accepted_vs02_sha".."$vs03_review_tip" -- "${production_test_paths[@]}" \
  > "$review_audit_dir/production-test-commits.txt"
git diff --name-status "$accepted_vs02_sha" "$vs03_review_tip" -- \
  "${production_test_paths[@]}" > "$review_audit_dir/production-test-paths.txt"
git diff --binary "$accepted_vs02_sha" "$vs03_review_tip" -- \
  "${production_test_paths[@]}" > "$review_audit_dir/production-test.diff"
test -s "$review_audit_dir/production-test-commits.txt"
test -s "$review_audit_dir/production-test-paths.txt"
test -s "$review_audit_dir/production-test.diff"
sha256sum "$review_audit_dir/production-test.diff" \
  > "$review_audit_dir/production-test.diff.sha256"
git diff --check "$accepted_vs02_sha" "$vs03_review_tip" -- \
  "${production_test_paths[@]}"
```

The handoff and independent high-risk review report must record the accepted VS-02 SHA,
candidate review-tip SHA, four existing unaccepted commit SHAs, every later correction
commit SHA, complete production/test name-status list, and the cumulative diff SHA-256.
The reviewer reviews `all.diff` for scope and the complete `production-test.diff` for
behavior; reviewing only the replacement-plan ancestry suffix, only the newest correction,
or `4baf129..71566e0` without the first commit's parent is invalid.

Coordinator acceptance of VS-03 additionally records the exact accepted review tip and
cumulative production/test diff SHA-256 in mutable execution metadata. VS-04 reruns the
same accepted-VS-02-to-accepted-VS-03-tip audit and compares the digest to that record. It
also proves its documentation/conformance-only work introduced no later production/test
change in committed `HEAD`, index, or worktree:

```bash
set -euo pipefail
accepted_vs02_sha=81270d9537329eea0477254094ef9fcdce6f17e6
accepted_vs03_tip="${ACCEPTED_VS03_REVIEW_TIP:?set ACCEPTED_VS03_REVIEW_TIP}"
expected_delta_sha256="${VS03_PRODUCTION_TEST_DIFF_SHA256:?set VS03_PRODUCTION_TEST_DIFF_SHA256}"
final_history_audit_dir=$(mktemp -d)
production_test_paths=(backend/src backend/tests frontend/src)

git cat-file -e "$accepted_vs03_tip^{commit}"
git merge-base --is-ancestor "$accepted_vs02_sha" "$accepted_vs03_tip"
git diff --binary "$accepted_vs02_sha" "$accepted_vs03_tip" -- \
  "${production_test_paths[@]}" > "$final_history_audit_dir/vs03-production-test.diff"
actual_delta_sha256=$(sha256sum "$final_history_audit_dir/vs03-production-test.diff" \
  | awk '{print $1}')
test "$actual_delta_sha256" = "$expected_delta_sha256"
if ! git diff --exit-code "$accepted_vs03_tip" HEAD -- \
  "${production_test_paths[@]}"; then exit 1; fi
if ! git diff --cached --exit-code "$accepted_vs03_tip" -- \
  "${production_test_paths[@]}"; then exit 1; fi
if ! git diff --exit-code "$accepted_vs03_tip" -- \
  "${production_test_paths[@]}"; then exit 1; fi
```

A merge-base-to-main diff may supplement these checks but must not substitute for the
replacement-planning-SHA integrity audit, the accepted-VS-02 cumulative implementation
audit, or the committed/index/worktree no-later-production/test audit.

## Slice graph

```text
VS-01 -> VS-02 -> VS-03 -> VS-04
```

## Execution overview

| Slice | Goal | Depends on | Risk | Status | Commit | Handoff |
|---|---|---|---|---|---|---|
| VS-01 | Source-safe transport-free walking skeleton through the existing Metric port | none | high-risk | COMPLETE | 1217266598aa5f20b902e9ae2edfe1da2ffed6c2 | `implementation/VS-01-handoff.md` |
| VS-02 | Complete bounded single-attempt request, mapping, and status classification | VS-01 | high-risk | COMPLETE | `99bce08`, `d01a104`, `0d35520`, `ee4d364` | `implementation/VS-02-handoff.md` |
| VS-03 | Observable deadline/result boundary, state-inert late cleanup, bounded capacity, deterministic retries, and terminal resilience integration | VS-02 | high-risk | IN_PROGRESS | - | - |
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

**Behavioral goal:** Complete production acquisition with an absolute observable
15-second attempt and 50-second `acquire()` result boundary. At either expiry, timeout
is committed before cancellation-resistant transport cleanup completes; cancellation and
close are signalled, detached cleanup becomes state-inert, and finite private
active-plus-cleanup capacity prevents it accumulating. The slice also preserves the
existing exact retry/orchestration behavior and current/reference pipeline semantics.

**OpenSpec coverage:** deadline/failure scenarios for retry eligibility/admission,
initial/retry completion, exhaustion, HTTPX taxonomy, proven hard timeout,
post-timeout transport cleanup, and final current/reference failure semantics;
logical-request-across-retries scenario; complete production resilience integration over
all VS-02 attempt variants; tasks 3.1, 3.2, exception/deadline/retry-orchestration
portions of 3.3, 3.4, transport-attempt portions of 3.5, retry/deadline portions of
4.3/4.4, current timeout/final retry failure and reference timeout/failure portions of
4.5, plus per-symbol docstrings from 5.1.

**Dependencies:** VS-02 accepted at execution tip
`81270d9537329eea0477254094ef9fcdce6f17e6`. All later production/test work remains
unaccepted VS-03 scope regardless of intervening planning, clarification, handoff, or
review-metadata commits.

**Vertical boundary:** VS-02 immutable request and complete one-attempt function ->
private capacity admission for eligible transport work -> injected monotonic 50-second
observable acquire-result boundary -> 15-second observable deadline around each request
and body read -> commit existing typed timeout before signalling cancellation/close ->
detach only state-inert resource cleanup while its private capacity remains held ->
discard late response/body/error/exception -> HTTPX exception classifier or VS-02 attempt
result before commitment -> remaining-budget admission -> exact fixed wait and up to two
identical retries -> existing typed available/failure/timeout -> unchanged current failed
or reference partial result.

**Expected code impact:** replace the current joined cancellation-cleanup deadline helper
inside the production provider with infrastructure-private deadline-commit, cancellation/
close, late-cleanup tracking, and finite-capacity seams; retain the existing clock,
sleeper, exception-classifier, and retry orchestration seams. Add focused resilience
tests and narrow adapter-backed pipeline tests. VS-02 response/body/status mapping is
consumed, not reimplemented. Do not change Metric domain, pipeline, result builder,
persistence, preflight policy, public settings, public port, public outcome/reason, or
source-resolution behavior.

**Contracts consumed/changed:** only existing `MetricSeriesAcquisitionFailure` and
`MetricSeriesAcquisitionTimeout` classifications are produced, with fixed bounded safe
diagnostics and optional safe status codes kept infrastructure-private where the existing
port cannot represent them. Capacity is provider-private and test-controllable only;
neither its value nor saturation state is a public setting, port field, result field, or
reason code. The sole permitted post-return provider bookkeeping is release of the held
private capacity after cleanup terminates; late cleanup has no authority over outcomes,
retries, requests, analytical/pipeline/Lens/runtime/persistence state, or observable
provider result state.

**Non-goals:** changing VS-01 source lookup/unavailable semantics or VS-02 request,
authentication, body, envelope, annotation, sample, or status classification; retrying
timeout or any VS-02 terminal rejection; making capacity public/configurable; using a
worker, queue, broker, or workflow engine; jitter/Retry-After; proxy/redirect support;
changing current/reference pipeline mapping; Observation-level deadlines or concurrency.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS03-AC01 | Observable attempt/acquire result deadlines | Hanging request, slow-progress body, retry waits, and cancellation-resistant response/client cleanup | Cross 15s attempt or 50s acquire deadline | The existing typed timeout is committed and returned at the deadline; cancellation/close is signalled, but cleanup is not awaited past the result boundary | deterministic clock + async service | injected monotonic deadline, return-time, cancellation, and close ledgers |
| VS03-AC02 | Retry eligibility/count/identity | ConnectError and each VS-02 retry-eligible 429/500/502/504 result sequence succeeding on attempt 1, retry 1, retry 2, or never | Acquire | Exact attempt counts are 1/2/3/3 with waits 0.5/1.0, never a fourth; every attempt uses byte-identical logical request and same source/auth/configuration | parameterized HTTP boundary | complete attempt/form/auth/config snapshots and sleep ledger |
| VS03-AC03 | Retry admission | For ConnectError and each retryable status, remaining budgets just below/at/above wait+15s | Admit next retry | Insufficient budget returns timeout with no wait/request; sufficient budget waits exactly and retries; three actually executed eligible failures exhaust as failure | deterministic unit + HTTP boundary | boundary clock vectors for retry 1 and retry 2 |
| VS03-AC04 | HTTPX hierarchy | Timeout subclasses, ConnectError, remaining TransportError subclasses, and non-Transport request/client errors named by the spec | Classify each | Only ConnectError retries; timeout subclasses time out without retry; every other named class fails without retry; no generic transport retry branch exists | parameterized unit | hierarchy table including representative subclasses and exact counts |
| VS03-AC05 | Hard-deadline precedence | Deadline completion races an HTTPX exception, successful result, or retry-eligible `ConnectError` | Observe attempt/acquire boundary | Hard local timeout commitment wins; no late result/exception can replace it, trigger retry, or start a request | deterministic concurrency unit | controlled completion/cancellation race seam and request/sleep ledgers |
| VS03-AC06 | Terminal versus retry-eligible integration | Every VS-02 terminal attempt result and retry-eligible result | Run full acquisition orchestrator | Terminal outcomes perform no retry/sleep; only retry-eligible statuses enter admission; retry exhaustion becomes failure; no body/status/envelope policy is reclassified by the orchestrator | parameterized service | VS-02 variant-to-attempt-count/outcome matrix |
| VS03-AC07 | Pipeline failure preservation | Real provider timeout and terminal/retry-exhausted failure on current versus one configured reference | Run existing pipeline | Current produces existing minimal failed Metric result; reference alone is omitted and yields accepted `reference_unavailable/reference_periods` partial while usable current survives | service | real-provider injected current/reference matrix with result equality |
| VS03-AC08 | State-inert late cleanup | Timeout-committed request/body/client whose cleanup later yields a response, exception, or close completion | Release cleanup after `acquire()` has returned | The committed timeout and all current/reference pipeline outcomes remain unchanged; no retry, sleep, request, provider result/state transition, Lens/runtime transition, persistence action, or late diagnostic occurs | deterministic async service + pipeline integration | controlled cleanup gate, late-result/error injection, complete provider/pipeline/Lens/persistence/request ledgers |
| VS03-AC09 | Finite active-plus-cleanup capacity | Private test capacity filled by active work and then by timeout-detached cleanup | Admit another valid transport-phase acquisition before and after cleanup termination | While full, the new acquisition returns the existing fixed-safe typed acquisition failure before client construction/request; each cleanup holds one slot until it finishes, then releases only that private slot and a later acquisition is admitted | deterministic async service + transport ledger | test-only private-capacity seam, cleanup gates, client-construction/request counters, outcome and slot-release ledger |

**Counterexample guards:** a cancellation-resistant fake must remain blocked beyond the
15/50-second result deadline, so a helper that awaits cleanup cannot pass VS03-AC01. A
late success, `ConnectError`, and close exception are each released after timeout
commitment; a late result that replaces timeout or starts a retry/request fails
VS03-AC05/08. Capacity tests first fill slots with active acquisitions, then with
post-timeout cleanup, use a fail-on-client-construction transport for the rejected call,
and prove release only after cleanup termination; an unbounded detached-task design, a
per-acquisition rather than shared capacity, or permanent capacity leakage cannot pass.
Retries mix ConnectError and all VS-02 retry-eligible status variants across attempts;
admission tests use exact equality as fitting. The orchestrator matrix feeds VS-02
terminal body/envelope/warning/status results and asserts no sleep/additional request,
preventing a broad "retry any failure" branch. Source-unavailable and invalid-target
regressions remain VS-01-owned and must retain their typed zero-request behavior without
transport-capacity admission.

**Focused verification:** `cd backend && uv run pytest
tests/test_prometheus_metric_provider_resilience.py
tests/test_prometheus_metric_provider.py
tests/test_prometheus_metric_provider_configuration.py
tests/test_metric_analysis_pipeline.py tests/test_prometheus_adapter.py -q`; deterministic
async deadline/cleanup/capacity tests must use no live time or network; targeted Ruff and
format checks; `git diff --check`; and the cumulative accepted-VS-02-to-candidate-tip
implementation audit above. Focused verification of only a new correction commit is
insufficient.

**Context pack:** approved source revision `2180c7d14862187635de21d716f27f6b3b9ff93f`;
accepted VS-01 and VS-02 handoffs and VS-02 attempt-result decision matrix; approved
deadline/retry/exception/current-reference scenarios; design decision on observable
deadlines, late cleanup, private capacity, retry admission, exhaustion, and ordered
exception precedence; exact-query logical-request identity; ADR-045, ADR-133-135,
ADR-157; current typed provider outcomes and Metrics pipeline mappings; current provider
deadline helper and resilience tests; HTTPX 0.28 exception hierarchy as used by the
installed dependency; accepted VS-02 execution baseline
`81270d9537329eea0477254094ef9fcdce6f17e6`; existing unaccepted VS-03 production/test
commits `4baf129`, `5c35ae8`, `3a3ef1b`, and `71566e0`; complete cumulative diff from the
accepted VS-02 baseline to the assigned candidate tip.

**Handoff expectations:** VS03-AC01 through VS03-AC09 evidence; exact observable
deadline-return traces; cancellation/close and cleanup-gate ledgers; a late-success,
late-error, and late-close-completion non-interference table; private-capacity
admission/retention/release table; no-client/no-request evidence for capacity rejection;
orchestration table linked to VS-02 attempt variants; attempts/waits/budget traces;
identical-request snapshots; HTTPX taxonomy; final pipeline outcomes; confirmation that
VS-01/VS-02 contracts and tests remain unchanged; accepted VS-02 implementation baseline
SHA `81270d9537329eea0477254094ef9fcdce6f17e6`; existing unaccepted VS-03 inclusive
history from `4baf129` through `71566e0` and its four production/test commit SHAs; every
new VS-03 correction commit; exact candidate review-tip SHA; complete cumulative
production/test name-status list and diff SHA-256; deviations; focused results; shared-
knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS03 evidence passes; the 15/50-second observable deadlines
cover body reads and waits and return the committed timeout without awaiting
cancellation-resistant cleanup; cancellation/close is signalled; late completion cannot
change outcome, retry, request, provider result, analytical/pipeline/Lens/runtime/
persistence state, or diagnostics; finite shared active-plus-cleanup capacity retains a
slot through cleanup, fails saturation before transport with the existing fixed-safe
typed failure, and releases only after termination; retries occur only for ConnectError
or VS-02's retry-eligible statuses and only when admitted; every named exception and
terminal-versus-retry orchestration branch is tested; VS-01 source behavior and VS-02
classification remain unchanged; logical request identity and secret-safe outcomes hold
across attempts; current/reference semantics remain unchanged; the slice remains bounded
to infrastructure orchestration and integration; focused checks pass; independent
high-risk review of the complete cumulative production/test delta from accepted VS-02 tip
`81270d9537329eea0477254094ef9fcdce6f17e6` through the exact candidate tip returns
`SLICE REVIEW PASS`; the review explicitly includes existing commits `4baf129`,
`5c35ae8`, `3a3ef1b`, `71566e0` and every later correction. The handoff and Coordinator
acceptance metadata record the baseline, all unaccepted/correction commits, reviewed tip,
complete name-status set, cumulative diff SHA-256, focused results, and accepted handoff.

### VS-04 — Compatibility, documentation, and whole-change conformance

**Behavioral goal:** Make the completed provider operationally understandable and prove
as a whole that it remains an infrastructure-only injected capability: shared startup,
capabilities, Observation creation, Metric preflight, fake-based pipeline tests, domain
imports, public contracts, persistence, and dependency/schema surfaces remain unchanged.
Document the approved observable-deadline rule: timeout return wins over
cancellation-resistant cleanup, which is private, state-inert, capacity-bounded, and
cannot alter the committed result.

**OpenSpec coverage:** conformance rerun of every requirement/scenario already implemented
and owned by VS-01 through VS-03; documentation and final audit tasks 5.1-5.4 only. Tasks
4.5 and 4.6 must already be complete through their behavioral owning slices; VS-04 does
not implement or add missing coverage for them. Its cleanup/capacity conformance work
consumes accepted VS-03 evidence; it does not redesign, implement, or add resilience
tests.

**Dependencies:** VS-03 accepted.

**Vertical boundary:** placeholder-only deployment configuration and developer guidance
-> application startup/composed provider -> mocked production current/reference runs and
existing public preflight/API/fake/persistence suites -> repository-wide static and
verification gates -> deployable, provider-neutral change with no new public execution
surface.

**Expected code impact:** `.env.example`, `docs/development-guide.md`, Coordinator-owned
task checkboxes, and mutable execution metadata only. No production code or test code may
be added or changed in this slice. Public provider/interface-method docstrings must
already have been added by their owning implementation slice and are audited here. A
discovered production/test gap stops VS-04. Only a gap owned by the currently re-approved
VS-03 may return to VS-03 under this replacement plan and must repeat the cumulative
high-risk review before VS-04 restarts. A defect attributable to accepted/frozen VS-01 or
VS-02 MUST NOT reopen either slice: stop and require a new approved re-plan/execution
decision.

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
| VS04-AC01 | Documentation task | Placeholder source configuration and approved production policy | Read deployment/developer docs and public provider docstrings | HTTPS/loopback and exact prefix grammar, auth/exclusions, secrets, resolution/limits/warnings, attempts/retries/classification, and lookback/staleness are concise and exact; docs also state the 15s attempt/50s observable result deadlines, timeout commitment, cancellation/close signalling, state-inert late cleanup, finite private active-plus-cleanup capacity, pre-transport fixed-safe capacity failure, and no public capacity setting/field/reason without real credentials | documentation review + secret scan | `.env.example`/guide/docstring audit against the complete task 5.1 and clarified cleanup/capacity checklist |
| VS04-AC02 | Shared behavior preservation | Production-valid and production-invalid shared sources | Run startup, capabilities, Observation create, and preflight suites | Existing outputs, 15-second/no-retry preflight, labels/warnings, and public error mapping remain compatible; production-invalid source affects only production acquire | API + service regression | focused existing and added tests with separate ledgers |
| VS04-AC03 | Provider-neutral pipeline and persistence | Existing fake provider matrix plus completed VS-01 through VS-03 real-provider tests | Rerun Metric tests and inspect modules/artifacts without editing them | Zero/one/multiple references remain independent; fake tests use no transport; all result variants and rollback behavior round-trip unchanged; no raw transport/provider data persists | service + persistence + static audit | existing completed test suites and import scan |
| VS04-AC04 | Scope/dependency/schema/API audit | Accepted VS-02 execution baseline, accepted cumulative VS-03 review tip/digest, and manifests/migrations/routes/contracts | Review change | Every accepted VS-03 production/test byte is traceable from the VS-02 baseline; VS-04 adds no production/test change; no dependency, migration/schema, public API, Metric result/analysis, History, Agent, reference semantics, persistence, or Observation orchestration change exists | repository audit | accepted-VS-02 cumulative diff/digest, no-post-VS03 committed/index/worktree diff, lock/manifest/migration/route/contract checks |
| VS04-AC05 | Final verification | Completed sequential slices, accepted VS03 late-cleanup/capacity evidence, and clean execution state | Run focused tests, strict OpenSpec validation, documentation audit, and `make check` | Every command passes accurately; the approved `2180c7d` clarification and replacement reviewed plan remain intact; task ownership is reconciled; the cleanup/capacity documentation matches accepted VS03 evidence; the cumulative VS03 implementation audit is unchanged; worktree is clean after accepted commits/metadata | repository gate | recorded commands, approved-source/plan integrity audit, accepted-VS02-to-VS03 implementation audit, task/plan mutable-only audit, and documentation-to-VS03-evidence trace |

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

**Counterexample guards:** documentation audit fails if it says cleanup completes before
the timeout returns, permits a late result/retry/request/state mutation, exposes a
capacity value as public configuration, or omits saturation's pre-transport fixed-safe
failure. Compatibility runs use a production-invalid source that shared
Settings still accepts; preflight tests record attempts and warnings so replacing it with
the production policy fails; persistence tests include every Metric terminal result and
rollback path; static scans cover both imports and serialized artifacts; secret scan uses
sentinel values absent from placeholder docs.

**Focused verification:** in one fail-fast Coordinator gate, run the committed/index/
worktree immutable, task-transition, task-ownership, and frozen-plan audits above; the
24/24 final task assertion; focused provider/configuration/preflight/Metrics/integration
tests; `openspec validate add-prometheus-metric-provider --strict`; `make check`;
accepted-VS-02-to-accepted-VS-03 cumulative implementation-diff/digest audit;
no-post-VS03 committed/index/worktree production/test audit; replacement-planning-SHA
normative integrity audit; `git diff --check`; and the final clean-status assertion. Every
shell block starts with `set -euo pipefail`, and loop comparisons use explicit
`if ! ...; then exit 1; fi` handling.

**Context pack:** accepted VS-03 handoff and all earlier handoffs; complete approved
OpenSpec; all architecture/ADR sources listed above; `.agents/PROJECT_KNOWLEDGE.md`;
development guide/workflow; root Makefile and manifests; replacement-planning-SHA
integrity results and accepted-VS-02-to-VS03 cumulative implementation diff;
accepted VS-02 execution baseline, accepted cumulative VS-03 review tip/digest, changed
production/tests/docs, and all focused existing regressions.

**Handoff expectations:** VS04-AC01 through VS04-AC05 evidence; documentation checklist
including observable deadline/late-cleanup/private-capacity policy; public docstring
audit; exact focused and full command results; regression counts;
approved-SHA committed/index/worktree artifact/task/plan integrity results; explicit
24/24 checked-task and all-owner acceptance result; accepted-VS-02 baseline, accepted
VS-03 tip, complete cumulative production/test name-status and matching diff digest;
proof of no later committed/index/worktree production/test change; dependency/schema/API/
import/secret audits; final clean status; deviations and shared-knowledge candidates;
explicit note that the change remains unarchived pending whole-change verification/review.

**Risk:** normal

**Completion gate:** VS04 evidence and all earlier acceptance IDs regress green without
production/test behavior edits in VS-04; documentation and docstrings are complete,
secret-safe, and match the approved observable-deadline/state-inert-cleanup/private-
capacity policy and accepted VS03 evidence; task ownership is reconciled;
focused tests, strict OpenSpec validation, accepted-VS-02 cumulative implementation diff,
approved-artifact
integrity, checkbox-only transition audit, exact 24/24 completion/ownership assertion,
mutable-only plan audit, scope/dependency/schema/API/secret audits, clean status, and
`make check` pass under fail-fast command execution. Any implementation/test gap stops
VS-04. Only a re-approved VS-03-owned gap may return to VS-03 under this plan; a VS-01/
VS-02 defect requires a new approved re-plan/execution decision and does not reopen those
accepted slices. One atomic documentation/conformance commit and handoff exist, followed
by Coordinator acceptance metadata. The change remains unarchived pending whole-change
verification and independent implementation review.

## Coverage matrix

Coverage target: **8 requirements, 46 acceptance scenarios, and 24 tasks**. A requirement
or task shared across slices completes only when every listed portion passes its owning
gate.

### Requirement ownership

| Approved requirement | Owning slice(s) | Verification |
|---|---|---|
| Resolve a server-managed Prometheus source without exposing credentials | VS-01, VS-02 | VS01-AC01/02/05/06/08; VS02-AC02 |
| Query the exact current or reference window through HTTP API v1 | VS-02, VS-03 | VS02-AC01/09; VS03-AC02 |
| Map one float series into the provider-neutral sample contract | VS-02 | VS02-AC03/04 |
| Fail closed on warning annotations or excessive Prometheus responses | VS-02 | VS02-AC05/06/08 |
| Bound acquisition time and map failures through existing typed outcomes | VS-01, VS-02, VS-03 | VS01-AC01-04; VS02-AC05/07/08; VS03-AC01-09 |
| Compose and verify the provider behind the existing Metric port | VS-01, VS-02, VS-03 | VS01-AC03/04/07; VS02-AC09; VS03-AC07-09 |
| Acquire metric series only through the internal provider boundary | VS-01, VS-02, VS-03 | VS01-AC03/07; VS02-AC09; VS03-AC07-09 |
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
| Map a proven timeout without extending the acquisition budget | VS-02, VS-03 | VS02-AC07; VS03-AC01/05/08 |
| Bound post-timeout transport cleanup | VS-03 | VS03-AC01/05/08/09 |
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
| 2.2 Bounded response streaming and cleanup | VS-02, VS-03 | VS02-AC05; VS03-AC01/08/09 |
| 2.3 Strict success/matrix/sample mapping | VS-02 | VS02-AC03-05 |
| 2.4 Preserve samples for deterministic preparation | VS-02 | VS02-AC03 |
| 2.5 Warning/info and diagnostic leakage policy | VS-02 | VS02-AC06-08 |
| 3.1 Hard attempt/acquire deadlines and cleanup | VS-03 | VS03-AC01/05/08/09 |
| 3.2 Exact retries and remaining-budget admission | VS-03 | VS03-AC02/03 |
| 3.3 Ordered classification table and safe diagnostics | VS-02, VS-03 | VS02-AC05-08; VS03-AC01/04-06 |
| 3.4 Retry/deadline/precedence tests | VS-03 | VS03-AC01-09 |
| 3.5 Exact acquisition-attempt tests | VS-01, VS-02, VS-03 | VS01-AC01-04; VS02-AC01; VS03-AC02/03 |
| 4.1 Exact request-target tests | VS-01, VS-02 | VS01-AC02; VS02-AC01 |
| 4.2 Deterministic-step boundary tests | VS-02 | VS02-AC01 |
| 4.3 HTTP/auth/current-reference boundary tests | VS-02, VS-03 | VS02-AC01/02/09; VS03-AC02 |
| 4.4 Response/error/annotation/body matrix | VS-02, VS-03 | VS02-AC03-08; VS03-AC04-06 |
| 4.5 Injected Metrics pipeline tests | VS-01, VS-02, VS-03 | VS01-AC03/04; VS02-AC09; VS03-AC07/08 |
| 4.6 Startup/capabilities/create/preflight regressions | VS-01 | VS01-AC05/08 |
| 5.1 Docstrings and developer/deployment documentation | VS-01, VS-02, VS-03, VS-04 | VS03 per-symbol docstrings; VS04-AC01 cleanup/capacity documentation audit |
| 5.2 Scope/dependency/schema/semantics audit | VS-04 | VS04-AC03/04 |
| 5.3 Focused provider/configuration/preflight/pipeline tests | VS-01, VS-02, VS-03, VS-04 | Every slice gate; VS04-AC02/03/05 |
| 5.4 Strict OpenSpec validation and `make check` | VS-04 | VS04-AC05 |

## Frozen plan and mutable execution state

Frozen at the exact independently reviewed and explicitly human-approved planning SHA:

- the planning-review snapshot/approval protocol, human-approved SHA definition,
  pre-execution readiness protocol, approved-artifact
  integrity rule, and task checkbox-only rule;
- the distinct normative-planning versus implementation-history baseline model, accepted
  VS-02 execution baseline SHA, known pre-existing unaccepted VS-03 commits, and
  cumulative review/digest protocol;
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
- resumed VS-03 candidate/review tip, later correction commit SHAs, cumulative
  production/test name-status evidence and diff SHA-256, and final accepted VS-03 review
  tip/digest;
- command results, evidence locations, reviewer/verifier outcomes, deviation dispositions,
  shared-knowledge disposition, and exact stop/escalation records;
- execution notes that do not add or alter requirements, proof levels, dependencies,
  boundaries, or design.

A later slice may detect a regression but may not silently take ownership of missing
earlier behavior. VS-01 and VS-02 are accepted/frozen and cannot be reopened by this
replacement plan. Before VS-03 acceptance, a code-path correction inside the re-approved
VS-03 boundary remains cumulative VS-03 scope and repeats full high-risk review. During
VS-04, only a VS-03-owned gap may return to VS-03; a VS-01/VS-02 defect, source conflict,
new behavior, missing dependency approval, contract/schema/API change, or slice-structure
problem stops for a new approved re-plan/execution decision.

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
- Accepted VS-02 execution baseline (2026-09-04): Coordinator acceptance metadata was
  committed at `81270d9537329eea0477254094ef9fcdce6f17e6`; this is the exact last
  accepted VS-02 execution tip and the immutable resumed-implementation baseline. It
  contains all accepted VS-01/VS-02 code, evidence, task state, handoffs, and acceptance
  metadata. No later production/test commit is accepted.
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
- Re-planning record (2026-09-04): the human-approved source clarification at
  `2180c7d14862187635de21d716f27f6b3b9ff93f` gives the observable acquire deadline
  priority over cancellation-resistant cleanup. This correction preserves the accepted
  VS-01/VS-02 graph, commits, handoffs, and evidence, replaces only the frozen VS-03/
  VS-04 plan content, and requires a new independently reviewed planning snapshot and
  explicit approval before VS-03 resumes.
- Replacement-plan review record (2026-09-04): snapshot
  `9fc35298419efdab2025d08c938b35b83b22df0e` received `PLAN CHANGES REQUIRED` because
  it incorrectly risked using its own ancestry as the implementation baseline. It is
  superseded and must not be approved. Existing unaccepted VS-03 production/test commits
  are `4baf129efeb84ba40c507934ad9e4451cf59b5b0`,
  `5c35ae84e141169375faff4e7f1c909ccb774cbb`,
  `3a3ef1b6e865afb257ab6ba72052cc80415a3acb`, and
  `71566e0b7b98251cd40f58361659ff52b76379df`; resumed review begins at accepted VS-02
  tip `81270d9537329eea0477254094ef9fcdce6f17e6` and includes all four plus every later
  VS-03 correction. VS-03 remains stopped pending a new reviewed and approved replacement
  planning SHA; no implementation is active and VS-04 is not ready.
- Resumed VS-03 readiness (2026-09-04): human approved replacement planning snapshot
  `b24e82bdf80893a93e313836666fdb1e4840ef37`. The complete committed/index/worktree
  approved-artifact, task-transition/ownership, and frozen-plan integrity audit passed;
  strict OpenSpec validation, expected branch, and empty-status checks passed. The
  required cumulative accepted-VS-02-to-resume-tip audit passed from
  `81270d9537329eea0477254094ef9fcdce6f17e6` through `b24e82bdf80893a93e313836666fdb1e4840ef37`.
  It recorded existing unaccepted commits `4baf129`, `5c35ae8`, `3a3ef1b`, and `71566e0`,
  production/test paths `backend/src/app/infrastructure/prometheus/composition.py`,
  `backend/tests/test_metric_analysis_pipeline.py`, and
  `backend/tests/test_prometheus_metric_provider_resilience.py`, and cumulative diff
  SHA-256 `5db57215f87d55859e95f70039e87dbdbf72b7cf166162973c49fd8071b3faef`.
  VS-03 is IN_PROGRESS; a fresh Slice Implementer is the only active assignment.
