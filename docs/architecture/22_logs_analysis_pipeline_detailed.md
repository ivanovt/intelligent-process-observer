# Logs Analysis Pipeline — подробен runtime дизайн

**Статус:** Accepted MVP working design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-19

## 1. Purpose

Документът описва runtime decomposition на `Logs Analysis Pipeline` за един `Log LensRun`.

## 2. Pipeline flow

```text
Log LensRun
  -> resolve immutable execution context
  -> Log Provider Adapter
       -> aggregate current evidence
       -> bounded current log content
       -> configured reference evidence/content
  -> parse / normalize / validate / sanitize
  -> Deterministic Log Analyzer
       -> activity/rate
       -> level/error-level evidence
       -> supplementary template evidence
       -> reference comparisons
  -> zero-log / agent invocation gate
  -> Log Analysis Agent when needed
       <-> optional analytical tools (max 3; each tool max once)
       <-> optional log knowledge retrieval (max 2; after findings)
  -> LogAnalysisResult Builder / Validator
  -> persistence
```

## 3. Immutable execution context

Преди data acquisition се фиксират поне:

```text
observation_id / observation_run_id
lens_id / lens_run_id
provider/source
selector
analysis window
configured reference offsets
parsing configuration
execution/tool budgets
```

Нито agentът, нито optional tools могат да променят тези стойности.

## 4. Acquisition

Provider adapter логически разделя:

```text
aggregate evidence acquisition
bounded textual content acquisition
```

Current и reference acquisitions са независими спрямо time window-а, но използват един и същ Lens scope.

## 5. Preparation

За LLM-visible textual content pipeline-ът изпълнява:

```text
parse -> normalize -> validate -> sanitize/redact
```

Invalid textual records могат да бъдат пропуснати, ако aggregate/current core evidence остава usable. Generic deduplication не се извършва.

## 6. Deterministic core

Mandatory current analytical core:

```text
log_activity.record_count
log_activity.logs_per_minute
level_distribution
error_level_activity.error_level_count
error_level_activity.known_level_count
error_level_activity.level_coverage
error_level_activity.error_level_rate [when definable]
```

Supplementary evidence:

```text
templates
reference comparisons
```

## 7. Template handling

Template extraction работи върху bounded content. Result projection може да съдържа `top_overall` и `top_error_level`. Ако content не представлява целия corpus, result-ът маркира coverage semantics като bounded/sample-derived.

## 8. Reference periods

За всеки configured offset се опитва independent reference analysis. MVP core comparisons:

```text
log_count
error_level_count
```

Unavailable reference -> partial, ако current core е usable.

## 9. Agent invocation gate

Agentът по принцип се извиква при usable non-trivial evidence. Специален zero-log fast path:

```text
current record_count = 0
AND available references also show 0 activity
-> skip agent
-> findings=[]
-> overall_importance=none
```

Ако reference evidence показва предходна activity, agentът се извиква.

## 10. Log Analysis Agent

Agentът работи върху compact structured analytical context + bounded template texts. Той може да използва optional analytical tools и bounded knowledge retrieval, но observational data scope остава immutable.

## 11. Knowledge retrieval order

Knowledge retrieval се допуска **само след формиране и freeze на Log findings**.

```text
Log findings
  -> need domain knowledge?
      -> no: finish
      -> yes: retrieval #1
          -> sufficient? yes: knowledge annotation
          -> no: optional refined retrieval #2
```

Retrieved knowledge не може да създава/редактира finding.

## 12. Result build

Builder/Validator комбинира:

```text
LensRun metadata
current deterministic evidence
supplementary evidence
successful reference comparisons
agent findings/overall_importance
knowledge annotations
partial reasons
provenance
```

и произвежда валиден `LogAnalysisResult` само при `completed|partial`.

## 13. Failure matrix

```text
current provider acquisition failed/timeout
-> failed LensRun; no LogAnalysisResult

minimal current core unavailable
-> failed LensRun; no LogAnalysisResult

reference unavailable
-> partial result

template analysis unavailable
-> partial result when current core usable

optional analytical tool failed/timeout
-> non-fatal; continue

knowledge retrieval failed/timeout
-> non-fatal knowledge-enrichment failure; continue without/with fewer annotations

Log Analysis Agent failed/timeout
-> partial result when current deterministic core usable

Builder validation failed
-> failed LensRun; no LogAnalysisResult
```

## 14. Persistence

Persist-ват се `completed|partial LogAnalysisResult` и runtime metadata. Failed LensRun няма type-specific result artifact.
