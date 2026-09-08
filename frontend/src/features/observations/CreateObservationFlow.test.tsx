import { act, cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../../App'
import { generateObservationChildId, type ObservationChildKind } from './draft'
import type { ObservationResponse } from './types'

const createdId='f47ac10b-58cc-4c6f-91ae-1f8b50b65165'
const created:ObservationResponse={id:createdId,name:'Release health',description:null,objective:'Observe releases',schema_version:1,lenses:[],alert_lenses:[{id:'release_alerts',name:'Release alerts',type:'alert',href:`/api/v1/observations/${createdId}/alert-lenses/release_alerts`,description:null,source:'jira_track_and_release',selector:{query:' project = REL  AND status != Done '},analysis_objectives:['Assess recurrence','Compare recurrence'],reference_periods:['1d','7d'],observation_href:`/api/v1/observations/${createdId}`}],relationships:[],href:`/api/v1/observations/${createdId}`}
const metricCapabilities={metric:[{adapter_type:'prometheus',sources:[{id:'primary',name:'Primary Prometheus'},{id:'secondary',name:'Secondary Prometheus'}]}]}
const metricCreated:ObservationResponse={id:'1e587ac1-8e9a-42e5-b9d4-8f9c9465553f',name:'Metric health',description:null,objective:'Observe metrics',schema_version:1,lenses:[{id:'cpu',name:'CPU utilization',type:'metric',href:'/api/v1/observations/1e587ac1-8e9a-42e5-b9d4-8f9c9465553f/lenses/cpu',description:null,metric_id:'node_cpu',adapter_type:'prometheus',source_id:'primary',query:'rate(cpu[5m])',unit:'%',analysis_objectives:['spike','drift'],reference_periods:['1d','7d'],observation_href:'/api/v1/observations/1e587ac1-8e9a-42e5-b9d4-8f9c9465553f'}],alert_lenses:[],relationships:[],href:'/api/v1/observations/1e587ac1-8e9a-42e5-b9d4-8f9c9465553f'}
type AlertValues={id:string;name:string;query:string;objectives?:string[];references?:string[]}
const renderAt=(path:string)=>render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>)
const renderBrowserAt=(path:string)=>{window.history.pushState({},'',path);return render(<BrowserRouter><App/></BrowserRouter>)}
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status})
const generatedAt=1_700_000_000_000
const generatedId=(name:string,kind:ObservationChildKind)=>generateObservationChildId(name,kind,[],generatedAt)
async function createAlert(user:ReturnType<typeof userEvent.setup>, values:AlertValues={id:'release_alerts',name:'Release alerts',query:' project = REL  AND status != Done '}) {
  await user.click(screen.getByText('Add Alert Lens'))
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
async function createMetric(user:ReturnType<typeof userEvent.setup>, values:{id:string;name:string;sourceId?:string}={id:'cpu',name:'CPU utilization'}) {await user.click(screen.getByText('Add Metric Lens'));await screen.findByRole('option',{name:'Primary Prometheus'});await screen.findByRole('option',{name:'Secondary Prometheus'});await user.type(screen.getByLabelText('Name'),values.name);await user.type(screen.getByLabelText('Metric ID'),'node_cpu');await user.type(screen.getByLabelText('Unit'),'%');await user.selectOptions(screen.getByLabelText('Metric source'),values.sourceId??'primary');await user.type(screen.getByLabelText('Provider query'),'rate_cpu_5m');await user.click(screen.getByLabelText('spike'));await user.click(screen.getByLabelText('drift'));await user.click(screen.getByText('Add reference period'));await user.type(screen.getByLabelText('Reference period 1'),'1d');await user.click(screen.getByText('Add reference period'));await user.type(screen.getByLabelText('Reference period 2'),'7d');await user.click(screen.getByText('Apply changes'))}
beforeEach(()=>vi.spyOn(Date,'now').mockReturnValue(generatedAt))
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
    expect(screen.getAllByText('Release alerts').length).toBeGreaterThan(0);expect(screen.queryByText('Discarded')).toBeNull()
    cleanup();renderBrowserAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getByText('Edit'));await user.clear(screen.getByLabelText('Name'));await user.type(screen.getByLabelText('Name'),'Also discarded');window.history.back()
    expect((await screen.findAllByText('Release alerts')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Release alerts').length).toBeGreaterThan(0);expect(screen.queryByText('Also discarded')).toBeNull();expect(fetchMock).not.toHaveBeenCalled()
  })

  it('cancels a populated top-level draft, returns to the list, and starts the next create flow neutrally',async()=>{
    const user=userEvent.setup();vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response([])));renderAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getByRole('button',{name:'Cancel'}));expect(await screen.findByText('No Observation definitions yet')).toBeTruthy()
    await user.click(screen.getAllByText('New Observation')[0]);expect((await screen.findByLabelText('Name') as HTMLInputElement).value).toBe('');expect(screen.getByText('Alert lenses: 0')).toBeTruthy()
  })

  it('blocks locally invalid submits with no POST and retains the draft',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new')
    expect(screen.getAllByRole('button',{name:'Create Observation'})).toHaveLength(1)
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);const summary=await screen.findByRole('alert',{name:'Observation cannot be created'});expect(summary.textContent).toContain('Name is required.');expect(document.activeElement).toBe(summary);expect(screen.getAllByText('Configure at least one Lens.')).toHaveLength(1);expect(fetchMock).not.toHaveBeenCalled()
  })

  it('retains an exact server child error through local correction until Create revalidates it',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response({code:'validation_error',message:'Correct the provider selector.',field:'alert_lenses.0.selector.query'},422)).mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response(created));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getByRole('button',{name:'Create Observation'}));const summary=await screen.findByRole('alert',{name:'Observation cannot be created'});expect(document.activeElement).toBe(summary);expect(summary.textContent).toContain('Alert Lens “Release alerts”: Correct the provider selector.')
    const alertSection=screen.getByRole('heading',{name:'Alert lenses'}).closest('section')!;const row=Array.from(alertSection.querySelectorAll('p')).find(item=>item.textContent?.includes('Release alerts')&&item.querySelector('a'))!;expect(row.className).toContain('border-[var(--color-error-border)]');expect(row.nextElementSibling?.textContent).toContain('Correct the provider selector.')
    const navigation=within(screen.getByRole('navigation',{name:'Configuration sections'}));const alertNav=navigation.getAllByRole('link').find(link=>link.textContent?.includes('Alert lenses'))!;expect(alertNav.textContent).toContain('1');expect(alertNav.getAttribute('aria-current')).toBeNull()
    await user.click(screen.getByRole('link',{name:'Correct Alert Lens'}));await user.clear(screen.getByLabelText('Provider selector'));await user.type(screen.getByLabelText('Provider selector'),'project = RELEASE');await user.click(screen.getByRole('button',{name:'Apply changes'}));
    const retained=screen.getByRole('alert',{name:'Observation cannot be created'}),retainedAlertSection=screen.getByRole('heading',{name:'Alert lenses'}).closest('section')!,retainedNavigation=within(screen.getByRole('navigation',{name:'Configuration sections'})),retainedAlertNav=retainedNavigation.getAllByRole('link').find(link=>link.textContent?.includes('Alert lenses'))!;expect(document.activeElement).toBe(retained);expect(retained.textContent).toContain('Correct the provider selector.');expect(Array.from(retainedAlertSection.querySelectorAll('p')).find(item=>item.textContent?.includes('Release alerts')&&item.querySelector('a'))?.className).toContain('border-[var(--color-error-border)]');expect(retainedAlertNav.textContent).toContain('1');expect(screen.getByLabelText('Definition Summary').textContent).toContain('1 issue need attention.');const review=screen.getByRole('heading',{name:'Review'}).closest('section')!;expect(review.textContent).toContain('Values appear complete. Create again to confirm them.');expect(review.textContent).not.toContain('Ready to create')
    await user.click(screen.getByRole('button',{name:'Create Observation'}));expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(fetchMock.mock.calls.filter(([url,init])=>url==='/api/v1/observations'&&(init as RequestInit).method==='POST')).toHaveLength(2)
  })

  it('marks the exact child-root server error on its DraftRow and connects its Edit action to the local message',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response({code:'validation_error',message:'Correct this Alert Lens.',field:'alert_lenses.0'},422));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getByRole('button',{name:'Create Observation'}));const summary=await screen.findByRole('alert',{name:'Observation cannot be created'});expect(summary.textContent).toContain('Alert Lens “Release alerts”: Correct this Alert Lens.')
    const alertSection=screen.getByRole('heading',{name:'Alert lenses'}).closest('section')!,row=Array.from(alertSection.querySelectorAll('p')).find(item=>item.textContent?.includes('Release alerts')&&item.querySelector('a'))!,edit=row.querySelector('a')!;expect(row.className).toContain('border-[var(--color-error-border)]');expect(row.className).toContain('bg-[var(--color-error-surface)]');const errorId=edit.getAttribute('aria-describedby');expect(errorId).toBeTruthy();expect(row.nextElementSibling?.id).toBe(errorId);expect(row.nextElementSibling?.querySelector('.lucide-circle-alert')).toBeTruthy();expect(row.nextElementSibling?.textContent).toContain('Correct this Alert Lens.');expect(fetchMock.mock.calls.filter(([,init])=>(init as RequestInit|undefined)?.method==='POST')).toHaveLength(1)
  })

  it('keeps general-field guidance visible and associates validation feedback with its control',async()=>{
    const user=userEvent.setup();vi.stubGlobal('fetch',vi.fn());renderAt('/observations/new')
    expect(screen.getByText('Human-readable name for this Observation Definition.')).toBeTruthy()
    expect(screen.getByText('Optional context that explains this Observation.')).toBeTruthy()
    expect(screen.getByText('Outcome this Observation should evaluate.')).toBeTruthy()
    expect(screen.getByPlaceholderText('Cooling system health')).toBeTruthy()
    expect(screen.getByPlaceholderText('Monitors cooling-system operating conditions.')).toBeTruthy()
    expect(screen.getByPlaceholderText('Detect unexpected cooling pressure changes.')).toBeTruthy()
    await user.click(screen.getByRole('button',{name:'Create Observation'}))
    const name=screen.getByLabelText('Name')
    expect(name.getAttribute('aria-invalid')).toBe('true')
    const descriptions=name.getAttribute('aria-describedby')?.split(' ')??[]
    expect(descriptions).toHaveLength(2)
    expect(descriptions.map(id=>document.getElementById(id)?.textContent)).toEqual(expect.arrayContaining(['Human-readable name for this Observation Definition.','Name is required.']))
  })

  it('tracks the active configuration section from anchors and viewport geometry',async()=>{
    const user=userEvent.setup()
    const frames:FrameRequestCallback[]=[]
    let scrollTop=0
    let viewportHeight=600
    let documentHeight=3000
    vi.stubGlobal('requestAnimationFrame',(callback:FrameRequestCallback)=>{frames.push(callback);return frames.length})
    vi.stubGlobal('cancelAnimationFrame',vi.fn())
    vi.spyOn(window,'scrollY','get').mockImplementation(()=>scrollTop)
    vi.spyOn(window,'innerHeight','get').mockImplementation(()=>viewportHeight)
    vi.spyOn(document.documentElement,'scrollHeight','get').mockImplementation(()=>documentHeight)
    vi.stubGlobal('fetch',vi.fn())
    renderAt('/observations/new')
    await screen.findByLabelText('Name')
    const flushFrames=()=>{while(frames.length)act(()=>frames.shift()?.(0))}
    const setSectionTop=(id:string,top:number)=>vi.spyOn(document.getElementById(id)!,'getBoundingClientRect').mockReturnValue({x:0,y:top,width:0,height:500,top,right:0,bottom:top+500,left:0,toJSON:()=>({})})
    flushFrames()
    const navigation=within(screen.getByRole('navigation',{name:'Configuration sections'}))
    const current=()=>navigation.getAllByRole('link').filter((link)=>link.getAttribute('aria-current')==='location')

    expect(current()).toHaveLength(1)
    expect(current()[0].textContent).toBe('General')
    const alertLink=navigation.getByRole('link',{name:'Alert lenses'})
    expect(alertLink.getAttribute('href')).toBe('#alert-lenses')
    alertLink.addEventListener('click',(event)=>event.preventDefault(),{once:true})

    await user.click(alertLink)
    expect(current()).toHaveLength(1)
    expect(current()[0].textContent).toBe('Alert lenses')

    setSectionTop('general',-600)
    setSectionTop('metric-lenses',-100)
    setSectionTop('alert-lenses',300)
    setSectionTop('relationships',700)
    setSectionTop('review',1100)
    scrollTop=500
    window.dispatchEvent(new Event('scroll'))
    flushFrames()
    expect(current()[0].textContent).toBe('Metric lenses')

    setSectionTop('alert-lenses',-100)
    window.dispatchEvent(new Event('resize'))
    flushFrames()
    expect(current()[0].textContent).toBe('Alert lenses')

    scrollTop=0
    window.dispatchEvent(new Event('scroll'))
    flushFrames()
    expect(current()).toHaveLength(1)
    expect(current()[0].textContent).toBe('General')

    scrollTop=2400
    viewportHeight=600
    documentHeight=3000
    window.dispatchEvent(new Event('scroll'))
    flushFrames()
    expect(current()).toHaveLength(1)
    expect(current()[0].textContent).toBe('Review')
    expect(current()[0].getAttribute('aria-current')).toBe('location')
  })

  it('posts one exact Alert-only aggregate, protects a pending double submit, then keeps confirmation while the detail request is pending and fails',async()=>{
    const user=userEvent.setup();let resolvePost:(value:Response)=>void=()=>{},resolveDetail:(value:Response)=>void=()=>{};const post=new Promise<Response>(resolve=>{resolvePost=resolve}),detail=new Promise<Response>(resolve=>{resolveDetail=resolve});const fetchMock=vi.fn().mockReturnValueOnce(post).mockReturnValueOnce(detail).mockResolvedValueOnce(response([]));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user,{id:'release_alerts',name:'Release alerts',query:' project = REL  AND status != Done ',objectives:['Assess recurrence','Compare recurrence'],references:['1d','7d']})
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect((screen.getByRole('button',{name:'Cancel'}) as HTMLButtonElement).disabled).toBe(true);await user.click(screen.getByRole('button',{name:'Cancel'}));expect(screen.getByRole('heading',{name:'Create Observation'})).toBeTruthy();await user.click(screen.getAllByRole('button',{name:'Creating…'})[0]);expect(fetchMock).toHaveBeenCalledTimes(1)
    resolvePost(response(created,201));expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(screen.getByText('Loading definition')).toBeTruthy();resolveDetail(response({},500));expect(await screen.findByText(/Unable to load/i)).toBeTruthy();expect(screen.getByText(/created successfully/i)).toBeTruthy()
    const [url,init]=fetchMock.mock.calls[0] as [string,RequestInit];expect(url).toBe('/api/v1/observations');expect(init.method).toBe('POST');expect(JSON.parse(String(init.body))).toEqual({name:'Release health',description:null,objective:'Observe releases',lenses:[],alert_lenses:[{id:generatedId('Release alerts','alert'),name:'Release alerts',description:null,type:'alert',source:'jira_track_and_release',selector:{query:' project = REL  AND status != Done '},analysis_objectives:['Assess recurrence','Compare recurrence'],reference_periods:['1d','7d']}],relationships:[]})
    expect(fetchMock.mock.calls.every(([calledUrl])=>calledUrl==='/api/v1/observations'||calledUrl===`/api/v1/observations/${createdId}`)).toBe(true)
    await user.click(screen.getByText('Back to Observations'));expect(await screen.findByText('No Observation definitions yet')).toBeTruthy();await user.click(screen.getAllByText('New Observation')[0]);expect((await screen.findByLabelText('Name') as HTMLInputElement).value).toBe('');expect(screen.getByText('Alert lenses: 0')).toBeTruthy()
  })

  it('re-enables top-level Cancel after a create failure and retains the draft',async()=>{const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response({code:'unavailable',message:'Create unavailable'},503)).mockResolvedValueOnce(response([]));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user);await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText('Create unavailable')).toBeTruthy();expect((screen.getByRole('button',{name:'Cancel'}) as HTMLButtonElement).disabled).toBe(false);expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Release health');await user.click(screen.getByRole('button',{name:'Cancel'}));expect(await screen.findByText('No Observation definitions yet')).toBeTruthy()})

  it('renders neutral pre-submit Review guidance and ordered draft summaries without writes',async()=>{const user=userEvent.setup(),fetchMock=vi.fn();vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');expect(screen.getByRole('heading',{name:'Review'})).toBeTruthy();expect(screen.getByText('Complete required details')).toBeTruthy();expect(screen.queryByRole('alert',{name:'Observation cannot be created'})).toBeNull();await user.type(await screen.findByLabelText('Name'),'Review health');await user.type(screen.getByLabelText('Objective'),'Objective is distinct');expect(screen.getAllByText('Objective is distinct')).toHaveLength(2);await createAlert(user,{id:'first',name:'First alert',query:'  raw = query  ',objectives:['First objective','Second objective'],references:['1d','7d']});await createAlert(user,{id:'second',name:'Second alert',query:'project=SECOND'});const review=screen.getByRole('heading',{name:'Review'}).closest('section')!;expect(review.textContent).toContain('Ready to create');expect(review.textContent).toContain('1. First alert · Alert');expect(review.textContent).toContain('2. Second alert · Alert');expect(review.textContent).toContain('Selector query:   raw = query  ');expect(fetchMock).not.toHaveBeenCalled()})

  it('disambiguates same-name children generated in the same millisecond',async()=>{const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response(created));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await user.type(await screen.findByLabelText('Name'),'Duplicate names');await user.type(screen.getByLabelText('Objective'),'Observe duplicates');await createAlert(user,{id:'first',name:'Release alerts',query:'project=FIRST'});await createAlert(user,{id:'second',name:'Release alerts',query:'project=SECOND'});await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);await screen.findByText(/created successfully/i);const body=JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));const first=generatedId('Release alerts','alert');expect(body.alert_lenses.map((item:{id:string})=>item.id)).toEqual([first,`${first}_2`])})

  it('keeps creation confirmation on the loaded read-only destination returned by the aggregate create',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response(created));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user,{id:'release_alerts',name:'Release alerts',query:' project = REL  AND status != Done ',objectives:['Assess recurrence','Compare recurrence'],references:['1d','7d']})
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(await screen.findByRole('heading',{name:'Release health'})).toBeTruthy();expect(screen.getAllByText('Release alerts').length).toBeGreaterThan(0);expect(screen.getByText('References: 1d, 7d')).toBeTruthy();expect(fetchMock.mock.calls.map(([url])=>url)).toEqual(['/api/v1/observations',`/api/v1/observations/${createdId}`])
  })

  it('keeps creation confirmation when the successful create destination returns 404',async()=>{
    const user=userEvent.setup(),fetchMock=vi.fn().mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response({code:'not_found',message:'No definition'},404));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await populateValidDraft(user)
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText('Definition not found')).toBeTruthy();expect(screen.getByText(/created successfully/i)).toBeTruthy();expect(fetchMock.mock.calls.map(([url])=>url)).toEqual(['/api/v1/observations',`/api/v1/observations/${createdId}`])
  })

  it('shows mapped and fallback server errors, retains values, provides child correction, and retries successfully',async()=>{
    const user=userEvent.setup();const errors=[{field:'description',message:'Description is invalid'},{field:'alert_lenses.0',message:'Aggregate child error'},{field:'alert_lenses.0.selector.query',message:'Nested child error'},{field:'alert_lenses.99.name',message:'Out of range'},{field:'unknown.field',message:'Unknown field'},{message:'Aggregate failure'}];const fetchMock=vi.fn();for(const error of errors)fetchMock.mockResolvedValueOnce(response({code:'validation_error',...error},422));fetchMock.mockResolvedValueOnce(response(created,201)).mockResolvedValueOnce(response(created));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await user.type(await screen.findByLabelText(/^Description \(optional\)/),'Retained description');await populateValidDraft(user)
    for(const error of errors){await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);if(error.field==='description')expect((await screen.findByRole('alert',{name:'Observation cannot be created'})).textContent).toContain(error.message);else expect((await screen.findByRole('alert')).textContent).toContain(error.message);expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Release health');expect((screen.getByLabelText(/^Description \(optional\)/) as HTMLTextAreaElement).value).toBe('Retained description');if(error.field?.startsWith('alert_lenses.0'))expect(screen.getByText('Correct Alert Lens')).toBeTruthy()}
    await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(fetchMock).toHaveBeenCalledTimes(8)
  })
  it('posts one exact Metric-only aggregate, retains a selected non-default source through draft and failure, and succeeds on retry',async()=>{const user=userEvent.setup();let postCount=0;const fetchMock=vi.fn().mockImplementation((url:string,init?:RequestInit)=>{if(url==='/api/v1/observation-definition-capabilities')return Promise.resolve(response(metricCapabilities));if(url==='/api/v1/observations'&&init?.method==='POST'){postCount+=1;return Promise.resolve(postCount===1?response({code:'validation_error',message:'Correct Metric query',field:'lenses.0.query'},422):response(metricCreated,201))}return Promise.resolve(response(metricCreated))});vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await user.type(await screen.findByLabelText('Name'),'Metric health');await user.type(screen.getByLabelText('Objective'),'Observe metrics');await createMetric(user,{id:'cpu',name:'CPU utilization',sourceId:'secondary'})
    const metricList=screen.getByRole('heading',{name:'Metric lenses'}).parentElement!;expect(metricList.textContent).toContain('CPU utilization');await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect((await screen.findByRole('alert')).textContent).toContain('Correct Metric query');expect(screen.getByText('Correct Metric Lens')).toBeTruthy();expect(screen.getAllByText('CPU utilization').length).toBeGreaterThan(0);await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText(/created successfully/i)).toBeTruthy()
    const posts=fetchMock.mock.calls.filter(([url,init])=>url==='/api/v1/observations'&&(init as RequestInit).method==='POST');expect(posts).toHaveLength(2);expect(JSON.parse(String((posts[0][1] as RequestInit).body))).toEqual({name:'Metric health',description:null,objective:'Observe metrics',lenses:[{id:generatedId('CPU utilization','metric'),name:'CPU utilization',description:null,type:'metric',metric_id:'node_cpu',adapter_type:'prometheus',source_id:'secondary',query:'rate_cpu_5m',unit:'%',analysis_objectives:['spike','drift'],reference_periods:['1d','7d']}],alert_lenses:[],relationships:[]});expect(posts.map(([,init])=>JSON.parse(String((init as RequestInit).body)).lenses[0].source_id)).toEqual(['secondary','secondary']);expect(JSON.stringify((posts[0][1] as RequestInit).body)).not.toMatch(/clientKey|history|preflight|tool|free-text/i);expect(fetchMock.mock.calls.filter(([url])=>String(url).includes('preflight')||String(url).includes('/lenses/'))).toEqual([])
  })
  it('preserves Metric order and opaque edit keys across edit, Cancel, and browser back with no write beyond capability GET',async()=>{const user=userEvent.setup(),fetchMock=vi.fn().mockImplementation(()=>Promise.resolve(response(metricCapabilities)));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await createMetric(user,{id:'first',name:'First metric'});await createMetric(user,{id:'second',name:'Second metric'});const list=()=>screen.getByRole('heading',{name:'Metric lenses'}).parentElement!,cards=()=>Array.from(list().querySelectorAll('p')).filter(card=>card.querySelector('a')),hrefs=()=>cards().map(card=>card.querySelector('a')?.getAttribute('href')),names=()=>cards().map(card=>card.childNodes[0].textContent?.trim());const initialHrefs=hrefs();expect(names()).toEqual(['First metric','Second metric']);await user.click(cards()[0].querySelector('a')!);await user.clear(screen.getByLabelText('Name'));await user.type(screen.getByLabelText('Name'),'Updated first');await user.click(screen.getByText('Apply changes'));expect(names()).toEqual(['Updated first','Second metric']);expect(hrefs()[0]).toBe(initialHrefs[0]);expect(hrefs()[1]).toBe(initialHrefs[1]);await user.click(cards()[0].querySelector('a')!);await user.clear(screen.getByLabelText('Name'));await user.type(screen.getByLabelText('Name'),'Discarded');await user.click(screen.getByText('Cancel'));expect(names()).toEqual(['Updated first','Second metric']);cleanup();window.history.replaceState({},'', '/observations/new');renderBrowserAt('/observations/new');await createMetric(user,{id:'back_first',name:'Back first'});const backCard=cards()[0],backHref=backCard.querySelector('a')?.getAttribute('href');await user.click(backCard.querySelector('a')!);await user.clear(screen.getByLabelText('Name'));await user.type(screen.getByLabelText('Name'),'Back discarded');window.history.back();expect(await screen.findByRole('heading',{name:'Create Observation'})).toBeTruthy();expect(names()).toEqual(['Back first']);expect(hrefs()[0]).toBe(backHref);expect(fetchMock.mock.calls.filter(([,init])=>(init as RequestInit | undefined)?.method==='POST')).toEqual([])
  })
  it('allows an Alert-only aggregate after Metric capability failure and after an empty capability response',async()=>{for(const capability of [response({code:'down',message:'Capability down'},503),response({metric:[]})]){cleanup();const user=userEvent.setup();const fetchMock=vi.fn().mockImplementation((url:string,init?:RequestInit)=>url==='/api/v1/observation-definition-capabilities'?Promise.resolve(capability):url==='/api/v1/observations'&&init?.method==='POST'?Promise.resolve(response(created,201)):Promise.resolve(response(created)));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await user.click(screen.getByText('Add Metric Lens'));await screen.findByText(capability.status===503?/Unable to load Metric sources/:/No Metric source is configured/);await user.click(screen.getByText('Cancel'));await populateValidDraft(user);await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText(/created successfully/i)).toBeTruthy();expect(fetchMock.mock.calls.filter(([url,init])=>url==='/api/v1/observations'&&(init as RequestInit).method==='POST')).toHaveLength(1)}})
  it('posts a relationship-free mixed aggregate with the same type-local Lens ID and no child transport',async()=>{const user=userEvent.setup();const mixed:ObservationResponse={...metricCreated,name:'Mixed health',lenses:[{...metricCreated.lenses[0],id:'shared'}],alert_lenses:[{...created.alert_lenses[0],id:'shared'}]};const fetchMock=vi.fn().mockImplementation((url:string,init?:RequestInit)=>url==='/api/v1/observation-definition-capabilities'?Promise.resolve(response(metricCapabilities)):url==='/api/v1/observations'&&init?.method==='POST'?Promise.resolve(response(mixed,201)):Promise.resolve(response(mixed)));vi.stubGlobal('fetch',fetchMock);renderAt('/observations/new');await user.type(await screen.findByLabelText('Name'),'Mixed health');await user.type(screen.getByLabelText('Objective'),'Observe mixed');await createMetric(user,{id:'shared',name:'Shared'});await createAlert(user,{id:'shared',name:'Shared',query:'project=MIXED'});await user.click(screen.getAllByRole('button',{name:'Create Observation'})[0]);expect(await screen.findByText(/created successfully/i)).toBeTruthy();const posts=fetchMock.mock.calls.filter(([url,init])=>url==='/api/v1/observations'&&(init as RequestInit).method==='POST');expect(posts).toHaveLength(1);const body=JSON.parse(String((posts[0][1] as RequestInit).body));expect(body).toEqual({name:'Mixed health',description:null,objective:'Observe mixed',lenses:[{id:generatedId('Shared','metric'),name:'Shared',description:null,type:'metric',metric_id:'node_cpu',adapter_type:'prometheus',source_id:'primary',query:'rate_cpu_5m',unit:'%',analysis_objectives:['spike','drift'],reference_periods:['1d','7d']}],alert_lenses:[{id:generatedId('Shared','alert'),name:'Shared',description:null,type:'alert',source:'jira_track_and_release',selector:{query:'project=MIXED'},analysis_objectives:[],reference_periods:[]}],relationships:[]});expect(JSON.stringify(body)).not.toMatch(/clientKey|history|preflight|tool|free-text/i);expect(fetchMock.mock.calls.map(([url,init])=>({url,method:(init as RequestInit | undefined)?.method??'GET'}))).toEqual([{url:'/api/v1/observation-definition-capabilities',method:'GET'},{url:'/api/v1/observations',method:'POST'},{url:`/api/v1/observations/${mixed.id}`,method:'GET'}])})
})
