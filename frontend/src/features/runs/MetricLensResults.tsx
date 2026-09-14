import { X } from 'lucide-react'
import { useState } from 'react'
import { ExecutionStatusBadge } from '../../components/domain/RunStatusBadges'
import { Button } from '../../components/ui'
import { formatMetricNumber } from './metricFormatting'
import { MetricResultPresentation } from './metricPresentation'
import type { MetricRunResult, ObservationRunDetail, ObservationRunLensRun, StructuredReason, UsableMetricRunResult } from './types'

/** Browses the immutable Metric LensRun results held by one durable run-detail snapshot. */
export function MetricLensResults({ detail, lastSuccessfulAt, onViewAnalysis }: { detail: ObservationRunDetail; lastSuccessfulAt: number | null; onViewAnalysis: () => void }) {
  const lenses = detail.lens_runs.filter((lens) => lens.lens_type === 'metric')
  const [selectedId, setSelectedId] = useState<string | null>(() => lenses[0]?.id ?? null)

  if (!lenses.length) return <MetricEmpty detail={detail} lastSuccessfulAt={lastSuccessfulAt} />
  const selected = selectedId === null ? null : lenses.find((lens) => lens.id === selectedId) ?? lenses[0] ?? null
  return <section>
    <MetricHeader count={lenses.length} lastSuccessfulAt={lastSuccessfulAt} />
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(17rem,.75fr)_minmax(0,1.25fr)]">
      <div aria-label="Metric Lens results" className="grid gap-2">{lenses.map((lens) => <MetricListItem key={lens.id} lens={lens} selected={selected?.id === lens.id} onSelect={() => setSelectedId(lens.id)} />)}</div>
      {selected === null ? <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-5 text-sm text-[var(--color-text-secondary)]" role="status">Select a Metric Lens to inspect its durable result.</div> : <MetricDetail lens={selected} onDismiss={() => setSelectedId(null)} onViewAnalysis={onViewAnalysis} />}
    </div>
  </section>
}

function MetricListItem({ lens, selected, onSelect }: { lens: ObservationRunLensRun; selected: boolean; onSelect: () => void }) {
  const identity = metricIdentity(lens)
  return <button type="button" aria-pressed={selected} onClick={onSelect} className={`w-full rounded-xl border p-4 text-left shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] ${selected ? 'border-[var(--color-primary)] bg-[var(--color-primary-surface)]' : 'border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-primary)]'}`}>
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="break-words font-semibold" title={identity.reference}>{identity.reference}</p>{identity.unit ? <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">Unit: {identity.unit}</p> : null}<p className="mt-1 break-all font-mono text-xs text-[var(--color-text-secondary)]">Lens ID: {lens.lens_id}</p></div><LensStatus status={lens.status} /></div>
    <p className="mt-3 text-xs text-[var(--color-text-secondary)]">{lens.started_at ? `Started ${formatDate(lens.started_at)}` : 'Not started'} · {formatDuration(lens.duration_seconds)}</p>
    <MetricListSummary lens={lens} />
  </button>
}

function MetricListSummary({ lens }: { lens: ObservationRunLensRun }) {
  if (lens.result === null) return <p className="mt-3 text-sm text-[var(--color-text-secondary)]">{unavailableMessage(lens.status)}{lens.reason ? ` Limitation: ${formatReason(lens.reason)}.` : ''}</p>
  const result = lens.result as MetricRunResult
  if (!('data_quality' in result)) return <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Current evidence is unavailable. {result.status.error.message}{lens.reason ? ` Limitation: ${formatReason(lens.reason)}.` : ''}</p>
  if (result.data_quality === 'insufficient') return <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Data quality: insufficient. Current data was insufficient for usable evidence.{lens.reason ? ` Limitation: ${formatReason(lens.reason)}.` : ''}</p>
  const reason = lens.reason ?? result.reason
  return <div className="mt-3 space-y-1 text-sm"><p>Quality: {result.data_quality}</p><p>Trend: {result.current_state.trend.direction} · {result.current_state.trend.rate}</p><p>Variability: {result.current_state.variability.state}</p><p>Mean: {formatMetricNumber(result.evidence.current.mean)}</p>{reason ? <p className="text-[var(--color-warning)]">Limitation: {formatReason(reason)}</p> : null}</div>
}

function MetricDetail({ lens, onDismiss, onViewAnalysis }: { lens: ObservationRunLensRun; onDismiss: () => void; onViewAnalysis: () => void }) {
  const identity = metricIdentity(lens)
  return <article className="min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xs" aria-label={`Metric Lens detail: ${lens.id}`}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="break-words text-lg font-semibold">{identity.reference}</h3>{identity.unit ? <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Unit: {identity.unit}</p> : null}<p className="mt-1 break-all font-mono text-xs text-[var(--color-text-secondary)]">Lens ID: {lens.lens_id} · LensRun ID: {lens.id}</p></div><div className="flex items-center gap-2"><LensStatus status={lens.status} selected /><Button type="button" variant="secondary" onClick={onDismiss} aria-label="Dismiss Metric Lens detail"><X size={16} aria-hidden="true" />Dismiss</Button></div></div>
    <p className="mt-3 text-sm text-[var(--color-text-secondary)]">{lens.started_at ? `Started ${formatDate(lens.started_at)}` : 'Not started'} · {formatDuration(lens.duration_seconds)}</p>
    {lens.reason ? <LensReason reason={lens.reason} failed={lens.status === 'failed'} /> : null}
    <MetricDetailContent lens={lens} />
    <div className="mt-5 border-t border-[var(--color-border)] pt-4"><Button type="button" variant="secondary" onClick={onViewAnalysis}>View Observation analysis</Button></div>
  </article>
}

function MetricDetailContent({ lens }: { lens: ObservationRunLensRun }) {
  if (lens.result === null) return <MetricNotice tone="neutral" message={unavailableMessage(lens.status)} />
  const result = lens.result as MetricRunResult
  if (!('data_quality' in result)) return <MetricNotice message={`The Metric current evidence was unavailable. ${result.status.error.message}`} />
  if (result.data_quality === 'insufficient') return <MetricNotice message={`Current Metric data was insufficient for usable evidence.${lens.reason ? ` ${formatReason(lens.reason)}.` : ''}`} />
  return <MetricResultPresentation result={result as UsableMetricRunResult} reason={lens.reason ?? result.reason ?? null} />
}

function MetricNotice({ message, tone = 'warning' }: { message: string; tone?: 'neutral' | 'warning' }) { return <p role="status" className={`mt-5 rounded-lg border px-4 py-3 text-sm ${tone === 'warning' ? 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-warning)]' : 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)]'}`}>{message}</p> }
function LensReason({ failed, reason }: { failed: boolean; reason: StructuredReason }) { return <div role={failed ? 'alert' : 'status'} className={`mt-4 rounded-lg border px-4 py-3 text-sm ${failed ? 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-error)]' : 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-warning)]'}`}><p className="font-semibold">{failed ? 'Lens execution failed' : 'Lens execution issue'}</p><div className="mt-1 flex flex-wrap gap-x-2 font-mono text-xs"><span>{reason.code}</span>{reason.component ? <span>{reason.component}</span> : null}</div></div> }
function MetricHeader({ count, lastSuccessfulAt }: { count: number; lastSuccessfulAt: number | null }) { return <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Metric Lens results</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{count} Metric {count === 1 ? 'Lens' : 'Lenses'}</p></div>{lastSuccessfulAt !== null ? <p className="text-xs text-[var(--color-text-secondary)]" aria-label={`Last updated by this client at ${formatClientTime(lastSuccessfulAt)}`}>Last updated {formatClientTime(lastSuccessfulAt)}</p> : null}</div> }
function MetricEmpty({ detail, lastSuccessfulAt }: { detail: ObservationRunDetail; lastSuccessfulAt: number | null }) { const status = detail.summary.status; const message = status === 'pending' || status === 'running' ? 'Execution is still progressing; this artifact has not been produced yet.' : status === 'cancelled' ? 'Execution was cancelled before this artifact was produced.' : status === 'failed' ? 'Execution failed before this artifact was produced.' : 'This run legitimately produced an empty collection for this section.'; return <section><MetricHeader count={0} lastSuccessfulAt={lastSuccessfulAt} /><p role="status" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">{message}</p></section> }
function LensStatus({ status, selected = false }: { status: ObservationRunLensRun['status']; selected?: boolean }) { return status === 'partial' ? <span aria-label={selected ? 'Selected Lens execution status: Partial' : 'Lens execution status: Partial'} className="shrink-0 rounded-full border border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] px-2.5 py-1 text-xs font-semibold text-[var(--color-warning)]">Partial</span> : <ExecutionStatusBadge status={status} /> }
function metricIdentity(lens: ObservationRunLensRun) { const result = lens.result; return result?.lens_type === 'metric' ? { reference: result.identity.metric_ref, unit: result.identity.unit } : { reference: lens.lens_id, unit: null } }
function unavailableMessage(status: ObservationRunLensRun['status']) { if (status === 'pending' || status === 'running') return 'This Lens is still progressing; no result artifact is durable yet.'; if (status === 'cancelled') return 'This Lens was cancelled before a result artifact was produced.'; return 'This Lens finished before a result artifact was produced.' }
function formatReason(reason: StructuredReason) { return reason.component ? `${reason.code} · ${reason.component}` : reason.code }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString() }
function formatClientTime(value: number) { return new Date(value).toLocaleString() }
function formatDuration(seconds: number | null) { if (seconds === null) return 'In progress'; if (seconds < 60) return `${Math.round(seconds)}s`; return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s` }
