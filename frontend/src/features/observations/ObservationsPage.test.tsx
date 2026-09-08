import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ObservationsPage } from './ObservationsPage'

const definition = { id:'a',name:'Database Health',description:'Database behavior',objective:'Observe',schema_version:1,lenses:[{id:'m',name:'Metric',type:'metric',href:'/m'}],alert_lenses:[],relationships:[],href:'/a' }
function renderPage() { return render(<BrowserRouter><ObservationsPage/></BrowserRouter>) }
afterEach(()=>vi.restoreAllMocks())
describe('ObservationsPage',()=>{
  it('lists supported composition and searches name and description only',async()=>{ vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify([definition]),{status:200})));renderPage();expect(await screen.findByText('Database Health')).toBeTruthy();expect(screen.getByText(/1 Metric lens/)).toBeTruthy();const input=screen.getByLabelText('Search observations');await userEvent.type(input,'behavior');expect(screen.getByText('Database Health')).toBeTruthy();await userEvent.clear(input);await userEvent.type(input,'Observe');expect(screen.getByText('No matching definitions')).toBeTruthy();expect(screen.queryByText('Latest run')).toBeNull();expect(screen.queryByText('Edit')).toBeNull() })
  it('shows a retryable error and retries the list request',async()=>{ const fetchMock=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({code:'unavailable',message:'No connection'}),{status:503})).mockResolvedValueOnce(new Response(JSON.stringify([]),{status:200}));vi.stubGlobal('fetch',fetchMock);renderPage();expect(await screen.findByRole('alert')).toBeTruthy();await userEvent.click(screen.getByText('Try again'));expect(await screen.findByText('No Observation definitions yet')).toBeTruthy();expect(fetchMock).toHaveBeenCalledTimes(2) })
  it('aborts abandoned list reads',async()=>{ let signal:AbortSignal|undefined;vi.stubGlobal('fetch',vi.fn((_url,init)=>{signal=(init as RequestInit).signal as AbortSignal;return new Promise(()=>{})}));const result=renderPage();await waitFor(()=>expect(signal).toBeDefined());result.unmount();expect(signal?.aborted).toBe(true) })
})
