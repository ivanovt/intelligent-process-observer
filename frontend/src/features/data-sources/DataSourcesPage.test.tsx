import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { DefinitionCapabilities, PrometheusSourceCapability } from '../observations/types'

const bearerConfiguration = (id: string, name: string) => ({ id, name, base_url: `https://${id}.example.invalid`, credentials: { type: 'bearer_token' as const } })
const basicConfiguration = (id: string, name: string, username: string) => ({ id, name, base_url: `https://${id}.example.invalid`, credentials: { type: 'basic_auth' as const, username } })
const configurationWithoutUrl = (id: string, name: string) => ({ id, name, credentials: { type: 'bearer_token' as const } })
const source = (id: string, name: string, configuration: PrometheusSourceCapability['configuration'] = bearerConfiguration(id, name)): PrometheusSourceCapability => ({ id, name, configuration })
const capabilities = (sources: PrometheusSourceCapability[]): DefinitionCapabilities => ({ metric: [{ adapter_type: 'prometheus', sources }] })

function deferred<T>() {
  let resolve: (value: T) => void
  let reject: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve: resolve!, reject: reject! }
}

function renderAt(path = '/data-sources') {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('DataSourcesPage', () => {
  it('renders the route in the shared shell with active Data Sources navigation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(capabilities([])), { status: 200 })))
    renderAt()

    expect(await screen.findByText('No Metric sources are configured')).toBeTruthy()
    const dataSources = screen.getByRole('link', { name: 'Data Sources' })
    expect(dataSources.getAttribute('href')).toBe('/data-sources')
    expect(dataSources.getAttribute('aria-current')).toBe('page')
    expect(screen.getByRole('link', { name: 'Runs' }).getAttribute('href')).toBe('/runs')
  })

  it('shows an explicit loading state before presenting configured sources', async () => {
    const request = deferred<Response>()
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(request.promise))
    renderAt()

    expect(screen.getByText('Loading Metric sources')).toBeTruthy()
    expect(screen.queryByLabelText('Configured Metric sources')).toBeNull()
    request.resolve(new Response(JSON.stringify(capabilities([source('primary', 'Primary metrics')])), { status: 200 }))
    expect(await screen.findByText('Primary metrics')).toBeTruthy()
  })

  it('shows a retryable error instead of treating failures as an empty registry', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ code: 'unavailable', message: 'No connection' }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(capabilities([])), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    renderAt()

    expect((await screen.findByRole('alert')).textContent).toContain('Unable to load Metric sources')
    expect(screen.queryByText('No Metric sources are configured')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('No Metric sources are configured')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('renders each safe source once in API order without connection details or source lifecycle controls', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(capabilities([
      source('secondary', 'Secondary metrics'),
      source('primary', 'Primary metrics'),
    ])), { status: 200 })))
    renderAt()

    const list = await screen.findByLabelText('Configured Metric sources')
    expect(list.textContent).toMatch(/Secondary metrics[\s\S]*secondary[\s\S]*Primary metrics[\s\S]*primary/)
    expect(screen.getAllByText('Prometheus')).toHaveLength(2)
    expect(screen.getAllByText('Available for Metric Lens')).toHaveLength(2)
    expect(screen.queryByText(/https:\/\//)).toBeNull()
    expect(screen.queryByText(/Authorization|username|health|diagnostic/i)).toBeNull()
    for (const label of ['Add source', 'Edit', 'Delete', 'Enable', 'Disable', 'Test connection']) {
      expect(screen.queryByRole('button', { name: label })).toBeNull()
    }
  })

  it('keeps each source configuration collapsed until its independent accessible control is activated', async () => {
    const first = source('primary', 'Primary metrics')
    const second = source('secondary', 'Secondary metrics', basicConfiguration('secondary', 'Secondary metrics', 'observe-reader'))
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(capabilities([first, second])), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    renderAt()

    await screen.findByText('Primary metrics')
    const [primaryButton, secondaryButton] = screen.getAllByRole('button', { name: 'Show configuration' })
    expect(primaryButton.getAttribute('aria-expanded')).toBe('false')
    expect(secondaryButton.getAttribute('aria-expanded')).toBe('false')
    expect(document.getElementById(primaryButton.getAttribute('aria-controls')!)).toBeNull()

    await userEvent.click(primaryButton)
    const primaryPaneId = primaryButton.getAttribute('aria-controls')!
    const primaryPane = document.getElementById(primaryPaneId)!
    expect(primaryButton.getAttribute('aria-expanded')).toBe('true')
    expect(primaryPane.textContent).toBe(JSON.stringify(first.configuration, null, 2))
    expect(primaryPane.querySelector('pre > code')).toBeTruthy()
    expect(primaryPane.className).toContain('overflow-x-auto')
    expect(secondaryButton.getAttribute('aria-expanded')).toBe('false')
    expect(document.getElementById(secondaryButton.getAttribute('aria-controls')!)).toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await userEvent.click(secondaryButton)
    const secondaryPane = document.getElementById(secondaryButton.getAttribute('aria-controls')!)!
    expect(secondaryPane.textContent).toBe(JSON.stringify(second.configuration, null, 2))
    expect(primaryPane.isConnected).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await userEvent.click(primaryButton)
    expect(document.getElementById(primaryPaneId)).toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('renders an API-omitted unsafe URL as-is without a replacement or status', async () => {
    const unsafe = source('primary', 'Primary metrics', configurationWithoutUrl('primary', 'Primary metrics'))
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(capabilities([unsafe])), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    renderAt()

    const button = await screen.findByRole('button', { name: 'Show configuration' })
    await userEvent.click(button)

    const pane = document.getElementById(button.getAttribute('aria-controls')!)!
    expect(pane.textContent).toBe(JSON.stringify(unsafe.configuration, null, 2))
    expect(pane.textContent).not.toContain('base_url')
    expect(pane.textContent).not.toMatch(/health|diagnostic|status/i)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('gives safe empty-registry configuration guidance with the current nested credential shapes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(capabilities([])), { status: 200 })))
    const { container } = renderAt()

    expect((await screen.findAllByText(/PROMETHEUS_SOURCES/)).length).toBeGreaterThan(0)
    expect(screen.getByText('Bearer token (placeholder only)')).toBeTruthy()
    expect(screen.getByText('Basic authentication (placeholder only)')).toBeTruthy()
    const [bearer, basic] = Array.from(container.querySelectorAll('pre')).map((example) => example.textContent ?? '')
    expect(bearer).toMatch(/"credentials":\s+\{\n\s+"type":\s+"bearer_token",\n\s+"token":\s+"replace-with-a-real-secret"\n\s+\}/)
    expect(basic).toMatch(/"credentials":\s+\{\n\s+"type":\s+"basic_auth",\n\s+"username":\s+"replace-with-a-real-username",\n\s+"password":\s+"replace-with-a-real-secret"\n\s+\}/)
    expect(bearer).not.toMatch(/\n\s{4}"bearer_token":/)
    expect(basic).not.toMatch(/\n\s{4}"username":|\n\s{4}"password":/)
    expect(screen.getByText(/multiple Prometheus systems are supported/i)).toBeTruthy()
    expect(screen.getByText(/Restart the backend/)).toBeTruthy()
    expect(screen.getByText(/never commit them/i)).toBeTruthy()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('button', { name: /save|apply|configure/i })).toBeNull()
  })

  it('refreshes the existing capabilities endpoint without mutating a source', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(capabilities([source('primary', 'Primary metrics')])), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(capabilities([source('primary', 'Primary metrics'), source('secondary', 'Secondary metrics')])), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    renderAt()

    expect(await screen.findByText('Primary metrics')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh sources' }))
    expect(await screen.findByText('Secondary metrics')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls.every(([url, init]) => url === '/api/v1/observation-definition-capabilities' && (!init || !(init as RequestInit).method))).toBe(true)
  })

  it('aborts a capabilities request when the Data Sources view unmounts', async () => {
    let signal: AbortSignal | undefined
    vi.stubGlobal('fetch', vi.fn((_url, init) => {
      signal = (init as RequestInit).signal as AbortSignal
      return new Promise(() => undefined)
    }))
    const result = renderAt()

    await waitFor(() => expect(signal).toBeDefined())
    result.unmount()
    expect(signal?.aborted).toBe(true)
  })

  it('keeps the latest refresh result when an abandoned request resolves late', async () => {
    const abandoned = deferred<Response>()
    const active = deferred<Response>()
    vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(abandoned.promise).mockReturnValueOnce(active.promise))
    renderAt()

    await userEvent.click(screen.getByRole('button', { name: 'Refresh sources' }))
    active.resolve(new Response(JSON.stringify(capabilities([source('active', 'Active metrics')])), { status: 200 }))
    expect(await screen.findByText('Active metrics')).toBeTruthy()
    abandoned.resolve(new Response(JSON.stringify(capabilities([source('abandoned', 'Abandoned metrics')])), { status: 200 }))
    await new Promise((resolve) => setTimeout(resolve))
    expect(screen.getByText('Active metrics')).toBeTruthy()
    expect(screen.queryByText('Abandoned metrics')).toBeNull()
  })
})
