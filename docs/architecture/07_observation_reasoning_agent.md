# Observation Reasoning Agent — концепция и bounded knowledge reasoning

**Тип:** bounded contextual reasoning agent  
**Owner stage:** Observation Reasoning Stage  
**Статус:** Accepted MVP design  
**Версия:** 1.1  
**Актуализирано:** 2026-08-19

## 1. Purpose

`Observation Reasoning Agent` формира system-level интерпретация върху резултатите от всички usable Lens pipelines и Relationship Evaluator. Той е различна роля от Report Agent.

Основният въпрос е:

> **„Какво означават наличните структурирани резултати за текущото Observation изпълнение?“**

## 2. Inputs

```text
ObservationReasoningContext
usable_lens_results[]
relationship_evaluations[]
unavailable_lenses[]
```

### 2.1. ObservationReasoningContext

Compact semantic projection на Observation definition:

- observation id/name;
- description на наблюдавания обект;
- analytical objective;
- Lens id/type/description;
- Lens `analysis_objectives`, когато са семантично полезни.

Не включва execution/infrastructure noise: datasource queries, concurrency, timeout/retry, storage settings и др.

### 2.2. Usable Lens results

Agentът получава пълните **structured analytical results** на `completed` и `partial` Lens-ове, но не raw telemetry. Partial result носи кратка structured причина за непълната optional част.

### 2.3. Relationship evaluations

`RelationshipEvaluation` е self-contained: носи relationship identity/meaning и evaluated expected/observed evidence. Пълните relationship definitions не се дублират в reasoning context.

### 2.4. Unavailable Lens metadata

Failed/non-usable Lens-ове се представят отделно чрез `lens_id`, `type` и structured reason code. Липсващ Lens не се интерпретира като normal state.

### 2.5. Upstream Lens-local knowledge enrichment

Type-specific Lens result може да съдържа external knowledge enrichment. За MVP това се допуска при `LogAnalysisResult.knowledge_annotations`.

Тези annotations:

- не са observational evidence;
- не могат да бъдат използвани за създаване/промяна на Observation findings;
- могат да бъдат използвани при hypothesis formation като already-retrieved domain knowledge, ако original `knowledge_refs` се запазват;
- не отменят fixed max 2 direct retrieval calls на Observation Reasoning Agent, когато остава knowledge gap.

## 3. Core reasoning flow

```text
1. Inspect structured Observation evidence
2. Exclude upstream knowledge annotations from finding evidence
3. Form evidence-grounded findings
4. Freeze findings
5. Inspect available upstream knowledge annotations as knowledge-only context
6. Decide whether a finding needs additional domain knowledge
7. Optional bounded direct knowledge retrieval
8. Form 0..N grounded hypotheses
9. Determine overall_state
10. Return ObservationAnalysisResult
```

## 4. Findings boundary

Findings са заключения върху **текущото Observation evidence**:

```text
LensAnalysisResult[]
RelationshipEvaluation[]
```

Retrieved documentation и upstream Log `knowledge_annotations` не могат:

- да създават нов finding;
- да променят вече формиран finding;
- да „коригират“ наблюдаваното evidence.

Това пази границата „какво наблюдаваме“ срещу „как го обясняваме“.

## 5. Knowledge-need decision

Agentът не класифицира Observation-а като „тривиален/нетривиален“. Той решава по-конкретен въпрос:

> **„Необходимо ли е допълнително domain knowledge, за да се предложи смислена обяснителна хипотеза за конкретен finding?“**

Retrieval не е задължителен при всяко изпълнение и не се използва само за потвърждаване на очевидното evidence.

## 6. Bounded retrieval loop

RAG е **tool**, не отделен agent/stage.

```text
max_calls = 2  # fixed MVP system value
```

Conceptual loop:

```text
Findings
   ↓
Need knowledge?
   ├─ no -> hypotheses = [] or finish with evidence-only analysis
   └─ yes
        ↓
   Retrieval #1
        ↓
   sufficient?
     ├─ yes -> hypotheses
     └─ no
          ↓
     refined Retrieval #2
          ↓
     supported hypotheses or no hypothesis
```

Second retrieval може да използва:

- original finding(s);
- relevant context от Retrieval #1;
- unresolved knowledge gap.

Stop early е позволено.

## 7. Hypothesis grounding

Domain hypothesis се допуска само ако:

```text
supported_by -> one or more finding IDs
knowledge_refs -> one or more knowledge references actually used
```

`knowledge_refs` могат да идват от direct Observation retrieval или от upstream Log `knowledge_annotations`, ако provenance/reference идентификаторите са запазени.

LLM internal/general knowledge само по себе си не е достатъчно основание за domain hypothesis в MVP.

Може да има 0, 1 или повече hypotheses. Те не се rank-ват; order не означава probability/priority. Няма `primary_hypothesis`, probability или confidence.

## 8. Overall state

Agentът сам определя една от:

```text
no_significant_findings
significant_findings_present
uncertain
```

Това е overall analytical assessment, не абсолютна process classification `normal/anomalous`. `uncertain` може да съществува заедно с валидни findings, ако общата картина е непълна.

Няма отделен deterministic classifier и за MVP няма hard consistency validator между overall_state и findings count.

## 9. Limitations

Limitations остават прости и structured. MVP scope е ограничен до ясни evidence-availability ограничения, например:

```text
missing_lens_evidence
partial_lens_analysis
```

Не въвеждаме taxonomy за causal ambiguity/confidence/disambiguation.

## 10. Non-responsibilities

Agentът не трябва да:

- променя observational scope;
- fetch-ва нови process variables извън Observation;
- редактира Lens results;
- преизчислява deterministic Relationship rules;
- използва RAG за findings;
- генерира recommendations/confidence/severity/root cause classification за MVP;
- връща само narrative report.

## 11. Output

Structured `ObservationAnalysisResult`, описан в `08_observation_analysis_result_contract.md`.

## 12. Related ADRs

ADR-050..052, ADR-064..084 (v3 register).
