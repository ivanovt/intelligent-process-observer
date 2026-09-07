# UI Implementation Handoff — v1.0

**Project:** ObserveAI / Master Thesis
**Status:** Working implementation handoff based on frozen UI Direction v1.0
**Date:** 2026-09-07

## 1. Purpose

This document translates the frozen UI direction into implementation-oriented rules for the MVP frontend.

The frontend must preserve the architecture's semantic boundaries and must not invent new product-level classifications.

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
CSS custom properties
+
Tailwind theme integration
```

## 3. Screen set — v1

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

`00 Design System` is documentation/reference, not an application route.

## 4. Core semantic rules

### 4.1 Analytical state

Observation-level analytical state:

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

Suggested visual semantics:

```text
green  -> no_significant_findings
amber  -> uncertain
red    -> significant_findings_present
```

Color is a scan aid only; text must always be present.

### 4.2 Execution state

Execution state is separate from analytical state:

```text
completed
partial
failed
```

A failed execution means unavailable analytical evidence, not a detected anomaly.

### 4.3 Evidence vs knowledge

The UI must visually separate:

```text
Evidence reference
Relationship reference
Knowledge reference
```

Observation findings are supported by observational Lens/Relationship evidence.

Hypotheses may additionally use external knowledge references.

### 4.4 Findings vs hypotheses

```text
Finding
= evidence-grounded observation-level conclusion

Hypothesis
= possible explanation supported by finding(s) + knowledge reference(s)
```

The UI must not present a hypothesis as a confirmed root cause.

### 4.5 Report

The Report screen is presentation-only.

It presents the accepted Observation analysis and does not create new findings, hypotheses, recommendations, or analytical state.

## 5. Design tokens

Exact values should be consolidated during implementation from the frozen mock.

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

color.trace.evidence
color.trace.relationship
color.trace.knowledge

spacing.*
radius.*
typography.*
```

Avoid repeated raw Tailwind colors for domain semantics.

Bad:

```tsx
<span className="text-red-500 border-red-500">
```

Preferred:

```tsx
<AnalyticalStateBadge state="significant_findings_present" />
```

## 6. Project-owned component vocabulary

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

### Visualization

```text
MetricTimeSeriesChart
RunActivityChart
```

## 7. Screen implementation contracts

### 7.1 Overview

Purpose:

> What needs my attention right now?

Required areas:

```text
Page header
Summary cards
Observation list
Recent Findings
Run Activity
```

Observation row fields:

```text
name
description
latest run time
latest analytical state
latest execution state
duration
recent run history
```

Recent run history should show approximately the latest 7 runs.

Do not use TanStack Table unless richer table behavior becomes necessary.

### 7.2 Observation Detail

Purpose:

> What is this Observation, how is it configured, and what happened recently?

Required areas:

```text
Observation identity
Run Observation action
Latest run summary
Metric lenses
Alert lenses
Relationships
```

The page describes the Observation definition and recent execution context; it is not the analytical run-detail screen.

### 7.3 Observation Run Summary

Purpose:

> What happened during this execution, and where should I investigate next?

Required areas:

```text
Run header
Summary
Key Findings
Lens Overview
Relationships
Possible Explanation
```

Navigation:

```text
Summary
Metrics
Alerts
Relationships
Analysis
Report
```

### 7.4 Metric Lens Detail

Purpose:

> What evidence supports the Metric Lens result?

Required areas:

```text
Current window chart
Current analytical state
Reference periods
Persisted run history
Optional analyses
```

Current numerical evidence should include at least:

```text
mean
std
min
max
slope
```

Current semantic state should expose:

```text
trend.direction
trend.rate
variability.state
```

Reference periods and persisted history are distinct concepts and must remain visually separate.

### 7.5 Alert Lens Detail

Purpose:

> What alert activity and Lens-local findings were observed?

Required areas:

```text
Current alert summary
Current alerts
Lens findings
Reference periods
Analysis boundary
```

Important:

```text
provider importance != Observation analytical state
Alert Lens overall importance != Observation analytical state
```

The screen must not imply system-level root cause.

### 7.6 Relationships

Purpose:

> Which deterministic expected-behavior rules were applicable, and were they consistent?

Required states:

```text
applicability:
  applicable
  not_applicable
  unknown

state when applicable:
  consistent
  inconsistent
  uncertain
```

The UI must not merge applicability and state into one generic status.

Show:

```text
Conditions
Expectation
Observed values
Match/mismatch
Evaluation chain
```

### 7.7 Observation Analysis

Purpose:

> What did the system conclude from all usable evidence?

Required areas:

```text
Evidence coverage
Relationship evidence
Analysis limitations
Findings
Possible explanations
Traceability
```

Traceability direction:

```text
Lens / Relationship evidence
        -> Finding
        -> Hypothesis
        <- Knowledge reference
```

### 7.8 Report

Purpose:

> Present the accepted analysis in a human-readable format.

Required actions:

```text
Copy Markdown
Export
```

The screen should visually resemble a report/document more than an analytical dashboard.

## 8. Library usage guidance

### shadcn/ui / Base UI

Use for behavior/accessibility primitives:

```text
Tabs
Tooltip
Popover
Dialog
Dropdown
Select
```

Project styling remains authoritative.

### Lucide React

Use for application icons.

Do not use arbitrary mixed icon sets.

### Recharts

Use for:

```text
Metric time series
Run activity
Simple comparative/history charts
```

Do not expose the chart library API directly across feature code; wrap charts in project components.

### TanStack Table

Use only for genuinely advanced tabular screens such as future Runs listings when sorting/filtering/pagination become necessary.

## 9. Empty / partial / failed state rules

### Empty

Explain absence without implying normality.

Example:

```text
No findings were produced for this run.
```

Avoid:

```text
Everything is normal.
```

unless such a conclusion is explicitly present in the analytical result.

### Partial

Show usable evidence plus an explicit limitation.

### Failed

Show execution failure / evidence unavailable.

Never map failed execution to a red analytical-state badge.

## 10. Recommended frontend folder direction

Example only; exact repository fit may vary:

```text
src/
  app/
  components/
    ui/                 # shadcn-generated low-level primitives
    domain/
      observation/
      lens/
      analysis/
      traceability/
    charts/
  features/
    overview/
    observations/
    observation-runs/
    metrics/
    alerts/
    relationships/
    reports/
  styles/
    tokens.css
  lib/
```

Rule:

```text
components/ui
= generic primitive layer

components/domain
= ObserveAI semantic component layer

features
= screen/use-case composition
```

## 11. Implementation sequence

Recommended order:

```text
1. Foundations / tokens
2. App shell + navigation
3. Semantic badges/chips
4. Overview
5. Observation Detail
6. Observation Run Summary
7. Metric Lens Detail
8. Alert Lens Detail
9. Relationships
10. Observation Analysis
11. Report
```

The first production screen should reuse semantic primitives rather than introduce one-off styling.

## 12. Freeze rule

UI Direction v1.0 is frozen.

Implementation may make minor technical adjustments for:

```text
responsive fit
accessibility
browser behavior
real data length
```

but must not silently change:

```text
information architecture
domain terminology
analytical/execution semantics
finding/hypothesis boundary
evidence/knowledge boundary
```

A meaningful visual or semantic change requires an explicit v1.x/v2 decision rather than an incidental implementation deviation.
