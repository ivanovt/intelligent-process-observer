import { ArrowLeft } from 'lucide-react'
import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { ActionLink, Button, InlineNotice, PageHeader } from '../../components/ui'
import { getObservationRun } from './api'
import { useSequentialPolling } from './useSequentialPolling'

/** Provides a poll-safe detail-route seam while later sections add its artifact presentation. */
export function RunDetailPage() {
  const { observationRunId = '' } = useParams()
  const load = useCallback((signal: AbortSignal) => getObservationRun(observationRunId, signal), [observationRunId])
  const isActive = useCallback((detail: Awaited<ReturnType<typeof getObservationRun>>) => detail.summary.status === 'pending' || detail.summary.status === 'running', [])
  const merge = useCallback((_previous: Awaited<ReturnType<typeof getObservationRun>> | null, incoming: Awaited<ReturnType<typeof getObservationRun>>) => incoming, [])
  const { state, refresh } = useSequentialPolling({ resourceKey: observationRunId, load, isActive, merge })
  return <section className="mx-auto max-w-6xl"><PageHeader eyebrow="Observation run" title="Run detail" description={`Run ${observationRunId} is ready for its detailed runtime view.`} actions={<><Button disabled={state.refreshing} type="button" variant="secondary" onClick={refresh}>Refresh</Button><ActionLink variant="secondary" to="/runs"><ArrowLeft size={17} aria-hidden="true" />Back to Runs</ActionLink></>} />{state.loading ? <p>Loading run detail…</p> : null}{state.error && state.data === null ? <InlineNotice tone="error">Unable to load this run. <button className="font-semibold underline underline-offset-2" type="button" onClick={refresh}>Retry</button></InlineNotice> : null}{state.error && state.data !== null ? <InlineNotice tone="warning">Showing the last successful run detail. Refresh could not reach the server.</InlineNotice> : null}</section>
}
