import { describe, expect, it, vi } from 'vitest'
import { getKnowledgeChunk, knowledgeCitationDestination, parseCuratedLocator } from './api'

describe('curated knowledge citation routing', () => {
  const sourceId = 'knowledge-document:123e4567-e89b-12d3-a456-426614174000:v1'

  it('preserves an exact PDF page-local locator through the route and backend request', async () => {
    const reference = 'pdf:page:7:chunk:2'
    expect(knowledgeCitationDestination({ source_id: sourceId, reference })).toBe('/knowledge?document=123e4567-e89b-12d3-a456-426614174000&version=1&reference=pdf%3Apage%3A7%3Achunk%3A2')
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ordinal: 19, location: 'page 7, chunk 2', text: 'historical' })))
    vi.stubGlobal('fetch', fetchMock)
    await getKnowledgeChunk('123e4567-e89b-12d3-a456-426614174000', 1, parseCuratedLocator(reference)!)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/knowledge/documents/123e4567-e89b-12d3-a456-426614174000/versions/1/chunks/2?page=7', { signal: undefined })
    vi.unstubAllGlobals()
  })

  it('uses the document-local ordinal for Markdown and leaves unknown references inert', () => {
    expect(parseCuratedLocator('md:chunk:4')).toEqual({ reference: 'md:chunk:4', page: null, ordinal: 4 })
    expect(knowledgeCitationDestination({ source_id: sourceId, reference: 'md:chunk:4' })).toContain('reference=md%3Achunk%3A4')
    expect(knowledgeCitationDestination({ source_id: sourceId, reference: 'pdf:page:0:chunk:1' })).toBeNull()
    expect(knowledgeCitationDestination({ source_id: 'manual', reference: 'section 4' })).toBeNull()
  })
})
