import { Plus, Search } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { ActionLink, InlineNotice, Input, PageHeader } from '../../components/ui'
import { listObservations } from './api'
import { ObservationRow } from './ObservationRow'
import { useRequest } from './useRequest'

/** Renders the Observation Definition management list. */
export function ObservationsPage() {
  const [query, setQuery] = useState('')
  const { state, retry } = useRequest(listObservations, [])
  const filtered = useMemo(
    () => state.status === 'success'
      ? state.data.filter((item) => `${item.name} ${item.description ?? ''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
      : [],
    [state, query],
  )

  return (
    <section className="mx-auto max-w-6xl">
      <PageHeader
        title="Observations"
        description="Manage Observation definitions and inspect their configuration."
        actions={<NewObservationLink />}
      />

      <div className="mb-6 w-full">
        <label className="relative block">
          <span className="sr-only">Search observations</span>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]" size={18} aria-hidden="true" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search observations by name or description"
            className="pl-10"
          />
        </label>
      </div>

      {state.status === 'loading' ? <Panel title="Loading definitions" detail="Retrieving Observation definitions…" /> : null}
      {state.status === 'error' ? (
        <InlineNotice tone="error">
          Unable to load Observation definitions.{' '}
          <button className="font-semibold underline" onClick={retry}>Try again</button>
        </InlineNotice>
      ) : null}
      {state.status === 'success' && state.data.length === 0 ? (
        <Panel
          title="No Observation definitions yet"
          detail="Create a definition when configuration is available."
          action={<NewObservationLink />}
        />
      ) : null}
      {state.status === 'success' && state.data.length > 0 && filtered.length === 0 ? (
        <Panel
          title="No matching definitions"
          detail="Try a different name or description."
          action={<button className="font-medium text-[var(--color-primary)] underline" onClick={() => setQuery('')}>Clear search</button>}
        />
      ) : null}
      {state.status === 'success' && filtered.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xs">
          <div className="hidden grid-cols-[minmax(0,1fr)_15rem_auto] gap-6 border-b border-[var(--color-border)] bg-[var(--color-surface-muted)] px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)] md:grid">
            <span>Observation</span>
            <span>Definition</span>
            <span className="pr-1 text-right">Actions</span>
          </div>
          <ul aria-label="Observation definitions">
            {filtered.map((observation) => <ObservationRow key={observation.id} observation={observation} />)}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

/** Navigates to the aggregate Observation creation flow. */
function NewObservationLink() {
  return (
    <ActionLink to="/observations/new">
      <Plus size={17} aria-hidden="true" />
      New Observation
    </ActionLink>
  )
}

/** Renders a contained state for an asynchronous Observation-list result. */
function Panel({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-10 text-center shadow-xs">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{detail}</p>
      {action ? <p className="mt-4 text-sm">{action}</p> : null}
    </div>
  )
}
