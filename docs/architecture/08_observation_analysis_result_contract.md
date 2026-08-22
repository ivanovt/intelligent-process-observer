# ObservationAnalysisResult — минимален contract за MVP

**Статус:** Accepted MVP working contract  
**Версия:** 1.1  
**Актуализирано:** 2026-08-19

## 1. Purpose

`ObservationAnalysisResult` е **machine-readable analytical artifact** между Observation Reasoning Agent и Report Agent. Той не е финалният човекочетим отчет.

## 2. Minimal structure

```yaml
observation_analysis_result:
  schema_version: "1.0"

  identity:
    observation_id: ...
    observation_run_id: ...

  overall_state: significant_findings_present

  findings:
    - id: finding_1
      statement: >
        ...
      evidence_refs:
        - ...

  hypotheses:
    - id: hypothesis_1
      statement: >
        ...
      supported_by:
        - finding_1
      knowledge_refs:        # optional; required when hypothesis uses retrieved knowledge
        - source_id: ...
          reference: ...

  limitations:
    - code: missing_lens_evidence
      lens_id: ...
```

## 3. overall_state

```text
no_significant_findings
significant_findings_present
uncertain
```

Семантика:

- `no_significant_findings` — наличното evidence не е довело до значими findings;
- `significant_findings_present` — има значими findings, заслужаващи внимание;
- `uncertain` — наличното evidence не позволява надеждна обща оценка.

Това не е абсолютна `normal/anomalous` classification. `uncertain` може да съществува с 0..N findings.

За MVP не се налагат допълнителни hard schema invariants между `overall_state` и броя findings.

## 4. findings

Минималният finding contract е:

```yaml
- id: finding_1
  statement: ...
  evidence_refs:
    - ...
```

Няма задължителни `type`, `category`, `severity`, `confidence` или taxonomy.

Findings трябва да бъдат grounded **само** в Observation evidence. RAG knowledge не е finding source.

## 5. hypotheses

```yaml
- id: hypothesis_1
  statement: ...
  supported_by:
    - finding_1
  knowledge_refs:
    - source_id: ...
      reference: ...
```

Правила:

- `supported_by` свързва hypothesis с текущите findings;
- `knowledge_refs` свързва hypothesis с external knowledge, действително използвано при explanation; reference може да идва от direct Observation retrieval или от upstream Lens-local knowledge annotation с запазена provenance;
- може да има `0..N` hypotheses;
- няма ranking, probability, primary hypothesis или confidence;
- domain hypothesis не се генерира само от internal LLM knowledge;
- upstream Lens-local knowledge annotations не могат да бъдат source за Observation finding, но могат да предоставят knowledge refs за hypothesis.

## 6. limitations

Structured, intentionally small model. Примери:

```yaml
limitations:
  - code: missing_lens_evidence
    lens_id: system_logs

  - code: partial_lens_analysis
    lens_id: outlet_pressure
    component: oscillation_analysis
```

Не въвеждаме свободен текст като основен limitation contract и не добавяме сложна analytical-uncertainty taxonomy за MVP.

## 7. Explicitly excluded from MVP

```text
finding.type
finding.category
severity
confidence
recommendations
root_cause
probability
hypothesis ranking
primary_hypothesis
complex analytical-limitation taxonomy
```

## 8. Traceability chain

```text
Lens / Relationship observational evidence
        ↓
Finding
        ↓
+ direct retrieved knowledge and/or upstream Lens-local knowledge refs
        ↓
Hypothesis
```

`evidence_refs`, `supported_by` и `knowledge_refs` са трите основни traceability връзки.
