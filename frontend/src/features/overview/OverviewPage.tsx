import { ArrowRight, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { AnalyticalStateBadge, ExecutionStatusBadge } from '../../components/domain/RunStatusBadges'
import { RunActivityChart } from '../../components/charts/RunActivityChart'
import { Button, InlineNotice, PageHeader } from '../../components/ui'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunSummary } from '../runs/types'
import { projectObservationRows, projectRecentFindings, projectRunActivity, projectSummaryCounts, type OverviewObservationRow } from './projections'
import type { OverviewDataCoordinator } from './useOverviewData'
import { useOverviewData } from './useOverviewData'

const noDefinitions: readonly ObservationSummary[] = []
const noRuns: readonly ObservationRunSummary[] = []

/** Composes the read-only monitoring entry point from the Overview data coordinator. */
export function OverviewPage() {
  return <OverviewContent data={useOverviewData()} />
}

/** Renders the bounded Overview presentation from independently loaded monitoring sources. */
export function OverviewContent({ data }: { data: OverviewDataCoordinator }) {
  const definitions = data.definitions.data ?? noDefinitions
  const runs = data.runHistory.data ?? noRuns
  const hasDefinitions = data.definitions.data !== null
  const hasRunHistory = data.runHistory.data !== null
  const summary = hasDefinitions && hasRunHistory ? projectSummaryCounts(definitions, runs) : null
  const rows = hasDefinitions ? (hasRunHistory ? projectObservationRows(definitions, runs) : definitions.map((observation) => ({ observation, latestRun: null, recentRuns: [] }))) : []
  const recentFindings = projectRecentFindings(data.findingCandidates, data.findingDetails.data)

  return (
    <section className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Monitoring"
        title="Overview"
        description="Review durable Observation execution and analytical state without conflating them."
        actions={<Button type="button" variant="secondary" onClick={data.refresh} disabled={data.definitions.loading || data.runHistory.loading}><RefreshCw size={16} aria-hidden="true" />Refresh</Button>}
      />
      <OverviewFeedback data={data} />
      <SummaryCards configuredCount={hasDefinitions ? definitions.length : null} summary={summary} />
      <ObservationList hasDefinitions={hasDefinitions} hasRunHistory={hasRunHistory} rows={rows} />
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <RecentFindings data={data} findings={recentFindings} hasRunHistory={hasRunHistory} />
        {hasRunHistory ? <RunActivityChart activity={projectRunActivity(runs)} /> : <RunActivityUnavailable />}
      </div>
    </section>
  )
}

function OverviewFeedback({ data }: { data: OverviewDataCoordinator }) {
  const definitionUnavailable = data.definitions.data === null && data.definitions.error !== null
  const historyUnavailable = data.runHistory.data === null && data.runHistory.error !== null
  const stale = (data.definitions.data !== null && data.definitions.error !== null) || (data.runHistory.data !== null && data.runHistory.error !== null)
  const loading = data.definitions.loading || data.runHistory.loading
  const refreshing = data.definitions.refreshing || data.runHistory.refreshing

  if (definitionUnavailable && historyUnavailable) return <InlineNotice tone="error">Unable to load Overview monitoring data. <button type="button" className="font-semibold underline underline-offset-2" onClick={data.refresh}>Retry</button></InlineNotice>
  if (definitionUnavailable || historyUnavailable) return <InlineNotice tone="warning">Some monitoring data is unavailable. Successful sections remain visible. <button type="button" className="font-semibold underline underline-offset-2" onClick={data.refresh}>Retry</button></InlineNotice>
  if (stale) return <InlineNotice tone="warning">Some monitoring data is stale. Last successful data remains visible. <button type="button" className="font-semibold underline underline-offset-2" onClick={data.refresh}>Retry</button></InlineNotice>
  if (loading) return <InlineNotice>Loading monitoring data. Successful sources will appear as soon as they are available.</InlineNotice>
  if (refreshing) return <InlineNotice>Refreshing monitoring data. Displayed values remain available while the refresh completes.</InlineNotice>
  return null
}

function SummaryCards({ configuredCount, summary }: { configuredCount: number | null; summary: ReturnType<typeof projectSummaryCounts> | null }) {
  return (
    <section aria-label="Overview summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <SummaryCard label="Configured Observations" value={configuredCount === null ? 'Unavailable' : String(configuredCount)} detail={configuredCount === null ? 'Definition data is unavailable.' : 'All configured Observation definitions.'} />
      <SummaryCard label="Active Observations" value={summary === null ? 'Unavailable' : String(summary.activeObservations)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest run is pending or running.'} />
      <SummaryCard label="Significant findings" value={summary === null ? 'Unavailable' : String(summary.observationsWithSignificantFindings)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest analysis is significant findings present.'} />
      <SummaryCard label="Failed executions" value={summary === null ? 'Unavailable' : String(summary.observationsWithFailedExecution)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest run execution status is failed.'} />
    </section>
  )
}

function SummaryCard({ detail, label, value }: { detail: string; label: string; value: string }) {
  return <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xs"><p className="text-sm font-medium text-[var(--color-text-secondary)]">{label}</p><p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p><p className="mt-2 text-sm text-[var(--color-text-secondary)]">{detail}</p></article>
}

function ObservationList({ hasDefinitions, hasRunHistory, rows }: { hasDefinitions: boolean; hasRunHistory: boolean; rows: readonly OverviewObservationRow[] }) {
  return (
    <section aria-labelledby="observations-heading" className="mt-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xs">
      <div><h2 id="observations-heading" className="text-xl font-semibold">Observations</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Latest durable run context and up to seven newest run states per configured Observation.</p></div>
      {!hasDefinitions ? <StatePanel text="Observation definitions are unavailable." /> : !hasRunHistory ? (
        <><StatePanel text="Runtime data is unavailable. Observation definitions remain visible below." />{rows.length === 0 ? <StatePanel text="No Observation definitions exist yet." /> : <ul aria-label="Observations" className="mt-4 space-y-3">{rows.map((row) => <ObservationMonitoringRow key={row.observation.id} row={row} runtimeUnavailable />)}</ul>}</>
      ) : rows.length === 0 ? <StatePanel text="No Observation definitions exist yet." /> : <ul aria-label="Observations" className="mt-4 space-y-3">{rows.map((row) => <ObservationMonitoringRow key={row.observation.id} row={row} runtimeUnavailable={false} />)}</ul>}
    </section>
  )
}

function ObservationMonitoringRow({ row, runtimeUnavailable }: { row: OverviewObservationRow; runtimeUnavailable: boolean }) {
  const { observation, latestRun, recentRuns } = row
  return (
    <li className="rounded-lg border border-[var(--color-border)] p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0"><Link className="font-semibold text-[var(--color-primary)] underline underline-offset-2" to={`/observations/${observation.id}`}>{observation.name}</Link>{observation.description ? <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{observation.description}</p> : null}</div>
        {latestRun !== null && !runtimeUnavailable ? <Link className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold text-[var(--color-primary)] underline underline-offset-2" to={`/runs/${latestRun.id}`} aria-label={`Open latest run ${latestRun.id}`}><span>Open latest run</span><ArrowRight size={16} aria-hidden="true" /></Link> : null}
      </div>
      {runtimeUnavailable ? <p className="mt-4 text-sm text-[var(--color-text-secondary)]">Runtime unavailable</p> : latestRun === null ? <p className="mt-4 text-sm font-medium text-[var(--color-text-secondary)]">Not run yet</p> : <>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4"><DisplayValue label="Latest run" value={formatDate(latestRun.created_at)} /><DisplayValue label="Execution status" value={<ExecutionStatusBadge status={latestRun.status} />} /><DisplayValue label="Analytical state" value={<AnalyticalStateBadge state={latestRun.analytical_state} />} /><DisplayValue label="Duration" value={formatDuration(latestRun)} /></dl>
        <RecentRunsStrip runs={recentRuns} />
      </>}
    </li>
  )
}

function DisplayValue({ label, value }: { label: string; value: ReactNode }) {
  return <div><dt className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">{label}</dt><dd className="mt-1">{value}</dd></div>
}

function RecentRunsStrip({ runs }: { runs: readonly ObservationRunSummary[] }) {
  return <div className="mt-4"><p className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">Recent run states</p><ol className="mt-2 flex flex-wrap gap-2">{runs.map((run) => <li key={run.id} aria-label={`Recent run: ${formatDate(run.created_at)}; execution status: ${run.status}; analytical state: ${run.analytical_state ?? 'analysis unavailable'}`} className={`rounded-md border px-2 py-1 text-xs font-semibold ${historyMarkerClass(run.status)}`}><span aria-hidden="true">{statusToken(run.status)}</span><span className="sr-only">{formatDate(run.created_at)}; execution status {run.status}; analytical state {run.analytical_state ?? 'analysis unavailable'}</span></li>)}</ol></div>
}

function RecentFindings({ data, findings, hasRunHistory }: { data: OverviewDataCoordinator; findings: ReturnType<typeof projectRecentFindings>; hasRunHistory: boolean }) {
  const hasIncompleteDetails = data.findingDetails.loadingRunIds.size > 0 || data.findingDetails.errors.size > 0
  return (
    <section aria-labelledby="recent-findings-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xs">
      <h2 id="recent-findings-heading" className="text-xl font-semibold">Recent Findings</h2>
      <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Persisted Observation-level findings from at most five latest analyzed runs.</p>
      {!hasRunHistory ? <StatePanel text="Recent Findings are unavailable because run history is unavailable." /> : <>
        {hasIncompleteDetails ? <StatePanel text={data.findingDetails.loadingRunIds.size > 0 ? 'Checking the five latest analyzed runs for persisted findings.' : 'Recent Findings are incomplete because one or more eligible run details could not be loaded.'} /> : null}
        {findings.length > 0 ? <ul className="mt-4 space-y-3">{findings.map((finding) => <li key={`${finding.observationRunId}-${finding.id}`} className="rounded-lg border border-[var(--color-border)] p-4"><p className="text-sm">{finding.statement}</p><div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-[var(--color-text-secondary)]"><span>{finding.observationName}</span><span>{formatDate(finding.runCreatedAt)}</span><AnalyticalStateBadge state={finding.analyticalState} /><Link className="inline-flex items-center gap-1 font-semibold text-[var(--color-primary)] underline underline-offset-2" to={`/runs/${finding.observationRunId}`} aria-label={`Open source run ${finding.observationRunId}`}>Open run <ArrowRight size={16} aria-hidden="true" /></Link></div></li>)}</ul> : !hasIncompleteDetails && data.findingCandidates.length === 0 ? <StatePanel text="No analyzed runs are available to inspect yet." /> : !hasIncompleteDetails ? <StatePanel text="No findings are present in the five latest analyzed runs." /> : null}
      </>}
    </section>
  )
}

function RunActivityUnavailable() {
  return <section aria-labelledby="run-activity-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xs"><h2 id="run-activity-heading" className="text-xl font-semibold">Run Activity</h2><StatePanel text="Run Activity is unavailable because run history is unavailable." /><Link className="mt-4 inline-block text-sm font-semibold text-[var(--color-primary)] underline underline-offset-2" to="/runs">View all Runs</Link></section>
}

function StatePanel({ text }: { text: string }) {
  return <p className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">{text}</p>
}

function statusToken(status: ObservationRunSummary['status']) {
  return status.slice(0, 1).toUpperCase()
}

function historyMarkerClass(status: ObservationRunSummary['status']) {
  const classes = {
    pending: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-pending)]',
    running: 'border-[var(--color-info-border)] bg-[var(--color-info-surface)] text-[var(--color-execution-running)]',
    completed: 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-execution-completed)]',
    failed: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-execution-failed)]',
    cancelled: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-cancelled)]',
  }
  return classes[status]
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString()
}

function formatDuration(run: ObservationRunSummary) {
  if (run.duration_seconds === null) return run.status === 'pending' || run.status === 'running' ? 'In progress' : 'Unavailable'
  if (run.duration_seconds < 60) return `${Math.round(run.duration_seconds)}s`
  return `${Math.floor(run.duration_seconds / 60)}m ${Math.round(run.duration_seconds % 60)}s`
}
