# Component: AlertAnalysisResult Builder / Validator

**Тип:** deterministic component  
**Owner stage:** final analytical stage of Alerts Analysis Pipeline  
**Статус:** Accepted MVP design  
**Версия:** 2.0  
**Актуализирано:** 2026-08-13

## 1. Purpose

`AlertAnalysisResult Builder / Validator` е contract owner-ът на `AlertAnalysisResult`. Той сглобява final usable artifact от deterministic evidence и bounded agent output и налага schema/invariant validation.

## 2. Inputs

```text
LensRun identity/time metadata
normalized current alert records
deterministic evidence
successful comparisons
pipeline status/partial reason
agent output: findings + overall_importance
OR zero-record fixed output
minimal optional-tool unsuccessful trace, if any (`failed|timeout` only)
minimal provenance
```

## 3. Output

```text
validated AlertAnalysisResult
```

Само за:

```text
completed | partial
```

## 4. Responsibilities

- add `schema_version`;
- construct `identity`;
- set `lens_type=alert`;
- set `status`/structured `reason`;
- add analysis time/window;
- add minimal provenance;
- attach normalized current records;
- attach deterministic evidence;
- attach successful comparisons;
- attach findings;
- attach overall importance;
- validate cross-field invariants;
- validate `evidence_refs` resolution;
- include `optional_tool_execution` only when at least one optional call has status `failed|timeout`;
- never persist successful/not_applicable optional tool outputs as standalone analytical sections.

## 5. Non-responsibilities

Builder не:

- прави alert reasoning;
- променя agent findings;
- измисля findings;
- fetch-ва provider/reference data;
- прави severity mapping;
- persist-ва сам;
- управлява Observation lifecycle.

## 6. Zero-record behavior

При:

```text
record_count = 0
```

Builder приема fixed analytical output:

```yaml
findings: []
overall_importance: none
```

`duration_statistics` трябва да липсва.

## 7. Agent-output validation

При `record_count > 0`:

```text
overall_importance != none
```

`findings` винаги трябва да присъства като list, включително `[]`.

Всеки `evidence_ref` трябва да е resolvable към final result evidence. При finding derived от transient optional tool output, reference-ите трябва да сочат underlying persisted evidence; exact mapping policy остава Open.

## 8. Status validation

```text
completed -> no required partial reason
partial   -> primary reason required
failed    -> builder is not invoked
```

## 9. Failure semantics

Ако final contract не може да бъде валидирано произведен, няма usable analytical result. Runtime трябва да доведе LensRun до failed state и да не persist-ва invalid result.

Exact reason code за builder/schema failure може да се стандартизира при implementation design.

## 10. Persistence boundary

Builder връща validated artifact на отделна stage:

```text
Builder -> Persist AlertAnalysisResult
```

Не се фиксира `AlertRepository` abstraction в MVP architecture.

## 11. Observability / traceability

Builder трябва operationally да може да логва:

- validation error code/path;
- unresolved evidence_ref;
- invalid controlled value;
- invariant violation;
- build latency;
- serialized minimal optional-tool failure trace (`tool`, `failed|timeout`).

Тези diagnostics не се добавят автоматично в analytical result.

## 12. Related ADRs

ADR-111, ADR-116..ADR-120, ADR-131..ADR-132.

## 13. Open questions

- exact validation framework/schema technology;
- exact evidence-ref grammar и mapping за optional-derived findings;
- exact builder failure reason vocabulary.

## 14. Deferred extensions

- compatibility transforms between schema versions;
- record truncation/ranking;
- signature/hash/audit metadata.
