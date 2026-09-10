import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { listObservations } from '../observations/api'
import type { ObservationSummary } from '../observations/types'
import { getObservationRun, listObservationRuns } from '../runs/api'
import { hasActiveRuns, mergeRunHistory } from '../runs/runHistory'
import type { ObservationRunDetail, ObservationRunSummary } from '../runs/types'
import { useSequentialPolling, type PollingState } from '../runs/useSequentialPolling'
import { selectFindingCandidates, type FindingCandidate } from './projections'

/** Independent request state for a source whose successful data remains visible after a failed refresh. */
export type OverviewSourceState<T> = PollingState<T>

/** State for the bounded, best-effort Observation-run detail requests used by Recent Findings. */
export interface OverviewFindingDetailState {
  readonly data: ReadonlyMap<string, ObservationRunDetail>
  readonly errors: ReadonlyMap<string, unknown>
  readonly loadingRunIds: ReadonlySet<string>
}

/** Optional feature-local dependencies for deterministic Overview coordination. */
export interface UseOverviewDataOptions {
  /** Supplies the client receipt time used only for local refresh feedback. */
  readonly now?: () => Date
}

/** Read-only Overview data snapshot composed from existing public APIs. */
export interface OverviewDataCoordinator {
  readonly definitions: OverviewSourceState<readonly ObservationSummary[]>
  readonly runHistory: OverviewSourceState<readonly ObservationRunSummary[]>
  readonly findingCandidates: readonly FindingCandidate[]
  readonly findingDetails: OverviewFindingDetailState
  /** The latest client time at which definitions or run history loaded successfully. */
  readonly lastSuccessfulRefreshAt: Date | null
  /** Refreshes independent definition and history sources plus retryable finding details. */
  readonly refresh: () => void
}

const emptyDetails: OverviewFindingDetailState = {
  data: new Map(),
  errors: new Map(),
  loadingRunIds: new Set(),
}

function currentClientTime() { return new Date() }

/** Loads the independent sources, follows active history, and bounds cached detail retrieval. */
export function useOverviewData(options: UseOverviewDataOptions = {}): OverviewDataCoordinator {
  const now = options.now ?? currentClientTime
  const [lastSuccessfulRefreshAt, setLastSuccessfulRefreshAt] = useState<Date | null>(null)
  const recordSuccessfulRefresh = useCallback(() => setLastSuccessfulRefreshAt(now()), [now])
  const { state: definitionsState, refresh: refreshDefinitions } = useOverviewDefinitions(recordSuccessfulRefresh)
  const loadRunHistory = useCallback(async (signal: AbortSignal) => {
    const runs = await listObservationRuns(signal)
    if (!signal.aborted) recordSuccessfulRefresh()
    return runs
  }, [recordSuccessfulRefresh])
  const { state: runHistoryState, refresh: refreshRunHistory } = useSequentialPolling<readonly ObservationRunSummary[]>({
    load: loadRunHistory,
    isActive: hasActiveRuns,
    merge: mergeRunHistory,
  })
  const findingCandidates = useMemo(() => selectFindingCandidates(runHistoryState.data ?? []), [runHistoryState.data])
  const candidateKey = findingCandidates.map(({ run }) => run.id).join(',')
  const cache = useRef(new Map<string, ObservationRunDetail>())
  const detailErrors = useRef(new Set<string>())
  const [findingDetails, setFindingDetails] = useState<OverviewFindingDetailState>(emptyDetails)
  const [detailRefreshNonce, setDetailRefreshNonce] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const candidateIds = new Set(candidateKey === '' ? [] : candidateKey.split(','))
    detailErrors.current = new Set([...detailErrors.current].filter((runId) => candidateIds.has(runId) && !cache.current.has(runId)))
    const pendingRunIds = [...candidateIds].filter((runId) => !cache.current.has(runId) && (detailRefreshNonce > 0 || !detailErrors.current.has(runId)))
    setFindingDetails((previous) => ({
      data: new Map([...cache.current].filter(([runId]) => candidateIds.has(runId))),
      errors: new Map([...previous.errors].filter(([runId]) => candidateIds.has(runId) && !cache.current.has(runId))),
      loadingRunIds: new Set(pendingRunIds),
    }))

    if (pendingRunIds.length === 0) return () => controller.abort()

    void Promise.all(pendingRunIds.map(async (runId) => {
      try {
        const detail = await getObservationRun(runId, controller.signal)
        if (!controller.signal.aborted) cache.current.set(runId, detail)
        return { runId, detail, error: null as unknown }
      } catch (error: unknown) {
        return { runId, detail: null, error }
      }
    })).then((results) => {
      if (controller.signal.aborted) return
      setFindingDetails((previous) => {
        const data = new Map(previous.data)
        const errors = new Map(previous.errors)
        for (const result of results) {
          if (result.detail !== null) {
            data.set(result.runId, result.detail)
            errors.delete(result.runId)
            detailErrors.current.delete(result.runId)
          } else {
            errors.set(result.runId, result.error)
            detailErrors.current.add(result.runId)
          }
        }
        return { data, errors, loadingRunIds: new Set() }
      })
    })

    return () => controller.abort()
  }, [candidateKey, detailRefreshNonce])

  const refresh = useCallback(() => {
    refreshDefinitions()
    refreshRunHistory()
    setDetailRefreshNonce((previous) => previous + 1)
  }, [refreshDefinitions, refreshRunHistory])

  return {
    definitions: definitionsState,
    runHistory: runHistoryState,
    findingCandidates,
    findingDetails,
    lastSuccessfulRefreshAt,
    refresh,
  }
}

function useOverviewDefinitions(onSuccessfulReceipt: () => void) {
  const [state, setState] = useState<OverviewSourceState<readonly ObservationSummary[]>>({ data: null, error: null, loading: true, refreshing: false })
  const stateRef = useRef(state)
  const mounted = useRef(false)
  const controller = useRef<AbortController | null>(null)

  const refresh = useCallback(() => {
    if (!mounted.current) return
    controller.current?.abort()
    const nextController = new AbortController()
    controller.current = nextController
    const previous = stateRef.current
    const nextState = { ...previous, error: null, loading: previous.data === null, refreshing: previous.data !== null }
    stateRef.current = nextState
    setState(nextState)

    void listObservations(nextController.signal)
      .then((data) => {
        if (!mounted.current || nextController.signal.aborted) return
        onSuccessfulReceipt()
        const settled = { data, error: null, loading: false, refreshing: false }
        stateRef.current = settled
        setState(settled)
      })
      .catch((error: unknown) => {
        if (!mounted.current || nextController.signal.aborted || isAbortError(error)) return
        const current = stateRef.current
        const settled = { data: current.data, error, loading: current.data === null, refreshing: false }
        stateRef.current = settled
        setState(settled)
      })
  }, [onSuccessfulReceipt])

  useEffect(() => {
    mounted.current = true
    refresh()
    return () => {
      mounted.current = false
      controller.current?.abort()
    }
  }, [refresh])

  return { state, refresh }
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}
