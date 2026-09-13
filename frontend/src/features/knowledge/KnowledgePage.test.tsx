import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DocumentDetail, KnowledgePage } from './KnowledgePage'
import type { KnowledgeChunkLocation, KnowledgeDocument } from './api'

const documentId = '123e4567-e89b-12d3-a456-426614174000'
const version = (number: number, lifecycleState: 'imported' | 'approved' | 'deprecated', serviceTags = [{ service_id: 'cooling', aliases: ['chiller'], supported_versions: ['2.x'] }]) => ({ version: number, title: 'Cooling runbook', document_type: 'runbook' as const, authority: 'official' as const, owner: 'Operations', source_reference: `DOC-${number}`, media_type: 'application/pdf', content_hash: `hash-${number}`, extraction_state: 'ready' as const, lifecycle_state: lifecycleState, service_tags: serviceTags, indexed_chunk_locations: [] as KnowledgeChunkLocation[] })
const documentWith = (...versions: ReturnType<typeof version>[]) => ({ id: documentId, title: 'Cooling runbook', document_type: 'runbook' as const, authority: 'official' as const, service_tags: versions.flatMap((item) => item.service_tags), active_version: versions.find((item) => item.lifecycle_state === 'approved')?.version ?? null, versions })
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('KnowledgePage', () => {
  it('offers only manual PDF or Markdown upload and no external-sync, editor, or role controls', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response([])))
    render(<MemoryRouter><KnowledgePage /></MemoryRouter>)
    expect(await screen.findByText('Upload knowledge document')).toBeTruthy()
    const file = screen.getByLabelText('Source file') as HTMLInputElement
    expect(file.accept).toContain('application/pdf')
    expect(file.accept).toContain('text/markdown')
    expect(screen.queryByText(/Confluence|sync|editor|role/i)).toBeNull()
  })

  it('submits all entered service applicability tags, aliases, and supported-version labels', async () => {
    const uploaded = documentWith(version(1, 'imported'))
    const fetchMock = vi.fn((_: string, init?: RequestInit) => Promise.resolve(init?.method === 'POST' ? response(uploaded) : response([])))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><KnowledgePage /></MemoryRouter>)
    await screen.findByText('Upload knowledge document')
    await user.upload(screen.getByLabelText('Source file'), new File(['# Cooling'], 'runbook.md', { type: 'text/markdown' }))
    await user.type(screen.getByLabelText('Title'), 'Cooling runbook')
    await user.type(screen.getByLabelText('Owner'), 'Operations')
    await user.click(screen.getByRole('button', { name: 'Add service applicability' }))
    await user.type(screen.getByLabelText('Service ID 1'), 'cooling')
    await user.type(screen.getByLabelText('Service aliases 1 (optional)'), 'chiller, cooler')
    await user.type(screen.getByLabelText('Supported versions 1 (optional)'), '2.x, 3.x')
    await user.click(screen.getByRole('button', { name: 'Add service applicability' }))
    await user.type(screen.getByLabelText('Service ID 2'), 'compressor')
    await user.type(screen.getByLabelText('Service aliases 2 (optional)'), 'air')
    await user.type(screen.getByLabelText('Supported versions 2 (optional)'), '1.5')
    await user.click(screen.getByRole('button', { name: 'Upload document' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/knowledge/documents', expect.objectContaining({ method: 'POST' })))
    const uploadCall = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === 'POST')!
    const metadata = JSON.parse(((uploadCall[1] as RequestInit).body as FormData).get('metadata') as string)
    expect(metadata.service_tags).toEqual([
      { service_id: 'cooling', aliases: ['chiller', 'cooler'], supported_versions: ['2.x', '3.x'] },
      { service_id: 'compressor', aliases: ['air'], supported_versions: ['1.5'] },
    ])
  })

  it('shows immutable historical metadata and permits a later version upload without replacing it', async () => {
    const document = documentWith(version(1, 'deprecated', []), version(2, 'approved'))
    const fetchMock = vi.fn((url: string) => Promise.resolve(response(url.endsWith('/documents') ? [document] : document)))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={[`/knowledge?document=${documentId}&version=1&reference=pdf%3Apage%3A7%3Achunk%3A2`]}><KnowledgePage /></MemoryRouter>)
    expect(await screen.findByText('Version 1 · deprecated')).toBeTruthy()
    expect(screen.getAllByText(/Owner: Operations/)[0]).toBeTruthy()
    expect(screen.getByText(/Source reference: DOC-1/)).toBeTruthy()
    expect(screen.getAllByRole('link', { name: 'Download source' })[0].getAttribute('href')).toContain('/versions/1/source')
    await user.click(screen.getByRole('button', { name: 'Upload later version' }))
    expect(screen.getByText('Upload later immutable version')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Add service applicability' })).toHaveLength(2)
  })

  it('requires confirmation before lifecycle dispatch and sends approved actions to their endpoints', async () => {
    const document = documentWith(version(1, 'imported'), version(2, 'approved'))
    const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url) => Promise.resolve(response(url.endsWith('/documents') ? [document] : document)))
    vi.stubGlobal('fetch', fetchMock)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true)
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={[`/knowledge?document=${documentId}`]}><KnowledgePage /></MemoryRouter>)
    await screen.findByRole('button', { name: 'Approve version' })
    await user.click(screen.getByRole('button', { name: 'Approve version' }))
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === 'POST')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Approve version' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`/api/v1/knowledge/documents/${documentId}/versions/1/approve`, { method: 'POST', signal: undefined }))
    await user.click(screen.getByRole('button', { name: 'Deprecate version' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`/api/v1/knowledge/documents/${documentId}/versions/2/deprecate`, { method: 'POST', signal: undefined }))
    expect(confirm).toHaveBeenCalledTimes(3)
  })

  it('shows a safe error when a confirmed lifecycle action fails', async () => {
    const document = documentWith(version(2, 'approved'))
    const fetchMock = vi.fn((url: string, init?: RequestInit) => Promise.resolve(init?.method === 'POST' ? response({}, 503) : response(url.endsWith('/documents') ? [document] : document)))
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={[`/knowledge?document=${documentId}`]}><KnowledgePage /></MemoryRouter>)
    await screen.findByRole('button', { name: 'Deprecate version' })
    await user.click(screen.getByRole('button', { name: 'Deprecate version' }))
    expect((await screen.findByRole('alert')).textContent).toContain('The lifecycle action could not be completed. Try again.')
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/knowledge/documents/${documentId}/versions/2/deprecate`, { method: 'POST', signal: undefined })
  })
})

describe('DocumentDetail', () => {
  it('shows indexed Markdown heading and PDF page-local locations outside citation mode', () => {
    const document: KnowledgeDocument = documentWith(
      { ...version(1, 'deprecated', []), media_type: 'text/markdown', indexed_chunk_locations: [{ ordinal: 3, page_number: null, page_ordinal: null, heading_path: ['Operations', 'Cooling'] }] },
      { ...version(2, 'approved', []), indexed_chunk_locations: [{ ordinal: 5, page_number: 8, page_ordinal: 2, heading_path: null }] },
    )
    render(<DocumentDetail document={document} chunk={null} onAction={vi.fn()} onUploaded={vi.fn()} />)
    expect(screen.getAllByText('Indexed passage locations:')).toHaveLength(2)
    expect(screen.getByText('Markdown Operations > Cooling, chunk 3')).toBeTruthy()
    expect(screen.getByText('PDF page 8, chunk 2')).toBeTruthy()
    expect(screen.queryByText('Referenced knowledge passage')).toBeNull()
  })
})
