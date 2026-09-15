## 1. Absolute UTC Resolution

- [x] 1.1 Extend the discriminated time-range input and resolver with strict absolute UTC calendar parsing, canonical ISO output, and common ordering/future validation; verify focused `timeRange` tests cover the exact example, minute/second precision, invalid or missing endpoints, impossible dates, reversed/future windows, one clock capture, and unchanged preset/expression behavior.

## 2. Run Observation Interaction

- [x] 2.1 Add the accessible `Absolute UTC` mode and UTC-labeled second-precision From/To controls to the existing dialog while preserving the current default and other modes; verify focused dialog tests cover disabled incomplete input, exact submitted timestamps, local-time independence at the resolver boundary, validation feedback, and value retention after a failed launch.

## 3. Accepted UI Direction

- [x] 3.1 Advance `docs/ui/README.md` and `docs/ui/ui_implementation_handoff_v1.md` to UI Direction v1.12 and document the bounded absolute-UTC launch behavior; verify the documents preserve the existing Runs information architecture and concrete-timestamp API boundary without claiming backend or timezone support changes.

## 4. Integrated Verification

- [x] 4.1 Run the focused frontend test files for time-range resolution and the Run Observation dialog, and verify all changed-behavior scenarios pass.
- [x] 4.2 Run `make check` as the final local verification before archive or pull-request preparation and report any failure accurately.
