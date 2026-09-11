import { Activity, AlertTriangle, BellRing, ChartLine, CheckCircle2, ChevronRight, CircleAlert, CircleDashed, Clock3, Combine, RefreshCw, Search, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { RunActivityChart } from '../../components/charts/RunActivityChart'
import { Button, InlineNotice, Input, PageHeader } from '../../components/ui'
import type { ObservationSummary } from '../observations/types'
import type { AnalyticalState, ExecutionStatus } from '../runs/types'
import { filterObservationRows, projectObservationRows, projectRecentFindings, projectRunActivity, projectSummaryCounts, runtimeCreatedAt, runtimeId, runtimeStatus, type OverviewObservationRow } from './projections'
import type { OverviewRuntimeItem } from './types'
import type { OverviewDataCoordinator } from './useOverviewData'
import { useOverviewData } from './useOverviewData'

const noDefinitions: readonly ObservationSummary[] = []
const noRuns: readonly OverviewRuntimeItem[] = []
const observationGridClass = 'xl:grid xl:grid-cols-[minmax(0,2fr)_minmax(0,.85fr)_minmax(0,1.2fr)_minmax(0,1.2fr)_minmax(0,.9fr)_2rem] xl:items-start xl:gap-3'

/** Composes the read-only monitoring entry point from the Overview data coordinator. */
export function OverviewPage() { return <OverviewContent data={useOverviewData()} /> }

/** Renders the bounded Overview presentation from independently loaded monitoring sources. */
export function OverviewContent({ data }: { data: OverviewDataCoordinator }) {
  const [searchQuery, setSearchQuery] = useState('')
  const definitions = data.definitions.data ?? noDefinitions
  const runtimeFeed = data.runHistory.data
  const runs = runtimeFeed?.items ?? noRuns
  const hasDefinitions = data.definitions.data !== null
  const hasRunHistory = runtimeFeed !== null
  const summary = hasDefinitions && hasRunHistory ? projectSummaryCounts(definitions, runs) : null
  const rows = hasDefinitions ? (hasRunHistory ? projectObservationRows(definitions, runs) : definitions.map((observation) => ({ observation, latestRun: null, recentRuns: [] }))) : []
  const visibleRows = filterObservationRows(rows, searchQuery)
  const recentFindings = projectRecentFindings(data.findingCandidates, data.findingDetails.data)

  return <section className="mx-auto max-w-7xl">
    <PageHeader eyebrow="Monitoring" title="Overview" description={<><span>Scan durable Observation execution and analytical state.</span>{data.lastSuccessfulRefreshAt !== null ? <span className="mt-1 block text-sm" aria-label={`Last refresh was received by this client at ${formatDate(data.lastSuccessfulRefreshAt.toISOString())}`}>Last refreshed locally at {formatDate(data.lastSuccessfulRefreshAt.toISOString())}</span> : null}</>} actions={<Button type="button" variant="secondary" onClick={data.refresh} disabled={data.definitions.loading || data.runHistory.loading}><RefreshCw size={16} aria-hidden="true" />Refresh</Button>} />
    <OverviewFeedback data={data} />
    <SummaryCards configuredCount={hasDefinitions ? definitions.length : null} summary={summary} />
    <div data-testid="overview-primary-grid" className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)] xl:items-start">
      <ObservationList hasDefinitions={hasDefinitions} hasRunHistory={hasRunHistory} rows={visibleRows} searchQuery={searchQuery} onSearchQueryChange={setSearchQuery} />
      <aside aria-label="Overview insights" className="grid gap-6"><RecentFindings data={data} findings={recentFindings} hasRunHistory={hasRunHistory} limitedRunCount={runtimeFeed?.limited_run_count ?? 0} />{hasRunHistory ? <RunActivityChart activity={projectRunActivity(runs)} /> : <RunActivityUnavailable />}</aside>
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
  return <section aria-label="Overview summary"><div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
    <SummaryCard icon={Activity} label="Configured Observations" value={configuredCount === null ? 'Unavailable' : String(configuredCount)} detail={configuredCount === null ? 'Definition data is unavailable.' : 'All configured definitions.'} />
    <SummaryCard icon={Clock3} label="Active Observations" value={summary === null ? 'Unavailable' : String(summary.activeObservations)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest run is pending or running.'} tone="active" />
    <SummaryCard icon={CheckCircle2} label="No significant findings" value={summary === null ? 'Unavailable' : String(summary.observationsWithNoSignificantFindings)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest explicit analytical state.'} tone="success" />
    <SummaryCard icon={AlertTriangle} label="Uncertain analysis" value={summary === null ? 'Unavailable' : String(summary.observationsWithUncertainAnalysis)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest explicit analytical state.'} tone="warning" />
    <SummaryCard icon={CircleAlert} label="Significant findings" value={summary === null ? 'Unavailable' : String(summary.observationsWithSignificantFindings)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest explicit analytical state.'} tone="error" />
    <SummaryCard icon={CircleAlert} label="Failed executions" value={summary === null ? 'Unavailable' : String(summary.observationsWithFailedExecution)} detail={summary === null ? 'Runtime data is unavailable.' : 'Latest run execution status is failed.'} tone="executionFailure" />
  </div>{summary !== null && summary.observationsWithLimitedCurrentRuntime > 0 ? <p className="mt-3 text-sm text-[var(--color-text-secondary)]"><span className="font-semibold text-[var(--color-text-primary)]">Runtime coverage limited:</span> {summary.observationsWithLimitedCurrentRuntime} current Observation {summary.observationsWithLimitedCurrentRuntime === 1 ? 'item is' : 'items are'} limited.</p> : null}</section>
}

function SummaryCard({ detail, icon: Icon, label, tone = 'neutral', value }: { detail: string; icon: LucideIcon; label: string; tone?: 'neutral' | 'active' | 'success' | 'warning' | 'error' | 'executionFailure'; value: string }) {
  const accents = { neutral: 'text-[var(--color-text-primary)]', active: 'text-[var(--color-execution-running)]', success: 'text-[var(--color-analysis-no-findings)]', warning: 'text-[var(--color-analysis-uncertain)]', error: 'text-[var(--color-analysis-significant)]', executionFailure: 'text-[var(--color-execution-failed)]' }
  const accent = value === 'Unavailable' ? accents.neutral : accents[tone]
  return <article className="min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs"><div className="flex items-start justify-between gap-2"><p className="text-sm font-medium text-[var(--color-text-primary)]">{label}</p><Icon size={17} aria-label={`${label} indicator`} className={accent} /></div><p className={`mt-2 text-2xl font-semibold tracking-tight ${accent}`}>{value}</p><p className="mt-1 text-xs text-[var(--color-text-secondary)]">{detail}</p></article>
}

function ObservationList({ hasDefinitions, hasRunHistory, onSearchQueryChange, rows, searchQuery }: { hasDefinitions: boolean; hasRunHistory: boolean; onSearchQueryChange: (query: string) => void; rows: readonly OverviewObservationRow[]; searchQuery: string }) {
  const isNoMatch = hasDefinitions && rows.length === 0 && searchQuery.trim() !== ''
  return <section data-testid="observations-collection" aria-labelledby="observations-heading" className="min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs sm:p-5"><div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><h2 id="observations-heading" className="text-xl font-semibold">Observations</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Latest durable run context and up to seven newest run states per configured Observation.</p></div>{hasDefinitions ? <label className="relative block w-full sm:w-64"><span className="sr-only">Search Observations</span><Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]" size={16} aria-hidden="true" /><Input value={searchQuery} onChange={(event) => onSearchQueryChange(event.target.value)} placeholder="Search Observations" aria-label="Search Observations" className="pl-9" /></label> : null}</div>{!hasDefinitions ? <StatePanel text="Observation definitions are unavailable." /> : !hasRunHistory ? <><StatePanel text="Runtime data is unavailable. Observation definitions remain visible below." /><ObservationRows rows={rows} runtimeUnavailable searchQuery={searchQuery} isNoMatch={isNoMatch} onClearSearch={() => onSearchQueryChange('')} /></> : <ObservationRows rows={rows} runtimeUnavailable={false} searchQuery={searchQuery} isNoMatch={isNoMatch} onClearSearch={() => onSearchQueryChange('')} />}</section>
}

function ObservationRows({ isNoMatch, onClearSearch, rows, runtimeUnavailable, searchQuery }: { isNoMatch: boolean; onClearSearch: () => void; rows: readonly OverviewObservationRow[]; runtimeUnavailable: boolean; searchQuery: string }) {
  if (isNoMatch) return <div className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">No Observations match “{searchQuery.trim()}”. <button type="button" className="font-semibold text-[var(--color-primary)] underline underline-offset-2" onClick={onClearSearch}>Clear search</button></div>
  if (rows.length === 0) return <StatePanel text="No Observation definitions exist yet." />
  return <><div data-testid="observation-grid-header" className={`mt-5 hidden ${observationGridClass} border-b border-[var(--color-border)] px-3 pb-2 text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]`}><span>Observation</span><span>Latest run</span><span>Analytical state</span><span>Execution / duration</span><span>Recent runs</span><span aria-hidden="true" /></div><ul aria-label="Observations" className="mt-2 divide-y divide-[var(--color-border)]">{rows.map((row) => <ObservationMonitoringRow key={row.observation.id} row={row} runtimeUnavailable={runtimeUnavailable} />)}</ul></>
}

function ObservationMonitoringRow({ row, runtimeUnavailable }: { row: OverviewObservationRow; runtimeUnavailable: boolean }) {
  const { observation, latestRun, recentRuns } = row
  return <li className={`px-1 py-4 transition-colors hover:bg-[var(--color-surface-muted)] focus-within:bg-[var(--color-surface-muted)] xl:px-3 ${observationGridClass}`}><ObservationIdentity observation={observation} />{runtimeUnavailable ? <RuntimeUnavailableCells /> : latestRun === null ? <NeverRunCells /> : <AvailableRuntimeCells latestRun={latestRun} recentRuns={recentRuns} />}</li>
}

function ObservationIdentity({ observation }: { observation: ObservationSummary }) {
  const composition = compositionPresentation(observation); const Icon = composition.icon
  return <div className="min-w-0"><div className="flex min-w-0 items-start gap-2"><Icon size={18} aria-label={composition.label} className="mt-0.5 shrink-0 text-[var(--color-text-secondary)]" /><div className="min-w-0"><Link className="min-w-0 break-words font-semibold text-[var(--color-primary)] underline underline-offset-2" to={`/observations/${observation.id}`}>{observation.name}</Link>{observation.description ? <p className="mt-1 min-w-0 break-words text-sm text-[var(--color-text-secondary)]">{observation.description}</p> : null}</div></div></div>
}

function AvailableRuntimeCells({ latestRun, recentRuns }: { latestRun: OverviewRuntimeItem; recentRuns: readonly OverviewRuntimeItem[] }) {
  const limited = latestRun.availability === 'limited'; const status = runtimeStatus(latestRun)
  return <><DisplayValue label="Latest run" value={<><span>{formatDate(runtimeCreatedAt(latestRun))}</span>{limited ? <span className="mt-1 block text-xs text-[var(--color-text-secondary)]">Runtime data limited</span> : null}</>} /><DisplayValue label="Analytical state" value={<CompactAnalyticalState state={latestRun.availability === 'available' ? latestRun.summary.analytical_state : null} />} /><DisplayValue label="Execution status and duration" value={<><CompactExecutionStatus status={status} /><span className="mt-1 block text-xs text-[var(--color-text-secondary)]">{formatDuration(latestRun)}</span></>} /><RecentRunsStrip runs={recentRuns} /><Link className="mt-3 inline-flex size-8 items-center justify-center rounded-md text-[var(--color-primary)] hover:bg-[var(--color-surface-muted)] focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] xl:mt-0" to={`/runs/${runtimeId(latestRun)}`} aria-label={`Open latest run ${runtimeId(latestRun)}`} title="Open latest run"><ChevronRight size={18} aria-hidden="true" /></Link></>
}

function RuntimeUnavailableCells() { return <><DisplayValue label="Latest run" value="Runtime unavailable" /><DisplayValue label="Analytical state" value="Runtime unavailable" /><DisplayValue label="Execution status and duration" value="Runtime unavailable" /><DisplayValue label="Recent runs" value="Runtime unavailable" /><DisplayValue label="Run action" value="Runtime unavailable" /></> }
function NeverRunCells() { return <><DisplayValue label="Latest run" value="Not run yet" /><DisplayValue label="Analytical state" value="Unavailable" /><DisplayValue label="Execution status and duration" value="Unavailable" /><DisplayValue label="Recent runs" value="Unavailable" /><DisplayValue label="Run action" value="Unavailable" /></> }
function DisplayValue({ label, value }: { label: string; value: ReactNode }) { return <div className="mt-3 min-w-0 text-sm xl:mt-0"><p className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)] xl:sr-only">{label}</p><div className="mt-1 min-w-0 break-words xl:mt-0">{value}</div></div> }

function CompactAnalyticalState({ state }: { state: AnalyticalState | null }) {
  const presentation = state === null ? { label: 'Analysis unavailable', className: 'bg-[var(--color-text-secondary)]' } : { no_significant_findings: { label: 'No significant findings', className: 'bg-[var(--color-analysis-no-findings)]' }, uncertain: { label: 'Uncertain', className: 'bg-[var(--color-analysis-uncertain)]' }, significant_findings_present: { label: 'Significant findings present', className: 'bg-[var(--color-analysis-significant)]' } }[state]
  return <span aria-label={`Analytical state: ${presentation.label}`} className="inline-flex items-center gap-1.5 font-medium"><span aria-hidden="true" className={`size-2 rounded-full ${presentation.className}`} />{presentation.label}</span>
}

function CompactExecutionStatus({ status }: { status: ExecutionStatus | null }) {
  const presentation = status === null ? { label: 'Unavailable', className: 'bg-[var(--color-text-secondary)]' } : { pending: { label: 'Pending', className: 'bg-[var(--color-execution-pending)]' }, running: { label: 'Running', className: 'bg-[var(--color-execution-running)]' }, completed: { label: 'Completed', className: 'bg-[var(--color-execution-completed)]' }, failed: { label: 'Failed', className: 'bg-[var(--color-execution-failed)]' }, cancelled: { label: 'Cancelled', className: 'bg-[var(--color-execution-cancelled)]' } }[status]
  return <span aria-label={`Execution status: ${presentation.label}`} className="inline-flex items-center gap-1.5 font-medium"><span aria-hidden="true" className={`size-2 rounded-full ${presentation.className}`} />{presentation.label}</span>
}

function RecentRunsStrip({ runs }: { runs: readonly OverviewRuntimeItem[] }) { return <div className="mt-3 min-w-0 xl:mt-0"><p className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)] xl:sr-only">Recent run states</p><ol className="mt-2 flex flex-wrap gap-1.5 xl:mt-0">{runs.map((run) => <RecentRunMarker key={runtimeId(run)} run={run} />)}</ol></div> }
function RecentRunMarker({ run }: { run: OverviewRuntimeItem }) { const status = runtimeStatus(run); const detail = `${formatDate(runtimeCreatedAt(run))}; ${run.availability === 'limited' ? 'runtime data limited; ' : ''}execution status ${status ?? 'unavailable'}; analytical state ${run.availability === 'available' ? run.summary.analytical_state ?? 'analysis unavailable' : 'analysis unavailable'}`; return <li className="group relative"><button type="button" aria-label={`Recent run: ${detail}`} title={detail} className={`rounded-md border px-2 py-1 text-xs font-semibold focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] ${historyMarkerClass(status, run.availability)}`}><span aria-hidden="true">{statusToken(status, run.availability)}</span></button><span role="tooltip" className="pointer-events-none absolute bottom-full left-0 z-10 mb-2 hidden w-52 rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] p-2 text-xs font-normal text-[var(--color-text-primary)] shadow-md group-focus-within:block">{detail}</span></li> }

function RecentFindings({ data, findings, hasRunHistory, limitedRunCount }: { data: OverviewDataCoordinator; findings: ReturnType<typeof projectRecentFindings>; hasRunHistory: boolean; limitedRunCount: number }) {
  const hasIncompleteDetails = data.findingDetails.loadingRunIds.size > 0 || data.findingDetails.errors.size > 0
  const coverageNotice = limitedRunCount > 0 ? <StatePanel text={`Runtime coverage is limited for ${limitedRunCount} ${limitedRunCount === 1 ? 'run' : 'runs'}; only available analyzed runs are inspected.`} /> : null
  const emptyText = limitedRunCount > 0 ? 'No findings are present in the inspected available runs.' : 'No findings are present in the five latest analyzed runs.'
  return <section aria-labelledby="recent-findings-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs sm:p-5"><h2 id="recent-findings-heading" className="text-xl font-semibold">Recent Findings</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Persisted Observation-level findings from at most five latest analyzed runs.</p>{!hasRunHistory ? <StatePanel text="Recent Findings are unavailable because run history is unavailable." /> : <>{coverageNotice}{hasIncompleteDetails ? <StatePanel text={data.findingDetails.loadingRunIds.size > 0 ? 'Checking the five latest analyzed runs for persisted findings.' : 'Recent Findings are incomplete because one or more eligible run details could not be loaded.'} /> : null}{findings.length > 0 ? <ul className="mt-4 divide-y divide-[var(--color-border)]">{findings.map((finding) => <li key={`${finding.observationRunId}-${finding.id}`} className="py-3 first:pt-0"><p className="text-sm">{finding.statement}</p><div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-[var(--color-text-secondary)]"><span>{finding.observationName}</span><span>{formatDate(finding.runCreatedAt)}</span><CompactAnalyticalState state={finding.analyticalState} /><Link className="inline-flex items-center gap-1 font-semibold text-[var(--color-primary)] underline underline-offset-2" to={`/runs/${finding.observationRunId}`} aria-label={`Open source run ${finding.observationRunId}`}>Open run</Link></div></li>)}</ul> : !hasIncompleteDetails && data.findingCandidates.length === 0 ? <StatePanel text={limitedRunCount > 0 ? 'No available analyzed runs are available to inspect; runtime coverage is limited.' : 'No analyzed runs are available to inspect yet.'} /> : !hasIncompleteDetails ? <StatePanel text={emptyText} /> : null}</>}</section>
}

function RunActivityUnavailable() { return <section aria-labelledby="run-activity-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-xs sm:p-5"><h2 id="run-activity-heading" className="text-xl font-semibold">Run Activity</h2><StatePanel text="Run Activity is unavailable because run history is unavailable." /><Link className="mt-4 inline-block text-sm font-semibold text-[var(--color-primary)] underline underline-offset-2" to="/runs">View all Runs</Link></section> }
function StatePanel({ text }: { text: string }) { return <p className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">{text}</p> }
function statusToken(status: ExecutionStatus | null, availability: OverviewRuntimeItem['availability']) { if (availability === 'limited') return status === null ? '?' : '!'; return status === null ? '?' : { pending: 'P', running: 'R', completed: 'C', failed: 'F', cancelled: 'X' }[status] }
function historyMarkerClass(status: ExecutionStatus | null, availability: OverviewRuntimeItem['availability']) { if (availability === 'limited' || status === null) return 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)]'; return { pending: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-pending)]', running: 'border-[var(--color-info-border)] bg-[var(--color-info-surface)] text-[var(--color-execution-running)]', completed: 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-execution-completed)]', failed: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-execution-failed)]', cancelled: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-cancelled)]' }[status] }
function compositionPresentation(observation: ObservationSummary): { icon: LucideIcon; label: string } { if (observation.lenses.length > 0 && observation.alert_lenses.length > 0) return { icon: Combine, label: 'Mixed Metric and Alert Lens composition' }; if (observation.lenses.length > 0) return { icon: ChartLine, label: 'Metric Lens composition' }; if (observation.alert_lenses.length > 0) return { icon: BellRing, label: 'Alert Lens composition' }; return { icon: CircleDashed, label: 'Legacy or empty Lens composition' } }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString() }
function formatDuration(run: OverviewRuntimeItem) { const status = runtimeStatus(run); if (status === 'pending' || status === 'running') return 'In progress'; const duration = run.availability === 'available' ? run.summary.duration_seconds : run.duration_seconds; if (duration === null) return 'Unavailable'; if (duration < 60) return `${Math.round(duration)}s`; return `${Math.floor(duration / 60)}m ${Math.round(duration % 60)}s` }
