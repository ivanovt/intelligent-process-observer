# Log analytical tools и knowledge retrieval

**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-19

## 1. Analytical tool model

Log Agent има малък bounded registry от deterministic analytical tools. Те работят само върху вече придобитите current/reference data/evidence.

```text
max_optional_tool_calls = 3
max_calls_per_tool = 1
```

## 2. Bucketed Log Rate Analysis

Разделя current window на bounded времеви buckets и може да изчислява:

```text
min bucket count
max bucket count
mean bucket count
peak_to_mean_ratio
optional z-score when statistically applicable
```

Z-score не е самостоятелна anomaly classification.

## 3. Template Reference Difference Analysis

Сравнява current observed template evidence с available reference template evidence. При bounded content резултатът трябва да използва формулировка „observed/not observed in available evidence“, а не абсолютна novelty claim.

## 4. Error-Level Template Concentration Analysis

Изчислява концентрацията на observed error-level records около dominant template, например:

```text
top_error_template_share =
  observed_error_records_for_top_template /
  observed_error_records_in_analyzed_content
```

Tool-ът връща numerical evidence, без categorical anomaly label.

## 5. Tool failure semantics

```text
success        -> usable transient evidence
not_applicable -> normal outcome
failed         -> non-fatal
 timeout       -> non-fatal
```

Optional tool failure не прави LensRun partial/failed сам по себе си.

## 6. Knowledge retrieval е отделна capability

Knowledge retrieval не е analytical tool. Analytical tools извличат ново evidence от вече наличните данни; retrieval извлича external domain knowledge за интерпретация на вече наблюдавано evidence.

```text
max_log_knowledge_retrieval_calls = 2
```

## 7. Retrieval grounding

Query трябва да е anchored към frozen Log finding(s) и конкретен knowledge subject, например template/error code/component message.

Second retrieval може да използва:

```text
original finding(s)
useful context from retrieval #1
remaining knowledge gap
```

## 8. Retrieval output semantics

Retrieved knowledge може да доведе до `knowledge_annotations`, но не до нови/редактирани Log findings.

Annotation изисква:

```text
supported_by -> Log finding IDs
knowledge_refs -> actually used source refs
```

## 9. Downstream reuse

Observation Reasoning може да използва upstream Log `knowledge_annotations` само като knowledge layer за system-level hypotheses. Те не могат да служат като Observation finding evidence.
