## Context

See [proposal.md](proposal.md) for the motivation. Production currently composes an
`EmptyKnowledgeRetriever`, although the accepted reasoning workflow already has a bounded,
framework-neutral retrieval port, frozen-finding grounding, and provenance validation. PostgreSQL
is the workspace's approved database; the architecture previously left a real retriever, vector
store, ingestion, and knowledge scope open.

The new corpus must make approved PDF/Markdown operational knowledge durable and searchable without
weakening the finding-before-knowledge boundary. It also introduces a meaningful frontend workflow,
but remains within the existing trusted, unauthenticated MVP deployment boundary.

## Goals / Non-Goals

**Goals:**

- Retain source bytes and immutable, auditable document versions in PostgreSQL.
- Manually upload, review, approve, deprecate, and search only approved PDF/Markdown knowledge.
- Use hybrid lexical/vector retrieval filtered by explicit Observation knowledge scope, with exact
  source-version and page/heading provenance.
- Let operators explicitly request a constrained LLM scope suggestion from the approved service
  catalog and accept it into an Observation draft.

**Non-Goals:**

- External URLs, Confluence/Word connectors, schedules, webhooks, automated source sync, or a
  browser document editor.
- Authentication, authorization, person-level audit attribution, multi-tenant isolation, or
  public-network exposure.
- Log Lens work, recommendations, causal findings, reranking agents, automatic scope application,
  arbitrary corpus chat, or new provider/Observation data acquisition.

## Decisions

### PostgreSQL owns document durability and pgvector is its derived retrieval index

Add an Alembic migration that enables `vector` and creates explicit persistence records:

```text
knowledge_documents
  └─ stable identity and document-level creation metadata
knowledge_document_versions
  └─ document ID, positive version, title/type/authority/owner, optional canonical source reference,
     original bytes/media type/hash, derived extracted text/extraction state, lifecycle and timestamps
knowledge_document_service_tags
  └─ document-version ID, canonical service ID, aliases[], supported version labels[]
knowledge_chunks
  └─ document-version ID, immutable ordinal, PDF page + page-local ordinal or Markdown
     document-local ordinal + retained heading path, extracted text,
     PostgreSQL full-text projection, vector(1536)
```

The binary payload and normalized text are durable source artifacts; chunks, lexical projections,
and embeddings are derived data. Version records are immutable. An approved version is not
overwritten: a later approval atomically publishes its chunks and deprecates the earlier approved
version. The original binary/snapshot remains available for future re-extraction and historical
provenance. A partial unique index on approved document versions enforces at most one approved
version per document. Approval/deprecation publication locks the document row and checks that its
approved-version identity still matches the state observed when the action began; a stale contender
returns HTTP 409 and its prepared chunks remain unpublished. Embedding work may occur outside the
publication transaction, but publication and lifecycle state changes commit together.

PostgreSQL plus pgvector is selected over a separate vector service because it preserves the
existing modular-monolith deployment and backup model. `pgvector>=0.4,<1` supplies SQLAlchemy and
Psycopg type integration. Local Compose and CI replace `postgres:18-alpine` with the pinned
`pgvector/pgvector:0.8.6-pg18-bookworm` image, and tests verify `CREATE EXTENSION vector` before
the migration runs. Production must provide an equivalent PostgreSQL 18 + pgvector capability. A
deployment whose PostgreSQL role cannot create the extension fails migration visibly rather than
silently falling back to non-vector retrieval.

### Manual PDF/Markdown ingestion is a staged, publish-on-approval process

`POST /api/v1/knowledge/documents` creates a document and imported version; a version upload path
adds a later immutable version. Requests are multipart with an uploaded PDF/Markdown file and
strict JSON metadata. Upload admission validates the declared/filename type against bounded content
checks (PDF signature, valid UTF-8 Markdown), size, metadata, and duplicate hash, then durably
commits the original bytes and imported version before extraction begins. A missing PDF text layer
or parser failure is an extraction outcome, not an upload rejection. A disguised file with no PDF
signature or invalid Markdown encoding fails upload admission. Extraction runs once after upload;
an operator can explicitly retry a failed attempt through the version action. No automatic retry
is scheduled. Each version stores a current extraction-attempt UUID and state. A nonblocking
PostgreSQL per-version advisory lock admits one active attempt across requests/processes; a held
lock rejects an overlapping retry. If an earlier process dies, its lock releases while its persisted
state may remain `pending`, so the operator can explicitly claim a new attempt UUID. Completion
updates derived text and `pending|ready|failed` state only with a compare-and-swap on that current
UUID. A late completion from a superseded attempt cannot overwrite the retry's result. Markdown
extraction preserves heading paths; PDF extraction uses `pypdf>=6,<7` page by page. Each bounded
attempt changes only derived extraction data, never immutable source bytes/version identity.

Imported versions are retained and inspectable but non-searchable. Explicit approval requires
`ready` extraction, revalidates stored text, then performs deterministic chunking, batched
embedding, and index publication. Extraction or indexing failure leaves the imported version
non-searchable and preserves the existing approved version. A structurally valid image-only PDF
remains available for a later explicit retry, but without OCR it may continue to have no usable
text. Deprecation
removes a version from eligibility but not historical storage. Upload size and ingestion
extraction/embedding-batch safety limits are positive server-owned operational settings. They are
separate from the fixed retrieval-output and full-call limits below and are not browser
configurable.

The initial REST surface is deliberately small:

```text
GET  /api/v1/knowledge/documents
POST /api/v1/knowledge/documents
GET  /api/v1/knowledge/documents/{document_id}
POST /api/v1/knowledge/documents/{document_id}/versions
POST /api/v1/knowledge/documents/{document_id}/versions/{version}/retry-extraction
POST /api/v1/knowledge/documents/{document_id}/versions/{version}/approve
POST /api/v1/knowledge/documents/{document_id}/versions/{version}/deprecate
GET  /api/v1/knowledge/documents/{document_id}/versions/{version}/source
GET  /api/v1/knowledge/documents/{document_id}/versions/{version}/chunks/{ordinal}
POST /api/v1/knowledge/scope-suggestion
```

All endpoints are restricted only by ADR-170's trusted deployment boundary for this MVP; no endpoint
pretends to attribute an action to an authenticated user. The source endpoint returns exact retained
bytes as `application/octet-stream`, with `Content-Disposition: attachment`, a generated safe
filename, and `X-Content-Type-Options: nosniff`. It never renders uploaded content inline or
redirects a historical citation to the active version.

### Service catalog is an approved-version projection, not a second aggregate

Each document-version service tag supplies canonical service identity, aliases, and optional opaque
version labels. The service catalog is derived by union over approved versions only. This avoids
duplicated service ownership and lets deprecation automatically withdraw a unique tag. Conflicting
aliases remain ambiguous rather than being normalized or reassigned.

`ObservationDefinition` gains an optional `knowledge_scope` JSONB projection with service IDs and
one optional opaque version label. It is persisted with definition replacement/create and frozen
at run initialization in a retriever-only scope carrier, separate from the existing
`ObservationSemanticContext`. When the reasoning executor creates a retrieval session, it binds a
retriever instance to that frozen scope without adding a field to the public
`KnowledgeRetrievalRequest` or exposing the scope to finding or overall-state model invocations.
When absent, only globally applicable knowledge is eligible. Scope changes do not change Lens
identity, history, runtime data acquisition, Relationship evaluation, or the evidence catalog.

### Hybrid retrieval is metadata-first and preserves the framework-neutral port

The concrete retriever is an infrastructure adapter behind `KnowledgeRetriever`. Its run-bound
instance receives the frozen retriever-only scope; domain retrieval request and result contracts
remain unchanged. Eligibility filtering happens before search:

```text
approved active version
AND (
  global tag
  OR (
    matching Observation service ID
    AND (Observation scope has no version OR tag is unversioned OR tag contains exact scope version)
  )
)
```

If the Observation has no knowledge scope, only the global branch applies. A service scope without
a version admits all matching service tags regardless of their version labels; a specified version
narrows only versioned matching tags. Global documents remain eligible in both cases.

It embeds the admitted query through OpenRouter's embeddings API using the server-only default
`openai/text-embedding-3-small` at 1,536 dimensions. Approval confirmation explicitly discloses
that extracted approved document text and later bounded finding-grounded retrieval queries are
externally processed by OpenRouter; original binary, raw telemetry, and provider payloads are not
embedding input. It combines PostgreSQL full-text candidates
and pgvector cosine-similarity candidates through deterministic reciprocal-rank fusion. Before
fusion, candidates must pass an admission rule: a positive normalized full-text match above a
server-owned minimum rank, or cosine distance at or below a calibrated server-owned maximum. An
ineligible nearest vector neighbor is discarded even if it ranks first; no admitted candidate
returns an empty batch. Thresholds and query normalization are fixed by server configuration and
evaluated against positive and unrelated-query fixtures. The retriever returns only a bounded set
of admitted source text passages. `pypdf` extraction and retrieved text are untrusted data;
they never alter agent instructions, finding formation, or overall state.

Per admitted call, select at most four whole ranked passages while keeping the complete serialized
model-visible result (statements and references included) within 8,192 UTF-8 bytes. The chunker
bounds each approved item so one whole item can fit; selection never truncates a passage to fit.
Use one 30-second deadline across query embedding, PostgreSQL search, ranking, and serialization,
and surface expiration as `TimeoutError` for the existing bounded retrieval executor. This byte
bound is the MVP's enforceable context-size policy; no tokenizer-specific count is required.
The existing maximum of two sequential calls is unchanged.

The concrete corpus uses the existing opaque `KnowledgeReference` pair without changing its domain
contract. `source_id` is `knowledge-document:<document-uuid>:v<positive-version>` and `reference`
is either `pdf:page:<one-based-page>:chunk:<one-based-page-local-ordinal>` or
`md:chunk:<one-based-document-local-ordinal>`. The approved chunk snapshot stores the exact
extracted text and the PDF page or Markdown heading path. A PDF's page-local ordinal is assigned
in extraction order even when no heading can be identified; guessed PDF section headings never
become citation identity. The version and chunk metadata remain immutable after approval, so
citations continue to resolve after later approvals. The version chunk endpoint resolves the
reference to inert text and source-location metadata, while the existing source endpoint provides
the exact original attachment. This grammar is private to the curated-corpus adapter; other opaque
knowledge references remain valid under the framework-neutral contract.

The existing result validator remains the only authority permitting a cited hypothesis. A
completed search with no admitted relevant passage returns a valid empty batch. Only
composition-time unavailability uses the explicit empty retriever. During an admitted search,
embedding timeout propagates as `TimeoutError` to the bounded retrieval executor and becomes its
existing `timed_out` outcome; embedding, database, or index errors propagate as failures and become
the existing `failed` outcome. Neither is normalized to a successful empty batch or allowed to
prevent application startup.

### Scope suggestion is explicit, typed, and corpus-blind

The frontend adds an optional Knowledge scope section to the aggregate draft and a labelled Lucide
`Sparkles` control. Clicking it sends only current draft name, description, objective, and Lens
names/descriptions. The server derives the approved service catalog and calls a dedicated typed
PydanticAI suggestion adapter through the existing OpenRouter credential. The default suggestion
model is the existing reasoning default, `openai/gpt-5.6-terra`, with a separate server-only
setting so it can be changed later without altering contracts.

The typed response is a deduplicated subset of supplied catalog IDs or empty. It has no rationale,
confidence, probability, version, findings, or recommendations. The model receives neither chunks
nor document text. The UI binds the response to its initiating draft revision, discards stale
responses, and requires an explicit acceptance before changing the local draft. Model failures
produce a safe no-suggestion state and no automatic retry.

### UI placement preserves the existing application shell

Add Knowledge Administration as one application route beside existing operational functionality,
not a separate Admin application. Use the project-owned page/header/panel/form patterns and the
existing React/Tailwind/Base UI/Lucide stack. The document list is lightweight; the detail page
shows metadata, immutable version history, extraction/index state, and explicit actions. A
recognized curated-corpus knowledge reference in a persisted run Analysis view links to this route
with exact document/version/chunk selection; the detail view loads the retained chunk, shows its
page or heading location and passage as inert text, and offers the original attachment. Unknown or
unresolvable references remain visible without fabricated links. The view does not render uploaded
documents as active content or expose raw agent traces/provider diagnostics.

## Risks / Trade-offs

- [Untrusted document text can contain prompt-injection-like content] → Treat it as data at every
  extraction, retrieval, and agent boundary; only source text plus provenance reaches hypotheses.
- [A PDF has no usable text layer] → Retain the imported original with failed extraction status,
  expose an explicit retry action, and keep approval unavailable until extraction succeeds; OCR
  is deferred.
- [Embedding/provider cost, outage, or data disclosure] → Explicitly confirm before approval that
  OpenRouter processes approved document text and bounded finding-grounded retrieval queries; use
  bounded batches and server-only limits; failed ingestion is non-publishing and failed retrieval
  is non-fatal.
- [A service tag is wrong or aliases conflict] → Require operator-entered metadata; scope is
  explicit, suggestions are advisory/catalog-constrained, and ambiguous aliases do not auto-select.
- [PostgreSQL storage grows] → Keep limits server-owned and retain only the MVP corpus; object
  storage/retention policy is a later architecture change.
- [Unauthenticated upload/deprecation can be destructive in an exposed deployment] → ADR-170
  confines the entire MVP to trusted local/internal operation; authentication is explicitly out of
  scope.

## Migration Plan

1. Replace the local Compose and CI PostgreSQL image with pinned
   `pgvector/pgvector:0.8.6-pg18-bookworm` and verify the extension is available.
2. Add approved Python dependencies (`pypdf>=6,<7`, `pgvector>=0.4,<1`) and settings for
   OpenRouter embeddings, ingestion/retrieval bounds, and the suggestion role.
3. Apply an Alembic migration that enables pgvector and creates document, version, tag, chunk, and
   Observation knowledge-scope storage. Existing Observation definitions remain valid and unscoped.
4. Deploy APIs/UI and production composition. Until an operator imports and approves knowledge,
   retrieval continues to return empty valid batches.
5. Operators upload and approve initial documents manually; an approved version creates the only
   searchable index entries.
6. Roll back application code independently while leaving the additive database schema at its
   current Alembic revision; the earlier application ignores the extra nullable scope column and
   knowledge tables. The migration downgrade refuses to run while any retained knowledge record
   or non-null Observation knowledge scope exists, leaving both schema and Alembic revision
   unchanged. Only when both are empty may a tested downgrade remove the new schema objects;
   re-upgrade must succeed. Never mark the revision downgraded while retaining its tables or
   vector column.

## Architecture References

- `docs/architecture/02_architecture_principles_and_runtime.md`: findings remain frozen before
  bounded knowledge retrieval and Report remains presentation-only.
- `docs/architecture/07_observation_reasoning_agent.md` and
  `08_observation_analysis_result_contract.md`: hypotheses require findings plus provenance;
  knowledge cannot become finding evidence.
- `docs/architecture/03_ADR_log.md`: ADR-152 keeps PydanticAI/framework-neutral boundaries;
  ADR-169 supplies OpenRouter composition; ADR-170 confines unauthenticated operation to a trusted
  deployment.
- `docs/architecture/10_open_decisions_and_backlog.md`: this change resolves the concrete
  Observation-level corpus/retriever backend, while later source connectors and retention policy
  remain outside the MVP.
- `docs/ui/frontend_ui_stack_adr.md` and `docs/ui/ui_implementation_handoff_v1.md`: retain one
  application shell, project-owned semantics, and the evidence/knowledge distinction.
