import { Activity, AlertTriangle, CheckCircle2, CircleAlert, Clock3, RefreshCw, Search } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AnalyticalStateBadge, ExecutionStatusBadge } from '../../components/domain/RunStatusBadges'
import { RunActivityChart } from '../../components/charts/RunActivityChart'
import { Button, InlineNotice, Input, PageHeader } from '../../components/ui'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunSummary } from '../runs/types'
import { filterObservationRows, projectObservationRows, projectRecentFindings, projectRunActivity, projectSummaryCounts, type OverviewObservationRow } from './projections'
import type { OverviewDataCoordinator } from './useOverviewData'
import { useOverviewData } from './useOverviewData'

const noDefinitions: readonly ObservationSummary[] = []
const noRuns: readonly ObservationRunSummary[] = []

/** Composes the read-only monitoring entry point from the Overview data coordinator. */
export function OverviewPage() { return <OverviewContent data={useOverviewData()} /> }

/** Renders the bounded Overview presentation from independently loaded monitoring sources. */
export function OverviewContent({ data }: { data: OverviewDataCoordinator }) {
  const [searchQuery, setSearchQuery] = useState('')
  const definitions = data.definitions.data ?? noDefinitions
  const runs = data.runHistory.data ?? noRuns
  const hasDefinitions = data.definitions.data !== null
  const hasRunHistory = data.runHistory.data !== null
  const summary = hasDefinitions && hasRunHistory ? projectSummaryCounts(definitions, runs) : null
  const rows = hasDefinitions ? (hasRunHistory ? projectObservationRows(definitions, runs) : definitions.map((observation) => ({ observation, latestRun: null, recentRuns: [] }))) : []
  const visibleRows = filterObservationRows(rows, searchQuery)
  const recentFindings = projectRecentFindings(data.findingCandidates, data.findingDetails.data)

  return <section className="mx-auto max-w-7xl">
    <PageHeader
      eyebrow="Monitoring"
      title="Overview"
      description={<><span>Scan durable Observation execution and analytical state.</span>{data.lastSuccessfulRefreshAt !== null ? <span className="mt-1 block text-sm" aria-label={`Last refresh was received by this client at ${formatDate(data.lastSuccessfulRefreshAt.toISOString())}`}>Last refreshed locally at {formatDate(data.lastSuccessfulRefreshAt.toISOString())}</span> : null}</>}
      actions={<Button type="button" variant="secondary" onClick={data.refresh} disabled={data.definitions.loading || data.runHistory.loading}><RefreshCw size={16} aria-hidden="true" />Refresh</Button>}
    />
    <OverviewFeedback data={data} />
    <SummaryCards configuredCount={hasDefinitions ? definitions.length : null} summary={summary} />
    <div data-testid="overview-primary-grid" className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)] xl:items-start">
      <ObservationList hasDefinitions={hasDefinitions} hasRunHistory={hasRunHistory} rows={visibleRows} searchQuery={searchQuery} onSearchQueryChange={setSearchQuery} />
      <aside aria-label="Overview insights" className="grid gap-6">
        <RecentFindings data={data} findings={recentFindings} hasRunHistory={hasRunHistory} />
        {hasRunHistory ? <RunActivityChart activity={projectRunActivity(runs)} /> : <RunActivityUnavailable />}
      </aside>
    </div>
  </section>
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
  return <section aria-label="Overview summary" className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
    <SummaryCard icon={Activity} label="Configured Observations" value={configuredCount === null ? 'Unavailable' : String(configuredCount)} detail={configuredCount === null ? 'Definition data is unavailable.' : 'All configured definitions.'} />
    <SummaryCard icon={Clock3} label="Active Observations" value={summary === null ? 'Unavailable' : String(summary.activeObservations)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest run is pending or running.'} />
    <SummaryCard icon={CheckCircle2} label="No significant findings" value={summary === null ? 'Unavailable' : String(summary.observationsWithNoSignificantFindings)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest explicit analytical state.'} tone="success" />
    <SummaryCard icon={AlertTriangle} label="Uncertain analysis" value={summary === null ? 'Unavailable' : String(summary.observationsWithUncertainAnalysis)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest explicit analytical state.'} tone="warning" />
    <SummaryCard icon={CircleAlert} label="Significant findings" value={summary === null ? 'Unavailable' : String(summary.observationsWithSignificantFindings)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest explicit analytical state.'} tone="error" />
    <SummaryCard icon={CircleAlert} label="Failed executions" value={summary === null ? 'Unavailable' : String(summary.observationsWithFailedExecution)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest run execution status is failed.'} tone="executionFailure" />
  </section>
}

function SummaryCard({ detail, icon: Icon, label, tone = 'neutral', value }: { detail: string; icon: typeof Activity; label: string; tone?: 'neutral' | 'success' | 'warning' | 'error' | 'executionFailure'; value: string }) {
  const tones = {
    neutral: 'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)]',
    success: 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-analysis-no-findings)]',
    warning: 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-analysis-uncertain)]',
    error: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-analysis-significant)]',
    executionFailure: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-execution-failed)]',
  }
  return <article className={`min-w-0 rounded-xl border p-4 shadow-xs ${tones[tone]}`}><div className="flex items-start justify-between gap-2"><p className="text-sm font-medium">{label}</p><Icon size={17} aria-hidden="true" /></div><p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p><p className="mt-1 text-xs text-[var(--color-text-secondary)]">{detail}</p></article>
}

function ObservationList({ hasDefinitions, hasRunHistory, onSearchQueryChange, rows, searchQuery }: { hasDefinitions: boolean; hasRunHistory: boolean; onSearchQueryChange: (query: string) => void; rows: readonly OverviewObservationRow[]; searchQuery: string }) {
  const isNoMatch = hasDefinitions && rows.length === 0 && searchQuery.trim() !== ''
  return <section data-testid="observations-collection" aria-labelledby="observations-heading" className="min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs sm:p-5">
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><h2 id="observations-heading" className="text-xl font-semibold">Observations</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Latest durable run context and up to seven newest run states per configured Observation.</p></div>
      {hasDefinitions ? <label className="relative block w-full sm:w-64"><span className="sr-only">Search Observations</span><Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]" size={16} aria-hidden="true" /><Input value={searchQuery} onChange={(event) => onSearchQueryChange(event.target.value)} placeholder="Search Observations" aria-label="Search Observations" className="pl-9" /></label> : null}
    </div>
    {!hasDefinitions ? <StatePanel text="Observation definitions are unavailable." /> : !hasRunHistory ? <><StatePanel text="Runtime data is unavailable. Observation definitions remain visible below." /><ObservationRows rows={rows} runtimeUnavailable searchQuery={searchQuery} isNoMatch={isNoMatch} onClearSearch={() => onSearchQueryChange('')} /></> : <ObservationRows rows={rows} runtimeUnavailable={false} searchQuery={searchQuery} isNoMatch={isNoMatch} onClearSearch={() => onSearchQueryChange('')} />}
  </section>
}

function ObservationRows({ isNoMatch, onClearSearch, rows, runtimeUnavailable, searchQuery }: { isNoMatch: boolean; onClearSearch: () => void; rows: readonly OverviewObservationRow[]; runtimeUnavailable: boolean; searchQuery: string }) {
  if (isNoMatch) return <div className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">No Observations match “{searchQuery.trim()}”. <button type="button" className="font-semibold text-[var(--color-primary)] underline underline-offset-2" onClick={onClearSearch}>Clear search</button></div>
  if (rows.length === 0) return <StatePanel text="No Observation definitions exist yet." />
  return <><div className="mt-5 hidden grid-cols-[minmax(12rem,1.5fr)_minmax(7rem,.8fr)_minmax(9rem,1fr)_minmax(9rem,1fr)_minmax(8rem,.8fr)_auto] gap-3 border-b border-[var(--color-border)] px-3 pb-2 text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)] xl:grid"><span>Observation</span><span>Latest run</span><span>Analytical state</span><span>Execution / duration</span><span>Recent runs</span><span>Action</span></div><ul aria-label="Observations" className="mt-2 divide-y divide-[var(--color-border)]">{rows.map((row) => <ObservationMonitoringRow key={row.observation.id} row={row} runtimeUnavailable={runtimeUnavailable} />)}</ul></>
}

function ObservationMonitoringRow({ row, runtimeUnavailable }: { row: OverviewObservationRow; runtimeUnavailable: boolean }) {
  const { observation, latestRun, recentRuns } = row
  return <li className="px-1 py-4 transition-colors hover:bg-[var(--color-surface-muted)] focus-within:bg-[var(--color-surface-muted)] xl:grid xl:grid-cols-[minmax(12rem,1.5fr)_minmax(7rem,.8fr)_minmax(9rem,1fr)_minmax(9rem,1fr)_minmax(8rem,.8fr)_auto] xl:items-start xl:gap-3 xl:px-3">
    <div className="min-w-0"><Link className="min-w-0 break-words font-semibold text-[var(--color-primary)] underline underline-offset-2" to={`/observations/${observation.id}`}>{observation.name}</Link>{observation.description ? <p className="mt-1 min-w-0 break-words text-sm text-[var(--color-text-secondary)]">{observation.description}</p> : null}</div>
    {runtimeUnavailable ? <p className="mt-3 text-sm text-[var(--color-text-secondary)] xl:col-span-5 xl:mt-0">Runtime unavailable</p> : latestRun === null ? <p className="mt-3 text-sm font-medium text-[var(--color-text-secondary)] xl:col-span-5 xl:mt-0">Not run yet</p> : <><DisplayValue label="Latest run" value={formatDate(latestRun.created_at)} /><DisplayValue label="Analytical state" value={<AnalyticalStateBadge state={latestRun.analytical_state} />} /><DisplayValue label="Execution status and duration" value={<><ExecutionStatusBadge status={latestRun.status} /><span className="mt-1 block text-xs text-[var(--color-text-secondary)]">{formatDuration(latestRun)}</span></>} /><RecentRunsStrip runs={recentRuns} /><Link className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[var(--color-primary)] underline underline-offset-2 xl:mt-1" to={`/runs/${latestRun.id}`} aria-label={`Open latest run ${latestRun.id}`}>Open<span className="sr-only"> latest run</span></Link></>}
  </li>
}

function DisplayValue({ label, value }: { label: string; value: ReactNode }) { return <div className="mt-3 min-w-0 text-sm xl:mt-0"><p className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)] xl:sr-only">{label}</p><div className="mt-1 xl:mt-0">{value}</div></div> }

function RecentRunsStrip({ runs }: { runs: readonly ObservationRunSummary[] }) { return <div className="mt-3 xl:mt-0"><p className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)] xl:sr-only">Recent run states</p><ol className="mt-2 flex flex-wrap gap-1.5 xl:mt-0">{runs.map((run) => <RecentRunMarker key={run.id} run={run} />)}</ol></div> }

function RecentRunMarker({ run }: { run: ObservationRunSummary }) {
  const detail = `${formatDate(run.created_at)}; execution status ${run.status}; analytical state ${run.analytical_state ?? 'analysis unavailable'}`
  return <li className="group relative"><button type="button" aria-label={`Recent run: ${detail}`} title={detail} className={`rounded-md border px-2 py-1 text-xs font-semibold focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] ${historyMarkerClass(run.status)}`}><span aria-hidden="true">{statusToken(run.status)}</span></button><span role="tooltip" className="pointer-events-none absolute bottom-full left-0 z-10 mb-2 hidden w-52 rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-2 text-xs font-normal text-[var(--color-text-primary)] shadow-md group-focus-within:block">{detail}</span></li>
}

function RecentFindings({ data, findings, hasRunHistory }: { data: OverviewDataCoordinator; findings: ReturnType<typeof projectRecentFindings>; hasRunHistory: boolean }) {
  const hasIncompleteDetails = data.findingDetails.loadingRunIds.size > 0 || data.findingDetails.errors.size > 0
  return <section aria-labelledby="recent-findings-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs sm:p-5"><h2 id="recent-findings-heading" className="text-xl font-semibold">Recent Findings</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Persisted Observation-level findings from at most five latest analyzed runs.</p>{!hasRunHistory ? <StatePanel text="Recent Findings are unavailable because run history is unavailable." /> : <>{hasIncompleteDetails ? <StatePanel text={data.findingDetails.loadingRunIds.size > 0 ? 'Checking the five latest analyzed runs for persisted findings.' : 'Recent Findings are incomplete because one or more eligible run details could not be loaded.'} /> : null}{findings.length > 0 ? <ul className="mt-4 divide-y divide-[var(--color-border)]">{findings.map((finding) => <li key={`${finding.observationRunId}-${finding.id}`} className="py-3 first:pt-0"><p className="text-sm">{finding.statement}</p><div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-[var(--color-text-secondary)]"><span>{finding.observationName}</span><span>{formatDate(finding.runCreatedAt)}</span><AnalyticalStateBadge state={finding.analyticalState} /><Link className="inline-flex items-center gap-1 font-semibold text-[var(--color-primary)] underline underline-offset-2" to={`/runs/${finding.observationRunId}`} aria-label={`Open source run ${finding.observationRunId}`}>Open run</Link></div></li>)}</ul> : !hasIncompleteDetails && data.findingCandidates.length === 0 ? <StatePanel text="No analyzed runs are available to inspect yet." /> : !hasIncompleteDetails ? <StatePanel text="No findings are present in the five latest analyzed runs." /> : null}</>}</section>
}

function RunActivityUnavailable() { return <section aria-labelledby="run-activity-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs sm:p-5"><h2 id="run-activity-heading" className="text-xl font-semibold">Run Activity</h2><StatePanel text="Run Activity is unavailable because run history is unavailable." /><Link className="mt-4 inline-block text-sm font-semibold text-[var(--color-primary)] underline underline-offset-2" to="/runs">View all Runs</Link></section> }
function StatePanel({ text }: { text: string }) { return <p className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">{text}</p> }
function statusToken(status: ObservationRunSummary['status']) { return { pending: 'P', running: 'R', completed: 'C', failed: 'F', cancelled: 'X' }[status] }
function historyMarkerClass(status: ObservationRunSummary['status']) { return { pending: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-pending)]', running: 'border-[var(--color-info-border)] bg-[var(--color-info-surface)] text-[var(--color-execution-running)]', completed: 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-execution-completed)]', failed: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-execution-failed)]', cancelled: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-cancelled)]' }[status] }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString() }
function formatDuration(run: ObservationRunSummary) { if (run.status === 'pending' || run.status === 'running') return 'In progress'; if (run.duration_seconds === null) return 'Unavailable'; if (run.duration_seconds < 60) return `${Math.round(run.duration_seconds)}s`; return `${Math.floor(run.duration_seconds / 60)}m ${Math.round(run.duration_seconds % 60)}s` }
