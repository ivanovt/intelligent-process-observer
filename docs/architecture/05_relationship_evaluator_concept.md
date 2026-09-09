# Relationship Evaluator — концепция и детерминистична семантика

**Статус:** Работна нормативна референция за MVP  
**Версия:** 3.1

## 1. Цел

`Relationship Evaluator` проверява дали текущите semantic states на предварително определена група Lens-ове съответстват на конфигурирано qualitative expected behavior.

Той не открива dependencies и не поставя диагноза. За MVP Relationship participants могат да бъдат **само Metric Lens-ове**; Alert/Log Lens резултатите участват директно в Observation Reasoning.

```text
RelationshipDefinition
+ LensAnalysisResult[]
        ↓
Relationship Evaluator
        ↓
RelationshipEvaluation[]
```

## 2. Вход

### 2.1. Relationship definitions

Всеки Relationship съдържа:

- `id`;
- `participants` (2..N Lens IDs);
- `expected_behavior.conditions`;
- `expected_behavior.expected`.

Пример:

```yaml
relationship:
  id: pump_flow_behavior
  participants:
    - pump_speed
    - valve_position
    - flow

  expected_behavior:
    conditions:
      pump_speed:
        trend:
          direction: increasing
      valve_position:
        trend:
          direction: stable

    expected:
      flow:
        trend:
          direction: increasing
```

### 2.2. LensAnalysisResult collection

Evaluator-ът получава **целия набор** от Lens results за текущия ObservationRun, а не предварително projected participant subset.

Той сам:

1. resolve-ва `participants`;
2. проверява status/availability;
3. извлича необходимите semantic properties.

Тази отговорност не принадлежи на `Observation Orchestrator`, за да остане orchestrator-ът свободен от domain rule knowledge.

## 3. Какви данни използва

За MVP Relationship rules могат да използват само:

```text
participant.current_state.*
```

Не могат да адресират:

```text
participant.reference_periods.*
participant.history.*
raw telemetry
```

Поддържаният property набор е умишлено малък:

```text
trend.direction
trend.rate
variability.state
```

Разширение с optional semantic properties се прави изрично в бъдещ ADR.

## 4. Алгоритъм

```text
for each Relationship:
    1. resolve participant Lens results
    2. inspect required current_state properties
    3. evaluate conditions
    4. determine applicability
    5. if applicable:
           evaluate expected states
           determine state
    6. emit structured evidence
```

## 5. Applicability

Applicability отговаря на въпроса:

> „При текущото наблюдавано състояние това правило трябва ли изобщо да бъде приложено?“

```text
applicable
not_applicable
unknown
```

### applicable

Всички required conditions могат да бъдат оценени и са изпълнени.

### not_applicable

Conditions могат да бъдат оценени надеждно, но поне едно условие е ясно неизпълнено.

Това **не е** anomaly и **не е** uncertainty.

### unknown

Не може надеждно да се определи дали conditions са изпълнени, например:

- participant result липсва/failed и участва в condition;
- required descriptor липсва;
- descriptor е `unknown`.

При `not_applicable` и `unknown` expectation state не се изисква.

## 6. Evaluation state

Само при:

```text
applicability = applicable
```

се изчислява:

```text
state = consistent | inconsistent | uncertain
```

### consistent

Всички required expected properties са налични и съвпадат.

### inconsistent

Поне едно expected property е надеждно наблюдавано и категорично не съвпада с expected value.

### uncertain

Правилото е applicable, но expected side не може да бъде оценен достатъчно надеждно, например required expected participant/property е unavailable или `unknown`.

Това уточнява общото MVP правило „липсващ required participant → uncertain“: ако липсата пречи да се установи condition, `applicability=unknown`; ако conditions вече са applicable, но липсва expected evidence, `state=uncertain`.

## 7. Evidence

Резултатът трябва да съдържа достатъчно структурирано evidence, за да е ясно **как** е получена оценката.

Пример:

```yaml
relationship_evaluation:
  relationship_id: pump_flow_behavior
  applicability: applicable
  state: inconsistent

  conditions:
    - lens_id: pump_speed
      property: trend.direction
      expected: increasing
      observed: increasing
      match: true

    - lens_id: valve_position
      property: trend.direction
      expected: stable
      observed: stable
      match: true

  expectations:
    - lens_id: flow
      property: trend.direction
      expected: increasing
      observed: decreasing
      match: false
```

При not applicable:

```yaml
relationship_evaluation:
  relationship_id: pump_flow_behavior
  applicability: not_applicable
```

Точната JSON/YAML schema форма може да бъде доизчистена при implementation design, но горната семантика е нормативна.


## 7.1. Self-contained relationship identity

`RelationshipEvaluation` трябва да носи достатъчна семантична идентификация (`relationship_id`, по възможност `name`/кратко `description`) плюс evaluated expected/observed evidence. Reasoning context не трябва отделно да дублира целия `RelationshipDefinition`. Пълният rule DSL не е нужно да се копира, ако evaluation evidence показва използваните expectations.

## 7.2. Persisted evaluation order

Всеки persist-нат `RelationshipEvaluation` носи persistence-owned zero-based ordinal,
равен на позицията на Relationship-а във frozen Observation definition snapshot-а.
Ordinal-ът не е част от domain payload-а и не добавя schema version, но е required за
stable retrieval order. В един ObservationRun ordinal-ите са unique и contiguous
`0..N-1`; retrieval никога не reconstruct-ва order от UUID, timestamp, lexical ID или
текуща mutable definition.

## 8. Non-responsibilities

Relationship Evaluator не трябва да:

- fetch-ва Prometheus/Loki/alert-provider data;
- анализира raw time series;
- изчислява trend/variability;
- използва LLM;
- използва RAG;
- открива new relationships;
- променя engineer-defined relationship rule;
- определя root cause;
- генерира recommendation/report.

## 9. Downstream употреба

`Observation Reasoning Agent` получава Relationship evaluations като evidence и може да ги комбинира с:

```text
Metric/Alert/Log results
reference-period evidence
history evidence
unavailable/failed Lens information
retrieved documentation
```

и чак тогава да формира system-level findings/hypotheses.
