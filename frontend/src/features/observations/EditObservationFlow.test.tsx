import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import type { ObservationResponse } from './types'

const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status})
const alert=(id:string,name:string)=>({id,name,type:'alert' as const,href:`/alerts/${id}`,description:null,source:'jira_track_and_release' as const,selector:{query:`project=${id}`},analysis_objectives:['Assess recurrence'],reference_periods:[],observation_href:'/observations/observation-1'})
const metric=(id:string,name:string)=>({id,name,type:'metric' as const,href:`/metrics/${id}`,description:null,metric_id:id,adapter_type:'prometheus' as const,source_id:'primary',query:id,unit:'%',analysis_objectives:['spike'],reference_periods:[],observation_href:'/observations/observation-1'})
const definition=(overrides:Partial<ObservationResponse>={}):ObservationResponse=>({id:'observation-1',name:'Cooling health',description:null,objective:'Observe cooling',schema_version:1,lenses:[],alert_lenses:[alert('a1','First alert'),alert('a2','Second alert')],relationships:[],href:'/observations/observation-1',...overrides,operational_context:overrides.operational_context??null})
const renderAt=(path:string)=>render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>)
const renderBrowserAt=(path:string)=>{window.history.pushState({},'',path);return render(<BrowserRouter><App/></BrowserRouter>)}

afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})

describe('Observation aggregate editing',()=>{
  it('loads persisted values, saves exactly one PUT aggregate snapshot, and confirms the canonical detail',async()=>{
    const user=userEvent.setup(),persisted=definition(),saved={...persisted,name:'Updated cooling health'},fetchMock=vi.fn().mockResolvedValueOnce(response(persisted)).mockResolvedValueOnce(response(saved)).mockResolvedValueOnce(response(saved))
    vi.stubGlobal('fetch',fetchMock)
    renderAt('/observations/observation-1/edit')
    const name=await screen.findByLabelText('Name')
    expect((name as HTMLInputElement).value).toBe('Cooling health')
    await user.clear(name);await user.type(name,'Updated cooling health');await user.click(screen.getByRole('button',{name:'Save changes'}))
    expect(fetchMock.mock.calls.filter(([,init])=>(init as RequestInit|undefined)?.method==='PUT')).toHaveLength(1)
    expect(fetchMock.mock.calls[1]).toEqual(['/api/v1/observations/observation-1',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Updated cooling health',description:null,objective:'Observe cooling',operational_context:null,lenses:[],alert_lenses:[{id:'a1',name:'First alert',description:null,type:'alert',source:'jira_track_and_release',selector:{query:'project=a1'},analysis_objectives:['Assess recurrence'],reference_periods:[]},{id:'a2',name:'Second alert',description:null,type:'alert',source:'jira_track_and_release',selector:{query:'project=a2'},analysis_objectives:['Assess recurrence'],reference_periods:[]}],relationships:[]})}])
    expect(await screen.findByText(/updated successfully/i)).toBeTruthy()
    expect(screen.queryByText(/Ready to create/i)).toBeNull()
  })

  it('retains an edit draft after a save-time not-found response without falling back to create',async()=>{
    const user=userEvent.setup(),persisted=definition(),fetchMock=vi.fn().mockResolvedValueOnce(response(persisted)).mockResolvedValueOnce(response({code:'not_found',message:'Missing'},404))
    vi.stubGlobal('fetch',fetchMock);renderAt('/observations/observation-1/edit')
    const name=await screen.findByLabelText('Name');await user.clear(name);await user.type(name,'Local edit');await user.click(screen.getByRole('button',{name:'Save changes'}))
    expect(await screen.findByText(/no longer available/i)).toBeTruthy();expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Local edit')
    expect(fetchMock.mock.calls.some(([,init])=>(init as RequestInit|undefined)?.method==='POST')).toBe(false)
  })

  it('supports explicit collection removal and reordering in the one replacement payload',async()=>{
    const user=userEvent.setup(),persisted=definition(),fetchMock=vi.fn().mockResolvedValueOnce(response(persisted)).mockResolvedValueOnce(response({...persisted,alert_lenses:[alert('a2','Second alert')]})).mockResolvedValueOnce(response({...persisted,alert_lenses:[alert('a2','Second alert')]}))
    vi.stubGlobal('fetch',fetchMock);renderAt('/observations/observation-1/edit')
    await screen.findByLabelText('Name');await user.click(screen.getByRole('button',{name:'Move Second alert up'}));await user.click(screen.getByRole('button',{name:'Remove First alert'}));await user.click(screen.getByRole('button',{name:'Save changes'}))
    const payload=JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string)
    expect(payload.alert_lenses.map((item:{id:string})=>item.id)).toEqual(['a2'])
  })

  it('blocks saving a Relationship made invalid by Metric Lens removal without mutating its rule or sending PUT',async()=>{
    const user=userEvent.setup(),persisted=definition({lenses:[metric('m1','First metric'),metric('m2','Second metric')],alert_lenses:[],relationships:[{id:'r1',name:'Pressure relation',href:'/relationships/r1',description:null,participants:['m1','m2'],conditions:{},expected:{m1:{trend:{direction:'increasing'}},m2:{trend:{direction:'increasing'}}},observation_href:'/observations/observation-1'}]}),fetchMock=vi.fn().mockResolvedValue(response(persisted))
    vi.stubGlobal('fetch',fetchMock);renderAt('/observations/observation-1/edit')
    await screen.findByLabelText('Name');await user.click(screen.getByRole('button',{name:'Remove First metric'}));await user.click(screen.getByRole('button',{name:'Save changes'}))
    expect((await screen.findAllByText(/Relationship participants must be current Metric Lenses/i)).length).toBeGreaterThan(0);expect(fetchMock.mock.calls.some(([,init])=>(init as RequestInit|undefined)?.method==='PUT')).toBe(false)
  })

  it('distinguishes edit loading failures and recovers a direct nested URL by loading the parent aggregate without writes',async()=>{
    const fetchMock=vi.fn().mockResolvedValueOnce(response({code:'not_found',message:'Missing'},404)).mockResolvedValueOnce(response(definition()))
    vi.stubGlobal('fetch',fetchMock);const first=renderAt('/observations/missing/edit');expect(await screen.findByText('Definition not found')).toBeTruthy();first.unmount()
    renderAt('/observations/observation-1/edit/alert-lenses/new')
    expect(await screen.findByText(/previous draft is unavailable/i)).toBeTruthy();expect(fetchMock).toHaveBeenCalledTimes(2);expect(fetchMock.mock.calls.some(([,init])=>(init as RequestInit|undefined)?.method==='PUT')).toBe(false)
  })

  it('keeps a matching edit draft across nested Apply, Cancel, and browser-back without reloading it',async()=>{
    const user=userEvent.setup(),persisted=definition(),fetchMock=vi.fn().mockResolvedValue(response(persisted));vi.stubGlobal('fetch',fetchMock)
    renderBrowserAt('/observations/observation-1/edit')
    const general=await screen.findByLabelText('Name');await user.clear(general);await user.type(general,'Changed general')
    await user.click(screen.getByText('Add Alert Lens'));await user.type(screen.getByLabelText(/^Name\b/),'Applied alert');await user.type(screen.getByLabelText('Provider selector'),'project=applied');await user.click(screen.getByRole('button',{name:'Apply changes'}))
    expect((await screen.findByLabelText('Name') as HTMLInputElement).value).toBe('Changed general');expect(screen.getAllByText('Applied alert').length).toBeGreaterThan(0);expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('link',{name:/Edit Applied alert/}));await user.clear(screen.getByLabelText(/^Name\b/));await user.type(screen.getByLabelText(/^Name\b/),'Discarded alert');await user.click(screen.getByRole('button',{name:'Cancel'}));expect(screen.getAllByText('Applied alert').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('link',{name:/Edit Applied alert/}));await user.clear(screen.getByLabelText(/^Name\b/));await user.type(screen.getByLabelText(/^Name\b/),'Back discarded');await act(async()=>{window.history.back();window.dispatchEvent(new PopStateEvent('popstate'))});await screen.findByRole('heading',{name:'Alert lenses'});expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Changed general');expect(screen.getAllByText('Applied alert').length).toBeGreaterThan(0);expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('owns the draft by target identity across A-to-B navigation and nested B direct entry',async()=>{
    const user=userEvent.setup(),a=definition({id:'A',name:'Definition A',href:'/observations/A'}),b=definition({id:'B',name:'Definition B',href:'/observations/B'}),fetchMock=vi.fn().mockResolvedValueOnce(response(a)).mockResolvedValueOnce(response(b)).mockResolvedValueOnce(response(b)).mockResolvedValueOnce(response(b));vi.stubGlobal('fetch',fetchMock)
    renderBrowserAt('/observations/A/edit');const name=await screen.findByLabelText('Name');await user.clear(name);await user.type(name,'Unsaved A')
    await act(async()=>{window.history.pushState({},'', '/observations/B/edit/alert-lenses/new');window.dispatchEvent(new PopStateEvent('popstate'))})
    expect(await screen.findByText(/previous draft is unavailable/i)).toBeTruthy();expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Definition B');expect(fetchMock).toHaveBeenCalledTimes(2);expect(fetchMock.mock.calls.find(([,init])=>(init as RequestInit|undefined)?.method==='PUT')).toBeUndefined()
    await user.click(screen.getByRole('button',{name:'Save changes'}));const put=fetchMock.mock.calls.find(([,init])=>(init as RequestInit|undefined)?.method==='PUT')!;expect(put[0]).toBe('/api/v1/observations/B');expect(JSON.parse((put[1] as RequestInit).body as string).name).toBe('Definition B')
  })

  it('retries a non-not-found edit load failure and maps a PUT field error while retaining the draft',async()=>{
    const user=userEvent.setup(),persisted=definition(),fetchMock=vi.fn().mockResolvedValueOnce(response({code:'unavailable',message:'Offline'},503)).mockResolvedValueOnce(response(persisted)).mockResolvedValueOnce(response({code:'validation_error',message:'Correct selector.',field:'alert_lenses.0.selector.query'},422));vi.stubGlobal('fetch',fetchMock)
    renderAt('/observations/observation-1/edit');await user.click(await screen.findByText('Try again'));await screen.findByLabelText('Name');await user.click(screen.getByRole('button',{name:'Save changes'}));expect((await screen.findAllByText(/Correct selector/i)).length).toBeGreaterThan(0);expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Cooling health');expect(fetchMock.mock.calls.filter(([,init])=>(init as RequestInit|undefined)?.method==='PUT')).toHaveLength(1)
  })

  it('cancels the top-level edit without a write and returns to the persisted detail',async()=>{
    const user=userEvent.setup(),persisted=definition(),fetchMock=vi.fn().mockImplementation(()=>Promise.resolve(response(persisted)));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/observation-1/edit');await screen.findByLabelText('Name');await user.click(screen.getByRole('button',{name:'Cancel'}));expect(await screen.findByText('Read-only')).toBeTruthy();expect(fetchMock.mock.calls.some(([,init])=>(init as RequestInit|undefined)?.method==='PUT')).toBe(false)
  })

  it('shows one Edit breadcrumb when opening a persisted Relationship editor',async()=>{
    const user=userEvent.setup(),persisted=definition({lenses:[metric('m1','First metric'),metric('m2','Second metric')],alert_lenses:[],relationships:[{id:'r1',name:'Pressure relation',href:'/relationships/r1',description:null,participants:['m1','m2'],conditions:{},expected:{m1:{trend:{direction:'increasing'}},m2:{trend:{direction:'increasing'}}},observation_href:'/observations/observation-1'}]}),fetchMock=vi.fn().mockResolvedValue(response(persisted));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/observation-1/edit');await screen.findByLabelText('Name');await user.click(screen.getByRole('link',{name:'Edit Pressure relation'}));expect(await screen.findByText('Observations / Edit / Relationship')).toBeTruthy();expect(screen.queryByText('Observations / Create / Relationship')).toBeNull()
  })
})
