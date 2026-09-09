import { act, render, screen } from '@testing-library/react'
import { useCallback } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useSequentialPolling } from './useSequentialPolling'

type Item = { status: 'running' | 'completed'; label: string }

function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason?: unknown) => void; const promise = new Promise<T>((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise }); return { promise, resolve, reject } }

function PollingHarness({ load }: { load: (signal: AbortSignal) => Promise<Item> }) {
  const isActive = useCallback((item: Item) => item.status === 'running', [])
  const merge = useCallback((_previous: Item | null, incoming: Item) => incoming, [])
  const { state, refresh } = useSequentialPolling({ load, isActive, merge })
  return <><button type="button" onClick={refresh}>Manual refresh</button><p>{state.data?.label ?? 'none'}</p>{state.error ? <p role="alert">stale</p> : null}</>
}

afterEach(() => { vi.useRealTimers() })

describe('useSequentialPolling', () => {
  it('polls active data every five seconds without overlapping, then performs one final terminal refresh', async () => {
    vi.useFakeTimers()
    const first = deferred<Item>()
    const second = deferred<Item>()
    const third = deferred<Item>()
    const load = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise).mockReturnValueOnce(third.promise)
    render(<PollingHarness load={load} />)
    expect(load).toHaveBeenCalledTimes(1)
    await act(async () => { first.resolve({ status: 'running', label: 'active' }); await Promise.resolve() })
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(load).toHaveBeenCalledTimes(2)
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(load).toHaveBeenCalledTimes(2)
    await act(async () => { second.resolve({ status: 'completed', label: 'terminal' }); await Promise.resolve(); await vi.advanceTimersByTimeAsync(0) })
    expect(load).toHaveBeenCalledTimes(3)
    await act(async () => { third.resolve({ status: 'completed', label: 'final' }); await Promise.resolve() })
    expect(screen.getByText('final')).toBeTruthy()
  })

  it('retains last successful data and permits manual retry after a polling failure', async () => {
    vi.useFakeTimers()
    const load = vi.fn().mockResolvedValueOnce({ status: 'running', label: 'durable data' }).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ status: 'completed', label: 'recovered' })
    render(<PollingHarness load={load} />)
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('durable data')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.getByText('durable data')).toBeTruthy()
    await act(async () => { screen.getByRole('button', { name: 'Manual refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('recovered')).toBeTruthy()
  })
})
