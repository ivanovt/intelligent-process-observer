# Component: LogAnalysisResult Builder / Validator

**Тип:** deterministic result-contract component  
**Owner stage:** Logs Analysis Pipeline  
**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-19

## 1. Purpose

Builder/Validator е final analytical contract owner на `LogAnalysisResult`.

## 2. Inputs

```text
LensRun metadata
current deterministic evidence
reference comparisons
template evidence/coverage metadata
agent findings + overall_importance
knowledge annotations
partial reasons
provenance
```

## 3. Responsibilities

- сглобява common result envelope;
- валидира required fields/controlled vocabularies;
- проверява count/rate invariants;
- валидира `evidence_refs`;
- валидира `supported_by`/`knowledge_refs` за knowledge annotations;
- пази separation между observational findings и knowledge enrichment;
- определя `completed|partial`;
- отказва invalid result.

## 4. Key invariants

```text
failed Log LensRun -> NO LogAnalysisResult
completed|partial  -> valid LogAnalysisResult
knowledge_annotation -> >=1 supported_by + >=1 knowledge_ref
knowledge_annotations cannot be evidence_refs for Log findings
```

## 5. Failure semantics

Builder validation failure, когато не може да бъде произведен валиден result contract, води до failed Log LensRun и липса на type-specific result artifact.

## 6. Non-responsibilities

Builder-ът не:

- query-ва Loki;
- извиква LLM/RAG;
- генерира findings/annotations;
- persist-ва сам result-а.
