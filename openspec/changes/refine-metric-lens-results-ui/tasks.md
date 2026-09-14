## 1. Metric list and selection

- [x] 1.1 Make the Metric detail pane absent and all cards unselected on initial Metrics entry, open it only on explicit card selection, and close it on dismissal or selected-ID loss; verify interaction tests cover initial load, refresh while closed, selection, dismissal, and selected-ID loss.
- [x] 1.2 Recompose cards by result variant into the mock's ordered identity/status, timing, semantic-state, and evidence groups; verify focused tests cover usable partial, completed-insufficient, failed, and result-null cases without fabricated evidence or a mutable definition fetch.
- [x] 1.3 Widen the card area both with and without a selected pane and add Lucide trend/availability/failure icons with adjacent text; verify the responsive layout and decorative-icon accessibility in component tests or a visual check.
- [x] 1.4 Keep the selected side pane viewport-anchored at usable desktop widths around 1200px and above while card-list/page scrolling continues; make the card evidence strip reflow and verify at desktop widths with a long card list and a short viewport.

## 2. Selected evidence detail

- [x] 2.1 Recompose current semantic, numerical, and optional-analysis groups for the selected usable result while preserving the existing number formatter; verify focused tests distinguish small non-zero slope and explicit present/absent/unknown/null optional states.
- [x] 2.2 Present only returned reference comparisons and persisted History in separate groups with supported limitations; verify focused tests cover symmetric relative change, a missing reference offset, and unavailable History without an invented time series.

## 3. Run integration and verification

- [x] 3.1 Keep the existing run-detail refresh/polling lifecycle and last-updated timestamp, preserve explicit selection across snapshots, keep the pane closed when unselected, and link to run-level Analysis; verify interaction tests cover refresh, stale-data failure, selected-ID loss, and Analysis navigation.
- [x] 3.2 Verify the revised card list and viewport-anchored conditional pane, including the pane's internal evidence grids and independently reachable close action, remain keyboard accessible and readable at desktop and narrow widths, with textual status cues and no Time series, Logs, or JSON tabs; check rendered behavior and responsive layout.
- [x] 3.3 Run `make check` as the final local verification before archive or pull-request preparation, and record any failures accurately.
