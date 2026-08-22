# Component: Log Provider Adapter

**Тип:** deterministic integration component  
**Owner stage:** Logs Analysis Pipeline  
**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Current provider:** Loki  
**Актуализирано:** 2026-08-19

## 1. Purpose

`Log Provider Adapter` изолира provider-specific API/query/field semantics от source-agnostic Logs pipeline-а.

## 2. Scope/time boundary

```text
Log Lens selector -> which logs
LensRun window    -> when
```

Adapter-ът изпълнява provider-specific query така, че да спази общата time semantics.

## 3. Acquisition modes

Adapter boundary поддържа логически два типа extraction:

```text
aggregate evidence
bounded textual content
```

Това избягва архитектурното предположение, че целият corpus трябва да бъде transfer-нат към pipeline-а.

## 4. Parsing ownership

Provider adapter/configuration трябва да предостави достатъчно information за deterministic extraction на canonical fields като timestamp/message/level. Exact parser schema остава Open.

LLM не infer-ва provider field mapping.

## 5. Reference acquisition

Всеки configured reference offset използва същия Lens selector и equal-duration shifted window. Current/reference acquisitions са независими.

## 6. Bounded-content semantics

Adapter-ът може да върне ограничено количество textual content за template analysis. Limit/sampling strategy трябва да е traceable чрез metadata, когато evidence не покрива целия population.

## 7. Failure semantics

```text
current authoritative acquisition failed/timeout -> failed LensRun path
reference acquisition failed                    -> partial candidate
bounded content unavailable                     -> partial candidate if core aggregate evidence usable
```

## 8. Non-responsibilities

Adapter-ът не:

- генерира findings;
- избира LLM tools;
- прави RAG;
- извършва system diagnosis;
- променя Lens selector по собствена инициатива.
