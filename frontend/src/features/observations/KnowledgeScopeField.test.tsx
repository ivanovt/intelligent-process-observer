import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { KnowledgeScopeField } from './KnowledgeScopeField'
import type { ObservationDraft } from './draft'

const draft:ObservationDraft={name:'Cooling',description:'Context',objective:'Observe',lenses:[],alert_lenses:[],relationships:[]}
function Field(){const [current,setCurrent]=useState(draft);return <KnowledgeScopeField draft={current} onChange={knowledge_scope=>setCurrent({...current,knowledge_scope})}/>}
afterEach(()=>vi.unstubAllGlobals())
describe('KnowledgeScopeField',()=>{
  it('does not request advice while editing and applies a returned scope only after acceptance',async()=>{const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({service_ids:['mprm-server']})));vi.stubGlobal('fetch',fetchMock);render(<Field/>);await user.type(screen.getByLabelText('Service ID'),'manual-service');expect(fetchMock).not.toHaveBeenCalled();await user.click(screen.getByRole('button',{name:'Suggest knowledge scope'}));expect(await screen.findByText(/Suggested knowledge scope: mprm-server/)).toBeTruthy();await user.click(screen.getByRole('button',{name:'Accept suggestion'}));expect(screen.getByLabelText('Selected knowledge services').textContent).toContain('mprm-server')})
  it('keeps an empty suggestion advisory and non-blocking',async()=>{const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({service_ids:[]})));vi.stubGlobal('fetch',fetchMock);render(<Field/>);await user.click(screen.getByRole('button',{name:'Suggest knowledge scope'}));expect(await screen.findByText(/No knowledge scope suggestion is available/)).toBeTruthy();expect(screen.queryByLabelText('Selected knowledge services')).toBeNull()})
})
