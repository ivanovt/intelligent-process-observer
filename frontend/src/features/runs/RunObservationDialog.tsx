import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Field, InlineNotice, Input, Select } from '../../components/ui'
import { listObservations } from '../observations/api'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunLaunchRequest, ObservationRunSummary } from './types'
import { relativePresets, resolveTimeRange, type Clock, type RelativePresetId, type TimeRangeInput } from './timeRange'

type DefinitionsState =
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'success'; definitions: readonly ObservationSummary[] }

export interface RunObservationDialogProps {
  readonly activeRuns: readonly ObservationRunSummary[]
  readonly clock?: Clock
  readonly onClose: () => void
  readonly onLaunch: (payload: ObservationRunLaunchRequest) => Promise<void>
}

/** Collects one existing Observation and a concrete, server-safe analysis window before launch. */
export function RunObservationDialog({ activeRuns, clock = () => new Date(), onClose, onLaunch }: RunObservationDialogProps) {
  const [definitionsState, setDefinitionsState] = useState<DefinitionsState>({ status: 'loading' })
  const [retryNonce, setRetryNonce] = useState(0)
  const [observationId, setObservationId] = useState('')
  const [rangeInput, setRangeInput] = useState<TimeRangeInput>({ kind: 'preset', preset: '15m' })
  const [launchError, setLaunchError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => { dialogRef.current?.focus() }, [])

  useEffect(() => {
    const controller = new AbortController()
    listObservations(controller.signal)
      .then((definitions) => { if (!controller.signal.aborted) setDefinitionsState({ status: 'success', definitions }) })
      .catch(() => { if (!controller.signal.aborted) setDefinitionsState({ status: 'error' }) })
    return () => controller.abort()
  }, [retryNonce])

  const activeObservationIds = useMemo(() => new Set(activeRuns.filter((run) => run.status === 'pending' || run.status === 'running').map((run) => run.observation.id)), [activeRuns])
  const selectedEligible = definitionsState.status === 'success' && observationId !== '' && !activeObservationIds.has(observationId)
  const preview = resolveTimeRange(rangeInput, clock)
  const canSubmit = selectedEligible && preview.ok && !submitting

  async function submit() {
    const resolved = resolveTimeRange(rangeInput, clock)
    if (!resolved.ok) {
      setLaunchError(resolved.error)
      return
    }
    if (!selectedEligible) return
    setSubmitting(true)
    setLaunchError(null)
    try {
      await onLaunch({ observation_id: observationId, analysis_window: resolved.value })
    } catch (error) {
      setLaunchError(toLaunchMessage(error))
      setSubmitting(false)
    }
  }

  return (
    <div aria-describedby="run-observation-dialog-description" aria-labelledby="run-observation-dialog-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4" ref={dialogRef} role="dialog" tabIndex={-1} onKeyDown={(event) => { if (event.key === 'Escape' && !submitting) onClose() }}>
      <div className="max-h-[calc(100vh-2rem)] w-full max-w-xl overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4"><div><h2 id="run-observation-dialog-title" className="text-xl font-semibold">Run Observation</h2><p id="run-observation-dialog-description" className="mt-1 text-sm text-[var(--color-text-secondary)]">Choose an existing Observation and a finite UTC analysis window.</p></div><Button aria-label="Close Run Observation dialog" type="button" variant="ghost" onClick={onClose}>Close</Button></div>

        <div className="mt-6 grid gap-5">
          <DefinitionSelector activeObservationIds={activeObservationIds} observationId={observationId} state={definitionsState} onChange={setObservationId} onRetry={() => { setDefinitionsState({ status: 'loading' }); setRetryNonce((value) => value + 1) }} />
          <TimeRangeChooser input={rangeInput} preview={preview} onChange={setRangeInput} />
          {launchError ? <InlineNotice tone="error">{launchError}</InlineNotice> : null}
        </div>

        <div className="mt-7 flex flex-wrap justify-end gap-3 border-t border-[var(--color-border)] pt-5"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="button" disabled={!canSubmit} onClick={() => void submit()}>{submitting ? 'Launching…' : 'Run Observation'}</Button></div>
      </div>
    </div>
  )
}

function DefinitionSelector({ activeObservationIds, observationId, state, onChange, onRetry }: { activeObservationIds: ReadonlySet<string>; observationId: string; state: DefinitionsState; onChange: (id: string) => void; onRetry: () => void }) {
  if (state.status === 'loading') return <InlineNotice>Loading current Observation definitions…</InlineNotice>
  if (state.status === 'error') return <InlineNotice tone="error">Unable to load Observation definitions. <button className="font-semibold underline underline-offset-2" type="button" onClick={onRetry}>Retry</button></InlineNotice>
  if (state.definitions.length === 0) return <InlineNotice tone="info">No Observation is available to run. <Link className="font-semibold underline underline-offset-2" to="/observations/new">New Observation</Link></InlineNotice>
  return <Field label="Observation" description="Definitions with a known active run are unavailable until that run is terminal."><Select aria-label="Observation to run" value={observationId} onChange={(event) => onChange(event.target.value)}><option value="">Choose an Observation</option>{state.definitions.map((definition) => { const active = activeObservationIds.has(definition.id); return <option disabled={active} key={definition.id} value={definition.id}>{definition.name}{active ? ' — active run in progress' : ''}</option> })}</Select></Field>
}

function TimeRangeChooser({ input, preview, onChange }: { input: TimeRangeInput; preview: ReturnType<typeof resolveTimeRange>; onChange: (input: TimeRangeInput) => void }) {
  const isPreset = input.kind === 'preset'
  return <fieldset className="grid gap-4 rounded-lg border border-[var(--color-border)] p-4"><legend className="px-1 text-sm font-semibold">Analysis time range</legend><div className="flex gap-4 text-sm"><label className="flex items-center gap-2"><input checked={isPreset} name="range-mode" type="radio" onChange={() => onChange({ kind: 'preset', preset: '15m' })} />Relative range</label><label className="flex items-center gap-2"><input checked={!isPreset} name="range-mode" type="radio" onChange={() => onChange({ kind: 'expressions', from: 'now-15m', to: 'now' })} />Expressions</label></div>{isPreset ? <Field label="Relative range"><Select aria-label="Relative analysis range" value={input.preset} onChange={(event) => onChange({ kind: 'preset', preset: event.target.value as RelativePresetId })}>{relativePresets.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}</Select></Field> : <div className="grid gap-4 sm:grid-cols-2"><Field label="From" description="Supported: now, now-15m, now-1h"><Input aria-label="From expression" value={input.from} onChange={(event) => onChange({ kind: 'expressions', from: event.target.value, to: input.to })} /></Field><Field label="To" description="Supported: now, now-15m, now-1h"><Input aria-label="To expression" value={input.to} onChange={(event) => onChange({ kind: 'expressions', from: input.from, to: event.target.value })} /></Field></div>}{preview.ok ? <p aria-live="polite" className="text-sm text-[var(--color-text-secondary)]">Resolved UTC window: {preview.value.from} to {preview.value.to}</p> : <InlineNotice tone="error">{preview.error}</InlineNotice>}</fieldset>
}

function toLaunchMessage(error: unknown) {
  if (typeof error === 'object' && error !== null && 'status' in error && (error as { status?: unknown }).status === 409) return 'This Observation already has an active run. Refresh history and open the existing run.'
  return 'Unable to launch this Observation. Check the selected window and try again.'
}
