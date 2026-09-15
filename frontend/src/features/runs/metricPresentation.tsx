import type { MetricCurrentEvidence, MetricReferenceComparison, MetricReferenceEvidence, StructuredReason, UsableMetricRunResult } from './types'
import { formatMetricNumber } from './metricFormatting'

/** Presents the frozen semantic sections of one usable Metric result. */
export function MetricResultPresentation({ result, reason }: { result: UsableMetricRunResult; reason?: StructuredReason | null }) {
  const limitation = reason ?? result.reason ?? null
  return <div className="mt-5 space-y-5">
    <div><p className="[overflow-wrap:anywhere] text-sm font-semibold">Metric: {result.identity.metric_ref} <span className="font-normal text-[var(--color-text-secondary)]">({result.identity.unit})</span></p><p className="mt-1 break-all font-mono text-xs text-[var(--color-text-secondary)]">Lens ID: {result.identity.lens_id}</p></div>
    <div className="flex flex-wrap gap-2" aria-label="Metric semantic state">
      <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${result.data_quality === 'degraded' ? 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-warning)]' : 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-success)]'}`}>Data quality: {result.data_quality}</span>
      <span className="rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs">Trend: {result.current_state.trend.direction} · {result.current_state.trend.rate}</span>
      <span className="rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs">Variability: {result.current_state.variability.state}</span>
    </div>
    <section aria-labelledby="metric-current-numerical-evidence"><h4 id="metric-current-numerical-evidence" className="text-sm font-semibold">Current numerical evidence</h4><MetricValues evidence={result.evidence.current} /></section>
    <section aria-labelledby="metric-current-semantic-state"><h4 id="metric-current-semantic-state" className="text-sm font-semibold">Current semantic state</h4><dl className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-3 text-sm"><Value label="Trend direction" value={result.current_state.trend.direction} /><Value label="Trend rate" value={result.current_state.trend.rate} /><Value label="Variability" value={result.current_state.variability.state} /></dl></section>
    <OptionalAnalyses result={result} />
    <ReferencePeriods currentMean={result.evidence.current.mean} comparisons={result.reference_periods} evidence={result.evidence.reference_periods} reason={limitation} />
    <HistorySummary history={result.history} evidence={result.evidence.history} reason={limitation} />
  </div>
}

function MetricValues({ evidence }: { evidence: MetricCurrentEvidence }) {
  return <dl className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-3 text-sm"><Value label="Mean" value={formatMetricNumber(evidence.mean)} /><Value label="Standard deviation" value={formatMetricNumber(evidence.std)} /><Value label="Minimum" value={formatMetricNumber(evidence.min)} /><Value label="Maximum" value={formatMetricNumber(evidence.max)} /><Value label="Slope" value={formatMetricNumber(evidence.slope)} /></dl>
}

function OptionalAnalyses({ result }: { result: UsableMetricRunResult }) {
  const entries = [
    { label: 'Spike analysis', state: result.current_state.spike, evidence: result.evidence.current.spike },
    { label: 'Oscillation analysis', state: result.current_state.oscillation, evidence: result.evidence.current.oscillation },
    { label: 'Stuck-signal analysis', state: result.current_state.stuck_signal, evidence: result.evidence.current.stuck_signal },
  ]
  return <section aria-labelledby="metric-optional-analysis"><h4 id="metric-optional-analysis" className="text-sm font-semibold">Optional analysis</h4><div className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(12rem,1fr))] gap-3">{entries.map((entry) => <OptionalAnalysisCard key={entry.label} {...entry} />)}</div></section>
}

function OptionalAnalysisCard({ label, state, evidence }: { label: string; state: UsableMetricRunResult['current_state']['spike']; evidence: unknown }) {
  if (state === null) return <article className="rounded-lg border border-[var(--color-border)] p-3 text-sm"><h5 className="font-medium">{label}</h5><p className="mt-1 text-[var(--color-text-secondary)]">Unavailable in this result.</p></article>
  return <article className="rounded-lg border border-[var(--color-border)] p-3 text-sm"><h5 className="font-medium">{label}</h5><p className="mt-1">State: <span className="font-medium">{state.state}</span></p>{evidence === null ? <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Supporting evidence was not returned.</p> : <OptionalEvidence evidence={evidence} />}</article>
}

function OptionalEvidence({ evidence }: { evidence: unknown }) {
  if (!isRecord(evidence)) return null
  if ('method' in evidence) return <dl className="mt-2 grid gap-1 text-xs text-[var(--color-text-secondary)]"><OptionalValue label="Method" value={String(evidence.method)} />{'deviation_count' in evidence ? <OptionalValue label="Deviation count" value={formatMetricNumber(Number(evidence.deviation_count))} /> : null}<OptionalValue label="Detected samples" value={formatMetricNumber(Number(evidence.detected_sample_count))} />{'max_abs_modified_z' in evidence ? <OptionalValue label="Maximum modified Z" value={formatMetricNumber(Number(evidence.max_abs_modified_z))} /> : null}<OptionalValue label="Detected timestamps" value={Array.isArray(evidence.detected_timestamps) ? String(evidence.detected_timestamps.length) : 'Unavailable'} /></dl>
  if ('deadband' in evidence) return <dl className="mt-2 grid gap-1 text-xs text-[var(--color-text-secondary)]"><OptionalValue label="Deadband" value={formatMetricNumber(Number(evidence.deadband))} /><OptionalValue label="Significant residuals" value={formatMetricNumber(Number(evidence.significant_residual_count))} /><OptionalValue label="Sign changes" value={formatMetricNumber(Number(evidence.sign_change_count))} /><OptionalValue label="Sign-change ratio" value={formatMetricNumber(Number(evidence.sign_change_ratio))} /></dl>
  if ('repeated_value' in evidence) return <dl className="mt-2 grid gap-1 text-xs text-[var(--color-text-secondary)]"><OptionalValue label="Repeated value" value={formatMetricNumber(Number(evidence.repeated_value))} /><OptionalValue label="Longest repeated run" value={formatMetricNumber(Number(evidence.longest_run_sample_count))} /><OptionalValue label="Longest-run share" value={formatMetricNumber(Number(evidence.longest_run_share))} /></dl>
  return null
}

function ReferencePeriods({ comparisons, currentMean, evidence, reason }: { comparisons: readonly MetricReferenceComparison[] | null; currentMean: number; evidence: readonly MetricReferenceEvidence[] | null; reason: StructuredReason | null }) {
  if (comparisons === null || evidence === null) return <section aria-labelledby="metric-reference-periods"><h4 id="metric-reference-periods" className="text-sm font-semibold">Reference-period comparison</h4><UnavailablePerspective perspective="Reference-period comparison" reason={reason} /></section>
  const returned = evidence.flatMap((item) => {
    const comparison = comparisons.find((candidate) => candidate.offset === item.offset)
    return comparison ? [{ item, comparison }] : []
  })
  if (returned.length === 0) return <section aria-labelledby="metric-reference-periods"><h4 id="metric-reference-periods" className="text-sm font-semibold">Reference-period comparison</h4><UnavailablePerspective perspective="Reference-period comparison" reason={reason} /></section>
  return <section aria-labelledby="metric-reference-periods"><h4 id="metric-reference-periods" className="text-sm font-semibold">Reference-period comparison</h4><ul className="mt-2 grid grid-cols-1 gap-3">{returned.map(({ item, comparison }) => <li key={item.offset} className="rounded-lg border border-[var(--color-border)] p-3 text-sm"><h5 className="font-medium">Reference period: {item.offset}</h5><p className="mt-1 text-xs text-[var(--color-text-secondary)]">Window: {comparison.analysis_window.from} to {comparison.analysis_window.to}</p><dl className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-2"><Value label="Current mean" value={formatMetricNumber(currentMean)} /><Value label="Reference mean" value={formatMetricNumber(item.mean)} /><Value label="Reference standard deviation" value={formatMetricNumber(item.std)} /><Value label="Reference minimum" value={formatMetricNumber(item.min)} /><Value label="Reference maximum" value={formatMetricNumber(item.max)} /><Value label="Reference slope" value={formatMetricNumber(item.slope)} /><Value label="Symmetric relative change" value={formatMetricNumber(item.relative_level_change)} /><Value label="Level relation" value={comparison.level.relation} /><Value label="Trend direction relation" value={comparison.trend.direction_relation} /><Value label="Trend rate relation" value={comparison.trend.rate_relation} /><Value label="Variability relation" value={comparison.variability.relation} /></dl><p className="mt-3 text-xs text-[var(--color-text-secondary)]">Reference trend: {comparison.trend.direction} / {comparison.trend.rate}; reference variability: {comparison.variability.state}.</p></li>)}</ul></section>
}

function HistorySummary({ history, evidence, reason }: { history: UsableMetricRunResult['history']; evidence: UsableMetricRunResult['evidence']['history']; reason: StructuredReason | null }) {
  if (history === null || evidence === null) return <section aria-labelledby="metric-history"><h4 id="metric-history" className="text-sm font-semibold">Persisted History</h4><UnavailablePerspective perspective="Persisted History" reason={reason} /></section>
  return <section aria-labelledby="metric-history"><h4 id="metric-history" className="text-sm font-semibold">Persisted History</h4><dl className="mt-2 grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-3 text-sm"><Value label="Direction" value={history.direction} /><Value label="Pattern" value={history.pattern} /><Value label="Referenced runs" value={String(history.run_ids.length)} /><Value label="Direction changes" value={String(evidence.direction_changes)} /><Value label="Classifiable transitions" value={String(evidence.classifiable_transitions)} /><Value label="Unknown transitions" value={String(evidence.unknown_transitions)} /></dl></section>
}

function UnavailablePerspective({ perspective, reason }: { perspective: 'Reference-period comparison' | 'Persisted History'; reason: StructuredReason | null }) { const limitationApplies = reason !== null && (perspective === 'Reference-period comparison' ? reason.code.includes('reference') : reason.code.includes('history')); return <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{limitationApplies ? `${perspective} is limited: ${reason.code}.` : 'Unavailable in this result.'}</p> }

function Value({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">{label}</dt><dd className="mt-1 break-words text-[var(--color-text-primary)]">{value}</dd></div> }
function OptionalValue({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-3"><dt>{label}</dt><dd className="font-mono text-[var(--color-text-primary)]">{value}</dd></div> }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value) }
