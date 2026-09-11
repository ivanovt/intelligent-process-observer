import type { EvidenceReference, ObservationRunDetail } from './types'
import { compactTraceabilityId, formatResolvedValue, resolveTraceability, type TraceabilityResolution } from './traceability'

/** Collapsed, accessible evidence control with exact local traceability on demand. */
export function EvidenceDisclosure({ detail, reference }: { detail: ObservationRunDetail; reference: EvidenceReference }) { return <TraceabilityDisclosure resolution={resolveTraceability(detail, reference)} tone="evidence" /> }

/** Collapsed, accessible relationship control with exact local traceability on demand. */
export function RelationshipDisclosure({ detail, reference }: { detail: ObservationRunDetail; reference: EvidenceReference }) { return <TraceabilityDisclosure resolution={resolveTraceability(detail, reference)} tone="relationship" /> }

function TraceabilityDisclosure({ resolution, tone }: { resolution: TraceabilityResolution; tone: 'evidence' | 'relationship' }) {
  const style = tone === 'evidence' ? 'border-[var(--color-info-border)] bg-[var(--color-info-surface)] text-[var(--color-info)]' : 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-primary)]'
  return <details className={`rounded-lg border px-2 py-1 text-xs ${style}`}><summary className="cursor-pointer select-none font-medium">{resolution.sourceLabel} · {compactTraceabilityId(resolution.sourceId)} · {resolution.locator}</summary><dl className="mt-2 grid gap-1 border-t border-current/20 pt-2"><div><dt className="inline font-medium">Source ID: </dt><dd className="inline break-all font-mono">{resolution.sourceId}</dd></div><div><dt className="inline font-medium">Path: </dt><dd className="inline break-all font-mono">{resolution.locator}</dd></div>{resolution.available ? <div><dt className="inline font-medium">Resolved value: </dt><dd className="inline break-words font-mono">{formatResolvedValue(resolution.value)}</dd></div> : <div role="status">Traceability unavailable in this run.</div>}</dl></details>
}
