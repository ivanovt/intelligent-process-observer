# Implementation review triage

Status: both findings accepted by the user for bounded corrections; implementation in progress.

- IR-001 (MEDIUM, whole-change Sol review): `FindingPresentation.heading` may be absent, allowing a generic numbered heading even when the source finding supports a subject-and-event heading. Candidate correction: require a nonblank heading for every presented finding and reject omission.
- SR-001 (MEDIUM, focused Sol review): `report_generation_request()` combines `snapshot` semantic/window context with `result.identity` without checking their Observation IDs match. The normal stage validates earlier, but direct projector calls can misattribute a report. Candidate correction: reject mismatched Observation IDs at the projector and add a focused test.

Both findings are within the approved report behavior and architecture. Reviewers made no edits. The user accepted both for targeted fixes. Ownership is split between `backend/src/app/reporting/presentation.py` with `backend/tests/test_reporting.py` (IR-001) and `backend/src/app/execution/projectors.py` with `backend/tests/test_observation_execution_stages.py` (SR-001); neither correction changes OpenSpec or architecture semantics. Sol re-verification follows focused tests and the full check.
