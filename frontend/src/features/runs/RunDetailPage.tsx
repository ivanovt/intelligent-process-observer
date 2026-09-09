import { ArrowLeft } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { ActionLink, PageHeader } from '../../components/ui'

/** Provides the registered detail-route seam; durable artifact presentation is added in the next approved section. */
export function RunDetailPage() {
  const { observationRunId = '' } = useParams()
  return <section className="mx-auto max-w-6xl"><PageHeader eyebrow="Observation run" title="Run detail" description={`Run ${observationRunId} is ready for its detailed runtime view.`} actions={<ActionLink variant="secondary" to="/runs"><ArrowLeft size={17} aria-hidden="true" />Back to Runs</ActionLink>} /></section>
}
