import type { ObservationSummary } from '../observations/types'
import type { AnalyticalState, ExecutionStatus, ObservationRunDetail, ObservationRunSummary } from '../runs/types'

/** The independent current-state counts displayed by the Overview. */
export interface OverviewSummaryCounts {
  readonly configuredObservations: number
  readonly activeObservations: number
  readonly observationsWithSignificantFindings: number
  readonly observationsWithFailedExecution: number
}

/** One configured Observation paired with only its durable monitoring context. */
export interface OverviewObservationRow {
  readonly observation: ObservationSummary
  readonly latestRun: ObservationRunSummary | null
  readonly recentRuns: readonly ObservationRunSummary[]
}

/** A bounded run summary whose detail may contain persisted Observation findings. */
export interface FindingCandidate {
  readonly run: ObservationRunSummary
}

/** A persisted Observation-level finding prepared for display without added semantics. */
export interface RecentFinding {
  readonly id: string
  readonly statement: string
  readonly observationId: string
  readonly observationName: string
  readonly observationRunId: string
  readonly runCreatedAt: string
  readonly analyticalState: AnalyticalState
}

/** One exact execution-state item prepared for chronological activity display. */
export interface RunActivityItem {
  readonly observationRunId: string
  readonly observationId: string
  readonly createdAt: string
  readonly status: ExecutionStatus
}

/** Selects the first matching run from the API's newest-first history. */
export function selectLatestRun(observationId: string, runs: readonly ObservationRunSummary[]) {
  return runs.find((run) => run.observation.id === observationId) ?? null
}

/** Derives independent current-state counts from each configured Observation's latest run. */
export function projectSummaryCounts(definitions: readonly ObservationSummary[], runs: readonly ObservationRunSummary[]): OverviewSummaryCounts {
  let activeObservations = 0
  let observationsWithSignificantFindings = 0
  let observationsWithFailedExecution = 0

  for (const definition of definitions) {
    const latestRun = selectLatestRun(definition.id, runs)
    if (latestRun === null) continue
    if (latestRun.status === 'pending' || latestRun.status === 'running') activeObservations += 1
    if (latestRun.analytical_state === 'significant_findings_present') observationsWithSignificantFindings += 1
    if (latestRun.status === 'failed') observationsWithFailedExecution += 1
  }

  return {
    configuredObservations: definitions.length,
    activeObservations,
    observationsWithSignificantFindings,
    observationsWithFailedExecution,
  }
}

/** Pairs every configured Observation with seven newest run states, ordered for monitoring. */
export function projectObservationRows(definitions: readonly ObservationSummary[], runs: readonly ObservationRunSummary[]): readonly OverviewObservationRow[] {
  const runsByObservation = new Map<string, ObservationRunSummary[]>()
  for (const run of runs) {
    const matchingRuns = runsByObservation.get(run.observation.id)
    if (matchingRuns === undefined) runsByObservation.set(run.observation.id, [run])
    else matchingRuns.push(run)
  }

  const rows = definitions.map((observation, definitionOrder) => {
    const recentRuns = (runsByObservation.get(observation.id) ?? []).slice(0, 7)
    return { observation, latestRun: recentRuns[0] ?? null, recentRuns, definitionOrder }
  })

  return rows
    .sort((left, right) => {
      if (left.latestRun === null && right.latestRun === null) return left.definitionOrder - right.definitionOrder
      if (left.latestRun === null) return 1
      if (right.latestRun === null) return -1
      return Date.parse(right.latestRun.created_at) - Date.parse(left.latestRun.created_at)
    })
    .map((row) => ({ observation: row.observation, latestRun: row.latestRun, recentRuns: row.recentRuns }))
}

/** Selects at most five newest summaries with an available analytical-state artifact. */
export function selectFindingCandidates(runs: readonly ObservationRunSummary[]): readonly FindingCandidate[] {
  return runs.filter((run) => run.analytical_state !== null).slice(0, 5).map((run) => ({ run }))
}

/** Flattens only persisted Observation-level findings in candidate and server finding order. */
export function projectRecentFindings(candidates: readonly FindingCandidate[], detailsByRunId: ReadonlyMap<string, ObservationRunDetail>): readonly RecentFinding[] {
  const findings: RecentFinding[] = []
  for (const { run } of candidates) {
    const detail = detailsByRunId.get(run.id)
    if (detail?.analysis === null || detail === undefined || run.analytical_state === null) continue
    for (const finding of detail.analysis.findings) {
      findings.push({
        id: finding.id,
        statement: finding.statement,
        observationId: run.observation.id,
        observationName: run.observation.name,
        observationRunId: run.id,
        runCreatedAt: run.created_at,
        analyticalState: run.analytical_state,
      })
      if (findings.length === 5) return findings
    }
  }
  return findings
}

/** Produces at most fourteen newest runs in oldest-to-newest chart display order. */
export function projectRunActivity(runs: readonly ObservationRunSummary[]): readonly RunActivityItem[] {
  return runs.slice(0, 14).reverse().map((run) => ({
    observationRunId: run.id,
    observationId: run.observation.id,
    createdAt: run.created_at,
    status: run.status,
  }))
}
