import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { ExecutionStatusBadge } from '../../components/domain/RunStatusBadges'
import { Button } from '../../components/ui'
import { MetricLensCard } from './MetricLensCard'
import { MetricResultPresentation } from './metricPresentation'
import type { MetricRunResult, ObservationRunDetail, ObservationRunLensRun, StructuredReason, UsableMetricRunResult } from './types'

/** Browses the immutable Metric LensRun results held by one durable run-detail snapshot. */
export function MetricLensResults({ detail, lastSuccessfulAt, onViewAnalysis }: { detail: ObservationRunDetail; lastSuccessfulAt: number | null; onViewAnalysis: () => void }) {
  const lenses = detail.lens_runs.filter((lens) => lens.lens_type === 'metric')
  const lensIdSequence = JSON.stringify(lenses.map((lens) => lens.id))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [previousLensIdSequence, setPreviousLensIdSequence] = useState(lensIdSequence)
  const isWideLayout = useWideMetricLayout()
  const detailRef = useRef<HTMLElement | null>(null)
  const cardContainers = useRef(new Map<string, HTMLDivElement>())
  const returnFocusId = useRef<string | null>(null)

  if (lensIdSequence !== previousLensIdSequence) {
    setPreviousLensIdSequence(lensIdSequence)
    if (selectedId !== null && !lenses.some((lens) => lens.id === selectedId)) setSelectedId(null)
  }

  const selected = selectedId === null ? null : lenses.find((lens) => lens.id === selectedId) ?? null
  const selectedIsPresent = selected !== null

  useEffect(() => {
    if (selectedId !== null && selectedIsPresent) {
      const detailElement = detailRef.current
      if (detailElement !== null) {
        if (isWideLayout) detailElement.scrollTop = 0
        else if (typeof detailElement.scrollIntoView === 'function') detailElement.scrollIntoView({ block: 'start' })
        detailElement.focus({ preventScroll: true })
      }
      return
    }
    const focusId = returnFocusId.current
    if (focusId !== null) {
      cardContainers.current.get(focusId)?.querySelector<HTMLButtonElement>('button')?.focus()
      returnFocusId.current = null
    }
  }, [isWideLayout, selectedId, selectedIsPresent])

  function dismissDetail() {
    returnFocusId.current = selected?.id ?? null
    setSelectedId(null)
  }

  if (!lenses.length) return <MetricEmpty detail={detail} lastSuccessfulAt={lastSuccessfulAt} />

  return <section>
    <MetricHeader count={lenses.length} selectedCount={selected === null ? 0 : 1} lastSuccessfulAt={lastSuccessfulAt} />
    <div className={selected === null || !isWideLayout ? 'grid min-w-0 grid-cols-[minmax(0,1fr)] items-start gap-4' : 'grid min-w-0 items-start gap-4 min-[1170px]:grid-cols-[minmax(0,1.8fr)_minmax(17rem,1fr)]'}>
      <div aria-label="Metric Lens results" className="grid min-w-0 gap-3">{lenses.map((lens) => <div key={lens.id} className="min-w-0" ref={(element) => { if (element === null) cardContainers.current.delete(lens.id); else cardContainers.current.set(lens.id, element) }}><MetricLensCard lens={lens} selected={selected?.id === lens.id} onSelect={() => setSelectedId(lens.id)} />{!isWideLayout && selected?.id === lens.id ? <MetricDetail lens={selected} detailRef={detailRef} onDismiss={dismissDetail} onViewAnalysis={onViewAnalysis} /> : null}</div>)}</div>
      {isWideLayout && selected !== null ? <MetricDetail lens={selected} detailRef={detailRef} onDismiss={dismissDetail} onViewAnalysis={onViewAnalysis} /> : null}
    </div>
  </section>
}

function MetricDetail({ lens, detailRef, onDismiss, onViewAnalysis }: { lens: ObservationRunLensRun; detailRef: React.RefObject<HTMLElement | null>; onDismiss: () => void; onViewAnalysis: () => void }) {
  const identity = metricIdentity(lens)
  return <article ref={detailRef} tabIndex={-1} className="mt-4 min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-focus)] min-[1170px]:sticky min-[1170px]:top-4 min-[1170px]:self-start min-[1170px]:mt-0 min-[1170px]:max-h-[calc(100dvh-2rem)] min-[1170px]:overflow-y-auto" aria-label={`Metric Lens detail: ${lens.id}`}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="break-words text-lg font-semibold">{identity.reference}</h3>{identity.unit ? <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Unit: {identity.unit}</p> : null}<p className="mt-1 break-all font-mono text-xs text-[var(--color-text-secondary)]">Lens ID: {lens.lens_id} · LensRun ID: {lens.id}</p></div><div className="flex items-center gap-2"><LensStatus status={lens.status} selected /><Button type="button" variant="secondary" onClick={onDismiss} aria-label="Dismiss Metric Lens detail"><X size={16} aria-hidden="true" />Dismiss</Button></div></div>
    <p className="mt-3 text-sm text-[var(--color-text-secondary)]">{lens.started_at ? `Started ${formatDate(lens.started_at)}` : 'Not started'} · {formatDuration(lens.duration_seconds, lens.status)}</p>
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
function MetricHeader({ count, selectedCount, lastSuccessfulAt }: { count: number; selectedCount: number; lastSuccessfulAt: number | null }) { return <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-semibold">Metric Lens results</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{count} Metric {count === 1 ? 'Lens' : 'Lenses'} · {selectedCount} selected</p></div>{lastSuccessfulAt !== null ? <p className="text-xs text-[var(--color-text-secondary)]" aria-label={`Last updated by this client at ${formatClientTime(lastSuccessfulAt)}`}>Last updated {formatClientTime(lastSuccessfulAt)}</p> : null}</div> }
function MetricEmpty({ detail, lastSuccessfulAt }: { detail: ObservationRunDetail; lastSuccessfulAt: number | null }) { const status = detail.summary.status; const message = status === 'pending' || status === 'running' ? 'Execution is still progressing; this artifact has not been produced yet.' : status === 'cancelled' ? 'Execution was cancelled before this artifact was produced.' : status === 'failed' ? 'Execution failed before this artifact was produced.' : 'This run legitimately produced an empty collection for this section.'; return <section><MetricHeader count={0} selectedCount={0} lastSuccessfulAt={lastSuccessfulAt} /><p role="status" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">{message}</p></section> }
function LensStatus({ status, selected = false }: { status: ObservationRunLensRun['status']; selected?: boolean }) { return status === 'partial' ? <span aria-label={selected ? 'Selected Lens execution status: Partial' : 'Lens execution status: Partial'} className="shrink-0 rounded-full border border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] px-2.5 py-1 text-xs font-semibold text-[var(--color-warning)]">Partial</span> : <ExecutionStatusBadge status={status} /> }
function metricIdentity(lens: ObservationRunLensRun) { const result = lens.result; return result?.lens_type === 'metric' ? { reference: result.identity.metric_ref, unit: result.identity.unit } : { reference: lens.lens_id, unit: null } }
function unavailableMessage(status: ObservationRunLensRun['status']) { if (status === 'pending' || status === 'running') return 'This Lens is still progressing; no result artifact is durable yet.'; if (status === 'cancelled') return 'This Lens was cancelled before a result artifact was produced.'; return 'This Lens finished before a result artifact was produced.' }
function formatReason(reason: StructuredReason) { return reason.component ? `${reason.code} · ${reason.component}` : reason.code }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString() }
function formatClientTime(value: number) { return new Date(value).toLocaleString() }
function formatDuration(seconds: number | null, status: ObservationRunLensRun['status']) { if (seconds === null) return status === 'pending' || status === 'running' ? 'In progress' : 'Unavailable'; if (seconds < 60) return `${Math.round(seconds)}s`; return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s` }

function useWideMetricLayout() {
  const query = '(min-width: 1170px)'
  const [matches, setMatches] = useState(() => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(query).matches)
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const media = window.matchMedia(query)
    const update = () => setMatches(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return matches
}
