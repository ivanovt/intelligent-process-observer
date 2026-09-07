## Context

See `proposal.md` for motivation and `specs/report-generation/spec.md` for the behavioral contract. The backend already owns the strict immutable `ObservationAnalysisResult` 1.0 contract, PydanticAI adapters behind framework-neutral ports, safe typed agent outcomes, OpenRouter composition, and a persistence input for Markdown reports. It does not yet own an in-memory `ObservationReport` domain artifact or a presentation-only execution boundary.

Report generation is unusually sensitive to boundary drift: an unconstrained free-form model response could silently omit source material or turn a possible hypothesis into a confirmed cause. The implementation therefore needs a narrow intermediate contract and deterministic membership checks while still allowing the Report Agent to organize and translate supplied content into readable English.

## Goals / Non-Goals

**Goals:**

- Add a small `app.reporting` capability with strict immutable framework-neutral request, completion, artifact, outcome, and failure contracts.
- Permit presentation-level English wording while preserving the complete analytical membership, item types, certainty, identities, and traceability of the source result.
- Make one bounded, tool-free PydanticAI invocation and render validated structured presentation data into Markdown deterministically.
- Produce an in-memory report compatible with the existing persistence envelope without performing persistence.

**Non-Goals:**

- Prove arbitrary prose semantic equivalence with a second model or heuristic classifier.
- Fix a permanent Markdown heading sequence or introduce engineer/operator report variants.
- Add report retrieval, new analysis, recommendations, rendering adapters, localization infrastructure, persistence coordination, runtime lifecycle handling, HTTP endpoints, or frontend behavior.
- Change `ObservationAnalysisResult`, the runtime persistence schema, or existing reasoning execution.

## Decisions

### 1. Add a dedicated reporting module with a framework-neutral boundary

Create `app.reporting` with contracts, a port, deterministic validation/rendering, and an executor. `ReportSemanticContext` contains the correlated identity, Observation name, optional description, and optional analytical objective; it deliberately does not reuse `ObservationSemanticContext`, because that reasoning type includes Lens descriptions that the Report Agent must not receive. `ReportGenerationRequest` combines this context with the existing strict `ObservationAnalysisResult`.

`ObservationReport` contains only `observation_id`, `observation_run_id`, `generated_at`, literal `markdown` format, and content. Success and failure use a strict discriminated union. Public classes and interface methods receive concise behavior-focused docstrings.

Alternative considered: reuse the persistence `ObservationReportInput` as the domain output. Rejected because it omits the report's domain identity and would make an infrastructure persistence shape own the generation contract.

Alternative considered: reuse the reasoning semantic context. Rejected because it would expose Lens configuration beyond ADR-085's minimal input boundary.

### 2. Ask the model for a source-keyed presentation draft, not raw Markdown

The PydanticAI adapter receives only the strict report request serialized as data and returns a strict `ReportPresentationDraft`. The draft has:

- one English overall-assessment presentation;
- one source-keyed presentation entry for each finding;
- one source-keyed presentation entry for each hypothesis;
- one position-keyed presentation entry for each limitation.

Each entry can contain only its source key and plain English presentation text. The presentation text is data, not Markdown, and cannot own headings, lists, links, blockquotes, code blocks, or arbitrary document sections. The output has no fields for recommendations, conclusions, new references, confidence, severity, root cause, or arbitrary extra sections. A deterministic validator requires exact, duplicate-free membership against the source result and rejects missing, unknown, or duplicate source keys. It also rejects blank content and an overall-state discriminator that differs from the source. Evidence, finding, and knowledge references are never authored by the model; the renderer restores source ordering independently of draft ordering.

Deterministic validation does not attempt to classify arbitrary prose meaning with a keyword blacklist, language detector, or second model. Presentation-only semantics, English output, meaning preservation, and certainty preservation remain strict agent-instruction and evaluation obligations. This is an explicit boundary of what the one-request structured contract can prove: exact membership and shape are mechanically enforceable, while semantic equivalence of free prose is not.

Alternative considered: let the model return final Markdown. Rejected because deterministic code could not reliably prove that all source items and their traceability survived a free-form response.

Alternative considered: render every source statement verbatim without a model. Rejected because the accepted architecture assigns English narrative organization and presentation to a Report Agent, including presentation-level paraphrasing or translation. The source-keyed draft keeps that role narrow.

### 3. Render the report deterministically from validated presentation plus source data

After draft validation, a pure renderer builds Markdown. It chooses one internal default layout but does not expose headings as a public schema invariant. Only the renderer emits Markdown syntax. It normalizes line breaks and escapes Markdown control characters in every model-authored or source-authored string before inserting that string as plain content. It uses the validated English presentation text for assessment and item narratives, then appends deterministic source identifiers and canonical references directly from `ObservationAnalysisResult`:

- findings retain their IDs and `evidence_refs`;
- hypotheses retain their IDs, `supported_by`, and `knowledge_refs` and are labeled as possible explanations;
- limitations retain their exact code and structured fields.

Empty collections receive restrained absence text derived from the source state, never model-authored filler. The renderer builds the final immutable envelope with identity copied from the result and time supplied by an injected UTC clock. A final strict validation rejects blank content or a non-UTC time.

The final report presents the correlated `observation_id` and `observation_run_id` under deterministic English labels. The raw Observation name, description, and analytical objective remain agent input but are not copied directly into Markdown, because the source values may be non-English or contain document-control syntax. Adding separately declared English presentations for those context fields is outside this correction and would require a future contract decision.

This split makes membership, structure, and traceability mechanically verifiable. Like any single-model paraphrase, preserving meaning inside English prose remains an agent instruction and testable behavioral obligation rather than something a lexical validator can prove for every possible sentence.

Alternative considered: embed references in model-authored Markdown. Rejected because references are structured source-of-truth data and should not be copied or reformatted by a probabilistic component.

Alternative considered: reject semantic drift through a deterministic keyword blacklist. Rejected because paraphrases can express the same prohibited meaning without the listed words, while valid uncertainty-preserving statements can contain those words in a negated form. Such a blacklist creates both false acceptance and false rejection without proving semantic safety.

Alternative considered: invoke a second model as a semantic judge. Rejected because it adds a model request, latency, cost, and another probabilistic failure point while contradicting the one-request execution bound.

### 4. Use one isolated PydanticAI request with no tools and no retry

Add a `ReportGenerationAgent` protocol with one completion method and a PydanticAI implementation under `app.infrastructure.agents`. The adapter uses the existing no-tool wrapper pattern, a typed output, `UsageLimits(request_limit=1)`, `retries=0`, and configured timeout/output-token limits. The system instruction fixes English output, presentation-only semantics, uncertainty preservation, and untrusted-input handling. No tool is registered; any non-output tool call is a policy violation.

The adapter receives an injected PydanticAI `Model` for deterministic tests and framework isolation. Production composition follows the existing private OpenRouter pattern. Add `observation_report_model` with the existing production-agent default `openai/gpt-5.6-terra` and `observation_report_max_output_tokens` with an `8_192` default. Their environment names are `OBSERVATION_REPORT_MODEL` and `OBSERVATION_REPORT_MAX_OUTPUT_TOKENS`. Reuse the shared credential, request timeout, fallback, and provider-order policy. Update `.env.example`; no secret or dependency change is required.

Alternative considered: reuse the `observation_reasoning_model` setting directly. Rejected because report presentation and reasoning are separate roles under ADR-050 and should be independently configurable without renaming or changing the accepted reasoning setting.

### 5. Validate before invocation and normalize failures after it

The executor first validates strict input and exact identity correlation. It then performs the single agent call, validates exact draft membership, renders the report, and returns success. It catches timeout, PydanticAI request-limit/unexpected-output signals, reporting policy violations, validation errors, and other model exceptions into the fixed safe failure union. Request validation and report building use `report_result_invalid`; model-policy failures use `report_policy_violated`. Caller `asyncio.CancelledError` always propagates.

No exception string, prompt, request payload, partial Markdown, provider response, or model reasoning crosses the public boundary. Logging, if later connected by the caller, is outside this contract and must remain secret-safe.

Alternative considered: fall back to a deterministic bare report after model failure. Rejected because the spec requires fail-closed semantics and a fallback would create a second, unapproved presentation path.

### 6. Keep persistence and runtime integration outside this slice

The capability returns only an in-memory `ObservationReport`. Tests may demonstrate exact projection of `generated_at`, `format`, and `content` to the existing persistence `ObservationReportInput`; Observation and run identity remain on the domain report and are supplied separately through the repository's run/source-analysis correlation boundary. The executor does not open a transaction or call the repository. The later top-level Observation execution feature owns invocation order, identity correlation, persistence, and lifecycle completion.

Alternative considered: persist automatically on generation success. Rejected because it would couple a side-effect-free presentation capability to runtime transaction and lifecycle semantics outside this roadmap item.

## Risks / Trade-offs

- **[A model can introduce subtle meaning drift inside an otherwise valid source-keyed paraphrase]** → Keep one narrow presentation field per source item, preserve identifiers and references deterministically, strongly instruct against new claims or certainty, and cover representative certainty/grounding violations at the agent evaluation boundary. Do not claim lexical runtime proof of semantic equivalence.
- **[English-only output may require translating future non-English source statements]** → Treat source statements as agent input for English presentation, retain source IDs and references, and render correlated Observation/run IDs instead of copying untranslated semantic-context prose; localization remains deferred.
- **[Untrusted text can contain Markdown control syntax]** → Treat all dynamic strings as plain content, normalize line breaks, escape Markdown controls, and let deterministic renderer-owned constants provide the entire document structure.
- **[A default Markdown layout may become mistaken for a permanent contract]** → Test semantic sections and source coverage rather than exact full-document snapshots or fixed heading order.
- **[Model output length grows with large analysis results]** → Keep a configurable output-token ceiling and fail closed on truncation/invalid typed output; pagination and report splitting are outside MVP scope.
- **[New report-specific settings enlarge configuration slightly]** → Reuse all shared OpenRouter routing and timeout settings and add only `observation_report_model="openai/gpt-5.6-terra"` and `observation_report_max_output_tokens=8_192` defaults.

## Migration Plan

1. Add the reporting contracts and pure validation/renderer without changing existing modules' behavior.
2. Add the PydanticAI adapter, report settings, and private OpenRouter composition.
3. Verify compatibility with the existing persistence input through tests only.
4. Deploy as an unused internal capability until a later approved Observation execution change composes it.

Rollback removes the isolated reporting module, adapter, composition functions, settings, and tests. No database or stored-data rollback is required.

## Architecture References

- `docs/architecture/06_runtime_contracts_and_execution_semantics.md`, section 9: the design accepts only the approved inputs and returns the approved Markdown artifact.
- `docs/architecture/08_observation_analysis_result_contract.md`: the renderer preserves the exact result identity, analytical item types, and three traceability relations.
- `docs/architecture/09_report_agent.md`: the source-keyed draft implements narrative presentation while excluding raw evidence, retrieval, new analysis, recommendations, and expanded scope.
- ADR-050: reporting remains separate from Observation reasoning.
- ADR-085: the dedicated report context excludes Lens results and full configuration.
- ADR-086: the output is a minimal Markdown envelope, not a complex report schema.
- ADR-087: the port exposes no retrieval or analysis capability.
- ADR-152: PydanticAI remains an infrastructure adapter behind domain-owned contracts and limits.
- `docs/architecture/10_open_decisions_and_backlog.md`, section 6: this design does not close template-variant or rendering/notification decisions; only English output is fixed by the user's decision for this change.
