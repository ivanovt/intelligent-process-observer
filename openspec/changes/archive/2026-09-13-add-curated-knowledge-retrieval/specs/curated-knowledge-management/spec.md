## Purpose

Provide a durable, operator-managed knowledge corpus from approved PDF and Markdown uploads,
with immutable source versions and a small local administration experience.

## ADDED Requirements

### Requirement: Retain manually uploaded knowledge document versions durably

The system SHALL allow a trusted-MVP operator to create a knowledge document by uploading exactly
one Markdown (`text/markdown` or `.md`) or PDF (`application/pdf` or `.pdf`) file with required
title, document type, authority, owner, and applicability metadata. It SHALL retain the original
uploaded bytes, media type, content hash, submitted metadata, and an immutable positive version
identity in PostgreSQL before extraction runs. Extracted searchable text and extraction outcome
SHALL be stored as derived version data when extraction completes. A document type SHALL be one of
`official_document`, `runbook`, `maintenance_guide`, `incident`, or `operator_journal`; authority
SHALL be one of `official`, `internal_approved`, or `operator_authored`.

Each document version SHALL contain zero or more service applicability tags. A tag SHALL contain a
canonical non-empty service ID, zero or more non-empty aliases, and zero or more opaque supported
version labels. An empty tag collection means globally applicable knowledge. The system SHALL
retain an external/canonical source reference when the operator supplies one, without fetching it.
It SHALL reject unsupported or mislabeled file content, invalid Markdown text encoding, blank
required metadata, invalid tag shapes, or a duplicate content hash for the same document without
replacing any prior version. Filename extensions and client-declared media types alone SHALL not
establish that an upload is a supported PDF or Markdown file. A supported PDF with no extractable
text SHALL be retained as an imported version; lack of extractable text is an extraction failure,
not an upload rejection.

#### Scenario: Import a Markdown runbook
- **GIVEN** an operator uploads a valid Markdown runbook with required metadata and an
  `mprm-server` applicability tag
- **WHEN** the upload is accepted
- **THEN** the system retains the original payload, content hash, metadata, and a new immutable
  imported version before extraction begins
- **AND** successful extraction subsequently stores searchable text on that version
- **AND** the version is not searchable until it is approved

#### Scenario: Retain an image-only PDF for retry
- **GIVEN** a valid uploaded PDF has no extractable text
- **WHEN** upload succeeds and extraction runs
- **THEN** the original file remains retained as an imported version with failed extraction state
- **AND** it cannot be approved unless a later operator-initiated extraction succeeds

#### Scenario: Reject an unsupported upload without altering history
- **GIVEN** a document already has an approved version
- **WHEN** an operator attempts to upload a Word file as its next version
- **THEN** the system rejects the upload as unsupported
- **AND** the approved version and its searchable content remain unchanged

#### Scenario: Reject a disguised file
- **GIVEN** an upload is named `guide.pdf` but its content is not a valid PDF
- **WHEN** the operator submits it
- **THEN** the system rejects it before retaining a new version
- **AND** any existing approved version remains unchanged

### Requirement: Derive the approved service catalog from source metadata

The system SHALL derive its current service catalog from the canonical service IDs and aliases on
approved knowledge document versions. It SHALL not introduce a separate service-catalog CRUD
resource in this MVP. A service ID remains present while at least one approved version declares
it; its catalog aliases are the union of aliases declared by those approved versions. Imported,
deprecated, failed, and unavailable versions SHALL not contribute IDs or aliases.

The catalog is retrieval and advisory metadata, not Observation evidence. Conflicting or
overlapping aliases SHALL remain visible to server-side suggestion logic as ambiguous mappings;
they SHALL not silently select a service scope.

#### Scenario: Remove a deprecated document's unique service tag from the catalog
- **GIVEN** only one approved document declares service ID `legacy-gateway`
- **WHEN** its approved version is deprecated
- **THEN** `legacy-gateway` is absent from the derived service catalog
- **AND** it cannot be proposed by a later scope-suggestion request

### Requirement: Maintain explicit manual review and searchable-version lifecycle

Every successfully retained version SHALL begin as `imported`. A trusted-MVP operator SHALL be
able to retry failed or interrupted extraction explicitly without re-uploading or replacing the
original bytes. A retry while an extraction attempt is still running SHALL be rejected safely.
An imported version SHALL report extraction state `pending`, `ready`, or `failed` separately from
its review lifecycle. Each operator retry SHALL create a new extraction attempt and update only
derived extraction data and state; it SHALL not run automatically. Approval SHALL be available
only for an imported version with `ready` extraction and SHALL validate that stored text before
indexing and publishing its derived retrieval representation atomically. A document SHALL have at most one
`approved` searchable version; approving a later version SHALL make the previous approved version
`deprecated` while retaining it for history and audit. An operator SHALL be able to deprecate an
approved version, after which it SHALL no longer be retrieved. Failed extraction or indexing SHALL
leave the version non-searchable and SHALL not displace a previously approved version.

A successful retry SHALL supersede an interrupted earlier attempt. A completion from any
superseded attempt SHALL be ignored: it SHALL not overwrite the newer extraction text or state,
publish chunks, or make the version approvable. A current running attempt SHALL prevent a
concurrent retry; an abandoned `pending` attempt MAY be retried explicitly after its owner is no
longer active.

Approval and deprecation SHALL serialize per document and enforce at most one approved version in
the database. If another lifecycle action changes that document's approved version while an
approval is preparing its index, the stale action SHALL return a conflict; its candidate version
remains non-searchable and the committed approved version remains authoritative.

The lifecycle is intentionally unauthenticated only within the trusted single-user/internal MVP
boundary. It SHALL not claim a user identity or implement role-management behavior.

#### Scenario: Approve an imported version
- **GIVEN** a document has one imported PDF version with ready extraction and no approved version
- **WHEN** an operator approves that version
- **THEN** its validated searchable representation is published and the version becomes approved
- **AND** only its approved content is eligible for retrieval

#### Scenario: Preserve a prior approved version after publication failure
- **GIVEN** a document has an approved version and a later imported version
- **WHEN** extraction fails for the later version or indexing fails during its approval
- **THEN** the later version remains non-searchable and approval is unavailable after extraction
  failure
- **AND** the prior approved version remains approved and retrievable

#### Scenario: Retry failed or interrupted extraction on demand
- **GIVEN** an imported version has failed extraction or an interrupted pending attempt, and its
  original file is retained
- **WHEN** an operator explicitly retries extraction
- **THEN** a new attempt uses the same retained bytes and reports `ready` with extracted text or
  `failed` without searchable text
- **AND** no approved version is displaced and no automatic retry is scheduled

#### Scenario: Reject overlapping extraction retries
- **GIVEN** an extraction attempt for a retained imported version is still running
- **WHEN** an operator requests another extraction attempt
- **THEN** the system rejects the overlapping request without changing original bytes or starting
  a second attempt

#### Scenario: Fence a late completion from an interrupted attempt
- **GIVEN** an interrupted pending attempt has been superseded by an operator-initiated retry
- **WHEN** the older attempt completes after the retry has stored a newer result
- **THEN** the older completion is ignored and cannot change the version's extraction state or text
- **AND** only the current attempt's result can make the version ready for approval

#### Scenario: Resolve concurrent approvals without dual publication
- **GIVEN** two imported versions of the same document are approved concurrently
- **WHEN** both actions reach publication
- **THEN** at most one version becomes approved and searchable
- **AND** the stale action returns a conflict without publishing its candidate chunks

#### Scenario: Resolve concurrent deprecation and approval
- **GIVEN** deprecation and approval actions for the same document overlap
- **WHEN** the first action commits a change to the approved version
- **THEN** the stale second action returns a conflict
- **AND** the document's searchable version and lifecycle state remain consistent

### Requirement: Expose manual Knowledge Administration without document editing

The system SHALL expose a local Knowledge Administration API and UI that lists knowledge documents
and their versions; uploads a new PDF or Markdown document or a new version of an existing document;
shows retained source metadata, extraction/indexing state, and version history; and permits explicit
extraction retry, approval, or deprecation. The UI SHALL let the operator enter or confirm document metadata,
including service applicability tags and aliases, before upload. It SHALL show that a source is
manual-upload-only and SHALL not offer URL registration, Confluence integration, scheduled sync,
external credentials, browser document editing, user/role controls, or automatic approval.

The UI SHALL keep approved knowledge distinct from Observation evidence and present document
references as knowledge material, not as confirmed causes or recommendations.

#### Scenario: Review an imported document before approval
- **GIVEN** an imported document is visible in Knowledge Administration
- **WHEN** an operator opens its detail view
- **THEN** the UI shows its source metadata, retained version history, and non-searchable imported
state with an explicit approval action
- **AND** it does not present an automatic synchronization control or an in-browser editor

#### Scenario: Show no identity controls in the trusted MVP
- **GIVEN** Knowledge Administration is opened in the MVP deployment
- **WHEN** its actions are rendered
- **THEN** upload, approval, and deprecation controls are available without a login or role UI
- **AND** the UI does not claim which person performed an action

### Requirement: Inspect the exact retained source behind a knowledge reference

The system SHALL expose the retained original payload for an immutable knowledge document version
through a trusted-MVP attachment-only download operation. The response SHALL use a fixed inert
content type, a safe filename, and browser content-sniffing protection; it SHALL not serve uploaded
PDF or Markdown as inline same-origin active content. Knowledge Administration document detail SHALL let
an operator open that exact version and shall show its media type, content hash, source reference
when supplied, and the PDF page or Markdown heading locations used by indexed passages. The
operation SHALL never substitute the current approved version for a cited historical version. The
Knowledge Administration view SHALL resolve recognized persisted hypothesis knowledge references
to their exact retained document version and chunk, show the stored PDF page/chunk or Markdown
heading/chunk location and extracted passage as inert text, and offer the version's original file
as an attachment. Unknown or unresolvable references SHALL remain visible as text without a
misleading link or substitution.

#### Scenario: Open a historical cited source version
- **GIVEN** a persisted hypothesis cites version 1 of a document and version 2 later becomes
approved
- **WHEN** an operator opens version 1 from Knowledge Administration
- **THEN** the system serves the retained original version-1 payload and its version-specific
metadata
- **AND** it does not silently redirect to version 2

#### Scenario: Download a source as an inert attachment
- **GIVEN** an operator follows a retained-source link for a PDF or Markdown version
- **WHEN** the source download response is returned
- **THEN** it carries the exact retained bytes with attachment disposition, a safe filename,
  fixed inert content type, and `X-Content-Type-Options: nosniff`
- **AND** direct navigation does not render the uploaded content inline on the application origin

#### Scenario: Follow a persisted hypothesis citation after a newer approval
- **GIVEN** a run's hypothesis cites one approved chunk from document version 1 and version 2 is
  subsequently approved
- **WHEN** an operator follows that citation from the run Analysis view
- **THEN** Knowledge Administration opens version 1 with the cited chunk, its retained passage,
  and its PDF page/chunk or Markdown heading/chunk location
- **AND** the original version-1 file is available as an attachment without substituting version 2

#### Scenario: Keep an unknown knowledge reference inspectable
- **GIVEN** a persisted hypothesis has a knowledge reference outside the recognized curated-corpus
  locator format
- **WHEN** the run Analysis view displays it
- **THEN** the exact reference remains visible as inert text
- **AND** the UI does not construct a misleading curated-source link
