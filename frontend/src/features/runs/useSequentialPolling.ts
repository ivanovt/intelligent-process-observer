import { useCallback, useEffect, useRef, useState } from 'react'

export interface PollingState<T> {
  readonly data: T | null
  readonly error: unknown | null
  readonly loading: boolean
  readonly refreshing: boolean
  /** Client receipt time in milliseconds for the latest successful network load. */
  readonly lastSuccessfulAt?: number | null
}

export interface SequentialPollingOptions<T> {
  readonly load: (signal: AbortSignal) => Promise<T>
  readonly isActive: (data: T) => boolean
  readonly merge: (previous: T | null, incoming: T) => T
  /** Reinitializes the request lifecycle when a stable resource identity changes. */
  readonly resourceKey?: string
}

/** Loads durable data sequentially and follows active work without overlapping requests. */
export function useSequentialPolling<T>({ load, isActive, merge, resourceKey }: SequentialPollingOptions<T>) {
  const [state, setState] = useState<PollingState<T>>({ data: null, error: null, loading: true, refreshing: false, lastSuccessfulAt: null })
  const stateRef = useRef(state)
  const previousResourceKey = useRef(resourceKey)
  const mounted = useRef(false)
  const inFlight = useRef(false)
  const queued = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const finalRefreshPending = useRef(false)
  const refreshRef = useRef<() => void>(() => undefined)

  const setCurrent = useCallback((next: PollingState<T>) => {
    stateRef.current = next
    if (mounted.current) setState(next)
  }, [])

  const clearTimer = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current)
    timer.current = null
  }, [])

  const refresh = useCallback(() => {
    if (!mounted.current) return
    if (inFlight.current) {
      queued.current = true
      return
    }
    clearTimer()
    inFlight.current = true
    const previous = stateRef.current
    setCurrent({ ...previous, error: null, loading: previous.data === null, refreshing: previous.data !== null })
    const nextController = new AbortController()
    controller.current = nextController

    void load(nextController.signal)
      .then((incoming) => {
        if (!mounted.current || nextController.signal.aborted) return
        const priorData = stateRef.current.data
        const data = merge(priorData, incoming)
        if (priorData !== null && isActive(priorData) && !isActive(data)) finalRefreshPending.current = true
        setCurrent({ data, error: null, loading: false, refreshing: false, lastSuccessfulAt: Date.now() })
      })
      .catch((error: unknown) => {
        if (!mounted.current || nextController.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return
        const current = stateRef.current
        setCurrent({ ...current, error, loading: current.data === null, refreshing: false })
      })
      .finally(() => {
        if (controller.current === nextController) controller.current = null
        inFlight.current = false
        if (!mounted.current) return
        if (queued.current) {
          queued.current = false
          refreshRef.current()
          return
        }
        const data = stateRef.current.data
        clearTimer()
        if (data === null) return
        const delay = isActive(data) ? 5_000 : finalRefreshPending.current ? 0 : null
        if (delay === null) return
        finalRefreshPending.current = false
        timer.current = setTimeout(() => refreshRef.current(), delay)
      })
  }, [clearTimer, isActive, load, merge, setCurrent])

  const replaceData = useCallback((updater: (previous: T | null) => T) => {
    const data = updater(stateRef.current.data)
    setCurrent({ ...stateRef.current, data, error: null, loading: false, refreshing: stateRef.current.refreshing })
    clearTimer()
    if (isActive(data)) timer.current = setTimeout(() => refreshRef.current(), 5_000)
  }, [clearTimer, isActive, setCurrent])

  useEffect(() => {
    refreshRef.current = refresh
  }, [refresh])

  useEffect(() => {
    mounted.current = true
    if (previousResourceKey.current !== resourceKey) {
      previousResourceKey.current = resourceKey
      setCurrent({ ...stateRef.current, lastSuccessfulAt: null })
    }
    refresh()
    return () => {
      mounted.current = false
      clearTimer()
      controller.current?.abort()
    }
  }, [clearTimer, refresh, resourceKey, setCurrent])

  return { state, refresh, replaceData }
}
