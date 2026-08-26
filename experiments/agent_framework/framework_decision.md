# Agent Framework Evaluation — Final Decision Record

**Decision status:** Human approved

This document closes the isolated agent-framework evaluation. It preserves the
experimental conclusions and records the separate human architecture decision.
It does not change production code or add production dependencies.

## Experimental finding

The two controlled framework spikes produced the following findings:

| Spike | Experimental conclusion |
| --- | --- |
| Bounded Alert Analysis Agent | **CLOSE / INCONCLUSIVE** |
| Observation Reasoning / RAG | **FRAMEWORK EVIDENCE REMAINS INCONCLUSIVE** |

Both PydanticAI and LangChain demonstrated the required bounded-agent semantics
and Observation Reasoning/RAG capabilities under shared contracts, deterministic
domain controls, and matched configurations. The experiments did not demonstrate
a material, repeatable technical advantage for either framework. They are not
PydanticAI benchmark victories, and they do not compare or select language
models.

The completed raw artifacts, including historical invalid/incomplete matrices,
remain preserved under `results/`. The valid final Observation Reasoning matrix
is `results/observation-reasoning-final-matrix-attempt-5.json`; the earlier
`results/observation-reasoning-final-matrix.json` remains invalid/incomplete and
is not used for scoring.

## Human architecture decision

**PydanticAI is selected as the production agent framework for the MVP.**

This is an engineering tie-break based on project fit and implementation
simplicity, rather than a claim of semantic or runtime superiority over
LangChain:

- the backend already uses Pydantic as its primary typed-contract mechanism;
- PydanticAI integrates structured outputs directly with Pydantic models;
- the experiments showed comparable framework-specific implementation size;
- bounded budgets, findings freeze, retrieval constraints, evidence validation,
  and other critical runtime semantics remain framework-neutral domain code;
- LangChain's broader orchestration abstraction did not demonstrate sufficient
  benefit in the evaluated MVP scenarios to justify additional conceptual
  surface;
- minimizing framework coupling fits the modular-monolith and
  explicit-contract architecture.

LangChain remains a technically viable alternative. The decision is recorded
normatively in ADR-152.

## Scope and dependency boundary

The decision selects only `agent framework = PydanticAI`. It does **not** select:

- a production LLM model or model provider;
- a vector database, embedding model, RAG backend, or retrieval-ranking strategy;
- an observability product; or
- a production evidence-reference grammar.

GPT-5.6 Terra and OpenRouter were experiment configuration only. No experiment
dependency moves into the production backend in this closing step. PydanticAI
will be added only when the first approved production agent feature requires it;
LangChain is not a production dependency.

## Shared Reasoning/RAG follow-up

The repeated second-retrieval-refinement issue is a common design concern, not
framework-selection evidence. It concerns the sequence:

```text
partially useful / insufficient retrieval
-> refinement
-> knowledge availability
-> final hypothesis knowledge_refs validation
```

It occurred across both variants. A future approved production Observation
Reasoning/knowledge-retrieval feature must define and validate this boundary.
The experiment-local retrieval convention must not be silently promoted to a
production semantic or architecture decision.

## References

- `evaluation_report.md` — Alert spike report; conclusion unchanged.
- `observation_reasoning_README.md` — Reasoning-spike rules and conclusion.
- `docs/architecture/03_ADR_log.md` — ADR-152, the accepted architecture decision.
