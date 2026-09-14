import { act, render, screen } from '@testing-library/react'
import { useCallback } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useSequentialPolling } from './useSequentialPolling'

type Item = { status: 'running' | 'completed'; label: string }

function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason?: unknown) => void; const promise = new Promise<T>((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise }); return { promise, resolve, reject } }

function PollingHarness({ load, resourceKey }: { load: (signal: AbortSignal) => Promise<Item>; resourceKey?: string }) {
  const isActive = useCallback((item: Item) => item.status === 'running', [])
  const merge = useCallback((_previous: Item | null, incoming: Item) => incoming, [])
  const { state, refresh, replaceData } = useSequentialPolling({ load, isActive, merge, resourceKey })
  return <><button type="button" onClick={refresh}>Manual refresh</button><button type="button" onClick={() => replaceData((previous) => ({ status: 'completed', label: previous?.label ?? 'replaced' }))}>Replace data</button><p>{state.data?.label ?? 'none'}</p><p>Last successful: {state.lastSuccessfulAt ?? 'none'}</p>{state.error ? <p role="alert">stale</p> : null}</>
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
    vi.setSystemTime(new Date('2026-09-14T10:00:00Z'))
    const load = vi.fn().mockResolvedValueOnce({ status: 'running', label: 'durable data' }).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ status: 'completed', label: 'recovered' })
    render(<PollingHarness load={load} />)
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('durable data')).toBeTruthy()
    expect(screen.getByText('Last successful: 1789380000000')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.getByText('durable data')).toBeTruthy()
    expect(screen.getByText('Last successful: 1789380000000')).toBeTruthy()
    await act(async () => { screen.getByRole('button', { name: 'Manual refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('recovered')).toBeTruthy()
    expect(screen.getByText('Last successful: 1789380005000')).toBeTruthy()
  })

  it('preserves the receipt time for replaceData and resets it when the resource changes', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-14T10:00:00Z'))
    const load = vi.fn().mockResolvedValue({ status: 'completed', label: 'first resource' })
    const { rerender } = render(<PollingHarness load={load} resourceKey="first" />)
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('Last successful: 1789380000000')).toBeTruthy()
    await act(async () => { screen.getByRole('button', { name: 'Replace data' }).click() })
    expect(screen.getByText('Last successful: 1789380000000')).toBeTruthy()

    const next = deferred<Item>()
    load.mockReturnValueOnce(next.promise)
    rerender(<PollingHarness load={load} resourceKey="second" />)
    expect(screen.getByText('Last successful: none')).toBeTruthy()
    await act(async () => { next.resolve({ status: 'completed', label: 'second resource' }); await Promise.resolve() })
    expect(screen.getByText('Last successful: 1789380000000')).toBeTruthy()
  })
})
