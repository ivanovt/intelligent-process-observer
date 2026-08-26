# Observation Reasoning / RAG Framework Spike

This experiment compares PydanticAI and LangChain only. It uses the fixed
OpenRouter `openai/gpt-5.6-terra` configuration from the Alert spike.

Findings are formed from Observation evidence, validated, and stored in an
immutable `FrozenFindingsState` before direct retrieval is exposed. The final
builder uses that exact snapshot, so finding IDs, statements, and evidence refs
cannot change across retrieval.

`retrieve_knowledge` is experiment-local and allows two executed calls. Every
request must cite frozen finding IDs. A third call is blocked. A second call may
refine call one (`refines_attempt=1` plus `unresolved_gap`) or may independently
address another finding-grounded knowledge gap.

Experiment-local statuses: `success` knowledge can ground hypotheses;
`insufficient` partial knowledge can refine a second query but cannot alone
ground a hypothesis; `no_match`, `failed`, and `timeout` expose no usable
knowledge. Failed and timeout calls consume an attempt but allow completion with
`hypotheses=[]`.

Hard checks cover the output contract, frozen findings, reference membership,
retrieval budget, and knowledge grounding. Tool choices and wording are
behavioral observations. A valid matrix needs 24 outcomes per framework under
one configuration; individual structured-output failures remain outcomes, while
provider asymmetry, truncation, corruption, or harness failure invalidate it.

The final score uses the existing weights once, updating each category with the
strongest non-duplicated Alert and Reasoning evidence (Option A).

## Experimental outcome and human decision

The Observation Reasoning / RAG spike conclusion remains **FRAMEWORK EVIDENCE
REMAINS INCONCLUSIVE**. The completed matrix showed that both PydanticAI and
LangChain can support the tested phased execution, frozen findings, bounded
retrieval, and knowledge-grounding boundaries. It did not show a material,
repeatable framework advantage.

The human architecture decision subsequently selected PydanticAI for the MVP as
a project-fit tie-break, not because this experiment established semantic or
runtime superiority. LangChain remains technically viable. The shared
partially-useful/insufficient-retrieval refinement and final-hypothesis
`knowledge_refs` validation issue remains follow-up work for production
Observation Reasoning/knowledge retrieval; it is not framework-selection
evidence. See [`framework_decision.md`](framework_decision.md) and ADR-152.
