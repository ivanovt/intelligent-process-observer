## 1. Reporting Contracts and Input Boundary

- [x] 1.1 Create the `app.reporting` package with strict immutable framework-neutral contracts for minimal correlated semantic context, report request, source-keyed presentation entries/draft, the minimal Markdown `ObservationReport` envelope, typed success/failure outcomes, and an internal policy-violation signal; add concise public class and interface docstrings and reject unknown fields.
- [x] 1.2 Implement pre-invocation request validation that accepts only the analysis result plus name/optional description/objective context, enforces matching Observation/run identity, and rejects malformed or expanded inputs before calling the agent.
- [x] 1.3 Add contract and input tests for strict serialization, unknown-field rejection, identity mismatch, minimal optional context, immutable source preservation, literal Markdown format, no report schema version, and UTC generated-time validation.

## 2. Deterministic Presentation Validation and Markdown Rendering

- [x] 2.1 Implement exact source-membership validation for the structured presentation draft: unchanged overall state, non-blank presentation fields, and duplicate-free exact finding IDs, hypothesis IDs, and positional limitation keys, independent of model-returned ordering; keep English-language behavior at the agent contract and evaluation boundary rather than adding a heuristic language detector.
- [x] 2.2 Implement the pure Markdown renderer and report builder that restore source ordering, copy identity and injected UTC time, render readable assessment/findings/possible explanations/limitations, attach evidence/finding/knowledge references deterministically from `ObservationAnalysisResult`, and use deterministic absence text for empty collections.
- [x] 2.3 Add validator and renderer tests covering populated and empty collections, `uncertain` with findings, all three traceability relations, reordered valid draft entries, presentation-level English translation, flexible headings, and exact source-item coverage without mutating the input.
- [x] 2.4 Add negative tests for missing, unknown, and duplicate source keys; altered overall state; blank presentation; undeclared structured recommendation/root-cause fields or sections; invented references or analytical items; invalid/non-UTC clock values; and partial output rejection.

## 3. Bounded Report Execution

- [x] 3.1 Define the framework-neutral `ReportGenerationAgent` protocol with one typed presentation-completion method and implement the side-effect-free executor that validates input, invokes the agent once, validates the draft, renders the report, and returns the strict success union.
- [x] 3.2 Normalize timeout, request-limit exhaustion, tool-policy violations, unexpected/invalid model output, request validation failure, report build failure, and other model exceptions into the approved fixed safe failure codes/components with no partial report or diagnostic leakage.
- [x] 3.3 Add executor tests for success, each failure mapping, no invocation after invalid input, no fallback output, exception/prompt/input secrecy, exact one-call behavior, and unchanged propagation of caller cancellation.

## 4. PydanticAI and OpenRouter Integration

- [x] 4.1 Implement the PydanticAI report adapter with injected model, strict typed `ReportPresentationDraft` output, no registered tools, non-output tool-call rejection, no retries, one-request usage limit, configured timeout/output-token limits, and an English presentation-only system instruction that treats all supplied text as untrusted data.
- [x] 4.2 Add `observation_report_model="openai/gpt-5.6-terra"` and `observation_report_max_output_tokens=8_192`, document `OBSERVATION_REPORT_MODEL` and `OBSERVATION_REPORT_MAX_OUTPUT_TOKENS` in `.env.example`, and add private OpenRouter model/agent composition that reuses the existing credential, timeout, fallback, and provider-order policy without changing dependencies.
- [x] 4.3 Add adapter tests proving strict typed translation, one request and zero tools, no retry, request/token settings, instruction-like input isolation, policy rejection for attempted tools or undeclared output, model exception/timeout propagation, and cancellation behavior.
- [x] 4.4 Add settings and composition tests for defaults, environment overrides, missing credentials, secret-safe failure, and exact reuse of shared OpenRouter routing policy.

## 5. Integration and Verification

- [x] 5.1 Add one representative in-memory integration test from correlated semantic context and a populated `ObservationAnalysisResult` through a scripted presentation completion to strict English Markdown, including uncertainty, findings, possible hypotheses, limitations, and deterministic evidence/finding/knowledge references.
- [x] 5.2 Add integration coverage for `no_significant_findings` with empty findings/hypotheses; verify exact projection of report time, format, and content into the existing `ObservationReportInput` while retaining Observation/run identity for the repository's separate correlation boundary, without calling persistence or changing runtime lifecycle.
- [x] 5.3 Run focused backend reporting tests and Ruff checks, then run `make check`; report failures accurately and leave archive, Observation execution integration, and pull-request actions for their separately approved workflow steps.

## 6. Presentation-Boundary Correction

- [ ] 6.1 Remove lexical semantic and partial Markdown-syntax blacklists from runtime validation; retain strict non-blank and exact source-membership validation, and make the deterministic renderer normalize line breaks and escape every model-authored or source-authored value so only renderer constants can create Markdown structure.
- [ ] 6.2 Render the correlated Observation and run identifiers with deterministic English labels, and stop copying raw Observation name, description, or analytical-objective text into the final Markdown when no declared English context-presentation field exists.
- [ ] 6.3 Replace blacklist-oriented tests with focused coverage for escaped Markdown/control input, harmless negated boundary language, structurally undeclared fields and items, non-English semantic context exclusion, renderer-owned headings, and agent-instruction/evaluation examples for recommendations, causal overstatement, certainty preservation, and English presentation.
- [ ] 6.4 Run focused reporting tests and Ruff checks, run `make check`, and re-run bounded finding verification plus the repository implementation review before archive consideration.
