import type { AnalyticalState, ExecutionStatus, ObservationRunSummary } from './types'

export const unavailableAnalyticalState = 'unavailable' as const
export type AnalyticalStateFilter = AnalyticalState | typeof unavailableAnalyticalState | ''
/** Independently combinable local filters for the complete loaded run history. */
export interface RunFilters { observationId: string; status: ExecutionStatus | ''; analyticalState: AnalyticalStateFilter }
export const emptyRunFilters: RunFilters = { observationId: '', status: '', analyticalState: '' }

/** Applies typed predicates in order without mutating the API's newest-first sequence. */
export function filterRuns(runs: readonly ObservationRunSummary[], filters: RunFilters): ObservationRunSummary[] {
  return runs.filter((run) =>
    (filters.observationId === '' || run.observation.id === filters.observationId)
    && (filters.status === '' || run.status === filters.status)
    && (filters.analyticalState === '' || (filters.analyticalState === unavailableAnalyticalState ? run.analytical_state === null : run.analytical_state === filters.analyticalState)),
  )
}

/** Collects one display choice per Observation in first-seen (newest-first) order. */
export function observationChoices(runs: readonly ObservationRunSummary[]) {
  const seen = new Set<string>()
  return runs.filter((run) => !seen.has(run.observation.id) && (seen.add(run.observation.id), true)).map((run) => run.observation)
}
