import { ExternalLink, RefreshCw } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { ActionLink, Button, Field, InlineNotice, PageHeader, Select } from '../../components/ui'
import { AnalyticalStateBadge, ExecutionStatusBadge } from '../../components/domain/RunStatusBadges'
import { listObservationRuns } from './api'
import { emptyRunFilters, filterRuns, observationChoices, unavailableAnalyticalState, type RunFilters } from './filters'
import type { AnalyticalState, ExecutionStatus, ObservationRunSummary } from './types'
import { useRequest } from '../observations/useRequest'

const executionStatuses: readonly ExecutionStatus[] = ['pending', 'running', 'completed', 'failed', 'cancelled']
const analyticalStates: readonly AnalyticalState[] = ['no_significant_findings', 'uncertain', 'significant_findings_present']
const noRuns: readonly ObservationRunSummary[] = []

/** Renders complete newest-first runtime history with local primary-dimension filters. */
export function RunsPage() {
  const [filters, setFilters] = useState<RunFilters>(emptyRunFilters)
  const { state, retry } = useRequest(listObservationRuns, [])
  const runs = state.status === 'success' ? state.data : noRuns
  const visibleRuns = useMemo(() => filterRuns(runs, filters), [runs, filters])
  const choices = useMemo(() => observationChoices(runs), [runs])
  const hasFilters = filters.observationId !== '' || filters.status !== '' || filters.analyticalState !== ''

  return (
    <section className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Runtime history"
        title="Runs"
        description="Monitor active and historical Observation runs. Execution status and analytical state remain independent."
        actions={<Button variant="secondary" type="button" onClick={retry}><RefreshCw size={17} aria-hidden="true" />Refresh</Button>}
      />

      <RunFiltersForm choices={choices} filters={filters} hasFilters={hasFilters} onChange={setFilters} onClear={() => setFilters(emptyRunFilters)} />

      {state.status === 'loading' ? <StatePanel title="Loading runs" detail="Retrieving complete Observation run history…" /> : null}
      {state.status === 'error' ? <InlineNotice tone="error">Unable to load run history. <button className="font-semibold underline underline-offset-2" type="button" onClick={retry}>Retry</button></InlineNotice> : null}
      {state.status === 'success' && runs.length === 0 ? <StatePanel title="No Observation runs yet" detail="Run history will appear here after an Observation is launched." /> : null}
      {state.status === 'success' && runs.length > 0 && visibleRuns.length === 0 ? <StatePanel title="No runs match these filters" detail="The loaded run history has no entries matching every selected filter." action={<Button variant="secondary" type="button" onClick={() => setFilters(emptyRunFilters)}>Clear filters</Button>} /> : null}
      {state.status === 'success' && visibleRuns.length > 0 ? <RunsList runs={visibleRuns} /> : null}
    </section>
  )
}

/** Collects the three composable filters without tying them to request state. */
function RunFiltersForm({ choices, filters, hasFilters, onChange, onClear }: { choices: readonly { id: string; name: string }[]; filters: RunFilters; hasFilters: boolean; onChange: (filters: RunFilters) => void; onClear: () => void }) {
  return (
    <div className="mb-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs">
      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Observation"><Select aria-label="Filter by Observation" value={filters.observationId} onChange={(event) => onChange({ ...filters, observationId: event.target.value })}><option value="">All Observations</option>{choices.map((observation) => <option key={observation.id} value={observation.id}>{observation.name}</option>)}</Select></Field>
        <Field label="Execution status"><Select aria-label="Filter by execution status" value={filters.status} onChange={(event) => onChange({ ...filters, status: event.target.value as RunFilters['status'] })}><option value="">All execution statuses</option>{executionStatuses.map((status) => <option key={status} value={status}>{executionStatusLabel(status)}</option>)}</Select></Field>
        <Field label="Analytical state"><Select aria-label="Filter by analytical state" value={filters.analyticalState} onChange={(event) => onChange({ ...filters, analyticalState: event.target.value as RunFilters['analyticalState'] })}><option value="">All analytical states</option><option value={unavailableAnalyticalState}>Analysis unavailable</option>{analyticalStates.map((state) => <option key={state} value={state}>{analyticalStateLabel(state)}</option>)}</Select></Field>
      </div>
      {hasFilters ? <div className="mt-4"><Button variant="ghost" type="button" onClick={onClear}>Clear all filters</Button></div> : null}
    </div>
  )
}

/** Displays scan-oriented run information without elevating this list to a data-grid abstraction. */
function RunsList({ runs }: { runs: readonly ObservationRunSummary[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xs">
      <div className="hidden grid-cols-[minmax(11rem,1.3fr)_minmax(10rem,1fr)_minmax(8rem,.8fr)_minmax(8rem,.8fr)_minmax(10rem,1fr)_auto] gap-4 border-b border-[var(--color-border)] bg-[var(--color-surface-muted)] px-5 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)] lg:grid"><span>Observation / run</span><span>Window</span><span>Duration</span><span>Execution</span><span>Analysis</span><span>Action</span></div>
      <ul aria-label="Observation runs" className="divide-y divide-[var(--color-border)]">
        {runs.map((run) => <RunRow key={run.id} run={run} />)}
      </ul>
    </div>
  )
}

/** Renders one concise runtime row. */
function RunRow({ run }: { run: ObservationRunSummary }) {
  return (
    <li className="grid gap-3 px-5 py-4 lg:grid-cols-[minmax(11rem,1.3fr)_minmax(10rem,1fr)_minmax(8rem,.8fr)_minmax(8rem,.8fr)_minmax(10rem,1fr)_auto] lg:items-center lg:gap-4">
      <div className="min-w-0"><p className="truncate font-semibold">{run.observation.name}</p><p aria-label={`Run ID: ${run.id}`} className="mt-1 font-mono text-xs text-[var(--color-text-secondary)]">{compactRunId(run.id)}</p></div>
      <div className="text-sm text-[var(--color-text-secondary)]"><p>{formatWindow(run.analysis_window.from, run.analysis_window.to)}</p><p className="mt-1 text-xs">Started {formatDate(run.started_at ?? run.created_at)}</p></div>
      <span className="text-sm text-[var(--color-text-secondary)]">{formatDuration(run.duration_seconds)}</span>
      <ExecutionStatusBadge status={run.status} />
      <AnalyticalStateBadge state={run.analytical_state} />
      <ActionLink aria-label={`Open run ${run.id}`} variant="secondary" to={`/runs/${encodeURIComponent(run.id)}`}>Open<ExternalLink size={15} aria-hidden="true" /></ActionLink>
    </li>
  )
}

/** Renders a contained state with an optional recovery action. */
function StatePanel({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-10 text-center shadow-xs"><h2 className="font-semibold">{title}</h2><p className="mx-auto mt-2 max-w-xl text-sm text-[var(--color-text-secondary)]">{detail}</p>{action ? <div className="mt-4">{action}</div> : null}</div>
}

function compactRunId(id: string) { return id.length > 12 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString() }
function formatWindow(from: string, to: string) { return `${formatDate(from)} – ${formatDate(to)}` }
function formatDuration(seconds: number | null) { if (seconds === null) return 'In progress'; if (seconds < 60) return `${Math.round(seconds)}s`; const minutes = Math.floor(seconds / 60); return `${minutes}m ${Math.round(seconds % 60)}s` }
function executionStatusLabel(status: ExecutionStatus) { return status.charAt(0).toUpperCase() + status.slice(1) }
function analyticalStateLabel(state: AnalyticalState) { return state === 'no_significant_findings' ? 'No significant findings' : state === 'significant_findings_present' ? 'Significant findings present' : 'Uncertain' }
