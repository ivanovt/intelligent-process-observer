# Validated Project Knowledge

Purpose: compact, high-signal operational knowledge that is reusable across future agent work but is not itself a normative source of requirements or architecture.

Authority: accepted ADRs, normative architecture/contracts, approved OpenSpec, and repository governance outrank this file.

Only the Implementation Coordinator may promote validated entries during the slice workflow. Do not add speculation, task status, full review reports, duplicated documentation, or unresolved decisions.

## Entries

### PK-001 — PydanticAI rejected-call continuation
Category: framework
Scope: injected Alert adapter tool-call translation
Knowledge: Framework-level rejection of unknown or no-argument tool calls can occur before
the registered handler; preserve domain ledger semantics by normalizing only framework
dispatch after the domain executor records the original request.
Applies when: translating bounded domain tool executors through PydanticAI function tools.
Evidence: `backend/tests/test_pydantic_ai_alerts_adapter.py` VS-08 deterministic-model proofs.

<!-- Example shape:
### PK-001 — Short title
Category: testing | repository | framework | workflow | implementation
Scope: ...
Knowledge: ...
Applies when: ...
Evidence: file/symbol/test/review reference
-->
