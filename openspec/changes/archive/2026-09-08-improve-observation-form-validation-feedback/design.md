## Context

See `proposal.md` for motivation and `specs/observation-management-ui/spec.md` for observable behavior.

The frontend already has a project-owned `Field`, `InlineNotice`, semantic color tokens, persistent field guidance, and a scroll-aware sticky Create Observation configuration navigation. Validation functions return stable field paths, but presentation is fragmented: field errors are plain text, aggregate errors can duplicate incomplete-state copy, nested editors lack summaries, and notice tones do not consistently communicate severity. `DefinitionReview` also computes draft readiness continuously, while submitted blocking errors are retained separately in the page's explicit `errors` state.

The implementation must preserve current validation rules, API behavior, aggregate ownership, and the uncommitted UI refinements already present in the worktree. It must add no dependency.

## Goals / Non-Goals

**Goals:**

- Create a small reusable visual and accessibility vocabulary for validation and operational notices.
- Give users one reliable starting point after a failed Create or Apply action and clear local indicators thereafter.
- Derive summary entries and section counts from the same existing validation result so displayed states cannot disagree.
- Keep current helpers, draft values, native anchors, and correction routes intact.

**Non-Goals:**

- Change validation timing, validation rules, backend error contracts, or normalize provider-native values.
- Add toast notifications, a form library, schema generation, or a second icon system.
- Disable the Create action before the user can request validation.
- Add Observation update/delete behavior or modify nested Apply ownership.

## Decisions

### 1. Extend project-owned primitives instead of styling each error independently

Enhance `Field` so an `error` applies `aria-invalid`, a destructive border/focus treatment to its control, and a compact `CircleAlert` icon-and-text message while leaving neutral guidance visible. Field messages remain connected through `aria-describedby`, but they do not each use an assertive live role when several errors appear together.

Add a reusable `ValidationSummary` that accepts an ordered list of normalized issues. It renders a destructive contained panel with a heading, issue count, and anchor/correction links where targets exist. Existing validation functions and their field-path messages remain authoritative; the summary is a presentation projection, not a second validator.

Alternative considered: show only a red border or tooltip. Both hide corrective information and rely too heavily on color or discovery.

### 2. Focus and announce one summary after an invalid action

Create and nested Apply handlers retain their current synchronous validation. When validation returns issues, the page renders the summary and moves programmatic focus to it after React commits the state. The summary acts as the single assertive announcement for a multi-error submit. Field errors remain discoverable through their controls and descriptions.

If an API response maps to one represented field or child, it enters the same normalized summary and retains the existing field or correction-link association. Unmapped transport or aggregate failures remain prominent error notices rather than fabricated field errors.

Alternative considered: focus the first invalid input. A summary is preferable because it communicates total scope and provides navigation when errors span the aggregate or nested editors.

### 3. Normalize error paths once for summaries and Create section counts

Create Observation maps the latest explicit validation/API error paths into five sections:

| Section | Paths |
|---|---|
| General | `name`, `description`, `objective` |
| Metric lenses | `lenses.*` |
| Alert lenses | `alert_lenses.*` |
| Relationships | `relationships.*` |
| Review | `aggregate` and unmapped aggregate-level issues |

The normalized explicit-issue list supplies the validation summary and red numeric badges in the sticky configuration navigation. Active-section styling and issue styling are separate and may coexist. Counts do not include the continuously computed pre-submit Review readiness projection.

`DefinitionReview` continues to evaluate the current draft on render, but before an invalid Create attempt it presents missing work as neutral or amber incomplete guidance rather than submitted blocking errors. Field treatments, validation summaries, navigation badges, and the Definition Summary blocking state use only the latest explicit Create/API validation result. Editing does not silently revalidate or clear those errors; the next explicit validation replaces the complete displayed error set.

Retained explicit blocking state takes precedence over live readiness. While explicit issues remain, `DefinitionReview` must not show a ready/success message even if the edited draft currently passes the local validator. In that combined state it shows neutral guidance that the values appear complete and Create must be attempted again to confirm them. The Definition Summary remains blocking until that explicit revalidation. This prevents simultaneous “ready” and “issues need attention” signals without adding validation-on-change behavior.

### 4. Model Definition Summary as one state, not stacked messages

Before an invalid submit, an aggregate missing all Lenses shows one amber incomplete message. After validation produces the aggregate Lens error, the same area switches to one red blocking state and does not render the raw error again. Ready state remains green/success. Detailed correction remains in the validation summary and field/section indicators.

This avoids showing the same condition as both warning and error while preserving the useful distinction between an unfinished draft and a rejected submission.

### 5. Expand notices to four semantic tones with built-in Lucide icons

`InlineNotice` supports `info`, `warning`, `error`, and `success`, each with a consistent icon, border, surface, text token, and accessible role. Error notices use alert semantics when they appear; other tones use non-assertive status semantics. Existing Observation-management uses are classified deliberately: list/detail/capability/create transport failures are error; no configured Metric source is warning; draft-loss, draft-ownership, and persisted-history explanations are info; successful creation is success. The existing detail not-found panel remains a distinct absence state rather than being converted into a retryable error notice.

Use CSS variables for the additional notice surfaces and borders. Do not use analytical-state colors to represent form validity or transport failure.

## Risks / Trade-offs

- **[Risk] A summary plus field messages could feel repetitive.** → Keep the summary compact and navigational; keep field messages concise and corrective.
- **[Risk] Many assertive regions could overwhelm assistive-technology users.** → Use one focused/announced summary for multi-error actions and descriptive field associations without simultaneous field alerts.
- **[Risk] Section counts could diverge from the visible errors.** → Derive both from the same normalized issue collection and retain errors until the next explicit validation result.
- **[Risk] Live Review readiness could contradict retained blocking errors after edits.** → Give retained explicit validation state precedence and require a neutral revalidation prompt instead of a ready/success message.
- **[Risk] Adding icons could create decorative noise.** → Use one consistent Lucide icon per semantic tone and mark duplicate decorative icons hidden from assistive technology.
- **[Risk] Existing tests select generic alert roles.** → Update tests to target the intended summary or notice by accessible name while retaining transport and validation regressions.
- **[Risk] Broad notice standardization could spill into unrelated product areas.** → Limit the call-site audit to existing Observation-management pages and shared primitives used by them.

## Migration Plan

1. Add notice/error tokens and enhance shared `Field`, `InlineNotice`, and validation-summary primitives with focused tests.
2. Integrate normalized validation summaries, focus behavior, Definition Summary consolidation, and section issue counts into Create Observation.
3. Integrate the same invalid-Apply summary and every non-Field group treatment into Metric Lens, Alert Lens, and Relationship editors.
4. Classify and verify every existing Observation-management notice/absence call site without changing its message meaning or action.
5. Run focused and complete frontend verification followed by `make check`.

Rollback is a normal revert of frontend and change-artifact edits. There is no backend, API, dependency, or data migration.

## Architecture References

- `docs/architecture/`: N/A — the design presents existing validation and request outcomes without changing domain/runtime contracts.
- `docs/ui/ui_implementation_handoff_v1.md`: preserves local validation, aggregate review, draft ownership, nested Apply, and final Create semantics.
- `docs/ui/frontend_ui_stack_adr.md`: uses semantic CSS tokens, project-owned primitives, and Lucide React from the accepted stack.
