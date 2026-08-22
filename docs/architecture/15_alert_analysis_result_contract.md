# Contract: AlertAnalysisResult

**Status:** Accepted MVP working contract  
**Schema version:** 1.0  
**Owner producer:** `AlertAnalysisResult Builder / Validator`  
**Primary consumers:** Observation workflow persistence; `Observation Reasoning Agent` through `usable_lens_results`  
**Актуализирано:** 2026-08-13

## 1. Purpose

`AlertAnalysisResult` е machine-readable analytical artifact за успешно или partial изпълнение на `Alert LensRun`.

Той съдържа:

- common Lens execution identity;
- current normalized alert records;
- deterministic current evidence;
- successful reference comparisons;
- Lens-local findings;
- overall Lens importance;
- minimal provenance;
- minimal optional-tool failure trace only when an optional tool call actually fails or times out.

При `failed` Alert LensRun **не се създава** `AlertAnalysisResult`.

## 2. Semantic guarantees

1. Result съществува само ако е usable (`completed|partial`).
2. Current records са normalized/validated; raw provider payload не се включва.
3. Reference raw records не се включват.
4. Numeric/count/duration evidence е deterministic.
5. `findings` са Lens-local и evidence-grounded.
6. `overall_importance=none` означава надеждно установен `record_count=0`.
7. `evidence_refs` сочат само към evidence в същия result.
8. Missing optional section означава „няма налично/приложимо evidence“, не автоматично failure.
9. Successful optional analytical tool outputs са transient evidence за Alert Analysis Agent и не се сериализират като самостоятелни analytical sections.
10. `optional_tool_execution` се сериализира само ако има поне един optional call със status `failed|timeout`; `not_applicable` не се включва като неуспех.

## 3. Required top-level fields

За `completed` и `partial`:

```text
schema_version
identity
lens_type
status
analysis_timestamp
analysis_window
provenance
alerts
alert_activity
status_distribution
findings
overall_importance
```

`reason` е required при `partial` и absent при `completed`. `optional_tool_execution` е optional и се включва само при реални optional `failed|timeout` calls.

## 4. Identity

```yaml
identity:
  observation_id: ...
  observation_run_id: ...
  lens_id: ...
  lens_run_id: ...
```

Не се дублира `lens_name`; semantic name/description се resolve-ват от Lens/Observation context.

## 5. Lifecycle fields

```yaml
lens_type: alert
status: completed        # completed | partial
```

При partial:

```yaml
status: partial
reason:
  code: reference_unavailable
  component: reference_period_analysis   # optional
```

Само една primary reason се сериализира.

## 6. Temporal context

```yaml
analysis_timestamp: "2026-08-09T10:00:00Z"
analysis_window:
  start: "2026-08-09T09:00:00Z"
  end: "2026-08-09T10:00:00Z"
```

`analysis_timestamp` е semantic anchor за active duration и reproducibility.

## 7. Provenance

Минимално:

```yaml
provenance:
  source_provider: jira_track_and_release
  generated_at: "2026-08-09T10:00:03Z"
```

`generated_at` не е същото като `analysis_timestamp`.

## 8. Current alert records

```yaml
alerts:
  - id: "ALERT-1234"
    title: "Database connection saturation"
    description: "..."                  # optional

    started_at: "2026-08-09T07:46:00Z"
    ended_at: null
    duration_seconds: 8040

    status:
      normalized: active
      source: "In Progress"

    provider_importance:                 # optional
      type: priority
      value: "Highest"

    occurrence_count: 7                  # optional source field
    source_ref: "..."                    # optional
```

### Validation

- `id` required;
- `title` required;
- `started_at` required and valid;
- `ended_at` nullable;
- if present: `ended_at >= started_at`;
- `duration_seconds >= 0`;
- raw provider payload forbidden.

## 9. Alert activity

```yaml
alert_activity:
  record_count: 3
  occurrence_count: 21
```

Rules:

```text
record_count = len(alerts)
occurrence_count = sum(record.occurrence_count if present else 1)
```

## 10. Status distribution

```yaml
status_distribution:
  active: 2
  resolved: 1
  unknown: 0
```

Invariant:

```text
active + resolved + unknown = record_count
```

Counts са по records, не по occurrences.

## 11. Duration statistics

При `record_count > 0`:

```yaml
duration_statistics:
  min_seconds: 120
  max_seconds: 8040
  average_seconds: 2360.5
```

При `record_count = 0` section-ът липсва.

## 12. Provider importance distribution

Optional; включва се само ако поне един record има `provider_importance`.

Пример:

```yaml
provider_importance_distribution:
  type: priority
  values:
    Highest: 2
    High: 1
```

Не се прави provider-independent mapping.

## 13. Reference comparisons

```yaml
comparisons:
  - offset: 1d
    occurrence_comparison:
      current: 21
      reference: 8
      delta: 13
      direction: increased

  - offset: 7d
    occurrence_comparison:
      current: 21
      reference: 21
      delta: 0
      direction: unchanged
```

Rules:

```text
direction = increased | decreased | unchanged
```

Само successful reference comparisons се включват. Unavailable reference period не създава placeholder.

Concrete reference `start/end` не се сериализират в comparison-а за MVP.

## 14. Optional tool execution trace

Successful optional tool results не се persist-ват в `AlertAnalysisResult`; те се използват само за agent reasoning и формиране на findings.

Ако един или повече optional tool calls приключат с `failed` или `timeout`, Builder може да включи минимален trace:

```yaml
optional_tool_execution:
  unsuccessful_calls:
    - tool: duration_outlier_analysis
      status: timeout
    - tool: recurrence_concentration_analysis
      status: failed
```

Rules:

```text
serialized statuses: failed | timeout
success -> не се сериализира тук
not_applicable -> не се сериализира тук
section absent -> няма failed/timeout optional call
```

Detailed exceptions, retries, request/response payloads и stack traces остават само в operational logs.

## 15. Findings

`findings` е required за `completed` и `partial`, включително когато е празен:

```yaml
findings: []
```

или:

```yaml
findings:
  - id: af_1
    statement: >
      Current alert occurrence activity is higher than the configured 1d reference.
    evidence_refs:
      - comparisons.1d.occurrence_comparison
```

Minimal finding fields:

```text
id
statement
evidence_refs[]
```

No required:

```text
type
category
severity
confidence
```

## 16. evidence_refs

Semantic invariant:

> Всеки `evidence_ref` трябва да resolve-ва към реален елемент в същия `AlertAnalysisResult`.

Примерни conceptual paths:

```text
alerts.ALERT-1234
duration_statistics.max_seconds
alert_activity.occurrence_count
comparisons.1d.occurrence_comparison
```

Exact serialized path/URI grammar остава Open. При finding, derived от transient optional tool analysis, `evidence_refs` трябва да сочат underlying persisted records/aggregates/comparisons; exact mapping policy остава Open.

## 17. Overall importance

```yaml
overall_importance: high
```

Vocabulary:

```text
none | low | moderate | high | critical
```

Hard invariant:

```text
record_count = 0 -> overall_importance = none
record_count > 0 -> overall_importance != none
```

Няма `rationale` field.

## 18. Completed example

```yaml
alert_analysis_result:
  schema_version: "1.0"

  identity:
    observation_id: db_health
    observation_run_id: obsrun_20260809_1000
    lens_id: database_alerts
    lens_run_id: lensrun_alerts_01

  lens_type: alert
  status: completed

  analysis_timestamp: "2026-08-09T10:00:00Z"
  analysis_window:
    start: "2026-08-09T09:00:00Z"
    end: "2026-08-09T10:00:00Z"

  provenance:
    source_provider: jira_track_and_release
    generated_at: "2026-08-09T10:00:03Z"

  alerts:
    - id: ALERT-1234
      title: "Database connection saturation"
      started_at: "2026-08-09T07:46:00Z"
      ended_at: null
      duration_seconds: 8040
      status:
        normalized: active
        source: "In Progress"
      provider_importance:
        type: priority
        value: "Highest"
      occurrence_count: 7

    - id: ALERT-1300
      title: "Connection pool warning"
      started_at: "2026-08-09T09:15:00Z"
      ended_at: "2026-08-09T09:25:00Z"
      duration_seconds: 600
      status:
        normalized: resolved
        source: "Done"
      occurrence_count: 2

  alert_activity:
    record_count: 2
    occurrence_count: 9

  status_distribution:
    active: 1
    resolved: 1
    unknown: 0

  duration_statistics:
    min_seconds: 600
    max_seconds: 8040
    average_seconds: 4320

  provider_importance_distribution:
    type: priority
    values:
      Highest: 1

  comparisons:
    - offset: 1d
      occurrence_comparison:
        current: 9
        reference: 3
        delta: 6
        direction: increased

  findings:
    - id: af_1
      statement: >
        Current alert occurrence activity is higher than the 1d reference period.
      evidence_refs:
        - comparisons.1d.occurrence_comparison

    - id: af_2
      statement: >
        ALERT-1234 remains active and has the longest current lifecycle duration.
      evidence_refs:
        - alerts.ALERT-1234
        - duration_statistics.max_seconds

  overall_importance: high
```

## 19. Zero-record example

```yaml
alert_analysis_result:
  schema_version: "1.0"

  identity:
    observation_id: db_health
    observation_run_id: obsrun_20260809_1000
    lens_id: database_alerts
    lens_run_id: lensrun_alerts_01

  lens_type: alert
  status: completed

  analysis_timestamp: "2026-08-09T10:00:00Z"
  analysis_window:
    start: "2026-08-09T09:00:00Z"
    end: "2026-08-09T10:00:00Z"

  provenance:
    source_provider: jira_track_and_release
    generated_at: "2026-08-09T10:00:02Z"

  alerts: []

  alert_activity:
    record_count: 0
    occurrence_count: 0

  status_distribution:
    active: 0
    resolved: 0
    unknown: 0

  comparisons:
    - offset: 1d
      occurrence_comparison:
        current: 0
        reference: 5
        delta: -5
        direction: decreased

  findings: []
  overall_importance: none
```

`duration_statistics` липсва.

## 20. Partial example

```yaml
alert_analysis_result:
  schema_version: "1.0"
  identity:
    observation_id: db_health
    observation_run_id: obsrun_20260809_1000
    lens_id: database_alerts
    lens_run_id: lensrun_alerts_01

  lens_type: alert
  status: partial
  reason:
    code: reference_unavailable
    component: reference_period_analysis

  analysis_timestamp: "2026-08-09T10:00:00Z"
  analysis_window:
    start: "2026-08-09T09:00:00Z"
    end: "2026-08-09T10:00:00Z"

  provenance:
    source_provider: jira_track_and_release
    generated_at: "2026-08-09T10:00:03Z"

  alerts: []
  alert_activity:
    record_count: 0
    occurrence_count: 0
  status_distribution:
    active: 0
    resolved: 0
    unknown: 0

  comparisons: []
  findings: []
  overall_importance: none
```

## 21. Failure / missing-data semantics

При failed Alert LensRun няма result document от този schema type.

Пример runtime state:

```yaml
lens_run:
  status: failed
  reason:
    code: agent_timeout
```

`Observation Reasoning Agent` го вижда като unavailable Lens metadata, не като empty AlertAnalysisResult.

## 22. Validation rules summary

Builder трябва най-малко да валидира:

```text
identity completeness
lens_type == alert
status in {completed, partial}
partial => reason present
completed => no partial reason required
record_count == len(alerts)
status_distribution sum == record_count
duration stats absent when record_count == 0
overall_importance invariant
all evidence_refs resolvable
optional_tool_execution absent OR contains only failed|timeout statuses
all durations non-negative
all alert lifecycle timestamps valid
comparison direction consistent with current/reference values
```

## 23. Backward compatibility / versioning

`schema_version` е mandatory. Breaking contract change трябва да увеличи major version или да използва explicit compatibility policy.

## 24. Related ADRs

ADR-095..ADR-132 в `03_ADR_log.md`.

## 25. Open questions

- exact `evidence_refs` grammar и mapping за findings derived от transient optional tool analysis;
- exact serialization на duration numeric type/precision;
- exact primary reason precedence при multiple partial causes;
- scalability/truncation policy beyond MVP.
