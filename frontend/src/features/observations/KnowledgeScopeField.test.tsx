import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { KnowledgeScopeField } from './KnowledgeScopeField'
import type { ObservationDraft } from './draft'

const draft: ObservationDraft = { name: 'Cooling', description: 'Context', objective: 'Observe', lenses: [], alert_lenses: [], relationships: [] }
function Field() { const [current, setCurrent] = useState(draft); return <KnowledgeScopeField draft={current} onChange={knowledge_scope => setCurrent({ ...current, knowledge_scope })} /> }

afterEach(() => vi.unstubAllGlobals())

describe('KnowledgeScopeField', () => {
  it('does not request advice while editing and applies a returned scope only after acceptance', async () => {
    const user = userEvent.setup(); const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ service_ids: ['mprm-server'] })))
    vi.stubGlobal('fetch', fetchMock)
    render(<Field />)
    await user.type(screen.getByLabelText('Service ID'), 'manual-service')
    expect(fetchMock).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Suggest knowledge scope' }))
    expect(await screen.findByText(/Suggested knowledge scope: mprm-server/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Accept suggestion' }))
    expect(screen.getByLabelText('Selected knowledge services').textContent).toContain('mprm-server')
    expect((screen.getByLabelText('Version for mprm-server (optional)') as HTMLInputElement).value).toBe('')
  })

  it('dismisses a suggestion without changing the local draft', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ service_ids: ['mprm-server'] }))))
    render(<Field />)
    await user.click(screen.getByRole('button', { name: 'Suggest knowledge scope' }))
    expect(await screen.findByText(/Suggested knowledge scope: mprm-server/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByText(/Suggested knowledge scope/)).toBeNull()
    expect(screen.queryByLabelText('Selected knowledge services')).toBeNull()
  })

  it('keeps service versions independent through editing and removal', async () => {
    const user = userEvent.setup()
    render(<Field />)
    await user.type(screen.getByLabelText('Service ID'), 'first-service')
    await user.click(screen.getByRole('button', { name: 'Add service' }))
    await user.type(screen.getByLabelText('Version for first-service (optional)'), '1.0')
    await user.type(screen.getByLabelText('Service ID'), 'second-service')
    await user.click(screen.getByRole('button', { name: 'Add service' }))
    const first = screen.getByLabelText('Version for first-service (optional)') as HTMLInputElement
    const second = screen.getByLabelText('Version for second-service (optional)') as HTMLInputElement
    expect(first.value).toBe('1.0')
    expect(second.value).toBe('')
    await user.type(second, '3.0')
    expect(first.value).toBe('1.0')
    await user.click(screen.getByRole('button', { name: 'Remove second-service' }))
    expect(first.value).toBe('1.0')
    await user.click(screen.getByRole('button', { name: 'Remove first-service' }))
    await user.type(screen.getByLabelText('Service ID'), 'third-service')
    await user.click(screen.getByRole('button', { name: 'Add service' }))
    expect((screen.getByLabelText('Version for third-service (optional)') as HTMLInputElement).value).toBe('')
  })

  it('adds suggested services without versions and preserves entered versions', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ service_ids: ['second-service'] }))))
    render(<Field />)
    await user.type(screen.getByLabelText('Service ID'), 'first-service')
    await user.click(screen.getByRole('button', { name: 'Add service' }))
    await user.type(screen.getByLabelText('Version for first-service (optional)'), '1.0')
    await user.click(screen.getByRole('button', { name: 'Suggest knowledge scope' }))
    expect(await screen.findByText(/Suggested knowledge scope: second-service/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Accept suggestion' }))
    expect((screen.getByLabelText('Version for first-service (optional)') as HTMLInputElement).value).toBe('1.0')
    expect((screen.getByLabelText('Version for second-service (optional)') as HTMLInputElement).value).toBe('')
  })

  it('keeps empty and failed suggestions advisory and non-blocking', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ service_ids: [] }))).mockResolvedValueOnce(new Response('{}', { status: 503 })))
    render(<Field />)
    await user.click(screen.getByRole('button', { name: 'Suggest knowledge scope' }))
    expect(await screen.findByText(/No knowledge scope suggestion is available/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Suggest knowledge scope' }))
    expect(await screen.findByText(/No knowledge scope suggestion is available/)).toBeTruthy()
    expect(screen.queryByLabelText('Selected knowledge services')).toBeNull()
  })

  it('aborts a pending suggestion when the field unmounts', async () => {
    const user = userEvent.setup(); let signal: AbortSignal | undefined
    vi.stubGlobal('fetch', vi.fn((_: string, init?: RequestInit) => { signal = init?.signal as AbortSignal; return new Promise<Response>(() => {}) }))
    const view = render(<Field />)
    await user.click(screen.getByRole('button', { name: 'Suggest knowledge scope' }))
    expect(signal).toBeDefined()
    view.unmount()
    expect(signal?.aborted).toBe(true)
  })

  it('discards a response made stale by an explicit scope edit', async () => {
    const user = userEvent.setup(); let resolve: (value: Response) => void = () => {}
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise<Response>(done => { resolve = done })))
    render(<Field />)
    await user.click(screen.getByRole('button', { name: 'Suggest knowledge scope' }))
    await user.type(screen.getByLabelText('Service ID'), 'manual')
    await user.click(screen.getByRole('button', { name: 'Add service' }))
    resolve(new Response(JSON.stringify({ service_ids: ['mprm-server'] })))
    await new Promise(done => setTimeout(done, 0))
    expect(screen.queryByText(/Suggested knowledge scope/)).toBeNull()
    expect(screen.getByLabelText('Selected knowledge services').textContent).toContain('manual')
  })
})
