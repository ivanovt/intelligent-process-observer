# Implementation review triage

Status: awaiting human triage before bounded corrections.

- IR-001 (MEDIUM, whole-change Sol review): `FindingPresentation.heading` may be absent, allowing a generic numbered heading even when the source finding supports a subject-and-event heading. Candidate correction: require a nonblank heading for every presented finding and reject omission.
- SR-001 (MEDIUM, focused Sol review): `report_generation_request()` combines `snapshot` semantic/window context with `result.identity` without checking their Observation IDs match. The normal stage validates earlier, but direct projector calls can misattribute a report. Candidate correction: reject mismatched Observation IDs at the projector and add a focused test.

Both findings are within the approved report behavior and architecture. Reviewers made no edits. The Coordinator has requested user acceptance before dispatching corrections, as required by `AGENTS.md`.
