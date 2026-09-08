import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { InlineNotice } from '../../components/ui'
import { getObservation } from './api'
import { useRequest } from './useRequest'

/** Renders the supported read-only configuration inspection route. */
export function ObservationDetailPage() {
  const {observationId=''}=useParams(),location=useLocation(),{state,retry}=useRequest(signal=>getObservation(observationId,signal),[observationId])
  const confirmation=location.state?.created?<InlineNotice>Observation definition created successfully. You are viewing its read-only configuration.</InlineNotice>:null
  if(state.status==='loading')return <DetailFrame>{confirmation}<Panel title="Loading definition" detail="Retrieving the Observation definition…"/></DetailFrame>
  if(state.status==='error'){const notFound=(state.error as {status?:number}).status===404;return <DetailFrame>{confirmation}{notFound?<Panel title="Definition not found" detail="This Observation definition is unavailable or no longer exists."/>:<InlineNotice tone="error">Unable to load this Observation definition. <button className="font-semibold underline" onClick={retry}>Try again</button></InlineNotice>}</DetailFrame>}
  const observation=state.data
  return <DetailFrame>{confirmation}<header><p>Observation definition</p><h1>{observation.name}</h1><p><span>Objective:</span> {observation.objective}</p></header><section><h2>Metric lenses</h2>{observation.lenses.map(lens=><p key={lens.id}>{lens.name}</p>)}</section><section><h2>Alert lenses</h2>{observation.alert_lenses.map(lens=><p key={lens.id}>{lens.name}</p>)}</section><section><h2>Relationships</h2>{observation.relationships.map(item=><p key={item.id}>{item.name}</p>)}</section></DetailFrame>
}
function DetailFrame({children}:{children:ReactNode}) { return <section className="mx-auto max-w-6xl"><Link to="/observations" className="mb-7 inline-flex items-center gap-1"><ArrowLeft size={16}/>Back to Observations</Link>{children}</section> }
function Panel({title,detail}:{title:string;detail:string}) { return <div><h1>{title}</h1><p>{detail}</p></div> }
