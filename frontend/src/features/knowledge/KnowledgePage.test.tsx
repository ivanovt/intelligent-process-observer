import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { KnowledgePage } from './KnowledgePage'

afterEach(()=>vi.unstubAllGlobals())
describe('KnowledgePage',()=>{
  it('offers only manual PDF or Markdown upload and no external-sync, editor, or role controls',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify([]))));render(<MemoryRouter><KnowledgePage/></MemoryRouter>);expect(await screen.findByText('Upload knowledge document')).toBeTruthy();const file=screen.getByLabelText('Source file') as HTMLInputElement;expect(file.accept).toContain('application/pdf');expect(file.accept).toContain('text/markdown');expect(screen.queryByText(/Confluence|sync|editor|role/i)).toBeNull()})
})
