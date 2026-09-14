## 1. Definition Contract and Storage

- [x] 1.1 Add optional `operational_context` validation to Observation create/replace and canonical detail contracts; verify omitted/null, exact multi-line round-trip, blank-only, and 4,000-code-point boundary cases with API tests.
- [x] 1.2 Add the nullable definition column, migration, and repository create/replace/read projections; verify old rows read as null, valid replacement/clear is atomic, and compact list summaries omit the full text in persistence/API tests.

## 2. Frozen Runtime and Agent Inputs

- [x] 2.1 Carry the field into the detached Observation Run snapshot and project it only to Reasoning and Report semantic contexts; verify a mid-run definition edit does not alter either projected value and Lens/evidence inputs remain unchanged.
- [x] 2.2 Admit the note in all three strict Reasoning model requests as untrusted semantic context; verify request shapes, evidence-only findings, knowledge-grounded hypotheses, unchanged policies, and adversarial notes with focused reasoning tests.
- [x] 2.3 Admit the note in the strict Report request and presentation adapter without changing the draft or Markdown schema; verify faithful wording with supported context, omission of unsupported context claims, no raw-note disclosure, and unchanged no-tool policy in report tests.

## 3. Observation Management UI

- [x] 3.1 Add the field to draft hydration, serialization, client validation, and API types; verify blank-to-null, exact non-empty text, populated edit loading, and aggregate-only submission with frontend tests.
- [x] 3.2 Add the optional General disclosure, preview, guidance, error opening, Review value, and read-only inspection value; verify accessible open/closed behavior, line-break preservation, and unchanged list search/navigation with frontend tests.
- [x] 3.3 Version the accepted `docs/ui/` handoff for this General-field addition after plan approval; verify the documented behavior matches the approved UI delta and introduces no unrelated screen changes.

## 4. Integrated Verification

- [x] 4.1 Exercise a create-or-replace → run snapshot → Reasoning → Report path with and without the note, including a concurrent edit and an instruction-like note; verify value consistency and unchanged analytical/report boundaries in integration or contract tests.
- [x] 4.2 Run `make check` as the final local verification and record any failures before archive or pull-request preparation.
