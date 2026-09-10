# UI Implementation Handoff — v1.5

**Project:** ObserveAI / Master Thesis
**Status:** Accepted living major-v1 implementation handoff for MVP UI Direction v1.5
**Date:** 2026-09-10

## 1. Purpose

This document translates the accepted current UI direction into implementation-oriented rules for the MVP frontend.

UI Direction v1.5 includes the original monitoring/investigation experience, global run management, Observation Management configuration UX, and read-only Data Sources visibility. It refines UI-generated Observation-child identity to typed, compact metadata beside Name while retaining the global Runs history/launch screen and the initial routable run-detail foundation. The frontend must preserve the architecture's semantic boundaries and must not invent new product-level classifications, lifecycle semantics, or administrative capabilities that are not supported by accepted backend contracts.

## 2. Accepted frontend visual stack

```text
React
Tailwind CSS 4
shadcn/ui
Base UI primitives
Lucide React
Recharts
TanStack Table — only where advanced tabular behavior is required
```

Styling foundation:

```text
CSS custom properties + Tailwind theme integration
```

Third-party libraries provide primitives. Product/domain semantics remain project-owned.

## 3. UI authority and visual reference

ADR-167 defines the UI authority order:

1. accepted domain/runtime architecture and public contracts govern product semantics and API boundaries;
2. this accepted `docs/ui/` direction/handoff plus approved OpenSpec changes govern UI behavior, information architecture, and intentional visual evolution;
3. MagicPath is an informative visual reference and optional synchronization target, not a parity requirement or an implementation/acceptance gate;
4. meaningful UI changes remain versioned and human-approved rather than arising from incidental implementation drift.

Informative MagicPath project:

```text
Observation UI - Master Thesis
https://magicpath.ai/files/447597481925181440
```

MagicPath can inform look and feel but does not require 1:1 parity or canvas synchronization for an approved implementation. It is not permission to invent API fields or backend lifecycle operations. Accepted architecture/contracts remain authoritative for domain semantics.

## 4. Screen set — v1.5

### Monitoring and investigation

```text
00 Design System
01 Overview
02 Observation Detail
03 Observation Run Summary
04 Metric Lens Detail
05 Alert Lens Detail
06 Relationships
07 Observation Analysis
08 Report
```

### Observation Management

```text
09 Observations Management
10 Create Observation
11 Relationship Configuration
12 Metric Lens Configuration
13 Alert Lens Configuration
14 Data Sources
15 Runs History and Launch
```

`00 Design System` is documentation/reference, not an application route.

## 5. Core semantic rules

### Analytical state

```text
no_significant_findings
uncertain
significant_findings_present
```

UI labels:

```text
No significant findings
Uncertain
Significant findings present
```

Suggested scan colors:

```text
green  -> no_significant_findings
amber  -> uncertain
red    -> significant_findings_present
```

Always pair color with text.

### Execution state

```text
ObservationRun: pending | running | completed | failed | cancelled
LensRun:        pending | running | completed | partial | failed | cancelled
```

Execution state is independent from analytical state. A failed execution means unavailable analytical evidence, not a detected anomaly.

`partial` is a LensRun status only. The UI must not invent a partial or degraded
ObservationRun status. A failed ObservationRun may still have an already persisted
ObservationAnalysisResult when a later stage, such as report generation, failed; show
both truths independently.

### Findings, hypotheses and traceability

```text
Finding = evidence-grounded Observation-level conclusion
Hypothesis = possible explanation supported by finding(s) + knowledge reference(s)
```

Visually distinguish Evidence, Relationship and Knowledge references. Never present a hypothesis as a confirmed root cause.

### Report

The Report screen is presentation-only. It must not introduce new findings, hypotheses, recommendations or analytical state.

## 6. Design-token direction

Minimum semantic token groups:

```text
color.background.*
color.surface.*
color.text.*
color.border.*

color.analysis.no_findings
color.analysis.uncertain
color.analysis.significant

color.execution.completed
color.execution.partial
color.execution.failed
color.execution.pending
color.execution.running
color.execution.cancelled

color.trace.evidence
color.trace.relationship
color.trace.knowledge

spacing.*
radius.*
typography.*
```

Avoid scattering raw Tailwind colors for domain semantics. Prefer project-owned semantic components such as `AnalyticalStateBadge` and `ExecutionStatusBadge`.

## 7. Project-owned component vocabulary

### Shell

```text
AppShell
Sidebar
PageHeader
RunHeader
Tabs
```

### Status and traceability

```text
AnalyticalStateBadge
ExecutionStatusBadge
DataQualityBadge
ImportanceBadge
EvidenceChip
RelationshipChip
KnowledgeChip
```

### Content

```text
SummaryCard
ObservationRow
RecentRunsStrip
LensCard
FindingCard
HypothesisCard
RelationshipEvaluationCard
LimitationNotice
```

### Configuration

```text
ConfigurationSection
DefinitionSummary
AnalysisObjectivesField
ReferencePeriodsField
MetricLensEditor
AlertLensEditor
RelationshipEditor
ParticipantSelector
```

`AnalysisObjectivesField` should be shared by Metric and Alert Lens editors.

### Visualization

```text
MetricTimeSeriesChart
RunActivityChart
```

## 8. Monitoring screen contracts

### Overview

Purpose: quickly identify what needs attention.

Required areas:

```text
Page header
Summary cards
Observation list
Recent Findings
Run Activity
```

Observation rows show name, description, latest run time, latest analytical state, latest execution state, duration and approximately the latest 7 run states.

### Observation Detail

Show Observation identity, Run Observation action, latest run summary, Metric Lens definitions, Alert Lens definitions and Relationships.

### Observation Run Summary

Required areas:

```text
Run header
Summary
Key Findings
Lens Overview
Relationships
Possible Explanation
```

Run navigation:

```text
Summary
Metrics
Alerts
Relationships
Analysis
Report
```

### Metric Lens Detail

Keep current-state evidence, reference periods and persisted run history visually separate.

Current numerical evidence includes at least:

```text
mean
std
min
max
slope
```

Current semantic state includes:

```text
trend.direction
trend.rate
variability.state
```

### Alert Lens Detail

Show current alert summary, current alerts, Lens-local findings, reference periods and analysis boundary.

`provider importance` and Alert Lens `overall_importance` are not Observation analytical state.

### Relationships

Keep applicability separate from evaluation state:

```text
applicability: applicable | not_applicable | unknown
state when applicable: consistent | inconsistent | uncertain
```

Show conditions, expectations, observed values, match/mismatch and evaluation chain.

### Observation Analysis

Show evidence coverage, Relationship evidence, limitations, findings, possible explanations and traceability.

### Report

Presentation-focused document view with Copy Markdown. File/PDF export remains a later
versioned refinement and is not required by the initial run-detail foundation.

### Runs History and Launch

Purpose: monitor all active and historical ObservationRuns, start an eligible
Observation on demand, and open the initial detailed run view.

Required areas:

```text
Page header + Run Observation action
Manual refresh
Observation filter
ObservationRun status filter
Analytical-state filter, including unavailable/not-yet-produced
Newest-first lightweight run list
```

Each row shows only scan-oriented identity, time/window, duration when available,
ObservationRun status, optional analytical state, and Open. The list loads the complete
MVP history without pagination. Filters combine locally and preserve newest-first order.

`Run Observation` opens an accessible dialog. It selects one Observation and either a
relative range (`5m`, `15m`, `30m`, `1h`, `3h`, `6h`, `12h`, `24h`, `2d`, `7d`) or the
closed absolute-expression set `now`, `now-15m`, `now-1h`; initial range is `now-15m`
to `now`. Both endpoints resolve against one captured instant and only concrete UTC
timestamps are submitted. Unsupported Grafana expressions are rejected rather than
partially parsed.

The dialog loads current Observation Definitions independently from run history and
distinguishes loading, retryable failure, successful empty, and successful non-empty
states. Confirmation is disabled until a successful eligible selection. A definition
without prior runs remains selectable; history is used only to disable known active
Observations, and the backend remains authoritative for races. Closing aborts the
definition request; empty state links to New Observation.

An Observation with `pending|running` run is disabled and the backend remains
authoritative for races. After accepted launch the dialog closes, route remains `/runs`,
the new active row is shown, and automatic refresh continues while active runs exist.
Manual refresh remains available; a failed refresh preserves last successful data with
stale feedback.

The detail route `/runs/{observationRunId}` uses the existing run navigation:

```text
Summary
Metrics
Alerts
Relationships
Analysis
Report
```

This initial detail is a semantic foundation, not final visual refinement. It shows every
available durable artifact in its correct domain section, explains missing/not-yet-
produced artifacts, and never collapses findings into hypotheses, evidence into
knowledge, or execution failure into analytical significance.

On-demand execution follows ADR-168's single-process MVP boundary. Scheduling,
multi-process execution, public cancellation, retry/resume, pagination, and later
detail visualization refinements are not implied.

ADR-170 limits this unauthenticated UI/API to a trusted single-user or internal
environment. The frontend adds no login, token storage, permission UI, permissive CORS,
or browser-visible secret. Direct exposure to an untrusted network is unsupported until
a separate authentication/authorization change is approved.

## 9. Observation Management UX

### Product placement

Observation management is part of the existing `Observations` product area. Do not introduce a separate Admin application or top-level Admin navigation area for MVP.

Conceptual flow:

```text
Observations Management
        ↓
Create Observation
        ├─ Metric Lens Configuration
        ├─ Alert Lens Configuration
        └─ Relationship Configuration
        ↓
Review / validate aggregate
        ↓
Create Observation
```

### Observations Management

Purpose: find existing Observation definitions, inspect their latest runtime state, or start creating a new Observation.

Required areas:

```text
Page header
New Observation action
Search
Optional latest-state/execution filters
Observation definitions list
```

Rows may show definition composition, latest run timestamp, latest analytical state, latest execution state and Open action.

MVP boundary:

```text
Create and inspect are allowed.
Edit/Delete controls remain hidden until the corresponding API lifecycle is explicitly supported.
```

Do not invent Observation update/delete endpoints from the UI.

### Data Sources

Purpose: provide safe, read-only visibility of the environment-managed Prometheus
sources available to Metric Lens configuration. This is not an application-managed
source lifecycle or credential-management screen.

Required areas:

```text
Page header identifying environment-managed Metric sources
Manual Refresh action
Loading, retryable failure, empty, and configured states
Configured source list/card view
Safe empty-state environment setup guidance
```

Each configured source is shown exactly once in the capabilities response order using
only its provider type (`Prometheus`), stable ID, human-readable name, and wording that
it is available for Metric Lens configuration. The screen must not show or infer a base
URL, credentials, credential type, Basic username, Authorization data, connection
health, or diagnostics.

The configured registry comes from backend `PROMETHEUS_SOURCES`, an optional JSON array
in the root backend environment or deployment environment. Multiple entries are
supported; each needs a unique stable ID, display name, base URL, and exactly one
accepted credential shape. A manual Refresh re-reads the already running backend; it
does not reload Settings, test a connection, or mutate a source. The operational sequence
is: change environment, restart the backend, then refresh the page.

When no source is configured, show placeholder-only Bearer-token and Basic-auth JSON
examples, explain that all valid entries become Metric Lens choices, and warn that real
credentials belong only in local/deployment environment configuration. The UI must never
write `.env`, collect credentials in a browser form, put them in `VITE_*`, or imply they
may be committed.

### Create Observation

Build one Observation Definition as a single validated aggregate.

Sections:

```text
General
Metric lenses
Alert lenses
Relationships
Review
```

Maintain a local/client-side Observation draft until final `Create Observation` submission. Nested Lens/Relationship editors modify the draft only.

At least one Lens must be configured overall.

### Draft / nested-editor semantics

```text
Open nested editor
    ↓
change Lens/Relationship values
    ↓
Apply changes
    ↓
update Observation draft
    ↓
return to Create Observation
```

`Apply changes` is **not** a standalone backend persistence operation.

Do not implement standalone Lens persistence merely because a nested editor has its own screen.

### Generated child identity

New Metric Lens, Alert Lens, and Relationship editors generate their public-contract
ID once when the user leaves the initial non-empty Name field. Each new ID has the exact
composition `<metr|alrt|rel>_<normalized-name>_<8 lowercase hex random>`: Metric Lens
uses `metr`, Alert Lens uses `alrt`, and Relationship uses `rel`; the random part is
eight lowercase hexadecimal characters from browser-provided randomness. The ID remains
within the 255-character persistence boundary and public identifier grammar.

Before generation, Name guidance explains that a non-empty name generates the ID on
leaving the field. Once generated or when reopening a child with an existing ID, show
the value as compact, secondary, selectable `(id: <value>)` text adjacent to Name. It
must be exposed to assistive technology and must not be a separate input or another
editable/focusable form control. After generation, later name changes do not change the
ID. Reopening an applied draft or persisted child preserves its ID exactly, including a
legacy ID that does not use the typed format. Generation remains editor-local until
`Apply changes`; Cancel does not mutate the aggregate draft. Metric and Alert collision
checks remain type-local, while Relationship IDs remain unique within their own
collection. This UI-only refinement does not tighten backend identifier grammar, alter
aggregate ownership, or add standalone Lens or Relationship API boundaries.

### Metric Lens Configuration

One Metric Lens observes exactly one metric.

Keep these areas distinct:

```text
Lens identity
Metric reference / unit
Analysis objectives
Reference periods
Persisted-history policy (only where supported by current public config/API)
```

`analysis_objectives` UX:

```text
ordered free-text list
inline add/edit/remove
non-empty values
exact duplicates rejected
no controlled vocabulary
no priority
no tool-selection semantics
```

Target UI Direction v1.2 treats Metric objectives as free-text intent. The current
public Metric Lens API accepts only `spike`, `drift`, and `oscillation`. Until that
contract is explicitly changed, the Metric editor must constrain submitted values to
the accepted vocabulary or report free-text support as a backend dependency. Do not
silently send unsupported values.

`+ Add objective` inserts a new inline input. No separate objective screen/modal.

Do not expose analyzer/tool toggles unless a future accepted contract explicitly introduces them.

Reference periods and persisted history are separate temporal concepts.

Primary nested-editor action: `Apply changes`.

### Alert Lens Configuration

Drive the form from the accepted Alert Lens contract, including:

```text
id
type = alert
name
description (optional)
source
selector.query
analysis_objectives[]
reference_periods[]
```

Core UX rule:

```text
selector = which alerts
LensRun/runtime = when they are observed
```

The selector is opaque provider-native input. The UI must not parse/rewrite it, add lifecycle-status filters automatically, or encode runtime time windows into it.

Use the same inline `AnalysisObjectivesField` as Metric Lens.

Primary nested-editor action: `Apply changes`.

Alert Lens remains an owned child of Observation Definition. Do not imply standalone Alert Lens CRUD/resource lifecycle.

### Relationship Configuration

Relationships are engineer-defined deterministic qualitative rules over Metric Lens current-state descriptors.

MVP boundary:

```text
Metric Lens participants only
2..N participants
current_state properties only
```

Editor structure:

```text
Relationship identity
Participants
When — conditions
Expect — expectations
```

Provide `+ Add participant` because the model is 2..N.

Allowed properties come from the accepted explicit relationship vocabulary, for example:

```text
trend.direction
trend.rate
variability.state
```

Do not implement a generic free-form expression/rule builder.

Conditions determine applicability; expectations are evaluated only when applicable.

## 10. Form interaction rules

### Analysis objectives

Use a shared inline pattern:

```text
Analysis objectives
helper text
objective row [text] [remove]
+ Add objective
```

No objective route or modal is needed.

### Reference periods

Use repeatable compact values/rows. Reject duplicates and invalid offsets according to the actual domain contract.

### Validation

Prefer local field validation plus aggregate-level review before final create.

Do not expose prompts, agent models, tool-call budgets, orchestration internals or backend implementation details as user configuration.

## 11. Library usage

- shadcn/ui / Base UI: interaction/accessibility primitives such as Tabs, Tooltip, Popover, Dialog, Dropdown and Select.
- Lucide React: application icons; avoid mixed icon sets.
- Recharts: wrapped in project-owned chart components.
- TanStack Table: only when advanced sorting/filtering/pagination/column behavior is genuinely needed; simple dashboard/management rows should stay lightweight.

## 12. Empty / partial / failed state rules

Empty state explains absence without implying normality.

Partial state shows usable evidence plus explicit limitation.

Failed state means evidence unavailable. Never map failed execution to a red analytical-state badge.

## 13. Recommended frontend folder direction

```text
src/
  app/
  components/
    ui/
    domain/
      observation/
      lens/
      analysis/
      traceability/
      configuration/
    charts/
  features/
    overview/
    observations/
    observation-management/
    observation-runs/
    metrics/
    alerts/
    relationships/
    reports/
  styles/
    tokens.css
  lib/
```

`components/ui` = generic primitive layer.
`components/domain` = ObserveAI semantic component layer.
`features` = screen/use-case composition.

## 14. Implementation sequence

```text
1. Frontend foundations / tokens
2. App shell + navigation
3. Semantic badges/chips
4. Observation Management flow (first roadmap UI feature)
5. Data Sources
6. Runs History + Run Observation dialog
7. Observation Run Summary / initial run-detail foundation
8. Overview
9. Observation Detail monitoring refinement
10. Metric Lens Detail refinement
11. Alert Lens Detail refinement
12. Relationships refinement
13. Observation Analysis refinement
14. Report presentation/export refinement
```

If `add-observation-management-ui` is the first frontend OpenSpec change, it may establish the minimum reusable frontend foundations needed by that feature. Do not expand it into implementation of the entire monitoring UI.

## 15. Versioning and change-control rule

**UI Direction v1.5 is the accepted current direction.**

Implementation may make minor technical adjustments for responsive fit, accessibility, browser behavior, real data length and actual API constraints, but must not silently change:

```text
information architecture
product terminology
analytical/execution semantics
finding/hypothesis boundary
evidence/knowledge boundary
Observation aggregate ownership
Lens standalone-resource semantics
Metric-only Relationship boundary
selector "which" vs runtime "when" semantics
```

Meaningful visual, UX or semantic changes require an explicit versioned and human-approved decision rather than incidental implementation deviation. Under ADR-167, MagicPath may inform the change and may be synchronized later, but it is not a parity requirement or implementation/acceptance gate.
