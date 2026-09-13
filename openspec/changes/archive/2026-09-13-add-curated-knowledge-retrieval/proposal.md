## Why

Observation reports can accurately present evidence but cannot produce traceable possible
explanations while production reasoning is backed by an intentionally empty knowledge
retriever. Operators need a small, durable way to curate approved operational and official
documentation, retrieve relevant passages for frozen findings, and inspect that knowledge
through the existing frontend without broadening observational evidence or automating source
synchronization.

## What Changes

- Add a PostgreSQL-backed curated knowledge corpus that retains immutable uploaded document
  versions, their original PDF or Markdown payloads, extracted searchable text, review metadata,
  and derived pgvector chunks.
- Add manual, upload-only Knowledge Administration APIs and UI for PDF and Markdown sources,
  including metadata entry, retained-upload extraction with operator-initiated retry, import/index
  status, approval, deprecation, and version history.
- Replace the production empty retriever with a bounded, metadata-filtered hybrid retriever over
  approved active document versions. Retrieved passages retain exact document-version/chunk
  references that resolve to PDF page or Markdown heading context for knowledge-grounded
  hypotheses.
- Add an optional, operator-configured Observation knowledge scope (service identities and an
  optional version). Provide an explicit, non-persisting LLM scope suggestion from Observation and
  Lens text plus the derived approved service catalog; the operator must accept or replace it
  before it becomes scope metadata.
- Select pgvector in the existing PostgreSQL deployment as the MVP vector store, without adding a
  separate vector service, automatic synchronization, external source connectors, document
  editing, user authentication, or automated approval.
- Record the accepted knowledge-corpus ownership, persistence, retrieval, and trusted-MVP access
  boundaries in architecture documentation and remove the corresponding retrieval-backend items
  from the architecture backlog.

## Capabilities

### New Capabilities

- `curated-knowledge-management`: Manual PDF/Markdown upload, immutable document-version
  retention, metadata/review lifecycle, pgvector indexing, and local Knowledge Administration UI.
- `curated-knowledge-retriever`: Approved-corpus hybrid retrieval with service applicability
  filtering and stable provenance for the existing framework-neutral knowledge port.
- `knowledge-scope-suggestion`: Explicit, constrained LLM assistance that proposes zero or more
  catalog-backed service IDs for an Observation draft without changing it.

### Modified Capabilities

- `production-agent-composition`: Replace the production empty knowledge retriever with the
  approved curated-corpus retriever while retaining all existing reasoning budgets and grounding
  boundaries.
- `observation-definition-api`: Add optional durable Observation knowledge-scope metadata without
  changing existing Lens, Relationship, or runtime ownership.
- `observation-management-ui`: Add operator-controlled knowledge-scope editing and conservative
  advisory scope suggestions to the Observation draft and review flow.

## Impact

- Affected backend areas: knowledge contracts/adapters, FastAPI routes, PostgreSQL persistence and
  Alembic migrations, production execution composition, settings, and PDF/Markdown extraction.
- Affected frontend areas: application navigation, a new Knowledge Administration feature, and
  API clients/components following the accepted UI stack.
- Infrastructure: enable the PostgreSQL `vector` extension; use the existing OpenRouter credential
  with server-only default embedding model `openai/text-embedding-3-small` (1,536 dimensions); and
  add `pypdf>=6,<7` for PDF extraction plus `pgvector>=0.4,<1` for Psycopg/SQLAlchemy vector type
  support. Local Compose/CI SHALL use the pinned pgvector-enabled PostgreSQL 18 image
  `pgvector/pgvector:0.8.6-pg18-bookworm`. Approved document text and bounded
  finding-grounded retrieval queries are intentionally sent to OpenRouter for embedding; no second
  provider, credential, vector service, or local ML runtime is introduced.
- Architecture: `docs/architecture/03_ADR_log.md`, `02_architecture_principles_and_runtime.md`,
  `07_observation_reasoning_agent.md`, `10_open_decisions_and_backlog.md`, and architecture
  package metadata as applicable.

## Approval status

The architecture updates record decisions the user explicitly approved during planning,
including PostgreSQL/pgvector, the embedding boundary, the manual knowledge lifecycle, and the
Observation-level retrieval bound of four passages, 8 KiB serialized content, and 30 seconds per
call.
After the final independent plan review and the user-approved resolution of its findings, the
user approved this OpenSpec proposal, specifications, design, and tasks for implementation on
2026-09-13. This approval includes the dependency changes explicitly listed above. ADR-173's
`Accepted` status records architecture decisions; this paragraph records the separate human
implementation approval gate. No production implementation has begun.
