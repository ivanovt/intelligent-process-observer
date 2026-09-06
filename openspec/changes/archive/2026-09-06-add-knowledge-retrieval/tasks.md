## 1. Retrieval Contracts and Boundary

- [x] 1.1 Create the `app.knowledge` package and strict immutable request, refinement, knowledge-reference, retrieved-item, outcome, rejection, and attempt-ledger contracts with concise public docstrings, distinct submission/execution ordinals, fixed safe diagnostic codes, and invariants from the `knowledge-retrieval` spec.
- [x] 1.2 Define the asynchronous framework-neutral retriever protocol that accepts only the grounded retrieval request and returns a validated zero-or-more-item batch, with concise purpose-focused docstrings for both the public protocol and its public method.

## 2. Bounded Retrieval Execution

- [x] 2.1 Implement the run-scoped retrieval executor bound to a non-empty immutable frozen-finding set, including isolated state, a fixed two-executed-call budget, and first-match admission precedence `over_budget`, `concurrent`, `unknown_finding`, then `invalid_refinement`.
- [x] 2.2 Implement second-call refinement as an implicit link to executed-call ordinal 1, permit an independent non-refinement second call, and atomically reject invalid refinement or concurrent calls without automatic query rewriting or semantic sufficiency classification.
- [x] 2.3 Normalize successful empty/item batches, timeouts, other failures, invalid retriever returns, and rejected requests into typed outcomes with fixed non-disclosing diagnostic codes and an immutable metadata-only ledger containing exactly the fields allowed by the spec.
- [x] 2.4 Propagate caller task cancellation unchanged while retaining the started call's consumed slot, releasing active-call state in cancellation-safe cleanup, omitting the incomplete ledger entry, and never reusing its reserved ordinals.

## 3. Focused Verification

- [x] 3.1 Add contract tests for strict/frozen validation, non-empty query/finding/provenance fields, opaque reference preservation, exact outcome variants, fixed diagnostic codes, distinct ordinals, and absence of agent/provider framework types.
- [x] 3.2 Add executor tests for valid frozen-finding grounding, two-call budgeting, slot consumption after empty/failure/timeout outcomes, per-session isolation, and combined-rule rejection precedence across budget, concurrency, finding scope, and refinement validity.
- [x] 3.3 Add boundary tests proving executor admission validates only shared finding IDs, exposes no Log-specific subject-validation claim, and leaves concrete template/error-code/message/terminology validation to a future Log consumer.
- [x] 3.4 Add deterministic async tests for rejection before execution, refinement linked to executed-call ordinal 1, an independent second call, invalid refinement, overlapping-call rejection, invalid retriever returns, ordinal gaps, exact ledger fields, and absence of persistence or analytical side effects.
- [x] 3.5 Add security tests with sentinel credentials, query text, unresolved-gap text, retrieved statements, document text, and provider details, proving outcomes and ledger entries expose only permitted fixed codes, structural metadata, and retrieved references.
- [x] 3.6 Add a focused caller-cancellation test proving unchanged cancellation propagation, consumed-slot retention, active-guard release, omitted ledger entry, non-reused ordinals, and successful admission of one remaining call without asserting broader runtime lifecycle behavior.
- [x] 3.7 Run focused backend tests, Ruff linting, and Ruff formatting checks for the new capability and resolve all failures.

## 4. Final Validation

- [x] 4.1 Run `make check` and report any failures accurately before archive or pull-request work.
