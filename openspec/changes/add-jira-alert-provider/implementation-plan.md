# Implementation Plan — add-jira-alert-provider

**Status:** HUMAN_APPROVED — READY FOR EXECUTION
**Artifact type:** Non-normative execution plan
**Approved OpenSpec change:** `add-jira-alert-provider`
**Implementation branch:** `feature/add-jira-alert-provider`
**Planning-workflow baseline:** six-slice acceptance/change-map revision 2 (slice graph unchanged)
**Planning-baseline SHA:** `3e988b0380d1b7cf51127a78e2dca386266c5dbb`

## Approval state

The proposal, delta specifications, design, and tasks are human-approved. This
implementation plan is not approved for execution. It must pass independent slice-plan
review and receive explicit human approval before VS-01 may begin.

## Authority and constraints

This file describes how the approved change can be implemented. It does not redefine
the approved behavior. Accepted ADRs, normative architecture/contracts, and the approved
OpenSpec remain authoritative.

Approved change sources:

- `openspec/changes/add-jira-alert-provider/.openspec.yaml`
- `openspec/changes/add-jira-alert-provider/proposal.md`
- `openspec/changes/add-jira-alert-provider/design.md`
- `openspec/changes/add-jira-alert-provider/specs/jira-alert-provider/spec.md`
- `openspec/changes/add-jira-alert-provider/specs/alerts-analysis-pipeline/spec.md`
- `openspec/changes/add-jira-alert-provider/tasks.md`

Architecture and accepted-contract sources:

- `docs/architecture/README.md`
- `docs/architecture/03_ADR_log.md`: ADR-090 through ADR-098 and ADR-102 through
  ADR-105
- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, especially
  Alert current/reference failure propagation and failed-result absence
- `docs/architecture/10_open_decisions_and_backlog.md`, treating Open/Deferred entries
  only as boundaries and recognizing that the approved change resolves the Jira items
  expressly deferred to provider specification
- `docs/architecture/13_alert_lens_and_analysis_concept.md`, especially sections 4-7,
  10, and 16-19
- `docs/architecture/14_alerts_analysis_pipeline_detailed.md`, especially stages 2-5
  and failure/partial propagation
- `docs/architecture/19_alert_provider_adapter.md`
- `docs/development-guide.md`, especially the existing injected Alert integration
  boundary
- `openspec/specs/alerts-analysis-pipeline/spec.md`

Advisory source:

- `.agents/PROJECT_KNOWLEDGE.md` (currently contains no validated entries)

Repository constraints:

- Implement only the one approved Jira Cloud issue-search provider for the existing
  `jira_track_and_release` discriminator and existing `AlertProvider` port.
- Keep `app.alerts` provider-neutral. Jira settings, authentication, HTTP transport,
  response mapping, retry/deadline policy, and production construction remain under
  `app.infrastructure.jira` and application composition.
- Preserve the exact opaque provider selector. Add only the approved LensRun-owned JQL
  lifecycle predicate; do not parse, repair, trim, normalize, or otherwise rewrite the
  selector and do not add a status predicate.
- Reuse the existing `AlertProviderScope`, `AlertAnalysisWindow`, provider outcomes,
  provider records, pipeline normalization, reference acquisition, deterministic
  analysis, agent boundary, result builder, and terminal semantics unchanged except for
  any implementation-neutral compatibility correction strictly required by the
  approved provider contract.
- Add no dependency. `httpx`, Pydantic, `pydantic-settings`, and `SecretStr` are already
  available.
- Add no schema, migration, repository, persisted configuration, public API, frontend,
  LensRun creation path, Observation orchestration, scheduler, provider-driven agent or
  optional-tool query, analytical/result contract change, or new public reason code.
- Do not add Jira Service Management/Operations, Opsgenie, OAuth, scoped tokens,
  official Atlassian Service Accounts, Cloud-ID discovery, Atlassian gateway routing,
  custom domains, Government domains, Server/Data Center, webhooks, or writes.
- Never require a live Jira tenant or repository credential. HTTP-boundary evidence uses
  deterministic mocked/injected transport, time, sleep, and cancellation seams.
- Do not modify approved OpenSpec or `docs/architecture/`. Do not archive, push, open a
  pull request, or merge during execution of this plan.

After independent review and explicit human approval, slice structure, acceptance IDs,
proof levels, dependencies, and ownership are frozen. Acceptance sources and
GIVEN/WHEN/THEN assertions are normative traceability, while task numbers are
supplementary traceability. A task checkbox becomes complete only after every owning
slice portion has passed its gate.

Execution uses `PLANNED -> READY -> IN_PROGRESS -> COMPLETE`; `BLOCKED` records a
defined stop/escalation. Default execution is sequential. Only the Coordinator may
change execution status, accepted commit SHAs, handoff paths, verification/review
results, deviation dispositions, and execution notes after approval.

## Pre-execution readiness and planning-baseline gate

No slice may become `READY` or be delegated until the Coordinator completes every step
below after independent slice-plan review and explicit human approval of this plan:

1. Confirm the current branch is `feature/add-jira-alert-provider` and inspect the full
   worktree/index state. Preserve unrelated pre-existing roadmap material outside this
   feature execution boundary before removing it from this worktree. The preferred
   location is a separate branch/worktree; an explicit non-destructive external
   location with recorded filenames and hashes is acceptable when a separate worktree
   is unavailable. In particular, preserve `MVP_IMPLEMENTATION_ROADMAP.md` outside this
   feature worktree and do not include it in any feature commit.
2. Remove/exclude the unrelated `MVP_IMPLEMENTATION_ROADMAP.md:Zone.Identifier` sidecar
   from the feature worktree and every feature commit. It is not an approved source or
   implementation input.
3. Stage only the human-approved OpenSpec change metadata/artifacts and the
   human-approved `implementation-plan.md`: `.openspec.yaml`, `proposal.md`, `design.md`,
   `specs/**`, `tasks.md`, and this plan under
   `openspec/changes/add-jira-alert-provider/`. Verify the staged name/status list
   contains no production code, roadmap file, Zone.Identifier, or unrelated path.
4. Create one dedicated planning-baseline commit on the feature branch. It contains the
   approved planning sources and approved implementation plan, with no implementation
   changes. Resolve its immutable commit ID with `git rev-parse HEAD`; this commit is the
   accepted planning-baseline SHA for the entire execution.
5. Record that SHA in the Coordinator-owned `Planning-baseline SHA` field above and in
   the execution notes. Commit only that allowed metadata update as a Coordinator
   execution-metadata commit. This post-baseline metadata commit may change no frozen
   plan content and is classified separately from feature implementation during audits.
6. Require `git status --porcelain` to produce no output. Confirm the approved-source
   integrity command described below passes against the recorded baseline SHA. Only
   then may the Coordinator mark VS-01 `READY` and delegate it.

Minimum command evidence recorded by the Coordinator (with the baseline SHA substituted
after step 4):

```text
git branch --show-current
git status --porcelain
git diff --cached --name-status
git rev-parse HEAD

# after committing only the planning-baseline metadata update:
git diff --exit-code <planning-baseline-sha> HEAD -- \
  openspec/changes/add-jira-alert-provider/.openspec.yaml \
  openspec/changes/add-jira-alert-provider/proposal.md \
  openspec/changes/add-jira-alert-provider/design.md \
  openspec/changes/add-jira-alert-provider/specs \
  openspec/changes/add-jira-alert-provider/tasks.md
git diff --exit-code <planning-baseline-sha> -- \
  openspec/changes/add-jira-alert-provider/.openspec.yaml \
  openspec/changes/add-jira-alert-provider/proposal.md \
  openspec/changes/add-jira-alert-provider/design.md \
  openspec/changes/add-jira-alert-provider/specs \
  openspec/changes/add-jira-alert-provider/tasks.md
git status --porcelain
```

The first staged-name audit is captured immediately before the planning-baseline commit;
the same command is captured again before the metadata-only commit and must then list
only `implementation-plan.md`.

Failure to preserve/remove the unrelated files, create and record the dedicated
baseline, prove approved-source integrity, or obtain an empty porcelain status is a
pre-execution stop condition. It is not delegated to VS-01 and may not be waived by an
implementer.

Final verification performs two distinct audits against the recorded SHA:

**A. Implementation diff audit.** Compare the accepted planning-baseline SHA to the
implementation `HEAD` with commit and name/status/diff inspection. Classify all product,
test, and documentation changes as the actual feature implementation. Any
`implementation-plan.md` changes in that range must be separately proven to be only the
allowed Coordinator-owned mutable execution metadata. A merge-base-to-main diff may be
used as a supplementary scope check, but never as the approved-source or baseline proof.

```text
git log --oneline <planning-baseline-sha>..HEAD
git diff --name-status <planning-baseline-sha>..HEAD
git diff <planning-baseline-sha>..HEAD
```

**B. Approved-artifact integrity audit.** Compare the planning-baseline tree to `HEAD`
and the final worktree. `.openspec.yaml`, `proposal.md`, `design.md`, and the complete
`specs/` tree must be byte-for-byte unchanged in both comparisons.

`tasks.md` is approved text with mutable Coordinator-owned completion state. The only
allowed post-baseline change is an owning-slices-complete transition from `[ ]` to `[x]`
on an existing task line. Task wording, identifier/number, ordering, additions/removals,
section structure, scope, requirements, whitespace, and every other non-checkbox byte
remain frozen. Audit `tasks.md` twice—baseline versus committed `HEAD`, then baseline
versus final worktree—using both checks:

1. Normalize valid task-line checkbox tokens (`[ ]` or `[x]`) to one constant token in
   both files and require the normalized files to be byte-for-byte identical. This
   proves task text, numbering, order, count, sections, and all non-checkbox content are
   unchanged.
2. Compare the original files line-by-line and require every unequal pair to be exactly
   baseline `- [ ] <unchanged remainder>` versus current
   `- [x] <same unchanged remainder>`. Any reverse transition, other checkbox spelling,
   unequal line count, or non-task difference fails. Separately reconcile each observed
   `[ ] -> [x]` transition with the coverage matrix and Coordinator acceptance metadata
   proving every owning slice passed before that checkbox was committed.

Separately inspect the baseline-to-HEAD diff for `implementation-plan.md`: only
execution statuses, assignments, accepted commit/handoff fields, command/review results,
baseline SHA, and execution notes listed as mutable below may differ; all slice
structure, boundaries, coverage, risks, and gates must match the baseline exactly.
`git status --porcelain` must again be empty at final audit.

```text
git diff --exit-code <planning-baseline-sha> HEAD -- \
  openspec/changes/add-jira-alert-provider/.openspec.yaml \
  openspec/changes/add-jira-alert-provider/proposal.md \
  openspec/changes/add-jira-alert-provider/design.md \
  openspec/changes/add-jira-alert-provider/specs
git diff --exit-code <planning-baseline-sha> -- \
  openspec/changes/add-jira-alert-provider/.openspec.yaml \
  openspec/changes/add-jira-alert-provider/proposal.md \
  openspec/changes/add-jira-alert-provider/design.md \
  openspec/changes/add-jira-alert-provider/specs

# Mechanically audit tasks.md against both committed HEAD and final worktree.
audit_dir=$(mktemp -d)
git show <planning-baseline-sha>:openspec/changes/add-jira-alert-provider/tasks.md \
  > "$audit_dir/tasks.baseline.md"
git show HEAD:openspec/changes/add-jira-alert-provider/tasks.md \
  > "$audit_dir/tasks.head.md"
cp openspec/changes/add-jira-alert-provider/tasks.md "$audit_dir/tasks.worktree.md"
for current in "$audit_dir/tasks.head.md" "$audit_dir/tasks.worktree.md"; do
  sed -E 's/^- \[( |x)\] /- [STATE] /' "$audit_dir/tasks.baseline.md" \
    > "$audit_dir/tasks.baseline.normalized.md"
  sed -E 's/^- \[( |x)\] /- [STATE] /' "$current" \
    > "$audit_dir/tasks.current.normalized.md"
  diff -u "$audit_dir/tasks.baseline.normalized.md" \
    "$audit_dir/tasks.current.normalized.md"
  awk '
    FILENAME == ARGV[1] { baseline[FNR] = $0; baseline_count = FNR; next }
    FILENAME == ARGV[2] {
      current_count = FNR
      if ($0 == baseline[FNR]) next
      expected = baseline[FNR]
      changed = sub(/^- \[ \] /, "- [x] ", expected)
      if (changed != 1 || $0 != expected) {
        print "invalid tasks.md change at line " FNR > "/dev/stderr"
        invalid = 1
      }
    }
    END {
      if (baseline_count != current_count) invalid = 1
      exit invalid
    }
  ' "$audit_dir/tasks.baseline.md" "$current"
done
git diff <planning-baseline-sha> HEAD -- \
  openspec/changes/add-jira-alert-provider/implementation-plan.md
git status --porcelain
```

## Slice graph

```text
VS-01 -> VS-02 -> VS-03 -> VS-04 -> VS-05 -> VS-06
```

All slices execute sequentially. Each implementation slice depends on the contracts and
accepted handoff of its predecessor; graph edges are prerequisites, not authorization
for parallel execution.

## Execution overview

| Slice | Goal | Depends on | Risk | Status | Commit | Handoff |
|---|---|---|---|---|---|---|
| VS-01 | Compose a credential-safe Jira provider and complete an empty single-page walking skeleton | none | high-risk | IN_PROGRESS | — | `implementation/VS-01-handoff.md` |
| VS-02 | Map Jira lifecycle records through exact current/reference pipeline semantics | VS-01 | high-risk | PLANNED | — | `implementation/VS-02-handoff.md` |
| VS-03 | Exhaust cursor pages and fail closed at the approved record cap | VS-02 | high-risk | PLANNED | — | `implementation/VS-03-handoff.md` |
| VS-04 | Enforce cancellable hard attempt and acquisition deadlines | VS-03 | high-risk | PLANNED | — | `implementation/VS-04-handoff.md` |
| VS-05 | Apply exact bounded retry and failure classification semantics | VS-04 | high-risk | PLANNED | — | `implementation/VS-05-handoff.md` |
| VS-06 | Complete operator documentation and whole-change conformance | VS-05 | normal | PLANNED | — | `implementation/VS-06-handoff.md` |

## Slice definitions

### VS-01 — Credential-safe composition and empty Jira walking skeleton

**Behavioral goal:** In an environment with absent or malformed optional Jira
configuration, application settings/startup remain usable and composition produces only
a safe unavailable-provider implementation of the existing `AlertProvider` port; its
`acquire()` returns the existing typed `AlertProviderUnavailable` outcome. With a valid
ordinary-user/classic-token configuration, the application composes a real
`AlertProvider` implementation, sends one credential-safe enhanced-search request for
an immutable current window, accepts a terminal empty page, and the existing pipeline
completes its zero-record path without an agent or live Jira tenant. Only the
`jira_track_and_release` source can enter either Jira composition path.

**OpenSpec coverage:** configuration requirement and scenarios for token secrecy,
unconfigured startup, malformed optional configuration, valid composition, excluded
gateway credentials, and unsafe targets; enhanced-search target construction and
browser-path-removal scenario; redirect scenario; production-provider and fake-provider
pipeline scenarios in the modified capability; exact accepted-source isolation at the
composition boundary; tasks 1.1-1.3, composition/request portions of 1.4, foundational
portions of 2.1, 3.1, 3.5, and public-docstring/focused-test portions of 4.1-4.2.

**Dependencies:** none.

**Vertical boundary:** raw optional `JIRA_ALERT_PROVIDER` environment value -> global
Settings retains raw text -> Jira-owned strict parse, URL validation, and canonical
origin derivation -> source-isolated resolver returns an `AlertProvider` implementation:
fixed safe unavailable provider or real `HttpxJiraAlertProvider` -> caller invokes the
port's `acquire()` -> typed unavailable without transport, or one mocked POST to the
canonical REST v2 enhanced-search target with preemptive Basic authentication and exact
empty terminal envelope -> existing injected Alert pipeline -> completed zero-record
terminal outcome. Application lifespan may retain the selected provider on state but
does not invoke it or create runtime objects.

**Expected code impact:** one raw `Settings` field, a small new Jira infrastructure
package, application-state composition, placeholder environment documentation, and two
focused provider/configuration test modules plus startup regression coverage. No existing
Alert analytical implementation should need behavioral changes.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/core/settings.py::Settings` | modify | Add only raw optional `JIRA_ALERT_PROVIDER` input without provider parsing or startup failure |
| `backend/src/app/infrastructure/jira/__init__.py` | add | Expose only the infrastructure composition surface needed by application startup |
| `backend/src/app/infrastructure/jira/configuration.py` | add | Strict internal profile, serialized JSON parsing, and exact site-URL validation/canonicalization |
| `backend/src/app/infrastructure/jira/adapter.py::HttpxJiraAlertProvider` | add | Minimum real single-terminal-page acquire path, fixed v2 target/body, preemptive Basic auth, disabled redirects, empty-page outcome, and safe baseline failure mapping |
| `backend/src/app/infrastructure/jira/composition.py::UnavailableAlertProvider` | add | Implement `AlertProvider.acquire()` without transport and return the existing typed `AlertProviderUnavailable` with fixed safe diagnostic |
| `backend/src/app/infrastructure/jira/composition.py` | add | Source-isolated resolution: return an `AlertProvider` implementation for `jira_track_and_release`; never return an outcome directly and never resolve/construct/invoke Jira transport for another source |
| `backend/src/app/main.py::lifespan` | modify | Compose and retain the provider without invoking analysis or exposing a route |
| `.env.example` | modify | Add placeholder-only serialized configuration shape; no real email or token |
| `backend/tests/test_jira_alert_provider_configuration.py` | add | Settings/startup, strict JSON/profile, URL allowlist, safe diagnostics, and valid/unavailable composition proofs |
| `backend/tests/test_jira_alert_provider.py` | add | Empty-page request construction, Basic auth, redirect non-follow, and zero-record injected-pipeline proof |
| `backend/tests/test_health.py` | modify if needed | Prove health/startup remains usable with absent/malformed optional Jira configuration |

**Contracts consumed/changed:** consumes `Settings`, `AlertProvider`,
`AlertProviderScope`, `AlertAnalysisWindow`, `AlertRecordsAvailable`,
`AlertProviderUnavailable`, `AlertProviderFailure`, and existing zero-record pipeline
behavior. Every successful composition/resolution result retained by the application is
an `AlertProvider`; typed outcomes are produced only by `acquire()`. Adds infrastructure-
private Jira settings/request/page models and construction seams only. It does not
change a domain, analytical, result, persistence, or public API contract.

**Non-goals:** non-empty Jira issue mapping; reference evidence; cursor continuation;
volume cap; retries; normative hard deadlines; exhaustive HTTP/status/decode mapping;
JSM/Opsgenie; gateway/scoped/OAuth credentials; public runtime dispatch; migrations;
analytical changes.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS01-AC01 | Configure Jira / unconfigured and malformed scenarios; AlertProvider port | Missing Jira configuration; separately malformed JSON, invalid Jira URL, missing email, or missing token | Construct global Settings, resolve `source=jira_track_and_release`, then call `acquire(scope, window)` on the resolved object | Settings/startup remain usable; resolution returns an unavailable-provider implementation satisfying `AlertProvider`, never an outcome object; `acquire()` returns typed `AlertProviderUnavailable` with exact safe `not_configured` or `configuration_invalid`; no authenticated client/request exists and no exception/raw input leaks | unit + service | `backend/tests/test_jira_alert_provider_configuration.py::test_optional_jira_configuration_never_breaks_global_settings_or_startup`; `backend/tests/test_jira_alert_provider_configuration.py::test_unavailable_composition_implements_alert_provider_and_acquire_returns_typed_unavailable` |
| VS01-AC02 | Configure Jira / valid composition and unsafe-target scenarios | Every accepted root/`/jira` trailing-slash variant plus unsafe scheme, authority, host label, port, query, fragment, IP, or path cases | Validate and resolve `source=jira_track_and_release` | Accepted forms yield a real `HttpxJiraAlertProvider` satisfying `AlertProvider` with the same lowercase pathless site origin; every unsafe target yields an unavailable `AlertProvider` implementation before any client/request, and its `acquire()` returns typed unavailable rather than the resolver returning that outcome directly | unit | `backend/tests/test_jira_alert_provider_configuration.py::test_jira_site_url_allowlist_and_canonical_origin_are_exact`; `backend/tests/test_jira_alert_provider_configuration.py::test_valid_and_invalid_jira_resolution_always_returns_an_alert_provider` |
| VS01-AC03 | Configure Jira / token-secret and excluded gateway scenarios | Sentinel email/token and attempts to supply Cloud ID, scopes, gateway, Service-Account, or OAuth fields | Parse, inspect safe diagnostics/repr, and execute one admitted request | Only the selected ordinary-user/classic-token shape is accepted; credentials appear only in the preemptive Basic header, never URL/diagnostics/logs/examples; unsupported fields/discovery produce no gateway request | unit + HTTP boundary + repository audit | `backend/tests/test_jira_alert_provider_configuration.py::test_configuration_is_closed_and_secret_safe`; `backend/tests/test_jira_alert_provider.py::test_empty_search_uses_preemptive_basic_auth_without_secret_leakage` |
| VS01-AC04 | Query Jira / browser-path removal; fixed enhanced-search contract | Valid `/jira` input, opaque selector, and immutable UTC window | Acquire a terminal empty page | Exactly one POST targets `https://<site>.atlassian.net/rest/api/2/search/jql`; JSON contains only approved JQL, five fields, `maxResults=100`, and no `reconcileIssues`; `/jira/rest/...` is never requested | HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_empty_terminal_search_uses_exact_site_root_v2_request` |
| VS01-AC05 | Query Jira / cross-host redirect | Trusted site target responds with a 3xx to a sentinel foreign host | Acquire | Redirect is not followed, only the trusted host receives one request/Authorization header, and the result is a safe non-timeout provider failure | HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_redirect_is_not_followed_or_forwarded_credentials` |
| VS01-AC06 | Compose provider; modified provider-neutral pipeline scenarios | Real resolved provider with mocked terminal empty response and a fail-on-call agent; separately resolved unavailable provider and the existing fake provider suite | Inject the resolved `AlertProvider` and analyze/acquire | Every application-used resolution result implements `AlertProvider`; real provider returns only an existing typed outcome and the pipeline completes the unchanged zero-record path; unavailable provider returns typed unavailable through `acquire()`; fake tests still need no Jira settings/network; no Jira type/payload reaches the result | service | `backend/tests/test_jira_alert_provider.py::test_composed_provider_completes_existing_zero_record_pipeline`; `backend/tests/test_jira_alert_provider_configuration.py::test_unavailable_composition_implements_alert_provider_and_acquire_returns_typed_unavailable`; existing `backend/tests/test_alert_analysis_pipeline.py` regression |
| VS01-AC07 | Source-selection isolation | Sentinel source other than `jira_track_and_release`, valid Jira configuration, and a fail-on-HTTP Jira transport | Ask application composition/resolution for that other source and exercise any returned non-Jira path | The Jira resolver declines/rejects or delegates the other source before Jira configuration/provider construction; it does not return `JiraAlertProvider`, does not invoke Jira `acquire()`, and records zero Jira HTTP transport activity | unit + service + HTTP ledger | `backend/tests/test_jira_alert_provider_configuration.py::test_jira_provider_resolution_is_isolated_to_jira_track_and_release_source` |

**Counterexample guards:** VS01-AC01 supplies secret-bearing malformed text so exception
messages or eager global parsing fail. VS01-AC02 tests look-alike suffixes, extra labels,
explicit default ports, Unicode/IP hosts, and unsupported paths. VS01-AC04 uses `/jira`
input and rejects any derived URL that preserves it. VS01-AC05 records every requested
host so merely observing a 3xx failure cannot conceal credential forwarding. VS01-AC01/
AC06 assert the resolved unavailable object exposes and executes `acquire()`; a factory
that returns `AlertProviderUnavailable` directly fails before pipeline use. VS01-AC07
uses valid Jira credentials with a non-Jira source and a fail-on-use transport so source
selection after provider construction or accidental HTTP activity cannot pass.

**Implementation sketch (optional):**

```text
raw = Settings().jira_alert_provider_raw
provider = resolve_alert_provider(source, raw)
  source != jira_track_and_release -> decline/reject before Jira provider or transport
  Jira + absent config  -> UnavailableAlertProvider("not_configured")
  Jira + invalid config -> UnavailableAlertProvider("configuration_invalid")
  Jira + valid config   -> HttpxJiraAlertProvider(canonical_origin, email, SecretStr token)

all successful Jira resolution branches return AlertProvider
await UnavailableAlertProvider.acquire(scope, window)
  -> AlertProviderUnavailable("not_configured" | "configuration_invalid")

POST canonical_origin + "/rest/api/2/search/jql" (follow_redirects=false)
terminal empty page -> AlertRecordsAvailable(records=(), source="jira_track_and_release")
existing pipeline -> completed zero-record result
```

**Focused verification commands:** `cd backend && uv run pytest
tests/test_jira_alert_provider_configuration.py tests/test_jira_alert_provider.py
tests/test_health.py tests/test_alert_analysis_pipeline.py -q`; `cd backend && uv run
ruff check src/app/core/settings.py src/app/main.py src/app/infrastructure/jira
tests/test_jira_alert_provider_configuration.py tests/test_jira_alert_provider.py
tests/test_health.py`; corresponding `ruff format --check` paths; `git diff --check`.

**Context pack:** root `AGENTS.md`; approved configuration, enhanced-search, and
composition requirements/scenarios; design decisions on raw optional settings,
credential-safe origin, fixed REST v2, and composition; ADR-090-093; Alert provider
architecture sections 3-10; current `Settings`, `main.lifespan`, Alert contracts/port,
zero-record pipeline tests, and Prometheus HTTP test pattern.

**Handoff expectations:** evidence for VS01-AC01 through VS01-AC07; exact public/private
symbols; canonical-origin allow/reject matrix; request snapshot with secrets redacted;
client-construction and redirect traces; real/unavailable provider types and unavailable
`acquire()` outcome; non-Jira source-resolution/zero-HTTP ledger; provider/pipeline
result; changed-file and dependency audit; deviations; focused command results;
explicitly deferred mapping, pagination, deadlines, retries, and candidate shared
knowledge.

**Risk:** high-risk

**Completion gate:** all VS01 acceptance evidence passes; absent/invalid configuration
cannot break startup; every successful application-used resolution returns an
`AlertProvider` implementation; unavailable resolution returns typed
`AlertProviderUnavailable` only through `acquire()`; no authenticated request precedes
URL validation; root and `/jira` derive the same site-root target; redirects are not
followed; only `jira_track_and_release` enters Jira resolution and every other source
produces zero Jira construction/invocation/HTTP activity; the real empty provider path
and existing fake pipeline both pass without live Jira; no dependency, public API,
domain contract, schema, or excluded credential/provider model appears; public
class/interface docstrings, Ruff, format, and diff checks pass; independent high-risk
review returns `SLICE REVIEW PASS`; one atomic implementation commit and handoff exist,
followed by Coordinator acceptance metadata.

### VS-02 — Jira lifecycle mapping through current and reference behavior

**Behavioral goal:** Extend the real provider from an empty page to usable and malformed
Jira issues. Exact JQL candidate bounds preserve current/reference lifecycle overlap,
valid issues map to provider-neutral records with native status/priority and canonical
source references, malformed issues remain minimal normalization inputs, and the
unchanged pipeline applies exact overlap, invalid-record, current-failure, and reference-
partial semantics.

**OpenSpec coverage:** remaining enhanced-search behavior and scenarios for boundary-
spanning issues, opaque selector query errors, sub-millisecond candidate bounds, and
successful stale/empty responses; complete lifecycle-field mapping requirement and its
four scenarios; non-empty/current-reference and provider-neutral composition behavior;
tasks 2.1-2.2, mapping/overlap portions of 3.1-3.2 and 3.5, plus focused verification.

**Dependencies:** VS-01.

**Vertical boundary:** valid composed provider -> mocked terminal page with usable and
malformed Jira issues -> strict page-envelope decoding plus tolerant per-issue projection
-> existing `AlertRecordsAvailable` -> existing current/reference normalization and exact
lifecycle-overlap filter -> deterministic evidence and fake-agent/zero gate -> unchanged
completed, partial, or failed terminal outcome.

**Expected code impact:** extend only the Jira adapter/its focused tests and reuse the
existing Alert percent-encoder and normalization/reference/pipeline code. A nearby Alert
test changes only if needed to prove adapter-backed integration, not to change semantics.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/infrastructure/jira/adapter.py` | modify | Exact floor/ceil JQL construction, strict terminal response envelope, per-issue minimal projection, native fields, and safe status/decode/query failure mapping |
| `backend/src/app/infrastructure/jira/configuration.py` | modify if needed | Reuse the canonical origin independently for REST and navigation without widening URL input |
| `backend/src/app/alerts/evidence_refs.py::encode_dynamic_segment` | reuse | Existing canonical UTF-8 uppercase `%HH` segment encoder; no duplicate encoding dialect |
| `backend/tests/test_jira_alert_provider.py` | modify | Mapping, selector/JQL, reference, malformed-record, query-error, staleness, and source-ref HTTP-boundary tests |
| `backend/tests/test_alert_analysis_pipeline.py` | modify only if needed | Adapter-backed exact-overlap/current-reference integration proof; preserve fake-provider semantics |

**Contracts consumed/changed:** consumes existing provider outcome/record contracts and
application normalization unchanged. Valid issue projections may be
`AlertProviderRecord`; malformed individual projections remain minimal dictionaries
already admitted by `AlertRecordsAvailable`. Response-envelope failure stays an
acquisition outcome. No Jira model crosses the provider port.

**Non-goals:** cursor continuation; volume cap; retry/backoff; hard 15/60-second deadline
ownership; custom fields; description/ADF; occurrence reconstruction; severity mapping;
query repair; historical state reconstruction; persistence/agent/result changes.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS02-AC01 | Query Jira / spanning-start and sub-millisecond scenarios | Opaque selector, current/reference windows with sub-millisecond bounds, and records on/either side of exact overlap boundaries | Build requests and run through provider plus normalizer | Start is floored, end is ceiled, selector bytes are unchanged inside parentheses, no status predicate appears, candidate-only records reach normalization, and only exact `<`/`>` overlaps survive | unit + HTTP boundary + service | `backend/tests/test_jira_alert_provider.py::test_jql_bounds_form_a_candidate_superset_and_normalization_owns_exact_overlap` |
| VS02-AC02 | Map lifecycle fields / native status and priority | Jira issues with active/resolved timestamps, status `In Progress`, priority `Highest`, and no occurrence value | Decode/map | Exact ID/title/start/end/source-status and `{type: "priority", value: "Highest"}` are returned; description and occurrence count are absent; no global severity mapping occurs | unit + HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_issue_mapping_preserves_approved_native_lifecycle_fields` |
| VS02-AC03 | Map lifecycle fields / malformed issue scenario | One valid issue plus non-object issues/fields, missing/unusable key or required canonical fields, and unrelated large/raw fields | Map and analyze | Provider returns the valid record plus minimal malformed dictionaries without full payload; normalization rejects only malformed records via `invalid_records` and retains the usable record | HTTP boundary + service | `backend/tests/test_jira_alert_provider.py::test_malformed_issues_remain_minimal_record_level_normalization_inputs` |
| VS02-AC04 | Map lifecycle fields / canonical source-ref scenario | Equivalent root and `/jira` profiles plus issue keys containing reserved and Unicode characters | Map | Both yield the same site-root `/browse/<strict-uppercase-encoded-segment>` URL; `/jira/` is absent and the existing encoder defines the encoding | unit | `backend/tests/test_jira_alert_provider.py::test_source_ref_is_canonical_and_independent_of_input_path` |
| VS02-AC05 | Query/map / latest reference lifecycle; production provider scenario | Current succeeds and a same-duration reference issue has a returned resolution date after the historical window | Existing pipeline performs both provider calls | Requests use identical selector/fields with distinct approved window bounds; latest resolution is retained for full-lifecycle reference analysis; only compact comparison evidence reaches result/agent | service | `backend/tests/test_jira_alert_provider.py::test_real_provider_preserves_latest_reference_lifecycle_behind_existing_port` |
| VS02-AC06 | Query Jira / non-parenthesizable selector scenario | Stored selector with trailing `ORDER BY`; Jira returns a query error | Execute as current and as reference | Selector is sent unaltered in the approved composition; current maps to `current_query_failed`, reference is omitted and maps to partial `reference_unavailable`; no repair/rewrite/retry occurs | HTTP boundary + service | `backend/tests/test_jira_alert_provider.py::test_jira_query_error_uses_existing_current_and_reference_semantics` |
| VS02-AC07 | Query Jira / eventual-consistency limitation | Jira returns successful terminal empty/stale issue population | Acquire | Response is a normal successful provider outcome with no partial reason/error or extra query; `reconcileIssues` is absent | HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_successful_stale_or_empty_view_is_not_reconciled_or_failed` |
| VS02-AC08 | Compose provider / provider-neutral pipeline | Sentinel Jira response contains requested data plus unrequested/raw transport fields | Complete a non-empty current/reference run with a fake agent | Agent/result contain only canonical current data and compact comparisons; no Jira envelope, raw payload, auth, URL, or transport type crosses `AlertProvider` | service | `backend/tests/test_jira_alert_provider.py::test_jira_transport_stays_outside_agent_and_alert_result` |

**Counterexample guards:** VS02-AC01 includes equality boundaries and candidate-only
sub-millisecond records to fail inclusive/local-query substitutes. VS02-AC03 asserts
keys of each malformed dictionary, not only eventual rejection. VS02-AC04 uses characters
whose output differs under common URL encoders. VS02-AC05 makes the resolution timestamp
later than the reference window so clipping or historical reconstruction fails.

**Focused verification commands:** `cd backend && uv run pytest
tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py
tests/test_alert_contracts.py -q`; targeted Ruff and format checks for
`src/app/infrastructure/jira`, `src/app/alerts/evidence_refs.py`, and changed tests;
`git diff --check`.

**Context pack:** VS-01 accepted handoff; approved query and mapping requirements;
design decisions on v2 mapping, time filtering, individual-record versus acquisition
failure, and composition; ADR-090-098 and ADR-102-105; Alert concept sections 4-7 and 10;
provider adapter sections 4-10; current Alert contracts, normalization, references,
pipeline, evidence encoder, and focused tests.

**Handoff expectations:** VS02-AC01 through VS02-AC08 evidence; exact request fixtures;
valid/minimal-malformed projection shapes; encoding vectors; current/reference call and
pipeline projections; query-error and stale-success outcomes; change-map deviations;
focused results; deferred pagination/resilience work and shared-knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS02 acceptance evidence passes; request bounds and local exact
overlap have distinct proof; malformed individual records do not become acquisition
failure; raw Jira fields cannot reach agent/result; current/reference semantics remain
the existing ones; no new domain/result/failure contract or prohibited mapping appears;
focused regressions, Ruff, format, and diff checks pass; independent high-risk review
returns `SLICE REVIEW PASS`; one atomic implementation commit and handoff exist, followed
by Coordinator acceptance metadata.

### VS-03 — Cursor exhaustion and fail-closed volume bound

**Behavioral goal:** Extend each current or reference acquisition across Jira cursor
pages while preserving identical scope/time/field requests, accepting exactly 1,000
issues only on a terminal page, and converting every inconsistent pagination envelope or
unbounded population into a typed provider failure rather than truncated success.

**OpenSpec coverage:** complete pagination/volume requirement and all three scenarios;
task 2.3, pagination/volume portions of 3.3 and 3.5, plus focused verification.

**Dependencies:** VS-02.

**Vertical boundary:** one immutable acquisition -> first enhanced-search page -> strict
`isLast`/token validation -> zero or more cursor requests with identical JQL/fields ->
bounded accumulated provider records -> existing pipeline success, current failure, or
reference partial behavior.

**Expected code impact:** a bounded cursor loop and token/cap validation inside the Jira
adapter, with focused HTTP-boundary and existing-pipeline tests. No domain contract or
result projection changes.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/infrastructure/jira/adapter.py` | modify | Cursor loop, seen-token set, strict terminal/non-terminal state, `maxResults=100`, and 1,000-record fail-closed accounting |
| `backend/tests/test_jira_alert_provider.py` | modify | Multi-page request/body equality, token/envelope matrix, exact-cap, over-cap, and pipeline mapping tests |

**Contracts consumed/changed:** consumes the VS-02 page decoder, mapped provider records,
typed provider failure, and existing pipeline mappings. No truncation metadata or result
contract is added.

**Non-goals:** retries; Retry-After; attempt/acquire deadline ownership; parallel page
fetching; offset pagination; changing Jira page size/cap; partial successful record sets;
new analytical partial reasons.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS03-AC01 | Pagination / follow cursor scenario | Multiple valid pages, each shorter or equal to 100, with new continuation tokens and a terminal page | Acquire | Requests follow each cursor sequentially and preserve identical JQL/fields/maxResults; only `nextPageToken` changes; all records return in order | HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_cursor_pagination_exhausts_all_pages_with_stable_request_scope` |
| VS03-AC02 | Pagination / inconsistent non-terminal scenario | Matrix of missing/non-boolean `isLast`, missing/empty/repeated token, terminal non-empty token, malformed issues container, or contradictory state | Acquire | Each case returns safe typed provider failure, stops further requests, and returns no partial record set | unit + HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_inconsistent_pagination_envelopes_fail_without_truncated_success` |
| VS03-AC03 | Pagination / unbounded-volume scenario | Terminal page reaches exactly 1,000; separately a page crosses 1,000 or issue 1,000 occurs on non-terminal page | Acquire | Exact terminal 1,000 succeeds; over-cap/non-terminal-at-cap fails before another request or partial return | HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_volume_cap_accepts_only_exact_terminal_one_thousand` |
| VS03-AC04 | Pagination requirement / current-reference semantics | A current or one configured reference acquisition encounters token or volume failure | Run existing pipeline | Current becomes `current_query_failed` with no artifact; reference is omitted and a usable current result becomes partial `reference_unavailable` | service | `backend/tests/test_jira_alert_provider.py::test_pagination_failures_use_existing_current_and_reference_paths` |

**Counterexample guards:** VS03-AC01 allows short non-terminal pages so page length cannot
substitute for `isLast`. VS03-AC02 proves repeated-token detection across the entire
acquisition. VS03-AC03 distinguishes exact terminal 1,000 from 1,000 plus a continuation,
which catches first-N truncation.

**Focused verification commands:** `cd backend && uv run pytest
tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py -q`; targeted Ruff
and format checks for the Jira package/tests; `git diff --check`.

**Context pack:** VS-02 handoff; approved pagination requirement and design cursor/cap
decision; current/reference failure clauses; existing Jira page decoder/mapper and Alert
pipeline provider outcome mappings.

**Handoff expectations:** VS03-AC01 through VS03-AC04 evidence; ordered request ledger;
token-state matrix; exact/over-cap counts; proof no truncated success escapes; current/
reference terminal outcomes; deviations, focused results, and shared-knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS03 evidence passes; every successful acquisition terminates
only on consistent `isLast=true`; continuation tokens are new and non-empty; cap behavior
is exact; current/reference integration remains unchanged; no truncation metadata or
parallel/unbounded paging appears; focused regressions, Ruff, format, and diff checks
pass; independent high-risk review returns `SLICE REVIEW PASS`; one atomic implementation
commit and handoff exist, followed by Coordinator acceptance metadata.

### VS-04 — Hard monotonic deadlines and cancellation

**Behavioral goal:** Bound every complete HTTP attempt/body read to 15 monotonic seconds
and every whole acquisition to 60 monotonic seconds, cancel and clean up an in-flight
operation at either deadline, and refuse any first or later attempt when a complete
15-second attempt cannot fit in the remaining acquisition budget.

**OpenSpec coverage:** hard-deadline requirement clauses and scenarios for slow-progress
attempt interruption, acquisition exhaustion, and current deadline distinction;
deadline/reference timeout portions needed by the failure requirement; task 2.4,
deadline/cancellation portions of 3.3 and 3.5, plus focused verification.

**Dependencies:** VS-03.

**Vertical boundary:** acquisition monotonic budget -> per-page attempt admission ->
complete request/streamed-body operation under the smaller remaining/15-second deadline
-> cancellation and response/transport cleanup on expiry -> typed provider timeout ->
existing current failure or reference partial pipeline semantics.

**Expected code impact:** hard-deadline/cancellation ownership and injected deterministic
time seams inside the Jira adapter, plus slow-body/cleanup/integration tests. No pipeline
timeout wrapper or public configuration field.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/infrastructure/jira/adapter.py` | modify | Normative monotonic 15/60-second owners, pre-attempt admission, cancellable complete request/body read, cleanup, and typed timeout mapping; HTTPX phase timeouts remain defense in depth |
| `backend/tests/test_jira_alert_provider.py` | modify | Controlled clock, cancellation-observable slow/chunked body, cleanup, cumulative-page deadline, admission, current/reference timeout proofs |

**Contracts consumed/changed:** consumes typed `AlertProviderTimeout`, sequential paging,
and existing current/reference mappings. Adds only infrastructure-private injected clock/
deadline/HTTP seams needed for deterministic tests; public duration values remain exactly
15 and 60 seconds.

**Non-goals:** retry classification or waits; Retry-After; treating HTTPX inactivity
timeouts as normative; retrying deadline expiration; changing pipeline timeouts/reasons;
uncancellable background work.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS04-AC01 | Failures/deadlines / slow-progress scenario | Chunked body continues before any HTTPX read-inactivity timeout and exposes cancellation/close signals | Complete attempt reaches 15 monotonic seconds | In-flight request/body read is interrupted, response/transport cleanup is observed, outcome is typed timeout, and no retry starts | async HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_hard_attempt_deadline_cancels_slow_progress_body_and_cleans_up` |
| VS04-AC02 | Failures/deadlines / acquire deadline clauses | Successful multi-page activity cumulatively consumes the 60-second budget | A read or page attempt reaches total deadline | In-flight operation is cancelled, no later page starts, and acquisition returns typed timeout within the total budget | async HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_hard_acquire_deadline_spans_pages_and_stops_new_work` |
| VS04-AC03 | Failures/deadlines / pre-attempt admission | Less than 15 seconds remains before a first or next page attempt | Provider evaluates admission | Typed timeout returns without constructing/sending the attempt | unit + HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_attempt_requires_a_complete_fifteen_second_remaining_budget` |
| VS04-AC04 | Failures/deadlines / current distinction | Current Jira attempt reaches either hard deadline | Run existing pipeline | Provider returns `AlertProviderTimeout`; LensRun outcome is failed `current_query_timeout`, not generic failure, with no artifact | service | `backend/tests/test_jira_alert_provider.py::test_current_hard_deadline_preserves_timeout_reason` |
| VS04-AC05 | Existing reference timeout semantics | Current succeeds and a configured reference attempt reaches a hard deadline | Run existing pipeline | Current result remains usable, failed reference produces no comparison, and result is partial `reference_unavailable` | service | `backend/tests/test_jira_alert_provider.py::test_reference_hard_deadline_degrades_only_reference` |

**Counterexample guards:** VS04-AC01 sends frequent chunks so an HTTPX read timeout alone
cannot pass. VS04-AC02 consumes time over more than one page so resetting the acquisition
budget fails. VS04-AC03 observes request construction/send count. Cleanup assertions
distinguish returning timeout from abandoning live work.

**Implementation sketch (optional):**

```text
acquire_deadline = monotonic() + 60
before every attempt:
    if remaining < 15: return AlertProviderTimeout
    run complete request + body read under min(15, remaining)
    on expiry: cancel, await cleanup, return AlertProviderTimeout
```

**Focused verification commands:** `cd backend && uv run pytest
tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py -q`; targeted Ruff
and format checks; `git diff --check`.

**Context pack:** VS-03 handoff; approved deadline/failure requirement and design hard-
deadline decision; runtime failure propagation; current Jira adapter paging loop; Alert
provider timeout contract and pipeline/reference mappings; HTTPX phase-timeout semantics
as recorded in the approved design.

**Handoff expectations:** VS04-AC01 through VS04-AC05 evidence; clock timeline and
attempt/page ledger; cancellation/cleanup observation; exact pre-attempt budget cases;
current/reference terminal outcomes; defense-in-depth HTTPX timeout settings; deviations,
focused results, and shared-knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS04 evidence passes deterministically without 15/60 real-time
test sleeps; both deadline owners include full body read and clean up in-flight work;
attempt admission is exact; deadlines are never retried; current/reference typed mappings
remain unchanged; no pipeline reason/contract or background task leak appears; focused
regressions, Ruff, format, and diff checks pass; independent high-risk review returns
`SLICE REVIEW PASS`; one atomic implementation commit and handoff exist, followed by
Coordinator acceptance metadata.

### VS-05 — Exact bounded retry and failure mapping

**Behavioral goal:** Add at most two retries per failed page only for connection errors
and HTTP 502/503/504/429, choose exact deterministic waits from the approved single-value
`Retry-After` grammar or fallback schedule, admit waits/retries only inside the hard
acquisition budget, and map every exhausted, excessive-delay, non-retryable, malformed,
or successful-stale response through the approved typed current/reference paths without
secret/provider-body leakage.

**OpenSpec coverage:** complete failure/retry requirement and all nine scenarios,
including the cross-page/retry acquire deadline and retry-exhausted reference path;
remaining error-classification portions of query/composition behavior; tasks 2.5,
resilience portions of 3.3-3.5, plus focused verification.

**Dependencies:** VS-04.

**Vertical boundary:** one page attempt outcome -> exact retryability classification ->
raw repeated-header inspection and delay selection -> hard-deadline admission -> injected
deterministic sleep -> next complete attempt under VS-04 deadline -> terminal page or
typed timeout/failure -> unchanged current/reference pipeline outcome.

**Expected code impact:** retry classification, raw-header parsing, wait admission, and
safe diagnostics inside the Jira adapter, with deterministic timing/status tests. No new
dependency, retry library, or domain outcome.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `backend/src/app/infrastructure/jira/adapter.py` | modify | Exact retry set/count, raw Retry-After parsing, 15-second delay cap, 0.5/1.0 fallbacks, no jitter, deadline admission, exhausted/non-retryable classification, and safe diagnostics |
| `backend/tests/test_jira_alert_provider.py` | modify | Retryable/non-retryable matrix, raw duplicate headers, grammar/cap, fallback timing, deadline admission/exhaustion, staleness, secret-safe diagnostics, and pipeline mappings |

**Contracts consumed/changed:** consumes VS-04 hard deadlines and existing typed provider
timeout/failure/unavailable outcomes. Diagnostics remain bounded safe categories/status
codes; no raw Jira response body, URL with credentials, headers, validation exception, or
new domain reason crosses the port.

**Non-goals:** retrying hard deadlines, HTTP 400/401/403/404, redirects, decode/envelope/
pagination/volume errors, or arbitrary 4xx; exponential libraries/jitter; HTTP-date
Retry-After; per-status policy configuration; circuit breakers; provider telemetry schema;
public retry configuration.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS05-AC01 | Failures/retries general clauses | Connection errors and 502/503/504/429; separately hard deadline, 400/401/403/404/other status, redirect, malformed JSON/envelope, pagination, and volume errors | Execute a failed page | Only the approved transient set receives at most two retries; every excluded class receives exactly one attempt; exhaustion with time remaining is typed failure | unit + HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_retryability_and_attempt_counts_are_closed_and_exact` |
| VS05-AC02 | Retry-After grammar and rate-limit scenarios | Raw header matrix: one value with SP/HTAB, positive decimals/leading zeros, empty/zero/signed/fractional/combined/duplicate/date/non-decimal | Evaluate 429/retryable 5xx | Exact eligible integers through 15 select that many seconds; every unusable form selects fallback 0.5/1.0; duplicate fields are not silently combined | unit | `backend/tests/test_jira_alert_provider.py::test_retry_after_raw_header_grammar_and_waits_are_exact` |
| VS05-AC03 | Fallback-wait scenario | Retriable connection/HTTP failures without usable header on retry #1 and retry #2 | Retry | Sleeper records exactly 0.5 then 1.0 seconds, without jitter, and a third retry never occurs | unit + HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_fallback_retry_waits_and_maximum_attempts_are_exact` |
| VS05-AC04 | Excessive Retry-After and deadline-admission scenarios | Usable `Retry-After: 16`; separately insufficient remaining time for selected wait plus full 15-second attempt | Evaluate retry | Typed timeout returns immediately without sleep or request; exact 15 remains eligible only when the complete budget fits | unit | `backend/tests/test_jira_alert_provider.py::test_retry_delay_cap_and_remaining_budget_admission_return_timeout` |
| VS05-AC05 | Acquire-deadline-across-pages/retries scenario | Successful pages, retry waits, and retryable attempts cumulatively reach 60 seconds | Continue acquisition | Active wait/request/read is cancelled as applicable, no next retry/page starts, and typed timeout returns within the one acquisition budget | async HTTP boundary | `backend/tests/test_jira_alert_provider.py::test_hard_acquire_deadline_includes_all_pages_attempts_and_retry_waits` |
| VS05-AC06 | Current timeout/failure and reference-unavailable scenarios | Current retry path times out or exhausts; separately current succeeds and one reference exhausts retryable failures | Run pipeline | Current timeout remains `current_query_timeout`; exhausted non-timeout current is `current_query_failed`; reference supplies no comparison and usable result is partial `reference_unavailable` | service | `backend/tests/test_jira_alert_provider.py::test_retry_terminal_outcomes_preserve_current_and_reference_semantics` |
| VS05-AC07 | Failures/diagnostics and eventual-consistency scenario | Sentinel secrets/provider body/headers plus successful terminal stale/empty response | Exercise every failure class and successful stale response | Diagnostics expose only fixed category/status where allowed; secret/body/header text is absent; a successful stale view is not retried, failed, reconciled, or marked partial | HTTP boundary + repository audit | `backend/tests/test_jira_alert_provider.py::test_diagnostics_are_safe_and_successful_staleness_is_not_retried` |

**Counterexample guards:** VS05-AC02 constructs separate duplicate raw header fields and
comma-combined text. VS05-AC03 asserts both exact durations and attempt count. VS05-AC04
tests 15 versus 16 and the equality edge for wait plus attempt admission. VS05-AC05
combines pages, waits, and reads so per-page budget resets fail. VS05-AC06 distinguishes
timeout from retry exhaustion.

**Focused verification commands:** `cd backend && uv run pytest
tests/test_jira_alert_provider.py tests/test_alert_analysis_pipeline.py -q`; targeted Ruff
and format checks; `git diff --check`.

**Context pack:** VS-04 handoff; approved failure/retry requirement and design outcome-
classification decision; existing hard-deadline/paging implementation; Alert provider
typed outcomes and pipeline/reference failure mapping; raw HTTPX header APIs already
available through the approved dependency.

**Handoff expectations:** VS05-AC01 through VS05-AC07 evidence; complete status/error
attempt-count matrix; raw header parse table; clock/sleep/attempt timeline; cancellation
evidence; safe diagnostic snapshots; current/reference results; deviations, focused
results, and shared-knowledge candidates.

**Risk:** high-risk

**Completion gate:** all VS05 evidence passes; retry set/count, grammar, waits, 15-second
cap, and budget admission are exact; no excluded outcome retries; total deadline spans
all pages/attempts/waits/reads; timeout and non-timeout exhaustion remain distinct;
diagnostics are secret/body safe; focused regressions, Ruff, format, and diff checks pass;
independent high-risk review returns `SLICE REVIEW PASS`; one atomic implementation commit
and handoff exist, followed by Coordinator acceptance metadata.

### VS-06 — Operator documentation and whole-change conformance

**Behavioral goal:** Finish the change by documenting the deployable ordinary-user/
classic-token configuration, canonical-origin and visibility limitations, eventual
consistency and bounded failure policy; audit every approved requirement/scenario/task;
and prove the final provider remains an infrastructure-only injected implementation with
no prohibited scope, live dependency, secret, analytical change, migration, or public
API.

**OpenSpec coverage:** complete-visibility configuration scenario; final verification of
eventual-consistency, provider-neutral fake/real injection, secret/configuration, and all
other scenarios; documentation remainder of tasks 1.4 and 4.1; tasks 4.2-4.3 and final
verification of all 17 tasks.

**Dependencies:** VS-05.

**Vertical boundary:** final valid or unavailable application composition -> unchanged
provider-neutral runtime boundary -> operator/developer setup documentation and committed
placeholder configuration -> focused/full test and scope audit. Production behavior
defects return to their owning slice; this slice does not invent or absorb missing
behavior.

**Expected code impact:** developer/environment documentation, docstring and scope audits,
and only test corrections needed to express already-owned final conformance. This slice
does not own new production behavior.

#### Change map

| Path / symbol | Action | Slice responsibility |
|---|---|---|
| `.env.example` | audit/modify if needed | Final placeholder-only JSON shape and secret-local guidance |
| `docs/development-guide.md` | modify | Ordinary-user classic token, accepted site URL/canonical origin, permissions/silent omissions, eventual consistency, selector constraint, hard deadlines/retries/cap, and excluded gateway models |
| `backend/src/app/infrastructure/jira/*.py` | audit | Public class/interface docstrings, safe composition, final scope and dependency boundaries |
| `backend/tests/test_jira_alert_provider_configuration.py` | modify if needed | Final configuration/startup matrix and committed-secret guard |
| `backend/tests/test_jira_alert_provider.py` | modify if needed | Final cross-feature conformance matrix only; no new primary behavior |
| existing Alert tests and application composition tests | reuse | Fake-provider neutrality and absence of analytical/result/public API regressions |

**Contracts consumed/changed:** all completed provider and existing Alert contracts are
consumed unchanged. Documentation explains deployment preconditions and limitations; it
does not create runtime introspection, a public configuration API, or analytical
metadata.

**Non-goals:** new production behavior; refactoring; fixing a missing earlier-slice
obligation under a conformance label; live Jira call; architecture/OpenSpec edits;
dependency/schema/API/frontend changes; Observation orchestration; archive/push/PR/merge.

#### Acceptance evidence

| ID | Approved source | Given | When | Then | Proof level | Planned verification |
|---|---|---|---|---|---|---|
| VS06-AC01 | Configure Jira / complete selector visibility scenario | Deployment documentation for the dedicated ordinary Atlassian account | Review setup guidance | Browse Projects and applicable issue-security access for every selector are explicit preconditions; silent omission risk is explicit and is not represented as analytical completeness | documentation audit | exact-section review in `docs/development-guide.md` |
| VS06-AC02 | Configuration/query limitations | Root and `/jira` site forms, classic token, enhanced search, stale results, selector `ORDER BY`, deadlines/retries/cap | Review committed examples/docs | Canonical site-root REST/navigation behavior, eventual consistency/no reconcile, opaque-selector constraint, bounded policy, and excluded scoped/Service-Account/gateway/OAuth/JSM/Opsgenie models are accurate; examples contain placeholders only | documentation + secret scan | documentation assertions plus repository secret/scope scan |
| VS06-AC03 | Modified pipeline requirement / fake integration | Clean environment without Jira configuration, credentials, or network; separately a non-Jira source | Run existing Alert suite and final Jira suite | Fake pipeline behavior remains fully usable; every application-used valid/unavailable Jira resolution implements `AlertProvider` and unavailable outcome is returned only by `acquire()`; only `jira_track_and_release` selects Jira and the non-Jira source produces no Jira transport; `app.alerts` has no Jira/httpx/settings imports | repository checks | focused suites plus source/transport ledger and import-boundary scan |
| VS06-AC04 | Whole approved change and planning-baseline integrity | Recorded planning-baseline SHA, implementation HEAD/final clean worktree, approved `.openspec.yaml`/proposal/design/specs/tasks, task completion metadata, and execution-mutated implementation plan | Run the distinct implementation-diff and approved-artifact-integrity audits, audit coverage, and execute canonical checks | Baseline-to-HEAD implementation diff contains only in-scope feature work plus allowed Coordinator metadata; `.openspec.yaml`, proposal, design, and complete specs are byte-for-byte identical to the planning baseline; normalized baseline/current tasks are identical and every raw difference is exactly an authorized `[ ] -> [x]` transition backed by all owning slice gates, with no task text/identity/order/count/structure change; implementation-plan diff changes only allowed mutable execution metadata and preserves all frozen content; all 7 requirements, 32 scenarios, and 17 tasks have owning passing evidence; no dependency, migration, public API, Observation orchestration, analytical contract, architecture/OpenSpec semantic change, or excluded provider/auth scope appears; strict validation and `make check` pass | repository checks | recorded-baseline implementation diff; exact `.openspec.yaml`/proposal/design/specs HEAD/worktree zero-diff checks; normalized and raw-transition `tasks.md` comparator plus ownership reconciliation; implementation-plan frozen-content hunk audit; empty porcelain; coverage reconciliation; `openspec validate add-jira-alert-provider --strict`; `make check` |

**Counterexample guards:** documentation explicitly distinguishes ordinary operational bot
accounts from official Service Accounts and warns that a successful empty Jira response
cannot prove visibility. Scope scans inspect the actual feature diff and domain imports,
not only tests. Secret scans include committed examples and diagnostics fixtures while
allowing obvious placeholders. The tasks audit normalizes only the exact task-line
checkbox token, then separately validates raw forward transitions; wording edits hidden
beside a checkbox, renumbering/reordering, inserted/removed lines, `[x] -> [ ]`, and
unsupported checkbox spellings all fail.

**Focused verification commands:** from repository root, run focused Jira settings/
provider and existing Alert pipeline tests; `git diff --check`; `openspec validate
add-jira-alert-provider --strict`; compare the recorded planning-baseline SHA to `HEAD`
for the actual implementation commit/name-status/diff audit; run separate zero-diff
checks from that baseline to `HEAD` and the worktree for approved `.openspec.yaml`,
`proposal.md`, `design.md`, and `specs/`; run the normalized plus raw-transition
`tasks.md` comparator against both `HEAD` and the worktree and reconcile each completed
checkbox with all owning gates; inspect every baseline-to-HEAD `implementation-plan.md`
hunk against the mutable whitelist; require empty
`git status --porcelain`; scan the baseline implementation diff for dependency
manifests, migrations, frontend, public routes/contracts, architecture changes, and Jira/
httpx/settings imports under `backend/src/app/alerts`; optionally use merge-base-to-main
only as a supplementary scope view; then `make check`.

**Context pack:** all accepted predecessor handoffs; full approved proposal/design/specs/
tasks; this coverage matrix; root governance; architecture references listed above;
final feature diff; `.env.example`, development guide, Jira package, application
composition, existing Alert package/tests, root Makefile, and OpenSpec configuration.

**Handoff expectations:** VS06-AC01 through VS06-AC04 evidence; recorded planning-
baseline SHA; separate implementation-diff and approved-artifact-integrity audit output;
byte-identical `.openspec.yaml`/proposal/design/spec outputs; normalized tasks diff,
raw checkbox-transition audit, and per-task owning-gate reconciliation;
implementation-plan mutable-only hunk disposition; final empty porcelain; final
7-requirement/32-scenario/17-task reconciliation; documentation locations; public-
docstring and secret/dependency/import/scope audit; every command/result including
skips/failures; deviations; readiness for official verification and independent
implementation review.

**Risk:** normal

**Completion gate:** VS06 evidence and every earlier acceptance ID regress green;
documentation is complete and secret-safe; task ownership is reconciled; public classes
and interface methods satisfy docstring policy; focused tests, strict OpenSpec validation,
planning-baseline implementation diff, byte-identical `.openspec.yaml`/proposal/design/
spec audit, checkbox-only normalized/raw `tasks.md` audit with owning-gate proof,
mutable-only implementation-plan audit, empty porcelain, scope/dependency/secret audits,
and `make check` pass; no merge-base-only evidence substitutes for baseline integrity;
no earlier behavior is newly implemented here; one atomic documentation/conformance
commit and handoff exist, followed by Coordinator acceptance metadata. The change
remains unarchived pending the required whole-change review workflow.

## Coverage matrix

Coverage target: **7 requirements, 32 acceptance scenarios, and 17 tasks**. A task shared
across slices completes only when every listed sub-part passes its owning gate.

### Requirement ownership

| Approved requirement | Owning slice(s) | Verification |
|---|---|---|
| Configure one ordinary-user Jira Cloud bot integration without repository secrets | VS-01, VS-06 | VS01-AC01-03; VS06-AC01/02 |
| Query Jira Cloud issues through the verified enhanced JQL search surface | VS-01, VS-02, VS-05, VS-06 | VS01-AC04/05; VS02-AC01/05-07; VS05-AC07; VS06-AC02 |
| Exhaust cursor pages within a bounded provider volume | VS-03 | VS03-AC01-04 |
| Map Jira issue lifecycle fields faithfully to provider-neutral records | VS-02 | VS02-AC02-05/08 |
| Map Jira failures, deadlines, and retriable responses consistently | VS-01, VS-02, VS-03, VS-04, VS-05 | VS01-AC05; VS02-AC06; VS03-AC04; VS04-AC01-05; VS05-AC01-07 |
| Compose the real provider only behind the existing AlertProvider boundary | VS-01, VS-02, VS-06 | VS01-AC06/07; VS02-AC05/08; VS06-AC03/04 |
| Keep provider transport and production model selection outside the pipeline capability | VS-01, VS-02, VS-06 | VS01-AC06/07; VS02-AC08; VS06-AC03/04 |

### Scenario ownership

| Approved scenario | Owning slice | Acceptance evidence |
|---|---|---|
| Keep a configured token secret | VS-01 | VS01-AC03 |
| Preserve an unconfigured local environment | VS-01 | VS01-AC01 |
| Tolerate malformed optional Jira configuration | VS-01 | VS01-AC01 |
| Compose a valid Jira provider | VS-01 | VS01-AC02/04/06 |
| Exclude gateway-based account and token models | VS-01 | VS01-AC03 |
| Reject an unsafe Jira target | VS-01 | VS01-AC02 |
| Require complete selector-scope visibility | VS-06 | VS06-AC01 |
| Acquire an alert spanning the start boundary | VS-02 | VS02-AC01 |
| Remove the accepted browser path from the REST target | VS-01 | VS01-AC04 |
| Do not follow a cross-host redirect | VS-01 | VS01-AC05 |
| Treat a selector sort clause as a provider query error | VS-02 | VS02-AC06 |
| Preserve overlap candidates at sub-millisecond bounds | VS-02 | VS02-AC01 |
| Treat enhanced-search staleness as a provider limitation | VS-02, VS-05, VS-06 | VS02-AC07; VS05-AC07; VS06-AC02 |
| Follow cursor pagination | VS-03 | VS03-AC01 |
| Reject an inconsistent non-terminal page | VS-03 | VS03-AC02 |
| Reject unbounded result volume | VS-03 | VS03-AC03/04 |
| Preserve native status and priority | VS-02 | VS02-AC02 |
| Use the latest resolution information for a reference issue | VS-02 | VS02-AC05 |
| Preserve a malformed issue for normalization | VS-02 | VS02-AC03 |
| Construct the same canonical source reference from every accepted input path | VS-02 | VS02-AC04 |
| Respect Jira rate limiting | VS-05 | VS05-AC02/03 |
| Apply exact fallback retry waits | VS-05 | VS05-AC03 |
| Parse Retry-After with the exact grammar | VS-05 | VS05-AC02 |
| Reject an excessive Retry-After within the typed timeout path | VS-05 | VS05-AC04 |
| Refuse a retry that cannot fit the total deadline | VS-05 | VS05-AC04 |
| Interrupt a slow-progress response at the hard attempt deadline | VS-04 | VS04-AC01 |
| Exhaust the hard acquire deadline across pages and retries | VS-05 | VS05-AC05 |
| Preserve a current deadline distinction | VS-04, VS-05 | VS04-AC04; VS05-AC06 |
| Degrade only an unavailable reference | VS-05 | VS05-AC06 |
| Keep the pipeline provider-neutral | VS-02, VS-06 | VS02-AC08; VS06-AC03 |
| Exercise the pipeline without live integrations | VS-01, VS-06 | VS01-AC06; VS06-AC03 |
| Supply a production provider without changing pipeline semantics | VS-01, VS-02 | VS01-AC06; VS02-AC05/08 |

### Task ownership

| OpenSpec task | Owning slice(s) | Verification |
|---|---|---|
| 1.1 Raw optional global setting | VS-01 | VS01-AC01 |
| 1.2 Strict safe composition and selected credential model | VS-01 | VS01-AC01-03/06/07 |
| 1.3 Exact credential-safe Jira site URL contract | VS-01 | VS01-AC02/04/05 |
| 1.4 Examples, deployment limitations, exclusions, and port-only wiring | VS-01, VS-06 | VS01-AC03/06/07; VS06-AC01-03 |
| 2.1 Fixed v2/JQL/time-bound enhanced-search acquisition | VS-01, VS-02 | VS01-AC04; VS02-AC01/05-07 |
| 2.2 Strict response decoding and issue mapping | VS-02 | VS02-AC02-05/08 |
| 2.3 Cursor pagination and 1,000-record cap | VS-03 | VS03-AC01-04 |
| 2.4 Hard 15/60-second deadlines and cleanup | VS-04 | VS04-AC01-05 |
| 2.5 Exact retries, Retry-After, admission, and safe diagnostics | VS-05 | VS05-AC01-07 |
| 3.1 Request/JQL/current-reference HTTP-boundary tests | VS-01, VS-02 | VS01-AC03-05; VS02-AC01/05-07 |
| 3.2 Mapping/malformed/source-ref tests | VS-02 | VS02-AC02-05/08 |
| 3.3 Pagination and resilience tests | VS-03, VS-04, VS-05 | VS03-AC01-04; VS04-AC01-05; VS05-AC01/04-06 |
| 3.4 Exact Retry-After tests | VS-05 | VS05-AC02-04 |
| 3.5 Configuration/composition/injected-pipeline tests | VS-01, VS-02, VS-03, VS-04, VS-05 | VS01-AC01-07; VS02-AC05/06/08; VS03-AC04; VS04-AC04/05; VS05-AC06 |
| 4.1 Docstrings and developer/operator documentation | VS-01-VS-05 public symbols; VS-06 final audit/docs | Per-slice completion gates; VS06-AC01/02/04 |
| 4.2 Focused provider/settings/Alert/integration tests | Every slice | Every slice completion gate; VS06-AC03/04 |
| 4.3 Strict OpenSpec validation and `make check` | VS-06 | VS06-AC04 |

## Frozen plan and mutable execution state

Frozen after independent slice-plan review and explicit human approval:

- the pre-execution readiness protocol, planning-baseline definition, approved-artifact
  integrity paths, byte-identical `.openspec.yaml`/proposal/design/spec rules,
  checkbox-only `tasks.md` comparator/transition rules, and two final audit boundaries;
- implementation branch, slice count/order/graph, goals, dependencies, vertical
  boundaries, risk classifications, and completion gates;
- acceptance IDs, approved sources, GIVEN/WHEN/THEN assertions, proof levels,
  counterexample guards, and planned ownership;
- requirement/scenario/task coverage matrices, expected code impact, contract boundaries,
  non-goals, context packs, and handoff expectations.

Mutable only by the Coordinator after approval:

- planning-baseline SHA, unrelated-file preservation location/hash evidence, readiness
  command results, and the SHA of the Coordinator execution-metadata commit that records
  the baseline;
- `tasks.md` checkbox state only, and only as `[ ] -> [x]` after every owning slice
  portion has passed its completion gate; task text/identity/order/structure remain
  frozen;
- plan and slice execution statuses;
- active assignment, accepted implementation/correction commit SHAs, and handoff paths;
- command results, acceptance evidence locations, review/verifier outcomes, deviation
  dispositions, shared-knowledge disposition, and exact stop/escalation records;
- execution notes that do not add or alter requirements, proof levels, dependencies, or
  design.

A later slice may detect a regression but may not silently take ownership of missing
earlier behavior. A code-path change inside the same approved vertical boundary may be
recorded as a local deviation; a source conflict, new behavior, missing dependency
approval, schema/API/contract change, or slice-structure problem stops execution for
re-planning and renewed review/approval.

## Execution notes

Mutable Coordinator-owned execution metadata only. Do not place new requirements,
acceptance obligations, proof-level changes, or redesign decisions here.

- Planning record (2026-09-02): the approved OpenSpec was human-approved before this plan
  was created. `feature/add-jira-alert-provider` points to `main` commit `63d415b`; the
  approved change artifacts, this plan, and unrelated roadmap files are currently
  untracked. After this plan is independently reviewed and human-approved, the
  Coordinator must execute the frozen pre-execution readiness protocol above; no slice
  may start from this current state.
- Planning-baseline SHA: `3e988b0380d1b7cf51127a78e2dca386266c5dbb`.
- Unrelated roadmap preservation: local branch `docs/mvp-implementation-roadmap`, commit
  `01a19597db9c933e5b16324f3f1f7d84cf18725c`; `MVP_IMPLEMENTATION_ROADMAP.md`
  SHA-256 `2f4778799ccc633d0e9c3c7ba7a14c8f3afc7a2b7ca57bfdc0055e71c41dc401`.
  The `Zone.Identifier` sidecar was absent when readiness execution resumed and is not
  present in either commit or the feature worktree.
- Planning-baseline metadata commit: `61f589507abff3436d4810355afda36723fad546`.
  Readiness evidence passed on 2026-09-02: expected feature branch, empty staged diff,
  empty porcelain, byte-identical `.openspec.yaml`/proposal/design/specs/tasks against
  planning baseline `3e988b0380d1b7cf51127a78e2dca386266c5dbb` for both `HEAD` and
  worktree, mutable-only implementation-plan diff, and strict OpenSpec validation.
- VS-01 is `READY`; no implementation assignment has been created.
- Default execution order is VS-01 through VS-06 with no concurrent slice dispatch.
- VS-01 through VS-05 are high-risk because they implement credential/trusted-target,
  strict provider-contract, lifecycle/failure, pagination, cancellation, or retry
  semantics. Each requires fresh independent high-risk slice review before Coordinator
  acceptance. VS-06 is normal risk and still requires Coordinator evidence review.
- Every implementer uses a fresh context, reads the exact context pack and accepted
  predecessor handoff, runs focused verification/self-review, creates one atomic commit
  by default, and writes the repository-standard handoff.
- VS-01 assignment (2026-09-02): readiness gate accepted by the Coordinator against
  planning baseline `3e988b0380d1b7cf51127a78e2dca386266c5dbb`; a fresh Slice Implementer
  is active. No implementation commit is accepted yet.
