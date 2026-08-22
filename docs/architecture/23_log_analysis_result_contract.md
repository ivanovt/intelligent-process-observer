# Contract: LogAnalysisResult

**Status:** Accepted MVP working contract  
**Schema version:** 1.0  
**Owner producer:** LogAnalysisResult Builder / Validator  
**Primary consumers:** Observation Reasoning Agent, persistence/reporting infrastructure  
**Актуализирано:** 2026-08-19

## 1. Purpose

`LogAnalysisResult` е versioned structured analytical artifact за `completed|partial` Log LensRun. Той не съдържа целия raw/normalized log corpus.

## 2. Semantic guarantees

- result exists only for `completed|partial`;
- current observational evidence е отделено от knowledge enrichment;
- reference evidence е compact и offset-addressable;
- template evidence може да бъде bounded/sample-derived и трябва да носи coverage semantics;
- `knowledge_annotations` не са observational evidence.

## 3. Conceptual structure

```yaml
log_analysis_result:
  schema_version: "1.0"

  identity:
    observation_id: ...
    observation_run_id: ...
    lens_id: ...
    lens_run_id: ...

  lens_type: log
  status: completed
  reason: ...                  # partial only

  analysis_window:
    start: ...
    end: ...

  provenance:
    source: loki
    template_extractor: simple_template_extractor
    template_extractor_version: "1.0"

  log_activity:
    record_count: 1240
    logs_per_minute: 20.67

  level_distribution:
    error: 28
    warning: 47
    info: 1035
    debug: 40
    trace: 0
    unknown: 90

  error_level_activity:
    error_level_count: 28
    known_level_count: 1150
    level_coverage: 0.927
    error_level_rate: 0.0243

  templates:                  # optional/supplementary
    content_scope: bounded
    top_overall: []
    top_error_level: []

  comparisons:                # 0..N successful references
    - offset: 1d
      log_count:
        current: 1240
        reference: 820
        delta: 420
        direction: increased
      error_level_count:
        current: 28
        reference: 4
        delta: 24
        direction: increased

  findings: []
  overall_importance: high    # absent when agent unavailable

  knowledge_annotations:      # optional; RAG-derived, non-observational
    - id: log_knowledge_1
      subject:
        template_id: tmpl_17
      statement: ...
      supported_by:
        - log_finding_2
      knowledge_refs:
        - source_id: ...
          reference: ...
```

## 4. Controlled vocabularies

```text
status:
  completed | partial

level:
  error | warning | info | debug | trace | unknown

comparison.direction:
  increased | decreased | unchanged

overall_importance:
  none | low | moderate | high | critical
```

## 5. Core invariants

```text
record_count >= 0
sum(level_distribution values) should equal record_count when the distribution covers the same authoritative population
known_level_count = record_count - level_distribution.unknown
0 <= level_coverage <= 1
0 <= error_level_rate <= 1 when present
```

Когато level evidence се базира на различен bounded population от authoritative aggregate count, provenance/coverage metadata трябва да показва това; exact schema остава Open.

## 6. Template evidence

Template evidence е supplementary. При bounded content не се представя като абсолютен corpus-wide count без explicit evidence, че extraction е върху целия population.

## 7. Findings

Findings са Lens-local observational conclusions и трябва да бъдат grounded само в Log Lens evidence чрез `evidence_refs`.

RAG knowledge не може да е source на finding.

## 8. Knowledge annotations

`knowledge_annotations`:

- са optional;
- възникват само след findings;
- трябва да се свързват с един или повече findings чрез `supported_by`;
- трябва да носят `knowledge_refs` към действително използвания retrieved source;
- не могат да се използват downstream като observational evidence за Observation findings;
- могат да бъдат re-used като knowledge grounding за Observation hypotheses при запазена provenance.

## 9. Partial reasons

Примерен малък vocabulary:

```text
reference_unavailable
bounded_content_unavailable
invalid_records
parsing_degraded
template_analysis_failed
agent_unavailable
```

Exact precedence при multiple simultaneous reasons остава Open.

## 10. Failed execution

При failed Log LensRun **не се създава `LogAnalysisResult`**. Failure metadata остава в LensRun/operational telemetry.

## 11. Explicitly excluded

```text
full raw log corpus
full normalized corpus
raw reference logs
LLM chain-of-thought
system-level root cause
recommendations
confidence/probability
```
