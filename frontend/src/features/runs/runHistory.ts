import type { ExecutionStatus, ObservationRunSummary } from './types'

/** Identifies the only ObservationRun lifecycles that require automatic refresh. */
export function hasActiveRuns(runs: readonly ObservationRunSummary[]) { return runs.some((run) => run.status === 'pending' || run.status === 'running') }

/** Keeps a later durable terminal row from being overwritten by an older running snapshot. */
export function mergeRunHistory(previous: readonly ObservationRunSummary[] | null, incoming: readonly ObservationRunSummary[]) {
  if (previous === null) return incoming
  const previousById = new Map(previous.map((run) => [run.id, run]))
  return incoming.map((run) => {
    const old = previousById.get(run.id)
    return old && isTerminal(old.status) && !isTerminal(run.status) ? old : run
  })
}

/** Inserts the immutable acceptance snapshot without duplicating an already visible run. */
export function insertAcceptanceSnapshot(previous: readonly ObservationRunSummary[] | null, accepted: ObservationRunSummary) {
  const existing = previous ?? []
  const withoutAccepted = existing.filter((run) => run.id !== accepted.id)
  const old = existing.find((run) => run.id === accepted.id)
  return old && isTerminal(old.status) ? [...withoutAccepted, old] : [accepted, ...withoutAccepted]
}

function isTerminal(status: ExecutionStatus) { return status === 'completed' || status === 'failed' || status === 'cancelled' }
