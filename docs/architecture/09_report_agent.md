# Report Agent — presentation contract

**Тип:** presentation/generation agent  
**Owner stage:** Report Generation Stage  
**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-08

## 1. Purpose

`Report Agent` е последният agentic/presentation component в нормалния Observation workflow. Той преобразува вече формирания `ObservationAnalysisResult` в човекочетим отчет.

След него остават само deterministic persistence/lifecycle completion действия.

## 2. Inputs

```text
ObservationAnalysisResult
minimal Observation semantic context
```

Semantic context може да съдържа observation id/name, кратко description и objective. Не се подава full technical configuration.

## 3. Не се подават

```text
LensAnalysisResult[]
RelationshipDefinition[]
raw telemetry
raw logs/alerts
full retrieved RAG context
Prometheus/Loki/alert-provider queries
execution policies
```

`knowledge_refs`, които вече са част от hypotheses, могат да се представят като references без нов retrieval.

## 4. Responsibilities

- да организира информацията в логичен инженерно четим narrative;
- да представи overall assessment;
- да представи findings;
- да представи possible explanations/hypotheses без да увеличава certainty;
- да представи analysis limitations;
- да запази traceability/reference информация, когато е налична.

## 5. Non-responsibilities

Report Agent не трябва да:

- открива нови findings;
- създава нови hypotheses;
- променя `overall_state`;
- прави нов Lens/Relationship analysis;
- използва RAG/retrieval;
- предлага recommendations за MVP;
- разширява observed data scope.

## 6. Output format

За MVP `ObservationReport` е Markdown presentation artifact с минимален envelope:

```yaml
observation_report:
  observation_id: ...
  observation_run_id: ...
  generated_at: ...
  format: markdown
  content: |
    ## Обща оценка
    ...

    ## Основни констатации
    ...

    ## Възможни обяснения
    ...

    ## Ограничения на анализа
    ...
```

Точните Markdown секции са prompt/template guidance, не сложен public schema contract.

## 7. Design rationale

`ObservationAnalysisResult` е structured analytical artifact; `ObservationReport` е presentation artifact. Това позволява в бъдеще същият analysis result да се използва за short notification, API response или различен report template без повторно reasoning.
