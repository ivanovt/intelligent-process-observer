import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunDetail, ObservationRunSummary } from '../runs/types'
import { useOverviewData } from './useOverviewData'
import type { OverviewRuntimeFeed, OverviewRuntimeItem } from './types'

const api = vi.hoisted(() => ({
  listObservations: vi.fn(),
  getOverviewRuntime: vi.fn(),
  getObservationRun: vi.fn(),
}))

vi.mock('../observations/api', () => ({ listObservations: api.listObservations }))
vi.mock('../runs/api', () => ({ getObservationRun: api.getObservationRun }))
vi.mock('./api', () => ({ getOverviewRuntime: api.getOverviewRuntime }))

function observation(id: string): ObservationSummary {
  return { id, name: id, description: null, objective: 'Observe', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: `/api/v1/observations/${id}` }
}

function run(id: string, status: ObservationRunSummary['status'], analyticalState: ObservationRunSummary['analytical_state'] = null): ObservationRunSummary {
  return { id, observation: { id: 'observation', name: 'Observation' }, analysis_window: { from: '2026-09-10T10:00:00Z', to: '2026-09-10T11:00:00Z' }, status, reason: null, analytical_state: analyticalState, created_at: '2026-09-10T11:00:00Z', started_at: '2026-09-10T11:00:00Z', finished_at: status === 'running' || status === 'pending' ? null : '2026-09-10T11:01:00Z', duration_seconds: status === 'running' || status === 'pending' ? null : 60, href: `/api/v1/observation-runs/${id}` }
}

function feed(...summaries: readonly ObservationRunSummary[]): OverviewRuntimeFeed {
  return { schema_version: '1.0', items: summaries.map((summary): OverviewRuntimeItem => ({ availability: 'available', summary })), limited_run_count: 0 }
}

function limited(id: string, status: ObservationRunSummary['status'] | null): OverviewRuntimeItem {
  return { availability: 'limited', id, observation: { id: 'observation', name: 'Observation' }, created_at: '2026-09-10T11:00:00Z', status, started_at: null, finished_at: null, duration_seconds: null, analytical_state: null, limitation_code: 'runtime_projection_invalid', href: `/api/v1/observation-runs/${id}` }
}

function detail(summary: ObservationRunSummary): ObservationRunDetail {
  return { summary, lens_runs: [], relationship_evaluations: [], analysis: summary.analytical_state === null ? null : { schema_version: '1.0', identity: { observation_id: 'observation', observation_run_id: summary.id }, overall_state: summary.analytical_state, findings: [], hypotheses: [], limitations: [] }, report: null }
}

function Harness({ now }: { readonly now?: () => Date }) {
  const data = useOverviewData({ now })
  return <>
    <button type="button" onClick={data.refresh}>Refresh</button>
    <output data-testid="definitions">{JSON.stringify({ data: data.definitions.data?.length ?? null, error: data.definitions.error !== null })}</output>
    <output data-testid="runs">{JSON.stringify({ data: data.runHistory.data?.items.map((item) => item.availability === 'available' ? item.summary.status : item.status) ?? null, limited: data.runHistory.data?.limited_run_count ?? null, error: data.runHistory.error !== null })}</output>
    <output data-testid="details">{JSON.stringify({ data: data.findingDetails.data.size, errors: data.findingDetails.errors.size, loading: data.findingDetails.loadingRunIds.size })}</output>
    <output data-testid="last-refresh">{data.lastSuccessfulRefreshAt?.toISOString() ?? 'none'}</output>
  </>
}

async function settle() {
  await act(async () => {
    for (let index = 0; index < 8; index += 1) await Promise.resolve()
  })
}

afterEach(() => { vi.clearAllMocks(); vi.useRealTimers() })

describe('useOverviewData', () => {
  it('loads definitions, history, and bounded eligible details independently', async () => {
    const analyzed = run('analyzed', 'completed', 'significant_findings_present')
    api.listObservations.mockResolvedValue([observation('observation')])
    api.getOverviewRuntime.mockResolvedValue(feed(analyzed))
    api.getObservationRun.mockResolvedValue(detail(analyzed))
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('definitions').textContent).toBe('{"data":1,"error":false}')
    expect(screen.getByTestId('runs').textContent).toBe('{"data":["completed"],"limited":0,"error":false}')
    expect(screen.getByTestId('details').textContent).toBe('{"data":1,"errors":0,"loading":0}')
  })

  it('keeps a successful source visible when the other source fails', async () => {
    api.listObservations.mockResolvedValue([observation('observation')])
    api.getOverviewRuntime.mockRejectedValue(new Error('offline'))
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('definitions').textContent).toBe('{"data":1,"error":false}')
    expect(screen.getByTestId('runs').textContent).toBe('{"data":null,"limited":null,"error":true}')
  })

  it('records successful definition and run-history receipts with an injected clock, including polling', async () => {
    vi.useFakeTimers()
    const timestamps = [
      new Date('2026-09-10T11:00:01Z'),
      new Date('2026-09-10T11:00:02Z'),
      new Date('2026-09-10T11:00:03Z'),
    ]
    const now = vi.fn(() => timestamps.shift()!)
    const active = run('active', 'running')
    api.listObservations.mockResolvedValueOnce([observation('observation')]).mockRejectedValueOnce(new Error('definitions offline'))
    api.getOverviewRuntime
      .mockRejectedValueOnce(new Error('history offline'))
      .mockResolvedValueOnce(feed(active))
      .mockResolvedValueOnce(feed(active))
      .mockRejectedValueOnce(new Error('history offline'))

    render(<Harness now={now} />)
    await settle()
    expect(screen.getByTestId('last-refresh').textContent).toBe('2026-09-10T11:00:01.000Z')

    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    await settle()
    expect(screen.getByTestId('last-refresh').textContent).toBe('2026-09-10T11:00:02.000Z')
    expect(vi.getTimerCount()).toBe(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    await settle()
    expect(api.getOverviewRuntime).toHaveBeenCalledTimes(3)
    expect(screen.getByTestId('last-refresh').textContent).toBe('2026-09-10T11:00:03.000Z')

    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    await settle()
    expect(screen.getByTestId('last-refresh').textContent).toBe('2026-09-10T11:00:03.000Z')
    expect(now).toHaveBeenCalledTimes(3)
  })

  it('preserves stale history and prevents a terminal row regressing to running', async () => {
    vi.useFakeTimers()
    const terminal = run('stable', 'completed')
    api.listObservations.mockResolvedValue([])
    api.getOverviewRuntime.mockResolvedValueOnce(feed(terminal)).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(feed(run('stable', 'running')))
    render(<Harness />)
    await settle()
    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByTestId('runs').textContent).toBe('{"data":["completed"],"limited":0,"error":true}')
    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByTestId('runs').textContent).toBe('{"data":["completed"],"limited":0,"error":false}')
  })

  it('retains successful details when another bounded detail request fails', async () => {
    const first = run('first', 'completed', 'uncertain')
    const second = { ...run('second', 'completed', 'uncertain'), observation: { id: 'second-observation', name: 'Second' } }
    api.listObservations.mockResolvedValue([observation('observation'), observation('second-observation')])
    api.getOverviewRuntime.mockResolvedValue(feed(first, second))
    api.getObservationRun.mockResolvedValueOnce(detail(first)).mockRejectedValueOnce(new Error('detail offline'))
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('details').textContent).toBe('{"data":1,"errors":1,"loading":0}')
  })

  it('retries a failed bounded detail request through the manual refresh action', async () => {
    const analyzed = run('analyzed', 'completed', 'uncertain')
    api.listObservations.mockResolvedValue([observation('observation')])
    api.getOverviewRuntime.mockResolvedValue(feed(analyzed))
    api.getObservationRun.mockRejectedValueOnce(new Error('detail offline')).mockResolvedValueOnce(detail(analyzed))
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('details').textContent).toBe('{"data":0,"errors":1,"loading":0}')
    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByTestId('details').textContent).toBe('{"data":1,"errors":0,"loading":0}')
    expect(api.getObservationRun).toHaveBeenCalledTimes(2)
  })

  it('cancels superseded detail requests and reuses a successful stable-ID detail cache', async () => {
    const first = run('first', 'completed', 'uncertain')
    const second = run('second', 'completed', 'uncertain')
    let firstSignal: AbortSignal | undefined
    api.listObservations.mockResolvedValue([])
    api.getOverviewRuntime.mockResolvedValueOnce(feed(first)).mockResolvedValue(feed(second))
    api.getObservationRun
      .mockImplementationOnce((_id: string, signal: AbortSignal) => new Promise<ObservationRunDetail>(() => { firstSignal = signal }))
      .mockImplementation((id: string) => Promise.resolve(detail(id === 'first' ? first : second)))
    render(<Harness />)
    await settle()

    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve() })
    expect(firstSignal?.aborted).toBe(true)
    expect(api.getObservationRun).toHaveBeenCalledTimes(3)

    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    expect(api.getObservationRun).toHaveBeenCalledTimes(3)
  })

  it('keeps a pending detail request while an active-run poll returns the same candidate ID', async () => {
    vi.useFakeTimers()
    const candidate = run('candidate', 'completed', 'uncertain')
    const active = run('active', 'running')
    let candidateSignal: AbortSignal | undefined
    api.listObservations.mockResolvedValue([])
    api.getOverviewRuntime.mockResolvedValueOnce(feed(candidate, active)).mockResolvedValueOnce(feed({ ...candidate }, { ...active }))
    api.getObservationRun.mockImplementation((_id: string, signal: AbortSignal) => new Promise<ObservationRunDetail>(() => { candidateSignal = signal }))
    render(<Harness />)
    await settle()

    expect(api.getObservationRun).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })

    expect(api.getOverviewRuntime).toHaveBeenCalledTimes(2)
    expect(candidateSignal?.aborted).toBe(false)
    expect(api.getObservationRun).toHaveBeenCalledTimes(1)
  })

  it('stops after the final terminal refresh', async () => {
    vi.useFakeTimers()
    api.listObservations.mockResolvedValue([])
    api.getOverviewRuntime.mockResolvedValueOnce(feed(run('active', 'running'))).mockResolvedValueOnce(feed(run('active', 'completed'))).mockResolvedValueOnce(feed(run('active', 'completed')))
    render(<Harness />)
    await settle()
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })

    expect(api.getOverviewRuntime).toHaveBeenCalledTimes(3)
  })

  it('keeps a limited runtime item as successful data and polls only its independently valid active lifecycle', async () => {
    vi.useFakeTimers()
    api.listObservations.mockResolvedValue([observation('observation')])
    api.getOverviewRuntime.mockResolvedValue(feed())
      .mockResolvedValueOnce({ schema_version: '1.0', items: [limited('limited-active', 'running')], limited_run_count: 1 })
      .mockResolvedValueOnce({ schema_version: '1.0', items: [limited('limited-terminal', null)], limited_run_count: 1 })
      .mockResolvedValueOnce({ schema_version: '1.0', items: [limited('limited-terminal', null)], limited_run_count: 1 })
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('runs').textContent).toBe('{"data":["running"],"limited":1,"error":false}')
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(screen.getByTestId('runs').textContent).toBe('{"data":[null],"limited":1,"error":false}')
  })
})
