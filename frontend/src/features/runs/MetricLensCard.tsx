import { Activity, AlertTriangle, ChartNoAxesCombined, Clock3, Database, Gauge, History, Signal, Timer, TrendingDown, TrendingUp, TrendingUpDown } from 'lucide-react'
import { ExecutionStatusBadge } from '../../components/domain/RunStatusBadges'
import { formatMetricNumber } from './metricFormatting'
import type { MetricRunResult, ObservationRunLensRun, StructuredReason, UsableMetricRunResult } from './types'

/** Presents one immutable Metric LensRun as a selectable, evidence-aware result card. */
export function MetricLensCard({ lens, selected, onSelect }: { lens: ObservationRunLensRun; selected: boolean; onSelect: () => void }) {
  const identity = metricIdentity(lens)
  const result = lens.result?.lens_type === 'metric' ? lens.result : null
  const usable = result !== null && isUsableMetricResult(result)
  const unavailable = unavailableDescription(lens, result)

  return <button
    type="button"
    aria-pressed={selected}
    onClick={onSelect}
    className={`w-full rounded-xl border p-5 text-left shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] ${selected ? 'border-[var(--color-primary)] bg-[var(--color-primary-surface)]' : 'border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-primary)]'}`}
  >
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-[min(100%,16rem)] flex-1 gap-3">
        <LeadingIcon usable={usable} failed={lens.status === 'failed'} trendDirection={usable ? result.current_state.trend.direction : null} />
        <div className="min-w-0">
          <p className="break-words text-base font-semibold" title={identity.reference}>{identity.reference}</p>
          {identity.unit ? <p className="mt-0.5 text-sm text-[var(--color-text-secondary)]">Unit: {identity.unit}</p> : null}
          <p className="mt-1 break-all font-mono text-xs text-[var(--color-text-secondary)]">Lens ID: {lens.lens_id}</p>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {result !== null && 'data_quality' in result ? <DataQuality quality={result.data_quality} /> : null}
        <LensStatus status={lens.status} />
      </div>
    </div>

    <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-sm text-[var(--color-text-secondary)]">
      <span className="inline-flex items-center gap-1.5"><Clock3 size={15} aria-hidden="true" />{lens.started_at ? `Started ${formatDate(lens.started_at)}` : 'Not started'}</span>
      <span className="inline-flex items-center gap-1.5"><Timer size={15} aria-hidden="true" />Duration: {formatDuration(lens.duration_seconds, lens.status)}</span>
    </div>

    {usable ? <UsableSummary result={result} reason={lens.reason ?? result.reason ?? null} /> : <UnavailableSummary message={unavailable} reason={supportedReason(lens, result)} failed={lens.status === 'failed'} />}
  </button>
}

function UsableSummary({ result, reason }: { result: UsableMetricRunResult; reason: StructuredReason | null }) {
  const referenceOffsets = returnedReferenceOffsets(result)
  const history = result.history !== null && result.evidence.history !== null ? result.history : null
  return <>
    <section aria-label="Current semantic state" className="mt-4 rounded-lg border border-[var(--color-info-border)] bg-[var(--color-info-surface)] p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">Current semantic state</p>
      <dl className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-2 text-sm">
        <SemanticValue icon={trendIcon(result.current_state.trend.direction)} label="Trend direction" value={result.current_state.trend.direction} />
        <SemanticValue icon={Gauge} label="Trend rate" value={result.current_state.trend.rate} />
        <SemanticValue icon={Activity} label="Variability" value={result.current_state.variability.state} />
      </dl>
    </section>
    <section aria-label="Evidence summary" className="mt-3 border-t border-[var(--color-border)] pt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">Evidence summary</p>
      <dl className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-3 text-sm">
        <EvidenceValue icon={ChartNoAxesCombined} label="Mean" value={formatMetricNumber(result.evidence.current.mean)} />
        <EvidenceValue icon={Signal} label="Range" value={`${formatMetricNumber(result.evidence.current.min)} – ${formatMetricNumber(result.evidence.current.max)}`} />
        <EvidenceValue icon={TrendingUpDown} label="Slope" value={formatMetricNumber(result.evidence.current.slope)} />
        <EvidenceValue icon={Database} label="Reference availability" value={referenceOffsets.length ? `${referenceOffsets.join(', ')} returned` : availabilityText('Reference-period comparison', reason, 'reference')} />
        <EvidenceValue icon={History} label="Persisted History" value={history ? `${history.direction} / ${history.pattern}` : availabilityText('Persisted History', reason, 'history')} />
      </dl>
      {reason ? <p className="mt-3 text-sm text-[var(--color-warning)]">Limitation: {formatReason(reason)}</p> : null}
    </section>
  </>
}

function UnavailableSummary({ message, reason, failed }: { message: string; reason: StructuredReason | null; failed: boolean }) {
  return <section aria-label="Current semantic state unavailable" className={`mt-4 rounded-lg border p-3 text-sm ${failed ? 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-error)]' : 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-warning)]'}`}>
    <p className="font-semibold">Current semantic state: unavailable</p>
    <p className="mt-1">{message}</p>
    {reason ? <p className="mt-2 font-mono text-xs">Reason: {formatReason(reason)}</p> : null}
  </section>
}

function SemanticValue({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string }) {
  return <div className="min-w-0"><dt className="inline-flex items-center gap-1 text-xs text-[var(--color-text-secondary)]"><Icon size={14} aria-hidden="true" />{label}</dt><dd className="mt-0.5 break-words font-medium">{value}</dd></div>
}

function EvidenceValue({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string }) {
  return <div className="min-w-0"><dt className="inline-flex items-center gap-1 text-xs text-[var(--color-text-secondary)]"><Icon size={14} aria-hidden="true" />{label}</dt><dd className="mt-0.5 break-words font-medium">{value}</dd></div>
}

function LeadingIcon({ usable, failed, trendDirection }: { usable: boolean; failed: boolean; trendDirection: string | null }) {
  const className = failed ? 'bg-[var(--color-error-surface)] text-[var(--color-error)]' : usable ? 'bg-[var(--color-info-surface)] text-[var(--color-info)]' : 'bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)]'
  return <span className={`mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-lg ${className}`}>{failed ? <AlertTriangle size={18} aria-hidden="true" /> : usable ? <TrendDirectionIcon direction={trendDirection ?? 'stable'} /> : <Signal size={18} aria-hidden="true" />}</span>
}

function TrendDirectionIcon({ direction }: { direction: string }) {
  if (direction === 'increasing') return <TrendingUp size={18} aria-hidden="true" />
  if (direction === 'decreasing') return <TrendingDown size={18} aria-hidden="true" />
  return <TrendingUpDown size={18} aria-hidden="true" />
}

function DataQuality({ quality }: { quality: 'good' | 'degraded' | 'insufficient' }) {
  const classes = quality === 'good' ? 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-success)]' : quality === 'degraded' ? 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-warning)]' : 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-warning)]'
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${classes}`}>Data quality: {quality}</span>
}

function LensStatus({ status }: { status: ObservationRunLensRun['status'] }) {
  if (status === 'partial') return <span aria-label="Lens execution status: Partial" className="inline-flex rounded-full border border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] px-2.5 py-1 text-xs font-semibold text-[var(--color-warning)]">Partial</span>
  return <ExecutionStatusBadge status={status} />
}

function isUsableMetricResult(result: MetricRunResult): result is UsableMetricRunResult { return 'data_quality' in result && result.data_quality !== 'insufficient' }
function metricIdentity(lens: ObservationRunLensRun) { const result = lens.result; return result?.lens_type === 'metric' ? { reference: result.identity.metric_ref, unit: result.identity.unit } : { reference: lens.lens_id, unit: null } }
function returnedReferenceOffsets(result: UsableMetricRunResult) { if (result.reference_periods === null || result.evidence.reference_periods === null) return []; const evidenceOffsets = new Set(result.evidence.reference_periods.map((reference) => reference.offset)); return result.reference_periods.filter((reference) => evidenceOffsets.has(reference.offset)).map((reference) => reference.offset) }
function availabilityText(perspective: string, reason: StructuredReason | null, marker: string) { return reason?.code.includes(marker) ? `${perspective} limited: ${formatReason(reason)}` : 'Unavailable in this result' }
function supportedReason(lens: ObservationRunLensRun, result: MetricRunResult | null) { if (lens.reason) return lens.reason; return result !== null && 'reason' in result ? result.reason ?? null : null }
function unavailableDescription(lens: ObservationRunLensRun, result: MetricRunResult | null) { if (result !== null && !('data_quality' in result)) return `Current Metric evidence was unavailable. ${result.status.error.message}`; if (result !== null && result.data_quality === 'insufficient') return 'Current Metric data was insufficient for usable evidence.'; if (lens.status === 'pending' || lens.status === 'running') return 'This Lens is still progressing; no result artifact is durable yet.'; if (lens.status === 'cancelled') return 'This Lens was cancelled before a result artifact was produced.'; if (lens.status === 'failed') return 'This Lens failed before usable current evidence was available.'; return 'This Lens finished before a result artifact was produced.' }
function formatReason(reason: StructuredReason) { return reason.component ? `${reason.code} · ${reason.component}` : reason.code }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString() }
function formatDuration(seconds: number | null, status: ObservationRunLensRun['status']) { if (seconds === null) return status === 'pending' || status === 'running' ? 'In progress' : 'Unavailable'; if (seconds < 60) return `${Math.round(seconds)}s`; return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s` }
function trendIcon(direction: string) { if (direction === 'increasing') return TrendingUp; if (direction === 'decreasing') return TrendingDown; return TrendingUpDown }
