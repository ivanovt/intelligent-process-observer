import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RunObservationDialog } from './RunObservationDialog'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunLaunchRequest, ObservationRunSummary } from './types'

const definitions: ObservationSummary[] = [
  { id: 'never-run', name: 'Never run first', description: null, objective: 'Observe', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/never-run' },
  { id: 'active', name: 'Known active second', description: null, objective: 'Observe', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/active' },
]
const activeRun: ObservationRunSummary = { id: 'active-run', observation: { id: 'active', name: 'Known active second' }, analysis_window: { from: '2026-09-09T11:00:00Z', to: '2026-09-09T12:00:00Z' }, status: 'running', reason: null, analytical_state: null, created_at: '2026-09-09T12:00:00Z', started_at: '2026-09-09T12:00:00Z', finished_at: null, duration_seconds: null, href: '/api/v1/observation-runs/active-run' }
const fixedClock = () => new Date('2026-09-09T12:00:00.000Z')
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })

function renderDialog(overrides: Partial<React.ComponentProps<typeof RunObservationDialog>> = {}) {
  const onLaunch = vi.fn<(payload: ObservationRunLaunchRequest) => Promise<void>>().mockResolvedValue(undefined)
  const onClose = vi.fn()
  render(<MemoryRouter><RunObservationDialog activeRuns={[activeRun]} clock={fixedClock} onClose={onClose} onLaunch={onLaunch} {...overrides} /></MemoryRouter>)
  return { onClose, onLaunch }
}

function ReopenHarness() {
  const [open, setOpen] = useState(true)
  return <MemoryRouter><button type="button" onClick={() => setOpen(true)}>Open dialog</button>{open ? <RunObservationDialog activeRuns={[]} onClose={() => setOpen(false)} onLaunch={async () => undefined} /> : null}</MemoryRouter>
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('RunObservationDialog', () => {
  it('loads definitions independently in API order, keeps never-run definitions eligible, and disables only known active ones', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(definitions)))
    renderDialog()
    const selector = await screen.findByLabelText('Observation to run')
    expect([...((selector as HTMLSelectElement).options)].map((option) => option.text)).toEqual(['Choose an Observation', 'Never run first', 'Known active second — active run in progress'])
    expect((screen.getByRole('option', { name: /Known active second/ }) as HTMLOptionElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Run Observation' }) as HTMLButtonElement).disabled).toBe(true)
    await userEvent.selectOptions(selector, 'never-run')
    expect((screen.getByRole('button', { name: 'Run Observation' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps loading, retryable failure, and successful empty definitions distinct', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response({ code: 'unavailable' }, 503)).mockResolvedValueOnce(response([]))
    vi.stubGlobal('fetch', fetchMock)
    renderDialog()
    expect((await screen.findByRole('alert')).textContent).toContain('Unable to load Observation definitions')
    expect(screen.queryByText('No Observation is available to run.')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('No Observation is available to run.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'New Observation' }).getAttribute('href')).toBe('/observations/new')
    expect((screen.getByRole('button', { name: 'Run Observation' }) as HTMLButtonElement).disabled).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('submits one concrete selected preset window and retains inputs after a launch failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(definitions)))
    const { onLaunch } = renderDialog({ activeRuns: [] })
    await userEvent.selectOptions(await screen.findByLabelText('Observation to run'), 'never-run')
    await userEvent.selectOptions(screen.getByLabelText('Relative analysis range'), '1h')
    onLaunch.mockRejectedValueOnce(new Error('unavailable'))
    await userEvent.click(screen.getByRole('button', { name: 'Run Observation' }))
    await screen.findByRole('alert')
    expect(onLaunch).toHaveBeenCalledTimes(1)
    expect(onLaunch).toHaveBeenCalledWith({ observation_id: 'never-run', analysis_window: { from: '2026-09-09T11:00:00.000Z', to: '2026-09-09T12:00:00.000Z' } })
    expect((screen.getByLabelText('Observation to run') as HTMLSelectElement).value).toBe('never-run')
    expect((screen.getByLabelText('Relative analysis range') as HTMLSelectElement).value).toBe('1h')
  })

  it('rejects unsupported expressions before launch and renders server conflict as an existing active run', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(definitions)))
    const { onLaunch } = renderDialog({ activeRuns: [] })
    await userEvent.selectOptions(await screen.findByLabelText('Observation to run'), 'never-run')
    await userEvent.click(screen.getByLabelText('Expressions'))
    await userEvent.clear(screen.getByLabelText('From expression'))
    await userEvent.type(screen.getByLabelText('From expression'), 'now-5m')
    await userEvent.click(screen.getByRole('button', { name: 'Run Observation' }))
    expect(await screen.findByText(/Use exactly now/)).toBeTruthy()
    expect(onLaunch).not.toHaveBeenCalled()

    await userEvent.clear(screen.getByLabelText('From expression'))
    await userEvent.type(screen.getByLabelText('From expression'), 'now-15m')
    onLaunch.mockRejectedValueOnce({ status: 409 })
    await userEvent.click(screen.getByRole('button', { name: 'Run Observation' }))
    expect(await screen.findByText(/already has an active run/)).toBeTruthy()
    expect(onLaunch).toHaveBeenCalledTimes(1)
  })

  it('requires complete absolute UTC fields and shows validation feedback before launch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(definitions)))
    const { onLaunch } = renderDialog({ activeRuns: [] })
    await userEvent.selectOptions(await screen.findByLabelText('Observation to run'), 'never-run')
    await userEvent.click(screen.getByLabelText('Absolute UTC'))

    const from = screen.getByLabelText('From (UTC)') as HTMLInputElement
    const to = screen.getByLabelText('To (UTC)') as HTMLInputElement
    expect(from.type).toBe('datetime-local')
    expect(from.step).toBe('1')
    expect(to.type).toBe('datetime-local')
    expect(to.step).toBe('1')
    expect(from.value).toBe('')
    expect(to.value).toBe('')
    expect((screen.getByRole('button', { name: 'Run Observation' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('alert')).toBeTruthy()

    fireEvent.change(from, { target: { value: '2026-09-09T10:00:00' } })
    fireEvent.change(to, { target: { value: '2026-09-09T13:00:00' } })
    expect((screen.getByRole('button', { name: 'Run Observation' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('To cannot be in the future.')).toBeTruthy()
    expect(onLaunch).not.toHaveBeenCalled()
  })

  it('submits an exact absolute UTC interval and retains it after a launch failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(definitions)))
    const { onLaunch } = renderDialog({ activeRuns: [] })
    await userEvent.selectOptions(await screen.findByLabelText('Observation to run'), 'never-run')
    await userEvent.click(screen.getByLabelText('Absolute UTC'))
    const from = screen.getByLabelText('From (UTC)') as HTMLInputElement
    const to = screen.getByLabelText('To (UTC)') as HTMLInputElement
    fireEvent.change(from, { target: { value: '2026-09-09T10:00:00' } })
    fireEvent.change(to, { target: { value: '2026-09-09T11:00:00' } })

    onLaunch.mockRejectedValueOnce(new Error('unavailable'))
    await userEvent.click(screen.getByRole('button', { name: 'Run Observation' }))
    await screen.findByText(/Unable to launch this Observation/)
    expect(onLaunch).toHaveBeenCalledWith({ observation_id: 'never-run', analysis_window: { from: '2026-09-09T10:00:00.000Z', to: '2026-09-09T11:00:00.000Z' } })
    expect(from.value).toBe('2026-09-09T10:00')
    expect(to.value).toBe('2026-09-09T11:00')
  })

  it('aborts an in-flight definition request when closed and starts a fresh request when reopened', async () => {
    const signals: AbortSignal[] = []
    vi.stubGlobal('fetch', vi.fn((_url, init) => { signals.push((init as RequestInit).signal as AbortSignal); return new Promise(() => undefined) }))
    render(<ReopenHarness />)
    await waitFor(() => expect(signals).toHaveLength(1))
    await userEvent.click(screen.getByRole('button', { name: 'Close Run Observation dialog' }))
    expect(signals[0].aborted).toBe(true)
    await userEvent.click(screen.getByRole('button', { name: 'Open dialog' }))
    await waitFor(() => expect(signals).toHaveLength(2))
  })
})
