import { ArrowRight, Bell, ChartLine, Network, Pencil, Telescope } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ObservationSummary } from './types'

/** Shows only supported summary data for an Observation definition. */
export function ObservationRow({ observation }: { observation: ObservationSummary }) {
  const metrics = observation.lenses.length
  const alerts = observation.alert_lenses.length
  const relationships = observation.relationships.length

  return (
    <li className="grid gap-4 border-b border-[var(--color-border)] px-5 py-5 transition-colors last:border-b-0 hover:bg-[var(--color-surface-muted)] md:grid-cols-[minmax(0,1fr)_15rem_auto] md:items-center md:gap-6">
      <div className="flex min-w-0 items-start gap-3">
        <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-surface-muted)] text-[var(--color-primary)]">
          <Telescope size={18} aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 className="break-words font-semibold text-[var(--color-text-primary)]">{observation.name}</h2>
          {observation.description ? <p className="mt-1 break-words text-sm leading-5 text-[var(--color-text-secondary)]">{observation.description}</p> : null}
        </div>
      </div>
      <div className="grid gap-2 text-sm text-[var(--color-text-secondary)]" aria-label="Definition composition">
        <DefinitionCount icon={ChartLine} singular="Metric lens" plural="Metric lenses" count={metrics} />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <DefinitionCount icon={Bell} singular="Alert lens" plural="Alert lenses" count={alerts} />
          <DefinitionCount icon={Network} singular="Relationship" plural="Relationships" count={relationships} />
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1 md:justify-self-end"><Link className="inline-flex h-10 items-center gap-1 whitespace-nowrap rounded-lg px-3 text-sm font-medium text-[var(--color-primary)] transition-colors hover:bg-[color-mix(in_srgb,var(--color-primary),transparent_92%)] hover:text-[var(--color-primary-hover)]" to={`/observations/${observation.id}`}>Open<ArrowRight size={16} aria-hidden="true" /></Link><Link className="inline-flex h-10 items-center gap-1 whitespace-nowrap rounded-lg px-3 text-sm font-medium text-[var(--color-primary)] transition-colors hover:bg-[color-mix(in_srgb,var(--color-primary),transparent_92%)] hover:text-[var(--color-primary-hover)]" to={`/observations/${observation.id}/edit`}>Edit<Pencil size={16} aria-hidden="true" /></Link></div>
    </li>
  )
}

/** Renders an accessible icon-and-count item for one Definition child type. */
function DefinitionCount({ count, icon: Icon, plural, singular }: { count: number; icon: typeof ChartLine; plural: string; singular: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <Icon size={15} aria-hidden="true" />
      <span>{count} {count === 1 ? singular : plural}</span>
    </span>
  )
}
