## 1. Metric list and selection

- [x] 1.1 Replace the Metrics stacked-card layout with a responsive single-selection list/detail view; verify a mixed-outcome Run Detail test shows every Metric LensRun in response order, selects the first initially, switches selection by LensRun ID, and allows dismissal.
- [x] 1.2 Build compact, text-labelled list summaries by exact Metric result variant using frozen identity and safe reasons; verify focused tests cover usable partial, completed-insufficient, failed, and result-null active/cancelled cases without fabricated evidence or a mutable definition fetch.

## 2. Selected evidence detail

- [x] 2.1 Recompose current semantic, numerical, and optional-analysis groups for the selected usable result while preserving the existing number formatter; verify focused tests distinguish small non-zero slope and explicit present/absent/unknown/null optional states.
- [x] 2.2 Present only returned reference comparisons and persisted History in separate groups with supported limitations; verify focused tests cover symmetric relative change, a missing reference offset, and unavailable History without an invented time series.

## 3. Run integration and verification

- [x] 3.1 Keep the existing run-detail refresh/polling lifecycle, add a successful-refresh timestamp, preserve selection across snapshots, and link to the run-level Analysis section; verify interaction tests cover successful refresh, stale-data failure, selected-ID fallback, and Analysis navigation.
- [x] 3.2 Verify the Metrics list/detail remains keyboard accessible and readable at desktop and narrow widths, with textual status cues and no Time series, Logs, or JSON tabs; check the rendered component behavior and responsive layout.
- [x] 3.3 Run `make check` as the final local verification before archive or pull-request preparation, and record any failures accurately.
