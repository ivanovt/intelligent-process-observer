import type { ObservationSummary } from '../observations/types'
import type { AnalyticalState, ExecutionStatus, ObservationRunDetail, ObservationRunSummary } from '../runs/types'
import type { OverviewRuntimeItem } from './types'

/** The independent current-state counts displayed by the Overview. */
export interface OverviewSummaryCounts {
  readonly configuredObservations: number
  readonly activeObservations: number
  readonly observationsWithNoSignificantFindings: number
  readonly observationsWithUncertainAnalysis: number
  readonly observationsWithSignificantFindings: number
  readonly observationsWithFailedExecution: number
  readonly observationsWithLimitedCurrentRuntime: number
}

/** One configured Observation paired with only its durable monitoring context. */
export interface OverviewObservationRow {
  readonly observation: ObservationSummary
  readonly latestRun: OverviewRuntimeItem | null
  readonly recentRuns: readonly OverviewRuntimeItem[]
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
  readonly availability: 'available' | 'limited'
  readonly status: ExecutionStatus | null
}

/** Selects the first matching run from the API's newest-first history. */
export function selectLatestRun(observationId: string, runs: readonly OverviewRuntimeItem[]) {
  return runs.find((run) => runtimeObservation(run).id === observationId) ?? null
}

/** Derives independent current-state counts from each configured Observation's latest run. */
export function projectSummaryCounts(definitions: readonly ObservationSummary[], runs: readonly OverviewRuntimeItem[]): OverviewSummaryCounts {
  let activeObservations = 0
  let observationsWithNoSignificantFindings = 0
  let observationsWithUncertainAnalysis = 0
  let observationsWithSignificantFindings = 0
  let observationsWithFailedExecution = 0
  let observationsWithLimitedCurrentRuntime = 0

  for (const definition of definitions) {
    const latestRun = selectLatestRun(definition.id, runs)
    if (latestRun === null) continue
    const status = runtimeStatus(latestRun)
    if (status === 'pending' || status === 'running') activeObservations += 1
    if (latestRun.availability === 'available') {
      if (latestRun.summary.analytical_state === 'no_significant_findings') observationsWithNoSignificantFindings += 1
      if (latestRun.summary.analytical_state === 'uncertain') observationsWithUncertainAnalysis += 1
      if (latestRun.summary.analytical_state === 'significant_findings_present') observationsWithSignificantFindings += 1
    } else observationsWithLimitedCurrentRuntime += 1
    if (status === 'failed') observationsWithFailedExecution += 1
  }

  return {
    configuredObservations: definitions.length,
    activeObservations,
    observationsWithNoSignificantFindings,
    observationsWithUncertainAnalysis,
    observationsWithSignificantFindings,
    observationsWithFailedExecution,
    observationsWithLimitedCurrentRuntime,
  }
}

/** Pairs every configured Observation with seven newest run states, ordered for monitoring. */
export function projectObservationRows(definitions: readonly ObservationSummary[], runs: readonly OverviewRuntimeItem[]): readonly OverviewObservationRow[] {
  const runsByObservation = new Map<string, OverviewRuntimeItem[]>()
  for (const run of runs) {
    const observationId = runtimeObservation(run).id
    const matchingRuns = runsByObservation.get(observationId)
    if (matchingRuns === undefined) runsByObservation.set(observationId, [run])
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
      return Date.parse(runtimeCreatedAt(right.latestRun)) - Date.parse(runtimeCreatedAt(left.latestRun))
    })
    .map((row) => ({ observation: row.observation, latestRun: row.latestRun, recentRuns: row.recentRuns }))
}

/** Filters already projected Observation rows without changing their monitoring order. */
export function filterObservationRows(rows: readonly OverviewObservationRow[], query: string): readonly OverviewObservationRow[] {
  const normalizedQuery = query.trim().toLocaleLowerCase()
  if (normalizedQuery === '') return rows
  return rows.filter(({ observation }) =>
    observation.name.toLocaleLowerCase().includes(normalizedQuery)
    || (observation.description ?? '').toLocaleLowerCase().includes(normalizedQuery),
  )
}

/** Selects at most five newest summaries with an available analytical-state artifact. */
export function selectFindingCandidates(runs: readonly OverviewRuntimeItem[]): readonly FindingCandidate[] {
  return runs
    .filter((run): run is Extract<OverviewRuntimeItem, { availability: 'available' }> => run.availability === 'available' && run.summary.analytical_state !== null)
    .slice(0, 5)
    .map(({ summary }) => ({ run: summary }))
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
export function projectRunActivity(runs: readonly OverviewRuntimeItem[]): readonly RunActivityItem[] {
  return runs.slice(0, 14).reverse().map((run) => ({
    observationRunId: runtimeId(run),
    observationId: runtimeObservation(run).id,
    createdAt: runtimeCreatedAt(run),
    availability: run.availability,
    status: runtimeStatus(run),
  }))
}

/** Returns the independently safe Observation identity from either feed item variant. */
export function runtimeObservation(item: OverviewRuntimeItem) { return item.availability === 'available' ? item.summary.observation : item.observation }

/** Returns the durable item creation time without inferring an analysis window. */
export function runtimeCreatedAt(item: OverviewRuntimeItem) { return item.availability === 'available' ? item.summary.created_at : item.created_at }

/** Returns a status only when the public item independently admits one. */
export function runtimeStatus(item: OverviewRuntimeItem): ExecutionStatus | null { return item.availability === 'available' ? item.summary.status : item.status }

/** Returns the stable run identity shared by strict and limited Overview projections. */
export function runtimeId(item: OverviewRuntimeItem) { return item.availability === 'available' ? item.summary.id : item.id }
