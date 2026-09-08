import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { InlineNotice } from '../../components/ui'
import { getObservation } from './api'
import { useRequest } from './useRequest'
import { DefinitionInspection } from './DefinitionReview'

/** Renders the supported read-only configuration inspection route. */
export function ObservationDetailPage() {
  const {observationId=''}=useParams(),location=useLocation(),{state,retry}=useRequest(signal=>getObservation(observationId,signal),[observationId])
  const confirmation=location.state?.created?<div className="mb-5"><InlineNotice tone="success">Observation definition created successfully. You are viewing its read-only configuration.</InlineNotice></div>:null
  if(state.status==='loading')return <DetailFrame>{confirmation}<Panel title="Loading definition" detail="Retrieving the Observation definition…"/></DetailFrame>
  if(state.status==='error'){const notFound=(state.error as {status?:number}).status===404;return <DetailFrame>{confirmation}{notFound?<Panel title="Definition not found" detail="This Observation definition is unavailable or no longer exists."/>:<InlineNotice tone="error">Unable to load this Observation definition. <button className="font-semibold underline" onClick={retry}>Try again</button></InlineNotice>}</DetailFrame>}
  const observation=state.data
  return <DetailFrame>{confirmation}<header className="mb-8"><p className="text-sm text-[var(--color-text-secondary)]">Observation definition · Read-only configuration</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">{observation.name}</h1>{observation.description?<p className="mt-3 max-w-3xl whitespace-pre-wrap text-[var(--color-text-secondary)]">{observation.description}</p>:null}</header><div className="space-y-5"><DefinitionInspection definition={observation}/></div></DetailFrame>
}
function DetailFrame({children}:{children:ReactNode}) { return <section className="mx-auto max-w-6xl"><Link to="/observations" className="mb-7 inline-flex items-center gap-1 text-sm font-medium text-[var(--color-primary)] hover:underline"><ArrowLeft size={16} aria-hidden="true"/>Back to Observations</Link>{children}</section> }
function Panel({title,detail}:{title:string;detail:string}) { return <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-10 text-center"><h1 className="font-semibold">{title}</h1><p className="mt-2 text-sm text-[var(--color-text-secondary)]">{detail}</p></div> }
