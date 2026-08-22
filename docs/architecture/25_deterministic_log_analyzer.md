# Component: Deterministic Log Analyzer

**Тип:** deterministic analytical component  
**Owner stage:** Logs Analysis Pipeline  
**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-19

## 1. Purpose

`Deterministic Log Analyzer` произвежда проверимо structured evidence върху вече придобитите Log Lens данни. LLM не участва в mandatory counts/rates/level statistics.

## 2. Mandatory evidence

```text
log activity
logging rate
level distribution
error-level activity
```

## 3. Supplementary evidence

```text
simple deterministic templates
reference comparisons
```

Failure на supplementary analysis може да доведе до partial result, ако mandatory current core остава usable.

## 4. Log activity

```text
record_count
logs_per_minute
```

Authoritative count следва по възможност да идва от aggregate evidence, а не от броя bounded textual records.

## 5. Level/error-level evidence

Canonical levels:

```text
error | warning | info | debug | trace | unknown
```

Derived fields:

```text
error_level_count
known_level_count
level_coverage
error_level_rate [when known_level_count > 0]
```

## 6. Template extraction

MVP използва simple deterministic normalization, например masking на IP/UUID/selected identifiers. Exact algorithm остава implementation decision, но `template_extractor` и version се пазят в provenance.

## 7. Reference comparisons

За всеки successful configured reference offset:

```text
log_count: current/reference/delta/direction
error_level_count: current/reference/delta/direction
```

`direction` = `increased|decreased|unchanged`.

## 8. Non-responsibilities

Componentът не:

- използва LLM/RAG;
- генерира findings;
- определя overall_importance;
- разширява source scope;
- прави cross-Lens analysis;
- persist-ва final result.
