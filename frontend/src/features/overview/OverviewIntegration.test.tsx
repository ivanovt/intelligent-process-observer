import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunSummary } from '../runs/types'

const definition: ObservationSummary = { id: 'cooling', name: 'Cooling system', description: 'Cooling process monitoring.', objective: 'Observe cooling', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/cooling' }
const secondDefinition: ObservationSummary = { id: 'pressure', name: 'Pressure control', description: 'Reactor pressure monitoring.', objective: 'Observe pressure', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/pressure' }

function run(status: ObservationRunSummary['status'] = 'completed'): ObservationRunSummary {
  return { id: 'cooling-run', observation: { id: 'cooling', name: 'Cooling system' }, analysis_window: { from: '2026-09-10T10:00:00Z', to: '2026-09-10T11:00:00Z' }, status, reason: null, analytical_state: null, created_at: '2026-09-10T11:00:00Z', started_at: '2026-09-10T11:00:00Z', finished_at: status === 'running' || status === 'pending' ? null : '2026-09-10T11:01:00Z', duration_seconds: status === 'running' || status === 'pending' ? null : 60, href: '/api/v1/observation-runs/cooling-run' }
}

function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }) }

function renderAt(path = '/') { return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>) }

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined
  const promise = new Promise<T>((resolveRequest) => { resolve = resolveRequest })
  return { promise, resolve }
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('Overview application integration', () => {
  it('distinguishes initial loading from a successful empty monitoring snapshot', async () => {
    const definitions = deferred<Response>()
    const history = deferred<Response>()
    vi.stubGlobal('fetch', vi.fn((url: string) => url.endsWith('/observations') ? definitions.promise : history.promise))
    renderAt('/overview')

    expect(screen.getByRole('status').textContent).toContain('Loading monitoring data.')
    definitions.resolve(response([]))
    history.resolve(response([]))
    expect(await screen.findByText('No Observation definitions exist yet.')).toBeTruthy()
    expect(screen.getByText('No Observation runs exist yet.')).toBeTruthy()
  })

  it('redirects root to the active Overview route, supports direct entry, and keeps Observation and run detail navigation registered', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/observations')) return Promise.resolve(response([definition]))
      if (url.endsWith('/observation-runs')) return Promise.resolve(response([run()]))
      return Promise.resolve(response({ code: 'not_found' }, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    const view = renderAt()

    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Overview' }).getAttribute('aria-current')).toBe('page')
    expect(screen.getByRole('link', { name: 'Cooling system' }).getAttribute('href')).toBe('/observations/cooling')
    expect(screen.getByRole('link', { name: 'Open latest run cooling-run' }).getAttribute('href')).toBe('/runs/cooling-run')

    await userEvent.click(screen.getByRole('link', { name: 'Cooling system' }))
    expect(await screen.findByRole('heading', { name: 'Definition not found' })).toBeTruthy()
    view.unmount()

    const overviewView = renderAt('/overview')
    await screen.findByRole('link', { name: 'Open latest run cooling-run' })
    await userEvent.click(screen.getByRole('link', { name: 'Open latest run cooling-run' }))
    expect(await screen.findByRole('heading', { name: 'Run detail' })).toBeTruthy()
    overviewView.unmount()

    renderAt('/unknown-route')
    expect(await screen.findByRole('heading', { name: 'Observations' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Observations' }).getAttribute('aria-current')).toBe('page')
  })

  it('keeps each successful source visible through partial failure, supports retry, and never makes a mutation request', async () => {
    let runRequests = 0
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method !== undefined) return Promise.resolve(response({ code: 'method_not_allowed' }, 405))
      if (url.endsWith('/observations')) return Promise.resolve(response([definition]))
      if (url.endsWith('/observation-runs')) {
        runRequests += 1
        return Promise.resolve(runRequests === 1 ? response({ code: 'offline' }, 503) : response([]))
      }
      return Promise.resolve(response({ code: 'not_found' }, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/overview')

    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Some monitoring data is unavailable. Successful sections remain visible.'))
    expect(screen.getByRole('link', { name: 'Cooling system' })).toBeTruthy()
    expect(screen.getByText('Runtime unavailable')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Not run yet')).toBeTruthy()
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit | undefined)?.method === undefined)).toBe(true)
  })

  it('filters only loaded rows during successful monitoring without changing the summary, insights, or requests', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method !== undefined) return Promise.resolve(response({ code: 'method_not_allowed' }, 405))
      if (url.endsWith('/observations')) return Promise.resolve(response([definition, secondDefinition]))
      if (url.endsWith('/observation-runs')) return Promise.resolve(response([run()]))
      return Promise.resolve(response({ code: 'not_found' }, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/overview')

    expect(await screen.findByRole('link', { name: 'Cooling system' })).toBeTruthy()
    const summaryBeforeSearch = screen.getByLabelText('Overview summary').textContent
    const insightsBeforeSearch = screen.getByLabelText('Overview insights').textContent
    const requestsBeforeSearch = fetchMock.mock.calls.length

    await userEvent.type(screen.getByRole('textbox', { name: 'Search Observations' }), '  reactor PRESSURE  ')

    const rows = screen.getByRole('list', { name: 'Observations' })
    expect(rows.textContent).toContain('Pressure control')
    expect(rows.textContent).not.toContain('Cooling system')
    expect(screen.getByLabelText('Overview summary').textContent).toBe(summaryBeforeSearch)
    expect(screen.getByLabelText('Overview insights').textContent).toBe(insightsBeforeSearch)
    expect(fetchMock).toHaveBeenCalledTimes(requestsBeforeSearch)
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit | undefined)?.method === undefined)).toBe(true)
  })

  it('keeps successful definitions searchable when initial runtime history is unavailable', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/observations')) return Promise.resolve(response([definition, secondDefinition]))
      if (url.endsWith('/observation-runs')) return Promise.resolve(response({ code: 'offline' }, 503))
      return Promise.resolve(response({ code: 'not_found' }, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/overview')

    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Some monitoring data is unavailable. Successful sections remain visible.'))
    const summaryBeforeSearch = screen.getByLabelText('Overview summary').textContent
    const insightsBeforeSearch = screen.getByLabelText('Overview insights').textContent
    const requestsBeforeSearch = fetchMock.mock.calls.length

    await userEvent.type(screen.getByRole('textbox', { name: 'Search Observations' }), ' cooling ')

    const rows = screen.getByRole('list', { name: 'Observations' })
    expect(rows.textContent).toContain('Cooling system')
    expect(rows.textContent).not.toContain('Pressure control')
    expect(screen.getByText('Runtime unavailable')).toBeTruthy()
    expect(screen.getByLabelText('Overview summary').textContent).toBe(summaryBeforeSearch)
    expect(screen.getByLabelText('Overview insights').textContent).toBe(insightsBeforeSearch)
    expect(fetchMock).toHaveBeenCalledTimes(requestsBeforeSearch)
  })

  it('shows complete failure distinctly and retries both independent sources', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/observations') || url.endsWith('/observation-runs')) return Promise.resolve(response({ code: 'offline' }, 503))
      return Promise.resolve(response({ code: 'not_found' }, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/overview')

    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Unable to load Overview monitoring data.'))
    expect(screen.queryByText('No Observation definitions exist yet.')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
  })

  it('retains a complete snapshot with stale feedback when a manual refresh fails', async () => {
    let runRequests = 0
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/observations')) return Promise.resolve(response([definition]))
      if (url.endsWith('/observation-runs')) {
        runRequests += 1
        return Promise.resolve(runRequests === 1 ? response([run()]) : response({ code: 'offline' }, 503))
      }
      return Promise.resolve(response({ code: 'not_found' }, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/overview')

    expect(await screen.findByRole('link', { name: 'Open latest run cooling-run' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Some monitoring data is stale. Last successful data remains visible.'))
    expect(screen.getByRole('link', { name: 'Open latest run cooling-run' })).toBeTruthy()
  })

  it('presents the latest successful client refresh across manual and automatic refreshes without advancing it on failure', async () => {
    vi.useFakeTimers()
    const initialTime = new Date('2026-09-10T12:00:00Z')
    const manualTime = new Date('2026-09-10T12:01:00Z')
    vi.setSystemTime(initialTime)
    let runRequests = 0
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method !== undefined) return Promise.resolve(response({ code: 'method_not_allowed' }, 405))
      if (url.endsWith('/observations')) return Promise.resolve(response([definition]))
      if (url.endsWith('/observation-runs')) {
        runRequests += 1
        return Promise.resolve(runRequests === 4 ? response({ code: 'offline' }, 503) : response([run('running')]))
      }
      return Promise.resolve(response({ code: 'not_found' }, 404))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/overview')

    await act(async () => { for (let index = 0; index < 6; index += 1) await Promise.resolve() })
    expect(screen.getByLabelText(`Last refresh was received by this client at ${initialTime.toLocaleString()}`)).toBeTruthy()

    vi.setSystemTime(manualTime)
    await act(async () => { screen.getByRole('button', { name: 'Refresh' }).click(); for (let index = 0; index < 6; index += 1) await Promise.resolve() })
    expect(screen.getByLabelText(`Last refresh was received by this client at ${manualTime.toLocaleString()}`)).toBeTruthy()

    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    const automaticTime = new Date('2026-09-10T12:01:05Z')
    expect(screen.getByLabelText(`Last refresh was received by this client at ${automaticTime.toLocaleString()}`)).toBeTruthy()

    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(screen.getByLabelText(`Last refresh was received by this client at ${automaticTime.toLocaleString()}`)).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Some monitoring data is stale. Last successful data remains visible.')
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit | undefined)?.method === undefined)).toBe(true)
  })

  it('updates active-run-derived state after polling while keeping the displayed dashboard usable', async () => {
    vi.useFakeTimers()
    let runRequests = 0
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.endsWith('/observations')) return Promise.resolve(response([definition]))
      if (url.endsWith('/observation-runs')) {
        runRequests += 1
        return Promise.resolve(response(runRequests === 1 ? [run('running')] : [run('completed')]))
      }
      return Promise.resolve(response({ code: 'not_found' }, 404))
    }))
    renderAt('/overview')

    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve() })
    const summary = screen.getByLabelText('Overview summary')
    const activeSummaryCard = within(summary).getByText('Active Observations').closest('article')
    expect(activeSummaryCard?.textContent).toContain('1')
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
    expect(within(summary).getByText('Active Observations').closest('article')?.textContent).toContain('0')
    expect(screen.getByRole('link', { name: 'Open latest run cooling-run' })).toBeTruthy()
  })

  it('preserves Overview information in semantic narrow and desktop structures without unsupported dashboard controls', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.endsWith('/observations')) return Promise.resolve(response([definition]))
      if (url.endsWith('/observation-runs')) return Promise.resolve(response([run('completed')]))
      return Promise.resolve(response({ code: 'not_found' }, 404))
    }))
    renderAt('/overview')

    expect(await screen.findByRole('list', { name: 'Observations' })).toBeTruthy()
    const primaryGrid = screen.getByTestId('overview-primary-grid')
    expect(primaryGrid.className).toContain('xl:grid-cols-')
    expect(primaryGrid.className).toContain('xl:items-start')
    expect(screen.getByTestId('observations-collection').compareDocumentPosition(screen.getByLabelText('Overview insights')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    for (const label of ['Observation', 'Latest run', 'Analytical state', 'Execution / duration', 'Recent runs', 'Action']) expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Cooling system' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Open latest run cooling-run' })).toBeTruthy()
    expect(screen.queryByRole('img', { name: /avatar|user/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /time range|health/i })).toBeNull()
    expect(screen.queryByRole('combobox', { name: /time range|health/i })).toBeNull()
    expect(screen.queryByText(/health status|system health/i)).toBeNull()
    expect(screen.queryByRole('button', { name: /execution status partial/i })).toBeNull()
    expect(screen.queryByText('No findings are present in the five latest analyzed runs.')).toBeNull()
  })
})
