import { afterEach, describe, expect, it, vi } from 'vitest'
import { getOverviewRuntime } from './api'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('getOverviewRuntime', () => {
  it('loads the dedicated resilient Overview endpoint without using strict run history', async () => {
    const payload = { schema_version: '1.0', items: [], limited_run_count: 0 }
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify(payload), { status: 200 })))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getOverviewRuntime()).resolves.toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/overview-runtime', { signal: undefined })
  })

  it('preserves an infrastructure failure as a rejected request', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ code: 'runtime_read_unavailable', message: 'Runtime unavailable' }), { status: 503 }))))

    await expect(getOverviewRuntime()).rejects.toMatchObject({ status: 503, code: 'runtime_read_unavailable' })
  })
})
