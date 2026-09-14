import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { ObservationResponse } from './types'

const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status})
const definition=(operational_context:string|null):ObservationResponse=>({id:'observation-1',name:'Cooling health',description:null,objective:'Observe cooling',operational_context,schema_version:1,lenses:[],alert_lenses:[{id:'alert',name:'Cooling alerts',type:'alert',href:'/alerts/alert',description:null,source:'jira_track_and_release',selector:{query:'project=COOL'},analysis_objectives:[],reference_periods:[],observation_href:'/observations/observation-1'}],relationships:[],href:'/observations/observation-1'})
const renderAt=(path:string)=>render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>)

afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})

describe('Operational context UI',()=>{
  it('starts empty drafts collapsed, preserves exact text through the aggregate request, and opens field errors',async()=>{
    const user=userEvent.setup(),created=definition('line one\nline two'),fetchMock=vi.fn().mockImplementation((url:string,init?:RequestInit)=>url==='/api/v1/observations'&&init?.method==='POST'?Promise.resolve(response(created,201)):Promise.resolve(response(created)))
    vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new')
    const disclosure=screen.getByText('Add operational context (optional)').closest('details')!
    expect(disclosure.open).toBe(false)
    await user.click(screen.getByText('Add operational context (optional)'))
    const field=screen.getByLabelText('Operational context (optional)')
    await user.type(field,'  startup\nCooling terminology  ')
    expect((field as HTMLTextAreaElement).value).toBe('  startup\nCooling terminology  ')
    await user.clear(field);await user.type(field,' \n ')
    await user.click(screen.getByRole('button',{name:'Create Observation'}))
    expect((await screen.findAllByText('Operational context cannot be blank.')).length).toBeGreaterThan(0)
    expect(disclosure.open).toBe(true)
    await user.clear(field);await user.type(field,'  startup\nCooling terminology  ')
    await user.type(screen.getByLabelText('Name'),'Cooling health');await user.type(screen.getByLabelText('Objective'),'Observe cooling');await user.click(screen.getByText('Add Alert Lens'));await user.type(screen.getByLabelText(/^Name\b/),'Cooling alerts');await user.type(screen.getByLabelText('Provider selector'),'project=COOL');await user.click(screen.getByRole('button',{name:'Apply changes'}))
    await user.click(screen.getByRole('button',{name:'Create Observation'}));await screen.findByText(/created successfully/i)
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body)).operational_context).toBe('  startup\nCooling terminology  ')
  })

  it('opens populated edit drafts and preserves multiline context in review and read-only inspection',async()=>{
    const saved=definition('first line\nsecond line'),fetchMock=vi.fn().mockResolvedValue(response(saved));vi.stubGlobal('fetch',fetchMock)
    renderAt('/observations/observation-1/edit')
    const field=await screen.findByLabelText('Operational context (optional)')
    expect((field as HTMLTextAreaElement).value).toBe('first line\nsecond line')
    expect(screen.getByRole('heading',{name:'Review'}).closest('section')?.textContent).toContain('first line\nsecond line')
  })
})
