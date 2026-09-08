import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ObservationDetailPage } from './ObservationDetailPage'
const detail={id:'a',name:'Database Health',description:null,objective:'Observe',schema_version:1,lenses:[],alert_lenses:[],relationships:[],href:'/a'}
function renderDetail(){return render(<MemoryRouter initialEntries={['/observations/a']}><Routes><Route path="/observations/:observationId" element={<ObservationDetailPage/>}/><Route path="/observations" element={<p>List</p>}/></Routes></MemoryRouter>)}
afterEach(()=>vi.restoreAllMocks())
describe('ObservationDetailPage',()=>{it('renders a not-found state',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({code:'not_found',message:'No definition'}),{status:404})));renderDetail();expect(await screen.findByText('Definition not found')).toBeTruthy()});it('retries the same identity after a non-404 failure',async()=>{const fetchMock=vi.fn().mockResolvedValueOnce(new Response('{}',{status:500})).mockResolvedValueOnce(new Response(JSON.stringify(detail),{status:200}));vi.stubGlobal('fetch',fetchMock);renderDetail();await userEvent.click(await screen.findByText('Try again'));expect(await screen.findByText('Database Health')).toBeTruthy();expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/observations/a')})})
