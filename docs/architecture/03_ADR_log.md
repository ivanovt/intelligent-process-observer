# Architecture Decision Records (ADR) — регистър на приетите решения

**Проект:** „Интелигентна мулти-агентна система за откриване на аномалии и супервизия на технологични процеси“  
**Статус на записите:** Accepted, освен ако изрично не е посочено друго  
**Версия на регистъра:** 6.2

---

## Формат

Всеки ADR съдържа:

- **Context** — проблемът/решението, което е трябвало да бъде взето;
- **Decision** — приетото архитектурно решение;
- **Consequences** — основните последствия и trade-offs.

---

## ADR-001 — Observation е контейнер за множество Lens-ове

**Status:** Accepted

**Context**
Системата трябва да наблюдава един процес/система от различни гледни точки — метрики, аларми, логове и други източници.

**Decision**
`Observation` е основната конфигурационна единица и съдържа множество `Lens` конфигурации.

**Consequences**
- общ lifecycle за свързани наблюдения;
- възможност за Observation-level reasoning;
- Lens-овете могат да се обработват независимо и потенциално паралелно.

---

## ADR-002 — Predefined и ad-hoc Observation използват един и същ runtime pipeline

**Status:** Accepted

**Context**  
Освен предварително дефинирани Observations, оператор трябва да може да стартира анализ чрез кратък естествен език.

**Decision**  
Ad-hoc заявката се преобразува в временна стандартна Observation/Lens конфигурация. След това използва същите pipelines като предварително конфигурираните Observations.

**Consequences**
- няма два независими execution модела;
- единни contracts и persistence;
- ad-hoc сложността е концентрирана в request/configuration resolution.

---

## ADR-003 — Един Metric Lens наблюдава една метрика

**Status:** Accepted

**Context**  
Разгледани бяха два модела: Lens за една метрика и Lens за група от свързани метрики.

**Decision**  
За MVP `Metric Lens = една метрика`.

**Consequences**
- ясна отговорност;
- лесно тестване и повторна употреба;
- добра failure isolation;
- multivariate reasoning трябва да бъде изнесен на по-високо ниво.

---

## ADR-004 — Multivariate relationships се моделират на ниво Observation

**Status:** Accepted

**Context**  
Аномалия може да бъде видима само чрез комбинация от няколко метрики.

**Decision**  
Многопараметричните зависимости не са част от отделен Metric Lens. Те се дефинират и оценяват в контекста на Observation.

**Consequences**
- Lens остава атомарен;
- повторна употреба на Lens резултати;
- Observation получава отговорност за cross-Lens reasoning.

---

## ADR-005 — Relationship поддържа 2..N участници

**Status:** Accepted

**Context**  
Pairwise отношенията са прости, но не описват достатъчно условни поведения при индустриални и software/IoT системи.

**Decision**  
Relationship моделът поддържа две или повече величини. Двойката е специален случай на общия модел.

**Consequences**
- по-висока универсалност;
- възможност за условни multidimensional patterns;
- нужда от контрол върху прекалено големи/неясни relationship groups.

---

## ADR-006 — Инженерът определя кои величини се разглеждат заедно

**Status:** Accepted

**Context**  
Агент би могъл сам да търси зависимости, но това увеличава риска от неподходящи или несмислени връзки.

**Decision**  
Инженерът носи отговорността да определи релевантните relationship groups.

**Consequences**
- domain knowledge остава под човешки контрол;
- runtime reasoning space е ограничено;
- конфигурацията изисква инженерно участие.

---

## ADR-007 — Relationship discovery е configuration-time capability

**Status:** Accepted

**Context**  
Желателно е системата да подпомага инженера при намиране на зависимости.

**Decision**  
Агент може да предлага candidate relationships при конфигуриране чрез документация/RAG, topology, historical statistics или LLM hypothesis. Runtime не открива наново topology при всяко изпълнение.

**Consequences**
- по-предвидим runtime;
- candidate relationships могат да бъдат review-нати;
- по-ниска runtime цена и по-малък риск от nondeterministic dependency discovery.

---

## ADR-008 — Relationships живеят в Observation за MVP

**Status:** Accepted

**Context**  
Разгледана беше възможност за глобален Asset/Process Relationship Registry.

**Decision**  
За MVP relationships са част от конкретния Observation.

**Consequences**
- по-проста реализация;
- Observation е self-contained;
- възможно бъдещо дублиране между Observations;
- глобален registry може да се добави по-късно.

---

## ADR-009 — Expected relationships са структурирани и качествени

**Status:** Accepted

**Context**  
Числовите rule models са по-прецизни, но значително усложняват MVP.

**Decision**  
Expected behavior се описва чрез controlled semantic states, без сложни числови правила и математически модели.

**Consequences**
- лесна конфигурация;
- естествен интерфейс със semantic descriptors;
- по-ниска точност от пълни физични/числови модели;
- numeric rules могат да бъдат бъдещо разширение.

---

## ADR-010 — Relationship evaluation е детерминистична, process interpretation е agentic

**Status:** Accepted

**Context**  
Сравнявани бяха deterministic evaluator и LLM-only evaluator.

**Decision**  
Когато expected behavior е структуриран, consistency evaluation се прави детерминистично. LLM/Reasoning Agent интерпретира комбинацията от relationship evidence и останалия контекст.

**Consequences**
- повторяемост и лесно unit testing;
- по-добра проследимост;
- LLM остава на ниво, където контекстното reasoning носи стойност.

---

## ADR-011 — Semantic descriptors използват контролиран композиционен речник

**Status:** Accepted

**Context**  
Свободен текст или комбинирани labels затрудняват deterministic evaluation.

**Decision**  
Semantic descriptors използват fixed controlled values и отделни измерения, например `trend.direction` и `trend.rate`, вместо `increasing_fast`.

**Consequences**
- предвидим contract;
- лесно разширяване;
- по-малко ambiguity при downstream processing.

---

## ADR-012 — Baseline е изключен от MVP

**Status:** Accepted

**Context**  
Fixed historical baseline може да се окаже недостъпен поради observability retention и въвежда lifecycle/versioning сложност.

**Decision**  
MVP не използва baseline.

**Consequences**
- по-проста реализация;
- липсва абсолютна „distance from normal“ оценка;
- baseline остава бъдещо разширение.

---

## ADR-013 — Current window се сравнява с непосредствено предходен равен прозорец

**Status:** Superseded by ADR-133

**Context**  
Без baseline е необходим краткосрочен времеви контекст.

**Decision**  
За всеки current analysis window се използва непосредствено предходен прозорец със същата дължина.

**Consequences**
- минимална допълнителна сложност;
- полезна информация за локално развитие;
- предходният период не се интерпретира като normal baseline.

---

## ADR-014 — Previous-period comparison включва level, trend и variability

**Status:** Superseded by ADR-134

**Context**  
Трябва да се ограничи обхватът на comparative analysis за MVP.

**Decision**  
`previous_period.comparison` съдържа само:

- level;
- trend direction/rate;
- variability.

Реалният previous window се записва в резултата.

**Consequences**
- малък contract;
- достатъчна информация за краткосрочна динамика;
- бъдещи comparative dimensions могат да се добавят по-късно.

---

## ADR-015 — Историята използва запазени LensRun резултати, не raw telemetry

**Status:** Accepted

**Context**  
Raw metrics имат ограничен retention и не трябва да се fetch-ват повторно за всеки historical analysis.

**Decision**  
Historical analysis работи върху съхранените структурирани резултати от предходни LensRun-и.

**Consequences**
- независимост от telemetry retention;
- по-нисък runtime cost;
- необходимост от persistence на LensRun/analysis results.

---

## ADR-016 — History configuration има defaults и hierarchical override

**Status:** Accepted

**Decision**  
System defaults:

```text
lookback_runs = 5
level_change_tolerance = 5%
```

Override priority:

```text
Lens > Observation > System default
```

**Consequences**
- проста default конфигурация;
- възможност за специфични Lens настройки.

---

## ADR-017 — History Analyzer използва само валидни LensRun-и

**Status:** Accepted

**Decision**  
Използват се:

```text
completed + good/degraded
partial   + good/degraded
```

Пропускат се:

```text
failed
insufficient data quality
```

Системата търси назад, докато събере до N валидни runs.

**Consequences**
- partial резултатите остават полезни;
- технически успешен, но analytically unusable run не замърсява history.

---

## ADR-018 — History analysis винаги сравнява наличната история с текущия LensRun

**Status:** Accepted

**Decision**  
При поне един предходен валиден LensRun се изпълнява historical analysis върху:

```text
previous LensRuns + current LensRun
```

При нула предходни валидни runs секцията `history` липсва.

**Consequences**
- анализът има смисъл още при един предходен run;
- няма artificial `insufficient_history` status.

---

## ADR-019 — При един предходен run се определя direction, но pattern остава unknown

**Status:** Accepted

**Context**  
Две състояния позволяват посока, но не дават достатъчно информация за устойчив pattern.

**Decision**  
При 1 historical run + current:

```text
direction → calculated
pattern   → unknown
```

Pattern се класифицира при поне 2 classifiable transitions.

---

## ADR-020 — History direction се базира на промяна на mean между runs

**Status:** Accepted

**Context**  
Вътрешният trend на всеки window не описва непременно drift на operating level между runs.

**Decision**  
`history.direction` използва последователността от `mean` стойности на runs.

**Consequences**
- може да се открие постепенна промяна на нивото при локално stable windows;
- trend и history имат различна семантика.

---

## ADR-021 — History transition classification използва relative tolerance 5%

**Status:** Accepted

**Decision**  
Default:

```text
level_change_tolerance = 0.05
```

Под tolerance → stable; над него → increasing/decreasing според знака.

Near-zero reference → unknown transition.

**Consequences**
- unit-independent classification;
- simple MVP rule;
- 5% е аналитичен tolerance, не safety threshold.

---

## ADR-022 — Unknown historical transitions се изключват от denominator-а

**Status:** Accepted

**Decision**  
Unknown transitions не участват в `history.direction` процентите и в `history.pattern` classification.

**Consequences**
- липсваща/ненадеждна информация не наказва валидните transitions;
- трябва отделно да се отчита `unknown_transitions` в evidence.

---

## ADR-023 — History direction използва 70% dominance rule

**Status:** Accepted

**Decision**  
Върху classifiable transitions:

```text
>=70% increasing → increasing
>=70% decreasing → decreasing
>=70% stable     → stable
otherwise        → mixed
```

Без classifiable transitions → unknown.

---

## ADR-024 — History pattern е ограничен до пет MVP категории

**Status:** Accepted

**Decision**  
MVP vocabulary:

```text
sustained | reversing | oscillating | mixed | unknown
```

`progressive` и `intermittent` са отложени.

**Consequences**
- малък rule set;
- лесно тестване;
- по-малко нюанси в първата версия.

---

## ADR-025 — History pattern използва фиксиран приоритет на правилата

**Status:** Accepted

**Decision**

1. unknown — <2 classifiable transitions;
2. oscillating — >=2 consecutive direction changes;
3. reversing — една ясна смяна между противоположни доминиращи посоки;
4. sustained — >=70% от classifiable transitions са от един тип;
5. mixed — иначе.

**Consequences**
- deterministic classification;
- предвидима resolution на overlapping patterns.

---

## ADR-026 — Trend и variability са задължителното ядро на Metric Lens

**Status:** Accepted

**Decision**  
Всеки Metric Lens задължително изчислява `trend` и `variability`. Другите аналитични характеристики са optional.

**Consequences**
- общ semantic language между всички metrics;
- минимална гарантирана информация за history и multivariate reasoning.

---

## ADR-027 — Oscillation е отделна характеристика от trend

**Status:** Accepted

**Decision**  
`oscillating` не е `trend.direction`. `oscillation` е отделно property.

**Consequences**
- възможно е едновременно increasing trend + oscillation;
- по-чист композиционен модел.

---

## ADR-028 — Variability vocabulary не използва „normal“

**Status:** Accepted

**Decision**  
MVP values:

```text
low | moderate | high | not_classified | unknown
```

**Consequences**
- не се предполага baseline;
- семантиката остава описателна, а не normative.

---

## ADR-029 — Missing optional property означава „not evaluated“

**Status:** Accepted

**Decision**

```text
field missing    → not evaluated
state=absent     → evaluated, not detected
state=present    → evaluated, detected
state=unknown    → evaluated, inconclusive
```

**Consequences**
- downstream компоненти не смесват „липсва анализ“ с „липсва явление“.

---

## ADR-030 — Data quality е един общ статус в MVP

**Status:** Accepted

**Decision**  
Public contract съдържа само:

```text
good | degraded | insufficient | unknown
```

**Consequences**
- минимален contract;
- detailed quality diagnostics могат да останат вътрешни.

---

## ADR-031 — MetricAnalysisResult е structured-only; summary не е част от MVP

**Status:** Accepted

**Decision**  
Metric Lens резултатът е машинно структуриран. Текстово `summary` не се генерира/изисква на това ниво.

**Consequences**
- аналитичният contract не се смесва с reporting;
- текстово описание се генерира на по-високо ниво.

---

## ADR-032 — MetricAnalysisResult evidence е разделено по времеви контекст

**Status:** Accepted

**Decision**

```text
evidence.current
evidence.reference_periods
evidence.history
```

**Consequences**
- ясна връзка между numerical evidence и semantic conclusion;
- current/reference/history не се смесват.

---

## ADR-033 — Минималното current evidence ядро е mean/std/min/max/slope

**Status:** Accepted

**Decision**  
Всеки успешен Metric Lens изчислява поне:

```text
mean
std
min
max
slope
```

**Consequences**
- евтини за изчисление;
- достатъчна базова числена проследимост;
- optional tools могат да добавят собствен evidence.

---

## ADR-034 — Raw historical numeric sequence не се пази в MetricAnalysisResult

**Status:** Accepted

**Decision**  
`evidence.history` пази aggregate counts/characteristics, но не масив от historical means/relative changes.

Traceability се осигурява чрез `history.run_ids`.

**Consequences**
- по-компактен result;
- re-computation изисква достъп до съответните historical LensRun results.

---

## ADR-035 — MetricAnalysisResult има status completed/partial/failed

**Status:** Accepted

**Decision**

```text
completed → mandatory + optional requested analyses successful
partial   → mandatory successful, optional analysis failed
failed    → mandatory result cannot be produced
```

**Consequences**
- optional failure не прекъсва цялата обработка;
- downstream може да работи с partial резултат.

---

## ADR-036 — Execution status и data quality са независими

**Status:** Accepted

**Decision**  
Валиден сценарий е:

```text
status = completed
data_quality = insufficient
```

ако pipeline-ът успешно е установил недостатъчност на данните.

**Consequences**
- техническите грешки не се смесват с quality limitations.

---

## ADR-037 — Failed MetricAnalysisResult използва минимален contract

**Status:** Accepted

**Decision**  
При `failed` не се изискват `data_quality`, `current_state`, `reference_periods`, `history` и `evidence`.

Задължителни остават metadata + error:

```text
schema_version
identity
status.error.code
status.error.message
analysis_window
provenance
```

**Consequences**
- няма фиктивни `unknown` аналитични полета;
- по-прост failure handling.

---

## ADR-038 — MetricAnalysisResult identity съдържа шест задължителни атрибута

**Status:** Accepted

**Decision**

```text
observation_id
observation_run_id
lens_id
lens_run_id
metric_ref
unit
```

**Consequences**
- еднозначно свързване с конфигурация, execution и measurement semantics.

---

## ADR-039 — MetricAnalysisResult е versioned

**Status:** Accepted

**Decision**  
Добавя се:

```yaml
schema_version: "1.0"
```

**Consequences**
- безопасно бъдещо развитие на contract-а;
- старите persisted results могат да бъдат разпознати.

---

## ADR-040 — Provenance е минимален за MVP

**Status:** Accepted

**Decision**

```yaml
provenance:
  source: prometheus
  generated_at: ...
```

Не се изискват algorithm/tool/prompt versions.

**Consequences**
- прост contract;
- detailed audit trail остава future enhancement.

---

## ADR-041 — History пази конкретните използвани run_ids

**Status:** Accepted

**Decision**  
`history.run_ids` съдържа идентификаторите на използваните предходни LensRun-и.

Текущият run не се дублира в този списък.

**Consequences**
- traceability и debugging;
- може да се проследи основата на historical classification.

---

## ADR-042 — Baseline, global relationship registry и advanced historical models са deferred

**Status:** Accepted / Deferred scope

**Decision**  
Следните capabilities не са част от MVP:

- baseline management;
- operating-mode baselines;
- adaptive/seasonal baselines;
- global Relationship Registry;
- runtime relationship discovery;
- numeric relationship rule engine;
- progressive/intermittent history pattern classes.

**Consequences**
- ограничен MVP scope;
- оставени extension points за бъдеща работа.

---

---

## ADR-043 — Observation Orchestrator е детерминистичен workflow component

**Status:** Accepted

**Context**  
Трябва да се отдели управлението на lifecycle-а от аналитичното LLM reasoning.

**Decision**  
`Observation Orchestrator` управлява workflow topology, dispatch, JOIN и stage transitions, но не е AI агент и не извършва домейн reasoning.

**Consequences**
- предвидим lifecycle;
- по-лесно testing/replay;
- agentic autonomy остава само в специализирани analytical stages.

---

## ADR-044 — Observation execution използва йерархичен workflow със sub-pipelines

**Status:** Accepted

**Decision**  
Observation workflow съдържа stages, които могат сами да бъдат specialized pipelines. Metrics/Alerts/Logs analysis не се моделират като една линейна agent-to-agent chain.

**Consequences**
- ясни abstraction boundaries;
- локална еволюция на Lens pipelines;
- top-level Orchestrator не познава internal analytical steps.

---

## ADR-045 — Metrics pipeline има deterministic lifecycle с Metrics Analysis Agent вътре в него

**Status:** Accepted

**Decision**  
Fetch, preprocessing, mandatory analysis, semantic/result building и persistence са част от deterministic Metrics pipeline. `Metrics Analysis Agent` е bounded component вътре в този flow.

**Consequences**
- agentът не контролира infrastructure lifecycle;
- mandatory evidence е гарантирано от pipeline-а;
- adaptive analysis остава възможен.

---

## ADR-046 — Metrics Analysis Agent се извиква за всеки Metric Lens

**Status:** Accepted

**Decision**  
Всеки Metric Lens преминава през Metrics Analysis Agent. Agentът може да приключи без optional tool call, ако mandatory evidence е достатъчно.

**Consequences**
- единен Metrics pipeline;
- агентната роля е винаги налична;
- optional exploration остава условно.

---

## ADR-047 — Metrics Analysis Agent поддържа bounded multi-step tool loop

**Status:** Accepted

**Decision**  
Agentът може да избира разрешен analytical tool, да оцени резултата и при нужда да извика следващ tool, докато реши да спре или достигне runtime budget.

**Consequences**
- реална аналитична адаптивност;
- необходим allowed-tool registry и iteration/timeout limits;
- по-висока сложност от one-shot tool selection.

---

## ADR-048 — Metrics Analysis Agent не може да разширява observational data scope

**Status:** Accepted

**Decision**  
Agentът не може да добавя метрики, да променя time window, да модифицира source query или да изисква нови process variables извън LensRun scope-а.

**Consequences**
- Lens остава owner на observation scope;
- контролирана цена и latency;
- cross-variable exploration се извършва на по-високо ниво.

---

## ADR-049 — Analysis objectives задават intent, не tool whitelist

**Status:** Accepted

**Decision**  
`analysis_objectives` насочват какво трябва да бъде разбрано, но не фиксират конкретен analytical tool. Agentът избира измежду runtime-разрешените tools.

**Consequences**
- запазва се agentic reasoning стойността;
- tool registry остава централизирано ограничение;
- exact objectives schema остава Open към момента на това решение.

**Follow-up**
Exact Lens-definition `analysis_objectives` shape е по-късно фиксиран от ADR-162 като ordered duplicate-free list от opaque non-whitespace intent strings.

---

## ADR-050 — Observation Reasoning Agent и Report Agent са отделни роли

**Status:** Accepted

**Decision**  
Observation-level analytical synthesis и final narrative report generation са отделени. Reasoning Agent произвежда structured `ObservationAnalysisResult`; Report Agent го представя за човек.

**Consequences**
- analysis не се смесва с presentation;
- един analytical result може да има няколко output formats;
- exact schemas остават отделни design tasks.

---

## ADR-051 — Observation Reasoning Agent може да извлича knowledge context при нужда

**Status:** Accepted

**Decision**  
Agentът първо работи върху structured Observation evidence и сам решава дали и кога има информационна празнина. Тогава може да използва ограничена documentation/knowledge retrieval capability.

**Consequences**
- retrieval не е задължителен за всеки run;
- reasoning context може да се обогатява;
- точната RAG/tool реализация остава Open.

---

## ADR-052 — Knowledge retrieval не може да променя Observation data scope

**Status:** Accepted

**Decision**  
Reasoning Agent може да разширява knowledge/context evidence, но не може да добавя нови observed metrics/logs/alerts извън изпълнения Observation.

**Consequences**
- ясна граница между observed facts и external knowledge;
- предотвратява скрито динамично преформулиране на Observation-а.

---

## ADR-053 — Relationship Evaluation е задължителен детерминистичен stage преди Observation Reasoning

**Status:** Accepted

**Decision**  
Всички конфигурирани Relationships се оценяват детерминистично след Lens JOIN и преди Observation Reasoning Agent.

**Consequences**
- configuration-time domain rules се проверяват повторяемо;
- Reasoning Agent интерпретира relationship evidence, а не го замества.

---

## ADR-054 — Observation workflow продължава при частично неуспешни Lens pipelines

**Status:** Accepted

**Decision**  
Ако след JOIN има поне един usable Lens result, Relationship/Observation reasoning продължава. Failed/unavailable Lens-ове се отчитат като липсващо evidence, не като normal state.

**Consequences**
- graceful degradation;
- един source failure не блокира целия Observation;
- reasoning трябва да отчита limitations.

---

## ADR-055 — При нула usable Lens results ObservationRun приключва с failed и STOP

**Status:** Accepted

**Decision**  
Не се стартира допълнителен reasoning/fallback logic или нормален analytical report, когато няма нито един usable Lens result.

**Consequences**
- прост и предвидим failure path;
- няма LLM reasoning върху празен evidence set.

---

## ADR-056 — LensRuns са логически независими и могат да се изпълняват конкурентно

**Status:** Accepted

**Decision**  
LensRuns в рамките на ObservationRun нямат взаимни execution dependencies. Runtime може да ги изпълнява паралелно.

**Consequences**
- по-ниска latency при множество Lens-ове;
- cross-Lens dependencies се обработват след JOIN;
- нужда от execution correlation чрез run IDs.

---

## ADR-057 — Maximum LensRun concurrency е конфигурируема execution policy

**Status:** Accepted

**Decision**  
Системата трябва да позволява ограничаване на максималния брой едновременно изпълнявани LensRuns.

**Consequences**
- контрол на load/rate limits/cost;
- архитектурната независимост не зависи от физическия parallelism;
- точната config hierarchy/default е Open.

---

## ADR-058 — Lens JOIN е strict и чака всички LensRuns да достигнат terminal state

**Status:** Accepted

**Decision**  
Следващият Observation stage не започва, докато всеки LensRun не е `completed`, `partial` или `failed`. Няма early continuation по правило „достатъчно резултати“.

**Consequences**
- пълен и предвидим result set;
- straggler latency се управлява чрез Lens timeout policy;
- по-прост Relationship Evaluation input.

---

## ADR-059 — Всички Lens pipelines реализират общ execution contract

**Status:** Accepted

**Decision**  
Orchestrator-ът работи с обща абстракция `LensRun → LensAnalysisResult`, а конкретното analytical payload остава type-specific.

**Consequences**
- Orchestrator-ът не съдържа Metrics/Alerts/Logs domain logic;
- лесно добавяне на нов Lens type;
- изисква common lifecycle metadata.

---

## ADR-060 — Relationship Evaluator получава Relationship[] и целия LensAnalysisResult[] набор

**Status:** Accepted

**Decision**  
Orchestrator-ът не resolve-ва participant semantic fields. Relationship Evaluator сам намира participant results и извлича необходимите current-state descriptors.

**Consequences**
- domain matching logic остава локализирано в evaluator-а;
- Observation Orchestrator остава generic.

---

## ADR-061 — Relationship applicability е отделно от evaluation state

**Status:** Accepted

**Decision**  
`applicability = applicable | not_applicable | unknown`. Само при `applicable` се изчислява `state = consistent | inconsistent | uncertain`.

**Consequences**
- ясно се различават „правилото не се прилага“ и „липсва достатъчно evidence“;
- downstream reasoning получава по-точна семантика.

---

## ADR-062 — Relationship rules използват само current_state за MVP

**Status:** Accepted

**Decision**  
`reference_periods` и `history` не са част от Relationship rule language. Те се предоставят на Observation Reasoning като отделен evidence слой.

**Consequences**
- по-прост rule model;
- temporal reasoning остава на Observation level;
- бъдещо temporal relationship language е възможно разширение.

---

## ADR-063 — Relationship rule property vocabulary остава малък и explicit

**Status:** Accepted

**Decision**  
За MVP се поддържат ограничени current-state properties като `trend.direction`, `trend.rate` и `variability.state`. Не се допуска произволно адресиране на всяко поле от резултата.

**Consequences**
- deterministic evaluator е прост и лесен за validation;
- optional properties се добавят само чрез explicit extension.

---


---

## ADR-064 — Reasoning Agent получава full structured analytical results, но не raw telemetry

**Status:** Accepted

**Decision**  
Observation Reasoning Agent получава пълните структурирани usable Lens results (current/reference/history/evidence), без raw metric samples, raw log streams или необработени alert payload-и.

**Consequences**
- агентът има достатъчен аналитичен контекст;
- context growth е контролиран спрямо raw telemetry;
- детерминистичните pipelines остават semantic/evidence boundary.

---

## ADR-065 — Observation configuration се подава като compact semantic reasoning projection

**Status:** Accepted

**Decision**  
Reasoning Agent не получава full Observation config 1:1. Използва `ObservationReasoningContext` с identity, description/objective и полезна Lens semantic metadata; execution/infrastructure settings се изключват.

**Consequences**
- по-малък context;
- по-малко reasoning noise;
- configuration остава single source of truth, а reasoning context е deterministic projection.

---

## ADR-066 — RelationshipEvaluation е self-contained за downstream reasoning

**Status:** Accepted

**Decision**  
`RelationshipEvaluation` носи relationship identity/meaning и evaluated expected/observed evidence. Reasoning context не дублира целите Relationship definitions.

**Consequences**
- по-компактен input;
- по-малко downstream joins;
- traceability остава в аналитичния artifact.

---

## ADR-067 — Failed Lens-ове се отделят от usable results

**Status:** Accepted

**Decision**  
Reasoning input съдържа `usable_lens_results` за completed/partial и отделен `unavailable_lenses` списък за failed/non-usable Lens-ове.

**Consequences**
- агентът не получава празни failed contracts;
- липсата на evidence е explicit и не се смесва с normal state.

---

## ADR-068 — Partial/unavailable причините използват кратки structured reason codes

**Status:** Accepted

**Decision**  
Използват се `code` + минимален optional context (`component`) вместо свободен технически текст/stack traces.

**Consequences**
- machine-readable failure context;
- по-малък prompt noise;
- exact exhaustive code list може да се разширява контролирано.

---

## ADR-069 — Overall state е analytical assessment, не normal/anomalous classification

**Status:** Accepted

**Decision**

```text
no_significant_findings
significant_findings_present
uncertain
```

**Consequences**
- не се предполага baseline/absolute normality;
- терминологията описва резултата от текущия Observation analysis.

---

## ADR-070 — Finding contract остава минимален без taxonomy

**Status:** Accepted

**Decision**

```text
id
statement
evidence_refs
```

Не се изисква `type/category/severity/confidence`.

**Consequences**
- малък и гъвкав MVP contract;
- бъдеща taxonomy може да бъде добавена след емпирични наблюдения.

---

## ADR-071 — Hypothesis се свързва с supporting findings

**Status:** Accepted

**Decision**  
Минималният hypothesis contract е `id + statement + supported_by[]`.

**Consequences**
- ясна граница finding (evidence-based) vs hypothesis (interpretation);
- traceability от explanation към наблюдаваните findings.

---

## ADR-072 — Limitations остават кратки и structured

**Status:** Accepted

**Decision**  
MVP limitations използват малък structured vocabulary за evidence availability/partial analysis, вместо свободни аналитични essays или сложна uncertainty taxonomy.

**Consequences**
- machine-readable limitations;
- по-малка schema/agent complexity.

---

## ADR-073 — Recommendations са извън MVP ObservationAnalysisResult

**Status:** Accepted

**Decision**  
Reasoning Agent не връща prescriptive recommendations/actions в MVP.

**Consequences**
- scope остава supervision/interpretation;
- prescriptive behavior може да бъде бъдеща capability.

---

## ADR-074 — Confidence е извън MVP ObservationAnalysisResult

**Status:** Accepted

**Decision**  
Не се добавя numerical/categorical confidence без калибриран механизъм.

**Consequences**
- избягва false precision;
- uncertainty се представя чрез overall state/limitations/evidence availability.

---

## ADR-075 — Hypothesis може да съдържа optional knowledge_refs

**Status:** Accepted

**Decision**  
Когато е използван external retrieved knowledge, hypothesis пази references към конкретните използвани knowledge sources/sections/chunks.

**Consequences**
- provenance на domain interpretation;
- разграничава observed evidence от external knowledge.

---

## ADR-076 — RAG knowledge може да влияе само върху hypotheses, не върху findings

**Status:** Accepted

**Decision**  
Findings се формират само от Observation evidence. Retrieved knowledge не може да създава/променя findings и се използва единствено за explanatory hypotheses.

**Consequences**
- силна evidence/interpretation boundary;
- намален риск документацията да bias-не наблюдаваните факти.

---

## ADR-077 — Findings се формират преди първия retrieval

**Status:** Accepted

**Decision**  
Reasoning Agent първо анализира Observation evidence и формира/freeze-ва findings. Retrieval query трябва да произлиза от един или повече конкретни findings.

**Consequences**
- retrieval е grounded в текущия run;
- knowledge search не дефинира retroactively „какво е наблюдавано“.

---

## ADR-078 — Knowledge retrieval е tool в Observation Reasoning Agent, не отделен агент

**Status:** Accepted

**Decision**  
Не се въвеждат отделни RAG Decision/Knowledge agents. Reasoning Agent има allowed `retrieve_knowledge` capability в bounded loop.

**Consequences**
- по-малко orchestration complexity;
- запазена agentic autonomy за decision whether/when/query.

---

## ADR-079 — Observation Reasoning RAG loop има fixed max_calls=2 за MVP

**Status:** Accepted

**Decision**  
Максимум две knowledge retrieval извиквания на Observation Reasoning run; стойността е system-fixed, не Observation config.

**Consequences**
- контролирани cost/latency/context;
- демонстрира multi-step agentic behavior без unbounded search.

---

## ADR-080 — Вторият retrieval може да refine-не query чрез резултата от първия

**Status:** Accepted

**Decision**  
Retrieval #2 може да използва original findings + useful knowledge от Retrieval #1 + оставащ knowledge gap.

**Consequences**
- второто извикване е истински refinement step;
- не е просто повторение на първия query.

---

## ADR-081 — Domain hypotheses изискват RAG grounding; липсата на достатъчно knowledge допуска празен hypothesis list

**Status:** Accepted

**Decision**  
Domain hypothesis трябва да е едновременно linked към findings и retrieved `knowledge_refs`. Ако knowledge retrieval не даде достатъчна опора, агентът приключва без domain hypothesis.

**Consequences**
- по-добра traceability;
- system не е принудена да измисля обяснение за всеки finding.

---

## ADR-082 — Reasoning Agent може да връща 0..N unranked hypotheses

**Status:** Accepted

**Decision**  
Няма probability/ranking/primary hypothesis; позицията в масива не означава приоритет.

**Consequences**
- прост contract;
- избягва неподкрепено root-cause selection.

---

## ADR-083 — Overall state се определя от Reasoning Agent без отделен classifier

**Status:** Accepted

**Decision**  
Не се добавя отделен deterministic/LLM classification stage за `overall_state`; Reasoning Agent го връща по controlled vocabulary.

**Consequences**
- по-малко duplicate decision logic;
- един system-level reasoning owner.

---

## ADR-084 — overall_state=uncertain може да съществува с валидни findings; няма hard cross-field invariants за MVP

**Status:** Accepted

**Decision**  
Несигурната обща картина не премахва валидните локални findings. За MVP schema validation не налага правила като `no_significant_findings => findings.length==0`.

**Consequences**
- по-гъвкава degraded-mode семантика;
- consistency checks могат да се добавят след реални тестове.

---

## ADR-085 — Report Agent получава само ObservationAnalysisResult + minimal semantic context

**Status:** Accepted

**Decision**  
Report Agent не получава LensAnalysisResult[], raw telemetry или full Observation config.

**Consequences**
- не се дублира analysis reasoning;
- ясна граница analysis vs presentation.

---

## ADR-086 — ObservationReport е Markdown presentation artifact за MVP

**Status:** Accepted

**Decision**  
Не се въвежда сложен structured report schema; output е Markdown content с минимален metadata envelope.

**Consequences**
- проста реализация;
- human-readable artifact;
- бъдещи renderers могат да използват същия ObservationAnalysisResult.

---

## ADR-087 — Report Agent е presentation-only и няма RAG/new-analysis capability

**Status:** Accepted

**Decision**  
Report Agent не добавя findings/hypotheses, не променя overall_state, не извиква RAG и не генерира recommendations в MVP.

**Consequences**
- отчетът не може да измени аналитичната истина;
- presentation logic остава заменяем слой.

---

## ADR-088 — Relationships са само между Metric Lens-ове за MVP

**Status:** Accepted

**Decision**  
Alert/Log Lens-ове не участват в deterministic Relationship rules за MVP. Те се комбинират с metric/relationship evidence в Observation Reasoning.

**Consequences**
- не се изгражда преждевременно cross-type rule DSL;
- текущият semantic vocabulary остава metric-oriented и прост.

---


## ADR-089 — Един Alert Lens модел покрива specific rule и bounded filtered set

**Status:** Accepted

**Context**  
Бяха разгледани отделен Lens за конкретен alert rule/type и Lens за множество alert-и около asset/service/component.

**Decision**  
Използва се един `Alert Lens` модел. Specific rule е restrictive provider selector; по-широк alert scope е less restrictive selector.

**Consequences**
- една архитектура за двата случая;
- по-малко type proliferation;
- selector design става основният scope mechanism.

---

## ADR-090 — Alert Lens използва provider-native selector и source-agnostic analytical pipeline

**Status:** Accepted

**Decision**  
Alert Lens съдържа source/provider + provider-native query/filter. Provider adapter изолира provider-specific API и field mapping; downstream analysis работи върху canonical records.

**Consequences**
- текущият `Jira Track and Release` provider не lock-ва analytical design-а;
- бъдещ provider може да се добави чрез adapter.

---

## ADR-091 — Alert selector определя „which“, LensRun определя „when“

**Status:** Accepted

**Decision**  
Provider selector определя кои alert-и са в Lens scope-а. Analysis/reference time window идва от `LensRun`, а не от свободно encoded time predicate в query-то.

**Consequences**
- еднозначен runtime time context;
- по-добра reproducibility и reference-window semantics.

---

## ADR-092 — Lifecycle status е analytical data; MVP не валидира/пренаписва provider query

**Status:** Accepted

**Decision**  
Alert Lens selector не трябва целенасочено да филтрира по lifecycle status. Provider query остава opaque/native; за MVP няма automatic query validation/rewrite. Инженерът носи отговорност да не добавя status predicate.

**Consequences**
- active/resolved distribution остава видима за анализа;
- няма допълнителна query-control сложност.

---

## ADR-093 — Alert membership използва lifecycle overlap с analysis window

**Status:** Accepted

**Decision**  
Alert е релевантен, ако:

```text
started_at < window.end
AND
(ended_at is null OR ended_at > window.start)
```

Правилото важи за current и reference windows.

**Consequences**
- обхваща alerts, започнали преди window-а, но active вътре в него;
- не се разчита само на created/start timestamp inside window.

---

## ADR-094 — Alert analysis е retrospective latest-known и използва full lifecycle duration

**Status:** Accepted

**Decision**  
Исторически/reference анализ използва latest lifecycle information, налична при execution. Resolved alert duration е `ended_at-started_at`; active alert duration е `analysis_timestamp-started_at`. Duration не се clip-ва до overlap с window-а.

**Consequences**
- проста и възпроизводима semantics;
- няма point-in-time lifecycle reconstruction в MVP.

---

## ADR-095 — Normalized alert status е active/resolved/unknown и се извежда основно от ended_at

**Status:** Accepted

**Decision**  
MVP vocabulary:

```text
active | resolved | unknown
```

Основно:

```text
ended_at != null -> resolved
ended_at == null -> active
```

Provider status се пази като `status.source`.

**Consequences**
- provider-independent lifecycle core;
- source status остава traceable.

---

## ADR-096 — Provider priority/severity не се нормализира глобално

**Status:** Accepted

**Decision**  
Optional `provider_importance` пази original provider semantics:

```yaml
provider_importance:
  type: priority
  value: Highest
```

Не се правят mappings като `P1 -> critical`.

**Consequences**
- избягва false equivalence между providers;
- Observation reasoning може да вижда provider-native importance context.

---

## ADR-097 — Canonical current alert record е минимален и изисква валиден started_at

**Status:** Accepted

**Decision**  
Canonical record използва provider id като `id`, required `title` и `started_at`, nullable `ended_at`, normalized/source status, optional description/provider_importance/occurrence_count/source_ref. Record без valid `started_at` или с `ended_at < started_at` е invalid.

**Consequences**
- достатъчно lifecycle evidence за overlap/duration;
- не се въвежда отделен internal record/provenance object за MVP.

---

## ADR-098 — Missing occurrence_count има deterministic effective default 1

**Status:** Accepted

**Decision**  
Provider adapter не дописва липсващ `occurrence_count`. `Deterministic Alert Analyzer` използва effective default 1.

**Consequences**
- source record остава faithful към provider payload semantics;
- activity counting остава deterministic.

---

## ADR-099 — Alert activity пази и record_count, и occurrence_count

**Status:** Accepted

**Decision**  
`record_count` брои distinct usable provider records. `occurrence_count` сумира effective occurrence counts. Status distribution брои records и никога не се умножава по occurrence count.

**Consequences**
- различават се record cardinality и repeated occurrence activity;
- не се реконструират individual historical occurrence statuses.

---

## ADR-100 — Deterministic Alert Analyzer е собственик на measurable alert evidence

**Status:** Accepted

**Decision**  
Counts, status distribution, durations, provider importance distribution и reference comparisons се изчисляват детерминистично, не от LLM.

**Consequences**
- reproducibility/unit testing;
- agentът остава само за semantic interpretation.

---

## ADR-101 — Mandatory deterministic Alert evidence е ограничено до малко MVP ядро

**Status:** Accepted

**Decision**  
MVP evidence:

```text
alert_activity(record_count, occurrence_count)
status_distribution
duration_statistics(min/max/average seconds)
provider_importance_distribution [optional]
occurrence comparisons
```

Median, burst/clustering/flapping analysis не са mandatory.

**Consequences**
- прост и проверим pipeline;
- future analytical extensions остават възможни.

---

## ADR-102 — Alert Lens поддържа multiple reference periods със same-duration backward offsets

**Status:** Accepted

**Decision**  
Могат да се конфигурират 0..N reference offsets. Всеки reference window е със същата продължителност като current window и се измества назад по configured offset.

**Consequences**
- може да се сравнява спрямо различни temporal contexts;
- няма global historical score.

---

## ADR-103 — Alert reference comparison използва само occurrence_count и strict direction

**Status:** Accepted

**Decision**  
За MVP comparison-ът е:

```text
current occurrence_count
reference occurrence_count
delta
direction = increased|decreased|unchanged
```

Без tolerance и percentage-change classification.

**Consequences**
- deterministic/simple historical comparison;
- richer temporal semantics са deferred.

---

## ADR-104 — Reference raw alert records не се подават към agent/result

**Status:** Accepted

**Decision**  
Historical/reference records се използват само за deterministic comparison. Те не се подават на Alert Analysis Agent и не се включват в AlertAnalysisResult.

**Consequences**
- compact downstream context;
- по-малък риск от historical event dump.

---

## ADR-105 — Zero-alert fast path се определя само от record_count=0

**Status:** Accepted

**Decision**  
След successful current analysis, ако `record_count=0`, reference comparisons все пак се изпълняват, но Alert Analysis Agent се пропуска и се задава:

```text
findings=[]
overall_importance=none
```

`occurrence_count=0` при налични records не е sufficient fast-path criterion.

**Consequences**
- няма ненужно LLM извикване при надеждно zero-record state;
- provider-specific zero occurrence anomalies не се бъркат с „няма alert records“.

---

## ADR-106 — Alert Analysis Agent получава bounded source-agnostic input

**Status:** Accepted

**Decision**  
Agent input включва minimal Lens name/description, current normalized records, deterministic current evidence и successful reference comparisons. Не включва raw provider payload, historical records или provider-native query.

**Consequences**
- context efficiency;
- agentът остава независим от provider syntax.

---

## ADR-107 — Alert Analysis Agent е Lens-local descriptive reasoning component

**Status:** Accepted

**Decision**  
Agentът може да формулира само descriptive findings върху Alert Lens evidence. Не прави root cause, recommendations, metrics/logs correlation, Relationships или RAG/external-knowledge reasoning.

**Consequences**
- ясна граница с Observation Reasoning Agent;
- cross-lens diagnosis остава system-level concern.

---

## ADR-108 — Alert finding contract е минимален и допуска празен списък

**Status:** Accepted

**Decision**  
Finding съдържа само:

```text
id
statement
evidence_refs[]
```

Няма mandatory taxonomy/severity/confidence. `findings=[]` е валидно и при налични records. Няма hard max findings, но overlapping findings се deduplicate/merge-ват.

**Consequences**
- agentът не е принуден да генерира тривиални findings;
- result contract остава малък.

---

## ADR-109 — Alert Analysis Agent не прави semantic clustering и не infer-ва missing data

**Status:** Accepted

**Decision**  
Agentът не създава synthetic groups от similar alerts и не infer-ва missing status, severity, description, lifecycle или cause.

**Consequences**
- по-малък hallucination surface;
- grouping/burst analysis остава future capability.

---

## ADR-110 — Alert Lens има една overall_importance оценка с controlled vocabulary

**Status:** Accepted

**Decision**  
Vocabulary:

```text
none | low | moderate | high | critical
```

`none` е допустимо само при reliable `record_count=0`. При `record_count>0` agentът връща `low|moderate|high|critical`. Няма rationale field.

**Consequences**
- компактна Lens-level signal за downstream reasoning;
- няма fake provider severity normalization.

---

## ADR-111 — Alert finding evidence_refs трябва да resolve-ват в същия AlertAnalysisResult

**Status:** Accepted

**Decision**  
Всеки `evidence_ref` трябва директно да сочи към current alert record, aggregate или successful comparison, присъстващи в същия result.

**Consequences**
- deterministic validation и traceability;
- exact path grammar остава implementation detail.

---

## ADR-112 — Unavailable reference periods водят до partial и не създават placeholder comparisons

**Status:** Accepted

**Decision**  
Reference query failure/timeout не прекратява usable current analysis. Result става `partial` с `reference_unavailable`; неуспешният offset просто липсва от `comparisons`.

**Consequences**
- graceful degradation;
- comparison collection съдържа само валидно evidence.

---

## ADR-113 — Invalid current records се drop-ват и логват; partial ако usable subset остава, failed ако не остава

**Status:** Accepted

**Decision**  
Some invalid + usable remain -> continue as partial (`invalid_records`). All current records invalid/no usable current data -> failed. Rejected records се логват operationally.

**Consequences**
- не се използват corrupt records;
- incomplete current evidence се вижда downstream като partial.

---

## ADR-114 — Current query, deterministic core и required Alert Agent са mandatory failure boundaries

**Status:** Accepted

**Decision**  
Следните failures дават failed Alert LensRun:

```text
current_query_failed/current_query_timeout
deterministic_analysis_failed
agent_failed/agent_timeout
```

`partial` е само usable mandatory result с supplementary/current-subset incompleteness.

**Consequences**
- ясна usable/failed граница;
- липсващ mandatory agent output не се представя като partial.

---

## ADR-115 — Alert partial/failed reason е една structured primary причина

**Status:** Accepted

**Decision**  
Reason има:

```yaml
reason:
  code: ...
  component: ... # optional
```

Само една primary причина се пази в analytical/runtime contract; detailed diagnostics са в logs.

**Consequences**
- machine-readable downstream handling;
- precedence при multiple partial causes остава Open.

---

## ADR-116 — Failed Alert LensRun не създава и не persist-ва AlertAnalysisResult

**Status:** Accepted

**Decision**  
При failed Alert pipeline се persist-ват runtime `LensRun.status/reason` и operational logs, но няма type-specific `AlertAnalysisResult` artifact.

**Consequences**
- `AnalysisResult` означава usable analytical result;
- unavailable Lens metadata се derive-ва от LensRun.

---

## ADR-117 — AlertAnalysisResult използва common versioned identity/time/provenance envelope

**Status:** Accepted

**Decision**  
Result включва:

```text
schema_version
identity: observation_id, observation_run_id, lens_id, lens_run_id
lens_type=alert
status
analysis_timestamp
analysis_window
minimal provenance: source_provider, generated_at
```

`analysis_timestamp` и `generated_at` са различни concepts.

**Consequences**
- consistency с common Lens architecture;
- traceable/persistable artifact.

---

## ADR-118 — Alert duration се сериализира в секунди; duration_statistics липсва при zero records

**Status:** Accepted

**Decision**  
Per-record `duration_seconds`; aggregate `min_seconds|max_seconds|average_seconds`. При `record_count=0` `duration_statistics` се пропуска.

**Consequences**
- machine-readable numeric representation;
- не се използват artificial null/zero durations.

---

## ADR-119 — Findings е mandatory list при completed/partial; optional analytical sections се omit-ват когато няма evidence

**Status:** Accepted

**Decision**  
`findings` винаги присъства при usable AlertAnalysisResult, включително `[]`. Optional sections като duration/provider-importance distribution се пропускат, когато не са приложими/налични.

**Consequences**
- downstream различава „успешно няма findings“ от missing contract field;
- compact result без synthetic nulls.

---

## ADR-120 — AlertAnalysisResult се сглобява от deterministic Builder / Validator, не от agent-а

**Status:** Accepted

**Decision**  
Alert Analysis Agent връща само `findings + overall_importance`. `AlertAnalysisResult Builder / Validator` добавя common envelope, комбинира evidence, валидира invariants/evidence_refs и произвежда final result.

**Consequences**
- agentът не контролира public contract;
- същият ownership принцип като Metrics pipeline.

---

## ADR-121 — Persistence е отделна Alerts pipeline stage; няма отделен AlertRepository design за MVP

**Status:** Accepted

**Decision**  
След Builder има `Persist AlertAnalysisResult` deterministic stage. Concrete repository/database abstraction не се фиксира.

**Consequences**
- contract assembly и storage ownership са разделени;
- storage technology остава implementation decision.

---

## ADR-122 — MVP не truncatе-ва current alert records в AlertAnalysisResult

**Status:** Accepted

**Decision**  
Всички usable normalized current alert records могат да бъдат включени в `AlertAnalysisResult`. Не се въвеждат max-record limit, truncation, pagination или ranking policy за MVP.

**Consequences**
- прост и traceable MVP contract;
- scalability/volume policy се deferred-ва до реални измервания.

---

## ADR-123 — Alerts pipeline използва hybrid mandatory/optional tool model

**Status:** Accepted

**Decision**  
Mandatory acquisition, preparation и mandatory analytical operations се гарантират от deterministic pipeline lifecycle-а. `Alert Analysis Agent` не решава дали mandatory core да бъде изпълнен; agentът може да използва само optional analytical tools след формиране на mandatory evidence.

**Consequences**
- предвидимост и mandatory completeness не зависят от LLM;
- запазва се agentic адаптивност за допълнителен анализ;
- Alerts pipeline се доближава до общата hybrid architecture без да копира Metrics semantics механично.

---

## ADR-124 — Deterministic Alert Analyzer остава отделен coordinator на mandatory analytical tools/capabilities

**Status:** Accepted

**Decision**  
`Deterministic Alert Analyzer` не се премахва като архитектурна абстракция. Той остава owner/coordinator на mandatory alert analytical evidence и може вътрешно да използва тесни deterministic tools/capabilities за activity, status, duration, provider importance и reference comparison.

**Consequences**
- ясно single-responsibility ownership на mandatory evidence;
- internal tool decomposition може да се променя без промяна на pipeline contract-а.

---

## ADR-125 — Optional Alert tools работят само в immutable already-fetched Lens scope

**Status:** Accepted

**Decision**  
Optional tools, извиквани от `Alert Analysis Agent`, могат да работят само върху вече извлечените/нормализирани current данни, mandatory evidence и configured reference data. Те не могат да fetch-ват нови alerts, да променят selector/query, analysis window, reference configuration или Observation scope.

**Consequences**
- agentic tool loop не може да разширява observational scope;
- reproducibility и bounded execution се запазват.

---

## ADR-126 — Minimal optional Alert tool registry съдържа три прости анализа

**Status:** Accepted

**Decision**  
MVP optional registry съдържа:

```text
Recurrence Concentration Analysis Tool
Duration Outlier Analysis Tool
Reference Pattern Analysis Tool
```

**Consequences**
- малък и explainable MVP tool surface;
- burst/flapping, semantic clustering и по-сложни анализи остават deferred.

---

## ADR-127 — Duration Outlier Analysis използва high-side IQR с minimum sample 8

**Status:** Accepted

**Decision**  
Optional duration outlier tool използва:

```text
IQR = Q3 - Q1
upper_bound = Q3 + 1.5 * IQR
minimum_valid_durations = 8
duration > upper_bound -> high duration outlier
```

При по-малко от 8 валидни durations резултатът е `not_applicable` и не влияе на LensRun status.

**Consequences**
- прост robust deterministic method;
- няма LLM-defined threshold за prolonged outlier detection.

---

## ADR-128 — Recurrence Concentration използва само top_record_share

**Status:** Accepted

**Decision**  
Optional recurrence tool изчислява:

```text
top_record_share = max(effective_occurrence_count_i) / total_occurrence_count
```

Не се добавят Top-3 score, thresholds или categorical labels.

**Consequences**
- минимален quantitative indicator;
- semantic interpretation остава за agent-а.

---

## ADR-129 — Reference Pattern Analysis използва simple dominant direction и minimum 2 comparisons

**Status:** Accepted

**Decision**  
Tool-ът се прилага само при поне 2 successful reference comparisons. Той преброява `increased|decreased|unchanged`; unique most frequent value е `dominant_direction`, а при tie резултатът е `mixed`. Няма weights по offset, tolerance или percentage scoring.

**Consequences**
- проста агрегация на вече налично deterministic comparison evidence;
- не се въвежда Metrics-like History Analyzer за Alerts.

---

## ADR-130 — Alert Analysis Agent optional tool loop има max 10 calls и позволява repeated tool use

**Status:** Accepted

**Decision**  
За един non-zero Alert LensRun:

```text
max_optional_tool_calls = 10
```

Един и същ tool може да бъде извикван многократно. Всеки invocation attempt се брои към лимита, включително `success`, `failed`, `timeout` и `not_applicable`.

**Consequences**
- bounded execution с достатъчен резерв за adaptive analysis;
- няма per-tool single-call restriction.

---

## ADR-131 — Optional tool failure/timeout е non-fatal best-effort failure

**Status:** Accepted

**Decision**  
При `failed` или `timeout` optional analytical tool call `Alert Analysis Agent` продължава с наличното evidence. Самият tool failure не прави LensRun `partial` или `failed`. Неуспешният call все пак консумира една от 10-те позволени стъпки.

**Consequences**
- optional enrichment не застрашава mandatory usable analysis;
- техническият failure остава traceable без да се смесва с analytical availability semantics.

---

## ADR-132 — Optional tool outputs са transient; result пази само minimal failed/timeout trace

**Status:** Accepted

**Decision**  
Successful optional tool outputs и `not_applicable` outcomes не се persist-ват като отделни sections в `AlertAnalysisResult`; те служат за формиране на findings. Ако има реален `failed|timeout` call, result може да съдържа минимален trace с `tool + status`. Ако няма такъв call, `optional_tool_execution` липсва.

**Consequences**
- public result contract остава компактен;
- detailed tool execution остава в operational logs;
- exact `evidence_refs` mapping за findings derived от transient optional analysis остава Open.

---

## ADR-133 — Metric Lens поддържа множество конфигурируеми reference periods

**Status:** Accepted

**Context**  
Един непосредствено предходен прозорец предоставя само локален времеви контекст и не е достатъчен за процеси с периодично или сезонно поведение. Необходимо е текущото състояние да може да бъде сравнено с еквивалентни прозорци, изместени назад с различни интервали, например 1, 7 или 14 дни.

**Decision**  
Metric Lens поддържа `0..N` конфигурирани reference offsets. Всеки reference window има същата продължителност като current analysis window и е изместен назад с конкретния offset. Всеки reference period се извлича и сравнява независимо с current window.

Концептуален пример:

```yaml
reference_periods:
  - offset: 1d
  - offset: 7d
  - offset: 14d
```

Reference periods не са baseline и не заменят persisted Lens history.

**Consequences**
- позволява сравнение със съответстващи периоди при дневна, седмична или друга периодичност;
- подпомага разграничаването на регулярно повтарящо се поведение от нетипично изменение;
- увеличава броя на telemetry fetch операциите пропорционално на configured offsets;
- exact defaults/config hierarchy и partial policy при недостъпен reference period остават implementation decisions.

**Supersedes**
- ADR-013.

---

## ADR-134 — Metric reference comparison се оценява независимо за всеки offset

**Status:** Accepted

**Context**  
След въвеждането на multiple reference periods единичният `previous_period.comparison` contract вече не описва коректно сравнителния анализ.

**Decision**  
За всеки успешно извлечен reference period Metric pipeline изчислява отделно сравнение спрямо current window. MVP comparative dimensions остават:

```text
level
trend direction/rate
variability
```

Резултатът се моделира като collection, идентифицирана чрез `offset`, вместо като единичен `previous_period` object.

Концептуална форма:

```yaml
reference_periods:
  - offset: 1d
    comparison:
      level: ...
      trend: ...
      variability: ...
  - offset: 7d
    comparison:
      level: ...
      trend: ...
      variability: ...
```

**Consequences**
- downstream reasoning получава ясно разделено evidence за всеки temporal offset;
- comparison semantics остават deterministic;
- reference-period evidence може да се използва като сигнал за периодично/сезонно повторение, но не представлява automatic seasonality classification;
- collection contract заменя единичния `previous_period` contract.

**Supersedes**
- ADR-014.

---

## ADR-135 — MetricAnalysisResult разделя evidence на current, reference periods и history

**Status:** Accepted

**Context**  
Преминаването от единичен previous period към множество reference periods изисква съответна промяна на публичната семантика на MetricAnalysisResult.

**Decision**  
MetricAnalysisResult използва следните времеви секции:

```text
current_state
reference_periods[]
history [optional]

evidence.current
evidence.reference_periods[]
evidence.history
```

`reference_periods` съдържа само валидно изчислените configured comparisons и всеки елемент носи своя `offset`. `history` остава отделна перспектива, базирана на persisted LensRun results.

**Consequences**
- current/reference/history имат ясно различна семантика;
- downstream contracts вече не използват `previous_period`;
- exact serialized schema и version migration policy се фиксират при implementation contract design.

**Supersedes partially**
- ADR-032 по отношение на `evidence.previous_period`; останалата идея за разделяне по времеви контекст остава валидна.

---


## ADR-136 — Log Lens използва provider-native bounded scope и point-event time semantics

**Status:** Accepted

**Decision**  
`Log Lens` определя кои логове са релевантни чрез provider-native selector. `LensRun` определя current/reference time windows. Log record е релевантен, когато `window.start <= timestamp < window.end`.

**Consequences**
- ясна граница между semantic scope и time context;
- Loki-specific syntax остава зад provider adapter;
- semantics се различават от lifecycle-overlap модела при Alerts.

---

## ADR-137 — Log acquisition разделя aggregate evidence от bounded textual content

**Status:** Accepted

**Decision**  
Logs pipeline не изисква materialization на целия log corpus. Quantitative activity/reference evidence се извлича чрез aggregate/bounded operations, а textual records се извличат ограничено за content-dependent analyses.

**Consequences**
- по-добра scalability;
- count/rate evidence не зависи от template-sampling limit;
- exact sampling/coverage policy остава implementation decision.

---

## ADR-138 — Log parsing е deterministic/configured и LLM-visible text минава през sanitization boundary

**Status:** Accepted

**Decision**  
Canonical fields като level се извличат чрез configured/provider-specific parsing. LLM не infer-ва log level от свободен текст. Преди text/template content да се подаде към agent се прилага sanitization/redaction; content се третира като untrusted data.

**Consequences**
- по-висока repeatability и security;
- exact parser/redaction rules остават Open.

---

## ADR-139 — Generic log deduplication не се използва по подразбиране

**Status:** Accepted

**Decision**  
Logs pipeline не deduplicate-ва records по message/time similarity. Повторяемостта може да е аналитично значима.

**Consequences**
- recurrence evidence не се унищожава;
- transport-level dedupe може да бъде бъдеща explicit provider capability при стабилна event identity.

---

## ADR-140 — Mandatory Log evidence е activity/rate + level/error-level evidence

**Status:** Accepted

**Decision**  
Минималният current deterministic core съдържа `record_count`, logging rate, level distribution, `error_level_count`, `known_level_count`, `level_coverage` и `error_level_rate` когато е дефиниран.

**Consequences**
- core остава малък и проверим;
- `error_level_count` не се интерпретира като абсолютен брой реални faults.

---

## ADR-141 — Template extraction е deterministic supplementary analysis с versioned provenance

**Status:** Accepted

**Decision**  
MVP използва simple deterministic template normalization, не semantic clustering/LLM extraction. Template extractor/version се пазят в provenance. При bounded content template evidence носи coverage semantics.

**Consequences**
- explainable и testable template evidence;
- template counts не се представят като corpus-wide без съответно coverage доказателство.

---

## ADR-142 — Log reference periods са 0..N; core comparisons са log_count и error_level_count; persisted Log history е извън MVP

**Status:** Accepted

**Decision**  
Log Lens поддържа `0..N` equal-duration shifted reference windows. Core comparison dimensions са `log_count` и `error_level_count`. Не се изпълнява отделен persisted Log History Analyzer в MVP.

**Consequences**
- прост temporal context;
- historical analysis върху persisted LogAnalysisResult може да бъде добавен по-късно.

---

## ADR-143 — Log Analysis Agent е bounded Lens-local agent без observational scope expansion

**Status:** Accepted

**Decision**  
Agentът интерпретира structured Log Lens evidence, формира Lens-local findings/overall_importance и не може да променя selector/window/reference configuration, да fetch-ва metrics/alerts или да прави system-level diagnosis.

**Consequences**
- ясна separation между Lens-local analysis и Observation-level reasoning;
- agent autonomy остава bounded.

---

## ADR-144 — Zero-log path зависи от reference evidence

**Status:** Accepted

**Decision**  
`record_count=0` не означава автоматично normal state. Ако available references също показват 0 activity, agentът може да бъде пропуснат. Ако references показват prior activity, agentът се извиква за Lens-local difference finding. При липса на references не се прави causal inference.

**Consequences**
- избягва ненужни LLM calls;
- запазва значимостта на внезапна липса на log activity.

---

## ADR-145 — Logs MVP има три optional analytical tools и single-call-per-tool budget

**Status:** Accepted

**Decision**  
Registry:

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

**Consequences**
- малък и testable agentic surface;
- не се копира механично Alert tool budget.

---

## ADR-146 — Log optional analytical tool failure/timeout е non-fatal

**Status:** Accepted

**Decision**  
`failed|timeout` optional tool call не прави LensRun partial/failed сам по себе си; agentът продължава с наличното evidence.

**Consequences**
- optional enrichment не застрашава usable core;
- failure остава operationally traceable.

---

## ADR-147 — Log Analysis Agent failure води до partial при usable deterministic core

**Status:** Accepted

**Decision**  
Ако Log Agent failed/timeout, но mandatory deterministic current evidence е usable, `LogAnalysisResult` се създава като `partial` без agent-generated importance/knowledge enrichment.

**Consequences**
- resilience към LLM failure;
- deterministic evidence остава достъпно за Observation Reasoning.

---

## ADR-148 — LogAnalysisResult Builder / Validator е final contract owner; failed Log LensRun няма type-specific result

**Status:** Accepted

**Decision**  
Final result се сглобява/валидира детерминистично. `completed|partial` имат `LogAnalysisResult`; `failed` има само terminal LensRun failure metadata.

**Consequences**
- ясен lifecycle contract;
- agentът не контролира persistence/final schema validity.

---

## ADR-149 — Log Analysis Agent има bounded knowledge retrieval след freeze на findings

**Status:** Accepted

**Decision**  
След формиране и freeze на Log findings agentът може да използва до 2 knowledge-retrieval calls, anchored към конкретен вече наблюдаван template/error code/message. Retrieval не разширява observational data scope-а.

**Consequences**
- domain semantics могат да бъдат проверени близо до Log Lens-а;
- retrieval не се използва като mechanism за ново data discovery.

---

## ADR-150 — Log RAG knowledge е отделено от observational findings чрез knowledge_annotations

**Status:** Accepted

**Decision**  
Retrieved knowledge не може да създава или променя Log findings. RAG-derived semantic enrichment се пази като `knowledge_annotations`, които изискват `supported_by` към Log findings и `knowledge_refs` към използвани sources.

**Consequences**
- traceable separation между observation и explanation;
- LogAnalysisResult може да носи domain context без да замърсява evidence layer-а.

---

## ADR-151 — Observation Reasoning третира upstream Log knowledge_annotations като knowledge, не като finding evidence

**Status:** Accepted

**Decision**  
Observation Reasoning не може да използва `LogAnalysisResult.knowledge_annotations` за създаване/промяна на Observation findings. Тези annotations могат да бъдат използвани за system-level hypotheses като already-retrieved knowledge, ако original `knowledge_refs` се запазят.

**Consequences**
- запазва глобалното правило findings-before-knowledge;
- избягва duplicate retrieval, когато Lens-local RAG вече е намерил релевантна документация;
- provenance остава задължителна.

---

## ADR-152 — Select PydanticAI as the MVP agent framework

**Status:** Accepted

**Context**
Intelligent Process Observer requires bounded LLM agents with typed inputs and
outputs, deterministic domain-owned execution constraints, optional tools, and
later bounded knowledge retrieval. PydanticAI and LangChain were evaluated in
two controlled engineering spikes: the Alert Analysis Agent spike and the
Observation Reasoning / RAG spike. Both frameworks satisfied the relevant
architecture. Neither spike demonstrated a defensible, material, repeatable
technical advantage for either framework, so a project-fit tie-break is
required.

**Decision**
Use PydanticAI for production MVP agent implementations.

- Keep domain contracts, tools, budgets, orchestration rules, persistence
  contracts, and execution invariants framework-neutral.
- Treat PydanticAI as an adapter/integration mechanism, not the owner of domain
  workflow semantics.
- Use Pydantic models as the typed agent contract boundary.
- Do not allow framework-specific abstractions to leak unnecessarily into
  domain or application layers.

**Rationale**
- direct fit with the existing Pydantic-based backend contract strategy;
- direct structured-output model binding;
- lower conceptual surface for current MVP needs;
- no compensating LangChain advantage was demonstrated in the evaluated
  workflows;
- a simpler dependency and abstraction story for a modular-monolith MVP;
- framework-neutral boundaries keep a future migration possible.

**Consequences**

Positive:
- one agent framework is fixed for MVP implementation;
- production agent work can proceed without another framework-comparison gate;
- Pydantic contracts remain central;
- architectural ambiguity is reduced;
- experiment-only adapters are no longer production decision blockers.

Trade-offs:
- LangChain-specific graph/orchestration capabilities are not adopted for the
  MVP;
- future advanced workflows may require reassessing PydanticAI sufficiency;
- framework migration remains a non-zero cost even with framework-neutral
  boundaries.

**Rejected alternative — LangChain**
LangChain is technically viable and passed the relevant experiment semantics.
It is not selected because the evaluated MVP scenarios did not demonstrate
enough benefit to justify its broader abstraction surface. This is not a claim
that LangChain is technically inferior.

**Scope**
This ADR selects only `agent framework = PydanticAI`. It does not select a
production LLM model or provider, vector database, embedding model, RAG backend,
retrieval-ranking strategy, observability product, or production
evidence-reference grammar. GPT-5.6 Terra and OpenRouter were experiment
configuration only. PydanticAI is not added as a production dependency by this
ADR; that change belongs to the first approved production agent feature that
requires it.

**Follow-up**
The experiments exposed a shared Observation Reasoning / RAG design concern:
the boundary between partially useful/insufficient retrieval, refinement,
knowledge availability, and final-hypothesis `knowledge_refs` validation. It
occurred across both framework variants and is not framework-selection evidence.
A future production Observation Reasoning/knowledge-retrieval change must make
that behavior explicit without promoting the experiment-local convention to a
production rule prematurely.

---

## ADR-153 — Metric trend and variability use fixed normalized deterministic MVP rules

**Status:** Accepted

**Context**
Metric values have different units, scales, signs, and near-zero behavior. Absolute
thresholds cannot provide a reusable mandatory Metric semantic vocabulary, while
per-Lens threshold configuration would expand the definition contract and MVP setup
cost.

**Decision**
For every analytically sufficient current or reference series, the deterministic
Metric analyzer uses one system-fixed normalized policy.

```text
duration = analysis_window.to - analysis_window.from, in seconds
scale = max(abs(mean), max - min)
normalized_trend_change = abs(slope) * duration / scale
normalized_variability = population_std(OLS residuals) / scale
```

If `scale == 0`, trend is `stable` with rate `not_classified`, and variability is
`low`. Otherwise:

```text
normalized_trend_change < 0.05        -> stable / not_classified
0.05 <= value < 0.15                  -> sign(slope) / slow
0.15 <= value < 0.35                  -> sign(slope) / moderate
value >= 0.35                         -> sign(slope) / fast

normalized_variability < 0.05         -> low
0.05 <= value < 0.15                  -> moderate
value >= 0.15                         -> high
```

The policy is descriptive. It is not a safety threshold, baseline, definition of
normal behavior, severity model, or confidence model.

**Consequences**
- mandatory semantics remain deterministic, unit-independent, and explainable;
- signed and near-zero metrics do not require division by the mean alone;
- Metric Lens configuration and the observation-definition API do not change;
- domain-specific thresholds remain a possible future versioned policy.

---

## ADR-154 — Metrics MVP optional registry is spike, oscillation, and stuck_signal

**Status:** Accepted

**Context**
The always-invoked Metrics Analysis Agent needs a small registry of deterministic
capabilities that adds information beyond mandatory mean/std/min/max/slope,
trend/variability, and persisted History.

**Decision**
The Metrics MVP optional analytical registry is:

```text
spike
oscillation
stuck_signal
```

- `spike` detects isolated extremes with a median/MAD modified-z rule and a
  deterministic zero-MAD fallback.
- `oscillation` detects repeated alternating detrended residual behavior.
- `stuck_signal` detects long runs of exactly repeated provider values; it is not a
  claim that a physical sensor is proven to be stuck.

Successful optional evaluation produces a controlled optional current-state property
and matching deterministic evidence. `not_applicable` produces neither public property
nor public tool evidence. Failed/timeout execution produces no successful property or
evidence projection.

`drift` is not a separate optional tool: within-window direction/rate is mandatory
trend, while operating-level evolution across runs is owned by History.
`analysis_objectives` remain intent rather than a tool whitelist under ADR-049.

**Consequences**
- the optional surface is small, deterministic, and dependency-free;
- optional properties preserve missing versus absent/present/unknown semantics;
- transient datasets, tool request messages, and model trajectories are not result
  fields.

---

## ADR-155 — Metrics optional tool budget is three attempts with each tool at most once

**Status:** Accepted

**Decision**
The Metrics Analysis Agent tool loop uses:

```text
max_tool_attempts = 3
max_attempts_per_tool = 1
```

Each of the first three requested tool actions consumes one available slot, including
`success`, `not_applicable`, `failed`, `timeout`, and duplicate/unregistered/parallel
rejection. A request after all three slots are consumed is recorded as an over-budget
rejection but cannot consume or execute a fourth slot. A duplicate request never
executes the deterministic tool again.

`not_applicable` is not failure and does not change LensRun status. Tool `failed` or
`timeout`, duplicate/unregistered/parallel requests, and a fourth-call request mark
optional analysis incomplete. With a usable mandatory current core they contribute
`optional_analysis_failed`; the agent may continue only within remaining budget.

**Consequences**
- cost and iteration count are predictably bounded;
- repeating a fixed tool over one immutable dataset cannot manufacture new evidence;
- the authoritative attempt ledger is application/domain-owned and framework-neutral.

---

## ADR-156 — Metrics Agent sees structured evidence plus opaque dataset_ref and cannot invalidate an insufficient-quality determination

**Status:** Accepted

**Decision**
The Metrics Analysis Agent receives immutable identity/window/objective context,
data quality, mandatory numerical evidence and mandatory semantics when available,
the allowed tool descriptions, and an opaque run-scoped `dataset_ref`. Raw or compact
series values are not serialized into agent context. Only deterministic registered
tools can resolve the opaque reference, and tool requests cannot select a metric,
query, window, source, or dataset.

The framework-neutral final completion contract is only:

```text
MetricAgentCompletion.state = completed
```

It contains no summary, findings, severity, confidence, recommendations, or restated
tool list.

For `good|degraded` current quality, agent failure, timeout, or invalid/unacceptable
structured completion yields a usable partial Metric result with:

```text
reason.code = optional_analysis_failed
reason.component = metrics_agent
```

Valid deterministic optional results already produced may still be semanticized.

For `data_quality=insufficient`, the agent is still invoked with narrow identity and
quality context and no applicable analytical tools. Agent failure/timeout/invalid
completion is recorded operationally but does not replace the successfully determined
`completed + insufficient` result. If the mandatory current core or its quality
determination cannot be produced technically, the Metric LensRun is failed under the
existing Metric failure semantics.

**Consequences**
- the agent has a real adaptive tool-selection role without direct sample inspection;
- LLM infrastructure failure cannot overwrite trustworthy mandatory evidence or an
  insufficient-quality determination;
- PydanticAI remains an infrastructure adapter under ADR-152.

---

## ADR-157 — Missing configured Metric reference analysis makes a usable result partial

**Status:** Accepted

**Decision**
When the current mandatory Metric core is usable, any configured reference offset that
cannot produce a comparison makes the Metric LensRun/result `partial`. Both acquisition
unavailability and analytically insufficient acquired reference data use the public
primary reason:

```text
reason.code = reference_unavailable
reason.component = reference_periods
```

`reference_unavailable` describes result incompleteness and does not necessarily mean
the provider failed. Operational diagnostics retain the internal cause. Successful
offsets remain serialized; unsuccessful offsets are omitted without fake `unknown`
comparison placeholders.

Current `data_quality=insufficient` remains `completed + insufficient`; reference
comparisons are not formable and their absence does not make that result partial.

For simultaneous analytical incompleteness, one public primary reason is selected in
this order:

```text
reference_unavailable
> history_analysis_failed
> optional_analysis_failed
```

Secondary causes remain operational diagnostics.

**Consequences**
- configured temporal context is not silently reported as complete;
- usable current and successful reference evidence are preserved;
- reference periods do not become baselines or normality classifications.

---

## ADR-158 — Metric History uses analysis-window event time and permits overlapping earlier windows

**Status:** Accepted

**Context**
Sliding Observation executions may have overlapping windows, and persistence/completion
order may differ from the analytical event-time order.

**Decision**
A persisted same-`observation_id + lens_id` Metric result can be an earlier History
candidate when:

```text
historical.analysis_window.to < current.analysis_window.to
```

Overlapping earlier windows are eligible. Completion or persistence order does not
define analytical chronology. Candidates are totally ordered by:

```text
analysis_window.to, analysis_window.from, lexical lens_run_id
```

The newest effective `lookback_runs` candidates are selected, then supplied to the
History Analyzer oldest-to-newest before appending the current result. `history.run_ids`
contains only the selected previous LensRun IDs in that order.

No eligible previous results is normal absence and does not cause partial. Unknown
transition classification is serialized as accepted unknown History state/evidence and
does not cause partial. Unexpected deterministic History Analyzer failure with a usable
current core yields `history_analysis_failed`; failure of the required persistence query
is an infrastructure error and must not be reinterpreted as no History.

**Consequences**
- sliding-window run evolution remains observable;
- History stays run-level analysis rather than raw-telemetry reanalysis;
- persisted `run_ids` preserve traceability for late-visible candidates;
- persistence transaction failure cannot fabricate a completed or partial artifact.

---

## ADR-159 — Metric History near-zero transitions use a pair-relative tolerance guard

**Status:** Accepted

**Clarifies:** ADR-021

**Context**
ADR-021 established that a near-zero previous mean produces an `unknown` History
transition, but it did not define the near-zero predicate. An implementation-specific
epsilon would make classification dependent on metric units or local choices.

**Decision**
For consecutive eligible Metric result means `previous=p` and `current=c`, use the
effective `level_change_tolerance=t` selected by the already accepted
Lens > Observation > System precedence, with system default `0.05`.

```text
if p == 0 and c == 0:
    transition = stable
else:
    pair_scale = max(abs(p), abs(c))
    near_zero_reference = abs(p) <= t * pair_scale

    if near_zero_reference:
        transition = unknown
    else:
        relative_change = (c - p) / abs(p)

        if abs(relative_change) <= t:
            transition = stable
        elif relative_change > t:
            transition = increasing
        else:
            transition = decreasing
```

The stable boundary is inclusive. Near-zero detection uses the same effective
level-change tolerance; no absolute epsilon or metric-unit-specific threshold is
introduced. `p=0,c=0` is stable, not unknown. Near-zero is only a guard against an
unstable relative comparison and does not imply abnormality. Unknown transitions
remain excluded from History direction and pattern denominators under ADR-022.

**Consequences**
- History transition classification is deterministic across units and implementations;
- the existing tolerance configuration and override hierarchy are reused;
- exact equality and tolerance boundaries require explicit tests;
- ADR-021 remains the original decision and this ADR supplies its missing algorithm.

---

## ADR-160 — Metric History pattern uses directional runs with stable transitions neutral

**Status:** Accepted

**Clarifies:** ADR-025

**Context**
ADR-025 fixed the History pattern vocabulary and priority but left direction changes,
stable transitions, unknown removal, consecutiveness, and a clear reversal
underspecified.

**Decision**
Start from the chronological History transition sequence.

1. Remove every `unknown` transition while preserving `increasing`, `decreasing`, and
   `stable` in chronological order. The result is `classifiable_transitions`.
2. If `len(classifiable_transitions) < 2`, classify `pattern=unknown`.
3. For oscillation and reversal detection only, remove `stable` from
   `classifiable_transitions` without reordering the remaining values. The result is
   `directional_transitions`. Stable remains classifiable, participates in sustained
   shares, and neither creates nor resets a directional change.
4. Compress consecutive identical values in `directional_transitions` into
   `directional_runs`.
5. Define the public History evidence count exactly as:

```text
direction_changes = max(0, len(directional_runs) - 1)
```

Apply ADR-025 priority exactly:

```text
1. unknown:
     len(classifiable_transitions) < 2

2. oscillating:
     len(directional_runs) >= 3

3. reversing:
     len(directional_runs) == 2

4. sustained:
     neither oscillating nor reversing matched, and at least one of
     increasing_share, decreasing_share, stable_share is >= 0.70,
     with every share calculated over all classifiable_transitions

5. mixed:
     otherwise
```

Unknown transitions are removed before all pattern calculations and do not contribute
to any denominator. Stable transitions are excluded only from directional run
detection. The separate `history.direction` algorithm from ADR-023 is unchanged.

Normative examples use full transition names:

```text
[increasing, increasing]                         -> sustained
[stable, stable]                                 -> sustained
[increasing, decreasing]                         -> reversing
[increasing, increasing, decreasing, decreasing] -> reversing
[increasing, stable, decreasing]                 -> reversing
[increasing, decreasing, increasing]             -> oscillating
[decreasing, increasing, decreasing]             -> oscillating
[increasing, increasing, decreasing, decreasing,
 increasing]                                     -> oscillating
[increasing, stable, increasing]                  -> mixed
[increasing, unknown, decreasing]                 -> reversing
[stable, unknown, stable]                         -> sustained
```

**Consequences**
- pattern classification and `direction_changes` are mechanically testable;
- stable transitions remain evidence for sustained behavior without hiding an
  increasing/decreasing switch;
- removing unknown transitions may bring otherwise separated directional transitions
  together, consistently with ADR-022;
- the accepted vocabulary and priority remain unchanged;
- ADR-025 remains the original decision and this ADR supplies its missing mechanics.

---

## ADR-161 — Alert Lens definition е nested child на Observation Definition aggregate

**Status:** Accepted

**Context**
След приемането на Alert Lens analytical semantics е необходимо exact definition/API ownership да бъде фиксирано, без да се въвежда отделен Alert CRUD lifecycle или преждевременен generic Lens-definition модел.

**Decision**
`Observation Definition` съдържа отделна nested `alert_lenses` collection наред с `metric_lenses` и `relationships`. Alert Lens create/read/update се извършва чрез съществуващия Observation Definition aggregate/API; standalone Alert Lens endpoints не са част от MVP.

- update семантиката е snapshot/replacement и се прилага атомарно върху aggregate-а;
- липсващо `alert_lenses` при input означава `[]`; canonical read винаги връща `alert_lenses`, включително празен списък;
- Observation Definition трябва да съдържа поне един Lens общо, така че Metric-only, Alert-only и mixed Metric+Alert configurations са валидни;
- Metric Lens IDs са unique в `metric_lenses`, Alert Lens IDs са unique в `alert_lenses`; еднакъв `lens_id` между различни Lens типове е допустим;
- Relationship participant validation остава Metric-only и resolve-ва IDs само срещу `metric_lenses`; Alert Lens не става Relationship participant поради съвпадащ ID.

**Consequences**
- Alert Lens следва съществуващия Observation Definition ownership model;
- backward compatibility се запазва за Metric-only clients, които не изпращат `alert_lenses`;
- Alert-only Observation може да бъде валиден без да се въвеждат cross-type Relationships;
- не е необходима cross-table/global Lens ID uniqueness или нов type discriminator в Relationship DSL.

---

## ADR-162 — Alert Lens serialized definition използва explicit recognized fields с opaque provider query

**Status:** Accepted

**Context**
Работният Alert Lens пример до момента фиксираше semantic scope, но exact machine-readable configuration schema оставаше Open. Необходимо е стабилен definition contract преди Alerts Analysis Pipeline implementation.

**Decision**
MVP Alert Lens definition съдържа:

```yaml
id: database_alerts
type: alert
name: "Database alerts"
description: "Alert activity related to the database service" # optional
source: jira_track_and_release
selector:
  query: "<provider-native query>"
analysis_objectives: []   # optional, default []
reference_periods: []     # optional, default []
```

Rules:

- `id` reuse-ва canonical Lens ID primitive;
- `type` е required exact literal `alert`;
- `name` е required non-whitespace string; `description` е optional non-whitespace string;
- `source` е supported-provider identifier; MVP допуска само `jira_track_and_release`;
- `selector` е object с required `query`; query трябва да има non-whitespace content, но иначе е opaque provider-native string и се запазва точно както е подаден; system не го trim-ва, normalize-ва, parse-ва, lint-ва или rewrite-ва;
- `analysis_objectives` е optional ordered duplicate-free list от non-whitespace opaque strings, без max-count, controlled vocabulary, priority, inheritance/default hierarchy или tool-selection semantics;
- `reference_periods` е optional ordered `0..N` list, reuse-ва canonical Metric reference-offset primitive, забранява duplicate offsets и няма implicit defaults;
- configured order на `analysis_objectives` и `reference_periods` се запазва;
- unknown/extra input fields се толерират и игнорират, не се persist-ват и не се връщат в canonical read output; recognized fields продължават да се валидират по правилата по-горе.

**Consequences**
- Alert definition е self-describing чрез explicit `type`;
- provider query остава faithful към native syntax и definition layer-ът не поема Jira parsing responsibilities;
- objectives описват intent, не capabilities;
- reference semantics са съгласувани с Metric offset primitive без implicit temporal policy;
- tolerated unknown fields позволяват forward-compatible input, но не се превръщат в мълчаливо поддържана конфигурация.

---

## ADR-163 — Alert Lens definition persistence използва dedicated owned child storage

**Status:** Accepted

**Context**
Добавянето на Alert Lens definitions не трябва да преработва съществуващия Metric definition persistence в generic polymorphic model, но трябва да осигури atomic aggregate updates, ordering и deletion ownership.

**Decision**
Alert Lens definitions се persist-ват като owned children на Observation Definition в dedicated `alert_lens_definitions` storage/table.

- stable scalar properties (`lens_id`, `type`, `name`, `description`, `source`, `selector_query`) се моделират explicit;
- ordered list properties (`analysis_objectives`, `reference_periods`) използват подходящо structured storage, без generic opaque payload за целия Alert Lens;
- configured order трябва да се запазва при persistence/read, включително order на `alert_lenses` в Observation Definition projection;
- removal на Alert Lens от replacement snapshot физически премахва owned definition row;
- delete на Observation Definition cascade-ва към всички негови Alert Lens definition rows;
- create/update/delete на aggregate-а и owned Alert rows се извършват атомарно;
- soft-delete и independent Alert Lens lifecycle не се въвеждат за MVP;
- не се прави generic `lens_definitions` refactor само заради добавянето на Alert Lens.

**Consequences**
- persistence остава explicit и inspectable;
- Metric definition storage не се мигрира към нов polymorphic abstraction;
- няма orphan Alert definitions след snapshot update или Observation deletion;
- бъдещи Lens types могат да бъдат добавени отделно и да мотивират generalization само при реална нужда.

---

# Open decisions

Актуалният и нормативен backlog е в `10_open_decisions_and_backlog.md`. Отворените въпроси **не** са implicit requirements и трябва да получат нов ADR, когато бъдат решени.
