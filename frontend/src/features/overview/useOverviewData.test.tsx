import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunDetail, ObservationRunSummary } from '../runs/types'
import { useOverviewData } from './useOverviewData'

const api = vi.hoisted(() => ({
  listObservations: vi.fn(),
  listObservationRuns: vi.fn(),
  getObservationRun: vi.fn(),
}))

vi.mock('../observations/api', () => ({ listObservations: api.listObservations }))
vi.mock('../runs/api', () => ({ listObservationRuns: api.listObservationRuns, getObservationRun: api.getObservationRun }))

function observation(id: string): ObservationSummary {
  return { id, name: id, description: null, objective: 'Observe', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: `/api/v1/observations/${id}` }
}

function run(id: string, status: ObservationRunSummary['status'], analyticalState: ObservationRunSummary['analytical_state'] = null): ObservationRunSummary {
  return { id, observation: { id: 'observation', name: 'Observation' }, analysis_window: { from: '2026-09-10T10:00:00Z', to: '2026-09-10T11:00:00Z' }, status, reason: null, analytical_state: analyticalState, created_at: '2026-09-10T11:00:00Z', started_at: '2026-09-10T11:00:00Z', finished_at: status === 'running' || status === 'pending' ? null : '2026-09-10T11:01:00Z', duration_seconds: status === 'running' || status === 'pending' ? null : 60, href: `/api/v1/observation-runs/${id}` }
}

function detail(summary: ObservationRunSummary): ObservationRunDetail {
  return { summary, lens_runs: [], relationship_evaluations: [], analysis: summary.analytical_state === null ? null : { schema_version: '1.0', identity: { observation_id: 'observation', observation_run_id: summary.id }, overall_state: summary.analytical_state, findings: [], hypotheses: [], limitations: [] }, report: null }
}

function Harness() {
  const data = useOverviewData()
  return <>
    <button type="button" onClick={data.refresh}>Refresh</button>
    <output data-testid="definitions">{JSON.stringify({ data: data.definitions.data?.length ?? null, error: data.definitions.error !== null })}</output>
    <output data-testid="runs">{JSON.stringify({ data: data.runHistory.data?.map((item) => item.status) ?? null, error: data.runHistory.error !== null })}</output>
    <output data-testid="details">{JSON.stringify({ data: data.findingDetails.data.size, errors: data.findingDetails.errors.size, loading: data.findingDetails.loadingRunIds.size })}</output>
  </>
}

async function settle() { await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() }) }

afterEach(() => { vi.clearAllMocks(); vi.useRealTimers() })

describe('useOverviewData', () => {
  it('loads definitions, history, and bounded eligible details independently', async () => {
    const analyzed = run('analyzed', 'completed', 'significant_findings_present')
    api.listObservations.mockResolvedValue([observation('observation')])
    api.listObservationRuns.mockResolvedValue([analyzed])
    api.getObservationRun.mockResolvedValue(detail(analyzed))
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('definitions').textContent).toBe('{"data":1,"error":false}')
    expect(screen.getByTestId('runs').textContent).toBe('{"data":["completed"],"error":false}')
    expect(screen.getByTestId('details').textContent).toBe('{"data":1,"errors":0,"loading":0}')
  })

  it('keeps a successful source visible when the other source fails', async () => {
    api.listObservations.mockResolvedValue([observation('observation')])
    api.listObservationRuns.mockRejectedValue(new Error('offline'))
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('definitions').textContent).toBe('{"data":1,"error":false}')
    expect(screen.getByTestId('runs').textContent).toBe('{"data":null,"error":true}')
  })

  it('preserves stale history and prevents a terminal row regressing to running', async () => {
    vi.useFakeTimers()
    const terminal = run('stable', 'completed')
    api.listObservations.mockResolvedValue([])
    api.listObservationRuns.mockResolvedValueOnce([terminal]).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([run('stable', 'running')])
    render(<Harness />)
    await settle()
    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByTestId('runs').textContent).toBe('{"data":["completed"],"error":true}')
    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByTestId('runs').textContent).toBe('{"data":["completed"],"error":false}')
  })

  it('retains successful details when another bounded detail request fails', async () => {
    const first = run('first', 'completed', 'uncertain')
    const second = { ...run('second', 'completed', 'uncertain'), observation: { id: 'second-observation', name: 'Second' } }
    api.listObservations.mockResolvedValue([observation('observation'), observation('second-observation')])
    api.listObservationRuns.mockResolvedValue([first, second])
    api.getObservationRun.mockResolvedValueOnce(detail(first)).mockRejectedValueOnce(new Error('detail offline'))
    render(<Harness />)
    await settle()

    expect(screen.getByTestId('details').textContent).toBe('{"data":1,"errors":1,"loading":0}')
  })

  it('cancels superseded detail requests and reuses a successful stable-ID detail cache', async () => {
    const first = run('first', 'completed', 'uncertain')
    const second = run('second', 'completed', 'uncertain')
    let firstSignal: AbortSignal | undefined
    api.listObservations.mockResolvedValue([])
    api.listObservationRuns.mockResolvedValueOnce([first]).mockResolvedValue([second])
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

  it('stops after the final terminal refresh', async () => {
    vi.useFakeTimers()
    api.listObservations.mockResolvedValue([])
    api.listObservationRuns.mockResolvedValueOnce([run('active', 'running')]).mockResolvedValueOnce([run('active', 'completed')]).mockResolvedValueOnce([run('active', 'completed')])
    render(<Harness />)
    await settle()
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })

    expect(api.listObservationRuns).toHaveBeenCalledTimes(3)
  })
})
