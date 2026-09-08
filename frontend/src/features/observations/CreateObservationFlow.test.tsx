import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'

const created={id:'created',name:'Release health',description:null,objective:'Observe releases',schema_version:1,lenses:[],alert_lenses:[{id:'release_alerts',name:'Release alerts',type:'alert',href:'/api/v1/observations/created/alert-lenses/release_alerts',description:null,source:'jira_track_and_release',selector:{query:' project = REL  AND status != Done '},analysis_objectives:['Assess recurrence','Compare recurrence'],reference_periods:['1d','7d'],observation_href:'/api/v1/observations/created'}],relationships:[],href:'/api/v1/observations/created'}
type AlertValues={id:string;name:string;query:string;objectives?:string[];references?:string[]}
const renderAt=(path:string)=>render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>)
const renderBrowserAt=(path:string)=>{window.history.pushState({},'',path);return render(<BrowserRouter><App/></BrowserRouter>)}
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status})
async function createAlert(user:ReturnType<typeof userEvent.setup>, values:AlertValues={id:'release_alerts',name:'Release alerts',query:' project = REL  AND status != Done '}) {
  await user.click(screen.getByText('Add Alert Lens'))
  await user.type(screen.getByLabelText('Lens ID'),values.id)
  await user.type(screen.getByLabelText('Name'),values.name)
  await user.type(screen.getByLabelText('Provider selector'),values.query)
  for(const objective of values.objectives??[]){await user.click(screen.getByText('Add objective'));await user.type(screen.getByLabelText(`Objective ${screen.getAllByLabelText(/Objective \d+/).length}`),objective)}
  for(const reference of values.references??[]){await user.click(screen.getByText('Add reference period'));await user.type(screen.getByLabelText(`Reference period ${screen.getAllByLabelText(/Reference period \d+/).length}`),reference)}
  await user.click(screen.getByText('Apply changes'))
}
async function populateValidDraft(user:ReturnType<typeof userEvent.setup>, alertValues?:Parameters<typeof createAlert>[1]) {
  await user.type(await screen.findByLabelText('Name'),'Release health')
  await user.type(screen.getByLabelText('Objective'),'Observe releases')
  await createAlert(user,alertValues)
}
afterEach(()=>{vi.restoreAllMocks();vi.unstubAllGlobals()})

describe('Observation create routes',()=>{
  it.each(['alert-lenses/new','metric-lenses/new','relationships/new'])('redirects direct nested /%s navigation to a neutral draft without writes',async suffix=>{
    const fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock)
    renderAt(`/observations/new/${suffix}`)
    expect(await screen.findByText(/previous draft is unavailable/i)).toBeTruthy()
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('')
    expect(screen.getByText('Alert lenses: 0')).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('keeps the route-scoped draft through Alert edits, replaces by opaque key in order, and applies with zero writes',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new')
    await user.type(await screen.findByLabelText('Name'),'Release health');await user.type(screen.getByLabelText('Objective'),'Observe releases')
    await createAlert(user,{id:'first',name:'First alert',query:'project=FIRST'})
    await createAlert(user,{id:'second',name:'Second alert',query:'project=SECOND'})
    const alertList=()=>screen.getByRole('heading',{name:'Alert lenses'}).parentElement!,cards=()=>Array.from(alertList().querySelectorAll('p')).filter(card=>card.querySelector('a')),names=()=>cards().map(card=>card.childNodes[0].textContent?.trim()),firstHref=cards()[0].querySelector('a')?.getAttribute('href')
    expect(names()).toEqual(['First alert','Second alert']);expect(firstHref).toMatch(/\/observations\/new\/alert-lenses\/[^/]+$/)
    await user.click(cards()[0].querySelector('a')!);await user.clear(screen.getByLabelText('Name'));await user.type(screen.getByLabelText('Name'),'Updated first');await user.click(screen.getByText('Apply changes'))
    expect(names()).toEqual(['Updated first','Second alert']);expect(cards()[0].querySelector('a')?.getAttribute('href')).toBe(firstHref);expect(cards()[1].querySelector('a')?.getAttribute('href')).not.toBe(firstHref)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('cancels and browser-back editor changes without mutating the aggregate draft',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getByText('Edit'));await user.clear(screen.getByLabelText('Name'));await user.type(screen.getByLabelText('Name'),'Discarded');await user.click(screen.getByText('Cancel'))
    expect(screen.getByText('Release alerts')).toBeTruthy();expect(screen.queryByText('Discarded')).toBeNull()
    cleanup();renderBrowserAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getByText('Edit'));await user.clear(screen.getByLabelText('Name'));await user.type(screen.getByLabelText('Name'),'Also discarded');window.history.back()
    expect(await screen.findByText('Release alerts')).toBeTruthy()
    expect(screen.getByText('Release alerts')).toBeTruthy();expect(screen.queryByText('Also discarded')).toBeNull();expect(fetchMock).not.toHaveBeenCalled()
  })

  it('cancels a populated top-level draft, returns to the list, and starts the next create flow neutrally',async()=>{
    const user=userEvent.setup();vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response([])));renderAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getByRole('button',{name:'Cancel'}));expect(await screen.findByText('No Observation definitions yet')).toBeTruthy()
    await user.click(screen.getAllByText('New Observation')[0]);expect((await screen.findByLabelText('Name') as HTMLInputElement).value).toBe('');expect(screen.getByText('Alert lenses: 0')).toBeTruthy()
  })

  it('blocks locally invalid submits with no POST and retains the draft',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new')
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText('Name is required.')).toBeTruthy();expect(screen.getByText('Configure at least one Lens.')).toBeTruthy();expect(fetchMock).not.toHaveBeenCalled()
  })

  it('posts one exact Alert-only aggregate, protects a pending double submit, then keeps confirmation while the detail request is pending and fails',async()=>{
    const user=userEvent.setup();let resolvePost:(value:Response)=>void=()=>{},resolveDetail:(value:Response)=>void=()=>{};const post=new Promise<Response>(resolve=>{resolvePost=resolve}),detail=new Promise<Response>(resolve=>{resolveDetail=resolve});const fetchMock=vi.fn().mockReturnValueOnce(post).mockReturnValueOnce(detail).mockResolvedValueOnce(response([]));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user,{id:'release_alerts',name:'Release alerts',query:' project = REL  AND status != Done ',objectives:['Assess recurrence','Compare recurrence'],references:['1d','7d']})
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);await user.click(screen.getAllByRole('button',{name:'Creating…'})[0]);expect(fetchMock).toHaveBeenCalledTimes(1)
    resolvePost(response(created,201));expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(screen.getByText('Loading definition')).toBeTruthy();resolveDetail(response({},500));expect(await screen.findByText(/Unable to load/i)).toBeTruthy();expect(screen.getByText(/created successfully/i)).toBeTruthy()
    const [url,init]=fetchMock.mock.calls[0] as [string,RequestInit];expect(url).toBe('/api/v1/observations');expect(init.method).toBe('POST');expect(JSON.parse(String(init.body))).toEqual({name:'Release health',description:null,objective:'Observe releases',lenses:[],alert_lenses:[{id:'release_alerts',name:'Release alerts',description:null,type:'alert',source:'jira_track_and_release',selector:{query:' project = REL  AND status != Done '},analysis_objectives:['Assess recurrence','Compare recurrence'],reference_periods:['1d','7d']}],relationships:[]})
    expect(fetchMock.mock.calls.every(([calledUrl])=>calledUrl==='/api/v1/observations'||calledUrl==='/api/v1/observations/created')).toBe(true)
    await user.click(screen.getByText('Back to Observations'));expect(await screen.findByText('No Observation definitions yet')).toBeTruthy();await user.click(screen.getAllByText('New Observation')[0]);expect((await screen.findByLabelText('Name') as HTMLInputElement).value).toBe('');expect(screen.getByText('Alert lenses: 0')).toBeTruthy()
  })

  it('keeps creation confirmation on the loaded read-only destination returned by the aggregate create',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response(created));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user,{id:'release_alerts',name:'Release alerts',query:' project = REL  AND status != Done ',objectives:['Assess recurrence','Compare recurrence'],references:['1d','7d']})
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(await screen.findByRole('heading',{name:'Release health'})).toBeTruthy();expect(screen.getByText('Release alerts')).toBeTruthy();expect(screen.getByText('References: 1d, 7d')).toBeTruthy();expect(fetchMock.mock.calls.map(([url])=>url)).toEqual(['/api/v1/observations','/api/v1/observations/created'])
  })

  it('keeps creation confirmation when the successful create destination returns 404',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response({code:'not_found',message:'No definition'},404));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText('Definition not found')).toBeTruthy();expect(screen.getByText(/created successfully/i)).toBeTruthy();expect(fetchMock.mock.calls.map(([url])=>url)).toEqual(['/api/v1/observations','/api/v1/observations/created'])
  })

  it('shows mapped and fallback server errors, retains values, provides child correction, and retries successfully',async()=>{
    const user=userEvent.setup();const errors=[{field:'description',message:'Description is invalid'},{field:'alert_lenses.0',message:'Aggregate child error'},{field:'alert_lenses.0.selector.query',message:'Nested child error'},{field:'alert_lenses.99.name',message:'Out of range'},{field:'unknown.field',message:'Unknown field'},{message:'Aggregate failure'}];const fetchMock=vi.fn();for(const error of errors)fetchMock.mockResolvedValueOnce(response({code:'validation_error',...error},422));fetchMock.mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response(created));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await user.type(await screen.findByLabelText(/^Description \(optional\)/),'Retained description');await populateValidDraft(user)
    for(const error of errors){await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);if(error.field==='description')expect(await screen.findByText(error.message)).toBeTruthy();else expect((await screen.findByRole('alert')).textContent).toContain(error.message);expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Release health');expect((screen.getByLabelText(/^Description \(optional\)/) as HTMLTextAreaElement).value).toBe('Retained description');if(error.field?.startsWith('alert_lenses.0'))expect(screen.getByText('Correct Alert Lens')).toBeTruthy()}
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(fetchMock).toHaveBeenCalledTimes(8)
  })
})
