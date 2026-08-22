# Component / Agent: Log Analysis Agent

**Тип:** bounded analytical agent  
**Owner stage:** Logs Analysis Pipeline  
**Статус:** Accepted MVP design  
**Версия:** 1.0  
**Актуализирано:** 2026-08-19

## 1. Purpose

`Log Analysis Agent` интерпретира structured Log Lens evidence и формира Lens-local findings. При необходимост може да използва bounded deterministic analytical tools и bounded knowledge retrieval за семантично обогатяване на вече наблюдавани templates/error codes/messages.

## 2. Inputs

```text
compact Log Lens semantic context
current deterministic evidence
available reference comparisons
bounded template evidence
coverage/partial metadata
```

Agentът не получава целия raw/normalized log corpus.

## 3. Outputs

```text
findings[]
overall_importance
knowledge_annotations[] [optional]
```

## 4. Responsibilities

- да интерпретира activity/rate/level evidence;
- да разглежда reference differences;
- да анализира bounded template evidence;
- да избира 0..3 optional analytical tools;
- да формира evidence-grounded Lens-local findings;
- да freeze-не findings преди knowledge retrieval;
- при нужда да изпълни 0..2 knowledge retrieval calls;
- да формира knowledge annotations, grounded към findings + knowledge refs.

## 5. Non-responsibilities

Agentът не:

- променя selector/time/reference scope;
- fetch-ва нови logs извън фиксирания scope;
- извлича metrics или alerts;
- анализира Relationships;
- прави system-level diagnosis/root-cause selection;
- генерира recommendations;
- създава final `LogAnalysisResult`.

## 6. Allowed analytical tools

```text
Bucketed Log Rate Analysis
Template Reference Difference Analysis
Error-Level Template Concentration Analysis
```

Budget:

```text
max_optional_tool_calls = 3
max_calls_per_tool = 1
```

## 7. Knowledge retrieval capability

Conceptual capability:

```text
retrieve_log_knowledge(query, subjects/findings, scope)
```

Purpose:

> Да намери domain documentation/knowledge за конкретно вече наблюдавано log evidence.

Допустими subjects:

```text
template
error code
component-specific message
log terminology
```

Budget:

```text
max_knowledge_retrieval_calls = 2
```

Second query може да refine-не first query, но трябва да остане anchored към frozen Log finding(s).

## 8. Findings boundary

Findings се формират **преди retrieval** и се базират само на Log Lens evidence.

Retrieved knowledge не може:

- да създава finding;
- да променя finding statement;
- да увеличава observational certainty.

## 9. Knowledge annotations

Knowledge annotation е Lens-local explanation/semantic note върху вече наблюдаван finding.

Required traceability:

```text
supported_by -> Log finding IDs
knowledge_refs -> retrieved source references actually used
```

Annotation не е root-cause conclusion и не е observational finding.

## 10. Untrusted log text

Agent prompt/runtime трябва да третира template/message/labels като untrusted data. Text content не може да променя system instructions или tool policies.

## 11. Zero-log behavior

При `record_count=0` agentът се пропуска, когато наличното reference evidence също не показва activity. Ако references показват предходна activity, agentът може да формира Lens-local finding за difference-а без causal explanation.

## 12. Failure semantics

```text
optional analytical tool failed/timeout -> continue
knowledge retrieval failed/timeout      -> continue with fewer/no annotations
agent failed/timeout + deterministic core usable -> Log LensRun partial
```

## 13. Observability

Operational telemetry следва да проследява поне:

```text
agent invocation
analytical tool calls + status
knowledge retrieval calls + status
budget usage
agent timeout/failure
```

Successful internal reasoning trace/chain-of-thought не се persist-ва като public artifact.
