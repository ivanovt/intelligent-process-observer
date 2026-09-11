# VS-01 Handoff

Implemented server-owned Metric and hypothesis interaction guidance, capability-specific
Metric tool descriptions, and request-local `parallel_tool_calls=false` steering for
tool-enabled invocations. Existing deterministic admission, budgets, grounding, failure
mapping, and tool-free invocation behavior remain unchanged.

Changed paths:

- `backend/src/app/infrastructure/agents/pydantic_ai_metrics.py`
- `backend/src/app/infrastructure/agents/pydantic_ai_reasoning.py`
- `backend/src/app/infrastructure/agents/tracing.py`
- `backend/tests/test_pydantic_ai_metrics_adapter.py`
- `backend/tests/test_pydantic_ai_reasoning_adapter.py`
- `backend/tests/test_agent_tracing.py`
- `docs/development-guide.md`

Evidence: focused Ruff checks passed; focused Metric, reasoning, trace, executor,
production-composition, and reasoning-configuration tests passed (`89 passed`). Tests
cover guidance clauses, capability descriptions, initial/continuation request settings,
tool-free settings, preserved rejection behavior, empty unavailable-retrieval completion,
and private trace allowlisting.

Home DEV smoke: **INCONCLUSIVE**. Local `.env` has development tracing and a configured
OpenRouter key, but no operator-designated Home DEV Observation or approved no-knowledge
condition was available in this repository context. No live provider run was launched;
no trace content or secrets were recorded here.

Scope/normative concern: none. Upstream-reference wording is prompt-semantics-only; no
Log or reasoning provenance contract support was added.

Atomic commit: recorded in the Coordinator handoff response.

Shared knowledge candidates: none.
