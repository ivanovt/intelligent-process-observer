import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { InlineNotice, PageHeader } from '../../components/ui'
import { getObservation } from './api'
import { CreateObservationPage } from './CreateObservationPage'
import { useObservationDraft } from './draft'
import { useRequest } from './useRequest'

/** Loads one canonical Observation Definition into the aggregate edit draft. */
export function EditObservationPage() {
  const { draft } = useObservationDraft()
  if (draft) return <CreateObservationPage />
  return <EditObservationLoader />
}

function EditObservationLoader() {
  const { observationId = '' } = useParams()
  const { initialize, targetId } = useObservationDraft()
  const { state, retry } = useRequest((signal) => getObservation(observationId, signal), [observationId])

  useEffect(() => { if (state.status === 'success' && targetId === observationId) initialize(state.data) }, [initialize, observationId, state, targetId])

  if (state.status === 'loading') return <Frame><Panel title="Loading definition" detail="Loading the persisted Observation Definition for editing…" /></Frame>
  if (state.status === 'error') {
    const missing = (state.error as { status?: number }).status === 404
    return <Frame>{missing ? <Panel title="Definition not found" detail="This Observation definition is unavailable or no longer exists." /> : <InlineNotice tone="error">Unable to load this Observation definition. <button className="font-semibold underline" onClick={retry}>Try again</button></InlineNotice>}</Frame>
  }
  return <Frame><Panel title="Loading definition" detail="Preparing the persisted Observation Definition for editing…" /></Frame>
}

function Frame({ children }: { children: React.ReactNode }) { return <section className="mx-auto max-w-6xl"><PageHeader eyebrow="Observations / Edit" title="Edit Observation" description="Load the persisted definition before making aggregate changes." />{children}<p className="mt-5"><Link className="font-medium text-[var(--color-primary)] underline" to="/observations">Back to Observations</Link></p></section> }
function Panel({ title, detail }: { title: string; detail: string }) { return <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-10 text-center"><h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-[var(--color-text-secondary)]">{detail}</p></div> }
