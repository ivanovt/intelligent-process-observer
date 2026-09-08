# MVP Implementation Roadmap

**Project:** Intelligent Process Observer  
**Purpose:** Track implementation progress toward the first demonstrable MVP.  
**Roadmap scope:** Metric + Alert analysis, real providers, deterministic Relationships, Observation-level reasoning, report generation, and UI.  
**Deferred from the first MVP:** Log Lens / Logs Analysis Pipeline / Loki provider.

---

## Status convention

Use one of the following values in the **Status** column:

- `DONE` — merged and accepted
- `IN PROGRESS` — implementation/review currently active
- `PLANNED` — approved roadmap item not yet started
- `BLOCKED` — cannot proceed without resolving a dependency or decision
- `DEFERRED` — intentionally postponed outside the first MVP

Keep the checkbox and the status aligned:

```text
- [x] DONE
- [ ] IN PROGRESS
- [ ] PLANNED
- [ ] BLOCKED
- [ ] DEFERRED
```

---

## 1. Completed foundation

| Done | # | Feature / Change | Status | Purpose / Outcome |
|---|---:|---|---|---|
| [x] | 1 | `add-observation-definition-api` | DONE | Persisted Observation Definition aggregate, Metric Lens definitions, Relationships, and create/read API foundation. |
| [x] | 2 | `add-runtime-persistence` | DONE | Runtime persistence for ObservationRun, LensRun, analytical artifacts, lifecycle, and correlation. |
| [x] | 3 | `reusable-openspec-review-workflow` | DONE | Reusable OpenSpec review / verification workflow and agent skills. |
| [x] | 4 | `select-pydanticai-for-mvp-agents` | DONE | PydanticAI selected as the MVP agent-framework integration mechanism while domain contracts remain framework-neutral. |
| [x] | 5 | `add-metrics-analysis-pipeline` | DONE | End-to-end provider-neutral Metrics Analysis Pipeline with deterministic core, bounded Metrics Agent, reference periods, History, strict result contract, and persistence. |
| [x] | 6 | `add-alert-lens-definition` | DONE | Merged through PR #7. Adds persisted Alert Lens definitions, type-local identity, validation, migration, and type-aware LensRun uniqueness. |
| [x] | 7 | `add-alerts-analysis-pipeline` | DONE | Merged through PR #7. Adds the provider-neutral Alert pipeline, deterministic evidence, bounded Alert Agent/tools, strict `AlertAnalysisResult`, and atomic runtime persistence. |
| [x] | — | `document-frontend-ui-direction` | DONE | Merged through PR #16. Freezes UI Direction v1.1, the MVP visual stack, screen contracts, and the implementation sequence beginning with Observation Management. |

---

## 2. Current work

No critical-path feature is active. The next planned item is `add-observation-run-ui`.

---

## 3. MVP critical path

### Phase A — Complete the Alert analytical path

| Done | # | Feature / Change | Status | Depends on | Purpose / Exit condition |
|---|---:|---|---|---|---|
| [x] | 8 | `add-jira-alert-provider` | DONE | #7 | Merged through PR #8. Real Jira Track and Release provider adapter behind the Alert provider port. |
| [x] | 9 | `add-prometheus-metric-provider` | DONE | #5 | Merged through PR #10. Real Prometheus provider adapter behind the existing Metric provider port. |

**Phase A milestone:** Metric and Alert pipelines can both run against real external data sources.

---

### Phase B — Cross-Lens deterministic and knowledge capabilities

| Done | # | Feature / Change | Status | Depends on | Purpose / Exit condition |
|---|---:|---|---|---|---|
| [x] | 10 | `add-relationship-evaluator` | DONE | #5 | Merged through PR #11. Deterministic evaluation of engineer-defined Metric Relationships using accepted `current_state` semantics. |
| [x] | 11 | `add-knowledge-retrieval` | DONE | Foundation only | Merged through PR #13. Framework-neutral retrieval contracts and deterministic two-call execution with structured provenance; a concrete retrieval backend remains separate follow-up work. |

**Phase B milestone:** The system can combine deterministic cross-Metric evidence with a reusable bounded knowledge-retrieval capability.

---

### Phase C — Observation-level reasoning and reporting

| Done | # | Feature / Change | Status | Depends on | Purpose / Exit condition |
|---|---:|---|---|---|---|
| [x] | 12 | `add-observation-reasoning` | DONE | #5, #7, #10, #11 | PR #14. Produce structured Observation-level findings, grounded hypotheses, limitations, and `overall_state` from usable Metric/Alert results and Relationship evaluations. |
| [x] | 13 | `add-report-generation` | DONE | #12 | Merged through PR #15. Converts `ObservationAnalysisResult` into a validated human-readable Markdown `ObservationReport` without new analysis or retrieval. |

**Phase C milestone:** The analytical backend can produce a complete structured Observation interpretation and a human-readable report.

---

### Phase D — End-to-end Observation runtime

| Done | # | Feature / Change | Status | Depends on | Purpose / Exit condition |
|---|---:|---|---|---|---|
| [x] | 14 | `add-observation-execution` | DONE | #7–#13 | Merged through PR #17. Deterministic top-level Observation workflow with correlated runs, bounded Lens fan-out, strict JOIN, usable-results gate, Relationship Evaluation, Observation Reasoning, Report Generation, cancellation, and terminal lifecycle. |

**Phase D milestone:** One Observation can execute end-to-end over real Metric and Alert sources and produce persisted analytical results plus a final report.

---

### Phase E — Prototype UI

| Done | # | Feature / Change | Status | Depends on | Purpose / Exit condition |
|---|---:|---|---|---|---|
| [x] | 15 | `add-observation-management-ui` | DONE | #6, #9, #14 API stability | PR #18. Establishes the reusable frontend foundation and supports listing, creating, and inspecting Observation Definitions with draft-based Metric/Alert Lens and Relationship configuration. |
| [ ] | 16 | `add-observation-run-ui` | PLANNED | #14, #15 | Implement the frozen monitoring and investigation views for starting/inspecting runs, LensRun status, Metric/Alert results, Relationship evaluations, Observation analysis, and final report. |

**Phase E milestone — FIRST DEMONSTRABLE MVP:**  
A user can configure an Observation, run it against real Prometheus and Jira data, inspect Metric and Alert analysis, see deterministic Relationship results, review Observation-level reasoning, and read the final report through the UI.

---

## 4. Deferred after the first MVP

These features remain part of the architecture but are intentionally postponed to shorten the path to a usable prototype.

| Done | Feature / Change | Status | Reason for deferral |
|---|---|---|---|
| [ ] | `add-log-lens-definition` | DEFERRED | Log analysis is not required for the first Metric + Alert prototype. |
| [ ] | `add-logs-analysis-pipeline` | DEFERRED | Significant additional scope: parsing, sanitization, bounded textual content, templates, tools, and knowledge enrichment. |
| [ ] | `add-loki-log-provider` | DEFERRED | Depends on the deferred Log Lens and Logs Analysis Pipeline. |

When Logs are resumed, the intended order is:

```text
add-log-lens-definition
    -> add-logs-analysis-pipeline
    -> add-loki-log-provider
    -> integrate Log LensRuns into the existing Observation execution workflow
```

---

## 5. Explicitly outside the first MVP

Do not move these into the critical path unless the MVP goal changes:

- cross-type Relationships;
- global Relationship Registry / Process Model;
- baseline management and adaptive/seasonal baselines;
- runtime relationship discovery;
- advanced alert clustering, flapping, or escalation analysis;
- advanced semantic/embedding log clustering;
- persisted Log History Analyzer;
- autonomous expansion of observational scope by agents;
- confidence/probability/severity models;
- prescriptive recommendations or automated corrective actions;
- scheduling / periodic trigger infrastructure beyond what is required to demonstrate on-demand execution;
- production-grade notification channels.

---

## 6. Progress summary

Update this section when a feature changes state.

```text
Completed runtime/product features: 13 / 14 (implemented and accepted; PR #18 open)
Completed engineering/documentation foundations: 3
Current feature: none selected
First-MVP critical-path remaining: 1 (#16)
Deferred feature group: Logs
```

> Counting convention: runtime/product features start with `add-observation-definition-api`; workflow/documentation foundations are tracked separately and are not counted as user-facing runtime capabilities.

---

## 7. Roadmap maintenance rules

1. A feature becomes `DONE` only after implementation, required reviews/verification, archive where applicable, PR/CI, and merge.
2. `IN PROGRESS` should normally apply to only one critical-path feature at a time unless parallel work is explicitly intentional.
3. If a feature reveals a new required capability, add it to the roadmap only after deciding whether it is:
   - required for the first MVP;
   - a prerequisite of an existing item; or
   - safely deferred.
4. Do not silently promote Open/Deferred architecture decisions into roadmap requirements.
5. Revisit the roadmap after every 2–3 completed features or when a major architecture/implementation finding changes the critical path.
6. Feature-specific OpenSpec remains the authority for **what** each feature implements; this roadmap only records sequencing, dependencies, milestones, and progress.

---

## 8. Compact roadmap

```text
DONE
  #1  add-observation-definition-api
  #2  add-runtime-persistence
  #3  reusable OpenSpec review workflow
  #4  select PydanticAI for MVP agents
  #5  add-metrics-analysis-pipeline
  #6  add-alert-lens-definition
  #7  add-alerts-analysis-pipeline
  #8  add-jira-alert-provider
  #9  add-prometheus-metric-provider
  #10 add-relationship-evaluator
  #11 add-knowledge-retrieval
  #12 add-observation-reasoning
  #13 add-report-generation
  #14 add-observation-execution
  #15 add-observation-management-ui

NEXT
  #16 add-observation-run-ui

COMPLETED FOUNDATION (UNNUMBERED)
  document-frontend-ui-direction

DEFERRED / MVP+
  add-log-lens-definition
  add-logs-analysis-pipeline
  add-loki-log-provider
```
