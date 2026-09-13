## 1. Persistence and dependencies

- [x] 1.1 Replace local Compose and CI PostgreSQL images with pinned `pgvector/pgvector:0.8.6-pg18-bookworm`; verify `CREATE EXTENSION vector` succeeds in both environments before migration tests run.
- [x] 1.2 Add user-approved `pypdf>=6,<7` and `pgvector>=0.4,<1` backend dependencies plus server-only embedding, ingestion, retrieval, and scope-suggestion settings; verify dependency resolution and settings validation tests pass.
- [x] 1.3 Create an Alembic migration that enables PostgreSQL `vector`, stores immutable knowledge documents/versions/service tags/chunks and optional Observation knowledge scope, and preserves existing unscoped definitions; verify upgrade, empty-corpus/unscoped downgrade and re-upgrade, and downgrade refusal with retained records or non-null scope while the Alembic revision stays unchanged.
- [x] 1.4 Implement strict framework-neutral knowledge-management and knowledge-scope contracts with repository persistence and a partial unique approved-version index; verify unit/integration tests cover validation, duplicate-version rejection, one-approved-version behavior, and deprecation.

## 2. Manual document ingestion and management API

- [x] 2.1 Implement PDF and Markdown upload/version endpoints that commit original bytes, hash, metadata, and imported identity before extraction; verify API tests cover supported formats, disguised PDF, invalid UTF-8 Markdown, upload limits, and durable retention before extraction starts.
- [x] 2.2 Implement post-upload extraction and an explicit retry-extraction endpoint with separate `pending|ready|failed` state, per-version active-attempt exclusion, and durable attempt UUID fencing; verify image-only PDFs remain retained, restart leaves interrupted pending work retryable, overlapping retries are rejected, late superseded completions cannot overwrite newer results, no automatic retry runs, and an approved version is never displaced.
- [x] 2.3 Implement explicit approval/deprecation, list/detail/version-history, exact version-chunk lookup, and retained-source attachment endpoints with publish-on-approval semantics; verify approval requires ready extraction, integration tests preserve an earlier approved version on failure, serialize concurrent approvals/deprecations with safe 409 conflicts, resolve historical chunk metadata without substitution, and enforce attachment, inert content type, safe filename, and `nosniff` headers on direct navigation.
- [x] 2.4 Build the derived approved-service catalog from version tags and aliases; verify tests cover catalog union, alias ambiguity, and tag removal after deprecation.

## 3. Indexed retrieval and production composition

- [x] 3.1 Implement OpenRouter embedding infrastructure using server-only `openai/text-embedding-3-small` defaults and pgvector/Psycopg integration; disclose external approved-document and bounded retrieval-query processing in the approval confirmation and verify batched embedding, dimension validation, redacted failures, disclosure, and no-startup-failure fallback tests.
- [x] 3.2 Implement immutable curated reference construction using document/version identity and PDF page-local or Markdown document-local chunk ordinals, plus metadata-first hybrid PostgreSQL full-text/pgvector retrieval with server-owned lexical/semantic admission thresholds before rank fusion; enforce at most four whole passages and 8,192 UTF-8 bytes of complete serialized model-visible output per call, and verify duplicate Markdown headings, heading-free PDFs, scoped service with no version admitting versioned tags, global eligibility, exact version filtering when supplied, excluded services, unrelated queries returning empty, byte/count boundaries without truncation, and exact historical reference resolution.
- [ ] 3.3 Compose a run-scoped curated retriever behind the existing `KnowledgeRetriever` port while retaining the safe composition-time empty fallback; enforce one 30-second deadline across admitted query embedding, search, ranking, and serialization, and verify Observation Reasoning integration tests prove retrieved knowledge can ground a hypothesis, the frozen scope filters retrieval, finding/overall-state model payloads exclude knowledge scope, and admitted embedding/database timeout/failure yields distinct existing `timed_out`/`failed` outcomes rather than successful empty batches.

## 4. Observation scope and LLM assistance

- [x] 4.1 Extend Observation Definition create/replacement/read persistence and a separate run-frozen retriever-only scope carrier with optional knowledge scope, without altering Lens/Relationship semantics or existing `ObservationSemanticContext`; verify API and execution snapshot compatibility tests for scoped and legacy unscoped definitions.
- [x] 4.2 Implement the explicit server-side typed LLM scope-suggestion operation using only draft semantic text and the approved service catalog; verify tests reject invented IDs, return safe empty/unavailable outcomes, expose no corpus/provider diagnostics, and perform no persistence.
- [x] 4.3 Add the optional Knowledge scope draft/review UI and its labelled explicit Lucide `Sparkles` suggestion action; verify frontend tests cover acceptance, rejection, empty/failure, abort/stale-response handling, and no automatic request during editing.

## 5. Knowledge Administration UI and documentation

- [x] 5.1 Add a Knowledge Administration route, navigation item, upload/metadata form, document list/detail/version lifecycle controls, and accessible confirmation/empty/error states; make recognized run Analysis knowledge references navigate to the exact historical version/chunk while unknown references remain inert, and verify frontend tests cover PDF/Markdown-only input, imported versus approved visibility, citation navigation after newer approval, and no external-sync/editor/role controls.
- [x] 5.2 Record ADR-173 and synchronize architecture/UI direction/backlog documents with the approved pgvector, manual corpus, knowledge-scope, and bounded knowledge-only boundaries; verify documentation references are internally consistent.

## 6. Integrated verification

- [ ] 6.1 Add end-to-end coverage for upload → approve → scoped run retrieval → persisted cited hypothesis → exact historical chunk/source inspection after a newer version is approved, and for unavailable/empty/failure retrieval outcomes; verify no recommendation, causal finding, or sensitive content reaches public contracts.
- [ ] 6.2 Run `make check` and `openspec validate add-curated-knowledge-retrieval --strict`; resolve all failures before requesting implementation review.
