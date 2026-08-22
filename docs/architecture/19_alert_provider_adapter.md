# Component: Alert Provider Adapter

**Тип:** deterministic integration component  
**Owner stage:** Alerts Analysis Pipeline data acquisition/normalization boundary  
**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-13

## 1. Purpose

`Alert Provider Adapter` изолира Alerts Analysis Pipeline от provider-specific APIs, query syntax и field naming. Analytical components трябва да работят върху canonical alert representation, а не върху Jira-specific payload.

## 2. Current provider

MVP:

```text
Jira Track and Release
```

Дизайнът допуска бъдещи adapters без промяна на `Deterministic Alert Analyzer` и `Alert Analysis Agent`.

## 3. Inputs

```text
provider identity/config
provider-native selector/query
analysis/reference time window
```

## 4. Outputs

Provider records/canonical-mappable records, достатъчни за normalization към:

```text
id
title
description?
started_at
ended_at?
status.source
provider_importance?
occurrence_count?
source_ref?
```

## 5. Responsibilities

- provider authentication/access boundary;
- execution на provider-native selector;
- apply/realize common lifecycle-overlap time semantics;
- map provider-specific lifecycle/status fields;
- preserve provider importance without global mapping;
- preserve source reference where useful;
- expose provider error/timeout outcome to pipeline.

## 6. Non-responsibilities

Не:

- определя Lens semantic scope извън query;
- променя query по LLM/heuristic логика;
- филтрира lifecycle status като analytical shortcut;
- изчислява findings/importance;
- прави reference comparisons;
- използва RAG/LLM.

## 7. Query boundary

Provider-native query определя **which alerts**.

`LensRun.analysis_window` определя **when**.

Provider adapter трябва да спази:

```text
started_at < window.end
AND
(ended_at is null OR ended_at > window.start)
```

дори ако конкретният provider изисква по-различна API query construction техника.

## 8. Status filtering rule

Lifecycle status е analytical field и не трябва да бъде intentional selector restriction за MVP.

Тъй като provider query е opaque/native:

- няма автоматична validation/rewrite;
- инженерът носи отговорност да не добавя lifecycle status predicate.

## 9. Normalization boundary

Архитектурно:

- Adapter owns provider-specific mapping knowledge;
- pipeline normalization/validation stage owns canonical validity policy.

Така adapter може да бъде заменен, без да се променят analytical invariants.

## 10. Failure semantics

Current query:

```text
error   -> current_query_failed
 timeout -> current_query_timeout
```

Reference query:

```text
error/timeout -> reference_unavailable (partial path)
```

Operational diagnostics остават извън `AlertAnalysisResult`.

## 11. Related ADRs

ADR-089..ADR-096.

## 12. Open questions

- exact Jira API endpoint/query form;
- exact field mapping;
- adapter interface methods;
- retry/backoff/timeouts;
- authentication/secret handling.

## 13. Deferred extensions

- automatic query linting/rewriting;
- multi-provider aggregation inside one LensRun;
- point-in-time historical state reconstruction.
