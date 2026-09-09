import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import { RunsPage } from './RunsPage'
import type { ObservationRunSummary } from './types'

const runs: ObservationRunSummary[] = [
  { id: 'run-newest-1234', observation: { id: 'ob-a', name: 'Cooling system' }, analysis_window: { from: '2026-09-09T09:00:00Z', to: '2026-09-09T10:00:00Z' }, status: 'failed', reason: { code: 'analysis_failed', component: null }, analytical_state: null, created_at: '2026-09-09T10:01:00Z', started_at: '2026-09-09T10:01:00Z', finished_at: '2026-09-09T10:02:00Z', duration_seconds: 61, href: '/api/v1/observation-runs/run-newest-1234' },
  { id: 'run-middle-5678', observation: { id: 'ob-a', name: 'Cooling system' }, analysis_window: { from: '2026-09-09T08:00:00Z', to: '2026-09-09T09:00:00Z' }, status: 'completed', reason: null, analytical_state: 'significant_findings_present', created_at: '2026-09-09T09:01:00Z', started_at: '2026-09-09T09:01:00Z', finished_at: '2026-09-09T09:02:00Z', duration_seconds: 61, href: '/api/v1/observation-runs/run-middle-5678' },
  { id: 'run-oldest-9012', observation: { id: 'ob-b', name: 'Feed pump' }, analysis_window: { from: '2026-09-09T07:00:00Z', to: '2026-09-09T08:00:00Z' }, status: 'running', reason: null, analytical_state: 'uncertain', created_at: '2026-09-09T08:01:00Z', started_at: '2026-09-09T08:01:00Z', finished_at: null, duration_seconds: null, href: '/api/v1/observation-runs/run-oldest-9012' },
]
const launchDefinitions = [{ id: 'never-run', name: 'Never run Observation', description: null, objective: 'Observe', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/never-run' }]
const acceptedRun: ObservationRunSummary = { id: 'accepted-run', observation: { id: 'never-run', name: 'Never run Observation' }, analysis_window: { from: '2026-09-09T11:45:00.000Z', to: '2026-09-09T12:00:00.000Z' }, status: 'running', reason: null, analytical_state: null, created_at: '2026-09-09T12:00:00.000Z', started_at: '2026-09-09T12:00:00.000Z', finished_at: null, duration_seconds: null, href: '/api/v1/observation-runs/accepted-run' }

function renderAt(path = '/runs') { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>) }
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }) }

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('RunsPage', () => {
  it('activates Runs navigation and shows the newest-first mixed history with independent lifecycle and analysis', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(runs)))
    renderAt()

    const navigation = screen.getByRole('link', { name: 'Runs' })
    expect(navigation.getAttribute('href')).toBe('/runs')
    expect(navigation.getAttribute('aria-current')).toBe('page')
    const list = await screen.findByLabelText('Observation runs')
    expect(list.textContent).toMatch(/Cooling system[\s\S]*Cooling system[\s\S]*Feed pump/)
    expect(screen.getByLabelText('Run ID: run-newest-1234')).toBeTruthy()
    expect(screen.getByLabelText('Run ID: run-middle-5678')).toBeTruthy()
    expect(screen.getByLabelText('Execution status: Failed')).toBeTruthy()
    expect(screen.getByLabelText('Analytical state: unavailable')).toBeTruthy()
    expect(screen.getByLabelText('Execution status: Completed')).toBeTruthy()
    expect(screen.getByLabelText('Analytical state: Significant findings present')).toBeTruthy()
    expect(screen.getAllByText('Analysis unavailable')).toHaveLength(2)
  })

  it('combines all filters while retaining API order and offers one clear-all action', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(runs)))
    renderAt()
    await screen.findByLabelText('Observation runs')

    await userEvent.selectOptions(screen.getByLabelText('Filter by Observation'), 'ob-a')
    await userEvent.selectOptions(screen.getByLabelText('Filter by execution status'), 'failed')
    await userEvent.selectOptions(screen.getByLabelText('Filter by analytical state'), 'unavailable')
    expect(screen.getByLabelText('Run ID: run-newest-1234')).toBeTruthy()
    expect(screen.queryByLabelText('Run ID: run-middle-5678')).toBeNull()
    expect(screen.getByRole('button', { name: 'Clear all filters' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Clear all filters' }))
    expect(screen.getByLabelText('Run ID: run-oldest-9012')).toBeTruthy()
  })

  it('distinguishes a successful empty collection from a filter no-match', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response([])))
    renderAt()
    expect(await screen.findByText('No Observation runs yet')).toBeTruthy()
    expect(screen.queryByText('No runs match these filters')).toBeNull()
  })

  it('shows a no-match state and clears every active filter together', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(runs)))
    renderAt()
    await screen.findByLabelText('Observation runs')
    await userEvent.selectOptions(screen.getByLabelText('Filter by Observation'), 'ob-a')
    await userEvent.selectOptions(screen.getByLabelText('Filter by execution status'), 'running')
    expect(screen.getByText('No runs match these filters')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByLabelText('Run ID: run-newest-1234')).toBeTruthy()
  })

  it('keeps retryable errors distinct from a successful empty history', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response({ code: 'unavailable', message: 'No connection' }, 503)).mockResolvedValueOnce(response([]))
    vi.stubGlobal('fetch', fetchMock)
    renderAt()
    expect((await screen.findByRole('alert')).textContent).toContain('Unable to load run history')
    expect(screen.queryByText('No Observation runs yet')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('No Observation runs yet')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('shows initial loading before a resolved collection', async () => {
    let resolve!: (value: Response) => void
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise<Response>((resolveRequest) => { resolve = resolveRequest })))
    renderAt()
    expect(screen.getByText('Loading runs')).toBeTruthy()
    resolve(response(runs))
    expect(await screen.findByLabelText('Observation runs')).toBeTruthy()
  })

  it('navigates an Open action to the registered run detail route', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(runs)))
    renderAt()
    await screen.findByLabelText('Observation runs')
    await userEvent.click(screen.getByRole('link', { name: 'Open run run-newest-1234' }))
    expect(await screen.findByRole('heading', { name: 'Run detail' })).toBeTruthy()
    expect(screen.getByText(/run-newest-1234/)).toBeTruthy()
  })

  it('aborts an in-flight history request when the route unmounts', async () => {
    let signal: AbortSignal | undefined
    vi.stubGlobal('fetch', vi.fn((_url, init) => { signal = (init as RequestInit).signal as AbortSignal; return new Promise(() => undefined) }))
    const result = render(<MemoryRouter><RunsPage /></MemoryRouter>)
    await waitFor(() => expect(signal).toBeDefined())
    result.unmount()
    expect(signal?.aborted).toBe(true)
  })

  it('launches exactly one concrete request, inserts its acceptance snapshot, and remains on the Runs list', async () => {
    let launched = false
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/observations')) return Promise.resolve(response(launchDefinitions))
      if (init?.method === 'POST') { launched = true; return Promise.resolve(response(acceptedRun, 202)) }
      return Promise.resolve(response(launched ? [acceptedRun] : []))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt()
    await screen.findByText('No Observation runs yet')
    await userEvent.click(screen.getByRole('button', { name: 'Run Observation' }))
    const dialog = await screen.findByRole('dialog', { name: 'Run Observation' })
    await userEvent.selectOptions(within(dialog).getByLabelText('Observation to run'), 'never-run')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Run Observation' }))
    expect(await screen.findByText(/was accepted and is now being monitored/)).toBeTruthy()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByLabelText('Run ID: accepted-run')).toBeTruthy()
    const postCall = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === 'POST')
    expect(postCall).toBeDefined()
    expect(JSON.parse((postCall?.[1] as RequestInit).body as string)).toEqual({ observation_id: 'never-run', analysis_window: { from: expect.any(String), to: expect.any(String) } })
    expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === 'POST')).toHaveLength(1)
  })
})
