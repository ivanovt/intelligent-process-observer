import { CircleAlert } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { Button, Field, FormSideRail, InlineNotice, Input, Select, Textarea, ValidationSummary, type ValidationIssue } from '../../components/ui'
import { ReferencePeriodsField } from './configuration'
import { preflightMetricQuery } from './api'
import { generateObservationChildId, newMetric, useObservationDraft, validateMetric, type DraftErrors, type DraftMetric } from './draft'
import { ApiError, type MetricObjective, type MetricPreflightFailure, type MetricPreflightResponse } from './types'

const objectives:MetricObjective[]=['spike','drift','oscillation']
type PreflightState={status:'idle'}|{status:'pending'}|{status:'valid';result:Extract<MetricPreflightResponse,{valid:true}>}|{status:'invalid';result:MetricPreflightFailure}|{status:'request_failure';message:string}

function preflightFailureMessage(error:unknown):string {
  if (error instanceof ApiError) {
    if (error.code === 'provider_authentication_failed') return 'Prometheus authentication or authorization failed. Check the configured source and try again.'
    if (error.code === 'provider_unavailable') return 'Prometheus is unavailable. Try again when the configured source is reachable.'
    if (error.code === 'provider_failure') return 'Prometheus could not complete the preflight request. Try again.'
    return error.message
  }
  return 'Unable to validate the query. Try again.'
}

function LabelSet({ labels }: { labels: Record<string, string> }) {
  const entries=Object.entries(labels)
  if (!entries.length) return <p className="mt-2 text-sm">No labels were returned.</p>
  return <dl className="mt-2 grid gap-x-3 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">{entries.map(([name,value])=><div key={name} className="contents"><dt className="font-medium">{name}</dt><dd className="break-all">{value}</dd></div>)}</dl>
}

function PreflightResult({ state }: { state: PreflightState }) {
  if (state.status==='idle') return null
  if (state.status==='pending') return <InlineNotice>Validating the exact query against the selected source…</InlineNotice>
  if (state.status==='request_failure') return <InlineNotice tone="error">{state.message}</InlineNotice>
  if (state.status==='valid') return <InlineNotice tone="success"><p className="font-medium">Query validation succeeded.</p><p className="mt-1">Validation window: {state.result.resolved_start} to {state.result.resolved_end}.</p><p className="mt-1">Sample count: {state.result.samples.length}.</p><div className="mt-2"><p className="font-medium">Returned labels</p><LabelSet labels={state.result.labels}/></div></InlineNotice>
  const {result}=state
  if (result.code==='no_series_returned') return <InlineNotice tone="warning">The query returned no series for this validation window. This does not mean the query syntax is invalid.</InlineNotice>
  if (result.code==='multiple_series_returned') return <InlineNotice tone="warning"><p>The query returned {result.series_count ?? 'multiple'} series. One Metric Lens must resolve to exactly one series.</p><p className="mt-1">Aggregate the query or select one label combination; the query was not changed.</p>{result.label_sets.length?<div className="mt-2"><p className="font-medium">Returned label sets</p>{result.label_sets.map((labels,index)=><div key={index} className="mt-2"><p className="font-medium">Series {index+1}</p><LabelSet labels={labels}/></div>)}</div>:null}</InlineNotice>
  if (result.code==='query_rejected') return <InlineNotice tone="error"><p className="font-medium">Prometheus rejected this query.</p><p className="mt-1">{result.message}</p></InlineNotice>
  return <InlineNotice tone="warning"><p className="font-medium">The query could not be validated.</p><p className="mt-1">{result.message}</p></InlineNotice>
}

/** Edits one aggregate-owned Metric Lens using only current capability choices. */
export function MetricLensEditorPage(){const {key='new'}=useParams();const {draft,returnRoute}=useObservationDraft();if(!draft)return <Navigate to={returnRoute} replace state={{draftLost:true}}/>;const existing=key==='new'?undefined:draft.lenses.find(item=>item.clientKey===key);if(key!=='new'&&!existing)return <Navigate to={returnRoute} replace state={{draftLost:true}}/>;return <MetricLensEditorForm key={key} routeKey={key} seed={existing?structuredClone(existing):newMetric(crypto.randomUUID())}/>}
function MetricLensEditorForm({ routeKey, seed }: { routeKey: string; seed: DraftMetric }) {
  const navigate = useNavigate()
  const { draft, mode, returnRoute, upsertMetric, capabilities, loadCapabilities, cancelCapabilities } = useObservationDraft()
  const [value, setValue] = useState(seed)
  const [errors, setErrors] = useState<DraftErrors>({})
  const [preflight, setPreflight] = useState<PreflightState>({ status: 'idle' })
  const summaryRef = useRef<HTMLDivElement>(null)
  const preflightRequest = useRef<{ id: number; controller: AbortController } | null>(null)
  const preflightSequence = useRef(0)

  const cancelPreflight = useCallback((reset = true) => {
    const active = preflightRequest.current
    preflightRequest.current = null
    preflightSequence.current += 1
    active?.controller.abort()
    if (reset) setPreflight({ status: 'idle' })
  }, [])

  useEffect(() => () => { cancelCapabilities(); cancelPreflight(false) }, [cancelCapabilities, cancelPreflight])
  useEffect(() => {
    if (capabilities.status === 'idle') loadCapabilities()
  }, [capabilities.status, loadCapabilities])
  useEffect(() => { if (Object.keys(errors).length) summaryRef.current?.focus() }, [errors])

  if (!draft) return null

  const sources = capabilities.capabilities?.metric.flatMap((adapter) => adapter.sources.map((source) => ({ ...source, adapter_type: adapter.adapter_type }))) ?? []
  const update = (patch: Partial<DraftMetric>, invalidatesPreflight = false) => {
    if (invalidatesPreflight) cancelPreflight()
    setValue((current) => ({ ...current, ...patch }))
  }
  const generateId = () => {
    if (!value.id && value.name.trim()) update({ id: generateObservationChildId(value.name, 'metric', draft.lenses.map((item) => item.id), crypto.randomUUID()) })
  }
  const setObjectives = (next: MetricObjective[]) => update({ analysis_objectives: next })
  const apply = () => {
    const next = validateMetric(value, draft.lenses)
    setErrors(next)
    if (!Object.keys(next).length && capabilities.status === 'success') {
      upsertMetric(value, routeKey)
      navigate(returnRoute)
    }
  }
  const unavailable = capabilities.status !== 'success'
  const queryReady = Boolean(value.source_id && value.query.trim())
  const validateQuery = () => {
    if (!queryReady) return
    cancelPreflight(false)
    const id = ++preflightSequence.current
    const controller = new AbortController()
    preflightRequest.current = { id, controller }
    setPreflight({ status: 'pending' })
    preflightMetricQuery(value.source_id, value.query, controller.signal).then((result) => {
      if (preflightRequest.current?.id !== id || controller.signal.aborted) return
      preflightRequest.current = null
      setPreflight(result.valid ? { status: 'valid', result } : { status: 'invalid', result })
    }).catch((error:unknown) => {
      if (preflightRequest.current?.id !== id || controller.signal.aborted) return
      preflightRequest.current = null
      setPreflight({ status: 'request_failure', message: preflightFailureMessage(error) })
    })
  }
  const issues: ValidationIssue[] = Object.entries(errors).map(([path, message]) => ({ message, to: path === 'id' ? '#metric-name' : path === 'objectives' ? '#metric-objectives' : path === 'references' ? '#reference-periods' : `#metric-${path}` }))

  return (
    <section className="mx-auto max-w-6xl">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <header className="mb-3">
          <p className="text-sm text-[var(--color-text-secondary)]">Observations / {mode === 'edit' ? 'Edit' : 'Create'} / Metric Lens</p>
          <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Metric Lens Configuration</h1>
          <p className="mt-2 text-[var(--color-text-secondary)]">Configure one metric perspective. Analysis scope remains one metric per Lens.</p>
        </header>
        <FormSideRail
          className="lg:col-start-2 lg:row-span-2 lg:row-start-1"
          actions={<>
            <Button variant="secondary" onClick={() => navigate(returnRoute)}>Cancel</Button>
            <Button onClick={apply} disabled={unavailable}>Apply changes</Button>
          </>}
        >
          <aside className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <h2 className="text-lg font-semibold">Metric Lens semantics</h2>
            <p className="mt-4 text-sm leading-6 text-[var(--color-text-secondary)]">One Metric Lens observes exactly one metric. Analysis objectives describe intent; they do not select analytical tools. Reference periods compare equal-duration shifted windows.</p>
            <div className="mt-4"><InlineNotice tone="info">Saved into the Observation draft. No standalone Metric Lens resource is created.</InlineNotice></div>
          </aside>
        </FormSideRail>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          {issues.length ? <div className="mb-5"><ValidationSummary ref={summaryRef} issues={issues} title="Metric Lens changes cannot be applied" /></div> : null}
          <h2 className="text-lg font-semibold">Lens identity</h2>
          <div className="mt-5 min-w-0">
            <Field label={<span className="flex flex-wrap items-baseline gap-x-2 gap-y-1"><span>Name</span>{value.id ? <span id="metric-identity" className="break-all text-xs font-normal text-[var(--color-text-secondary)]">(id: {value.id})</span> : null}</span>} description={value.id ? 'Human-readable name shown in this Observation.' : 'Human-readable name shown in this Observation. An ID is generated after the initial non-empty name is entered.'} error={errors.name ?? errors.id}>
              <Input id="metric-name" aria-label="Name" aria-describedby={value.id ? 'metric-identity' : undefined} placeholder="Cooling pressure" value={value.name} onChange={(event) => update({ name: event.target.value })} onBlur={generateId} />
            </Field>
          </div>
          <div className="mt-4">
            <Field label="Description (optional)" description="Optional context for this metric perspective." error={errors.description}>
              <Textarea id="metric-description" placeholder="Tracks cooling-loop pressure over time." value={value.description ?? ''} onChange={(event) => update({ description: event.target.value === '' ? null : event.target.value })} />
            </Field>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <Field label="Metric ID" description="Provider metric identifier for the one metric this Lens observes." error={errors.metric_id}>
              <Input id="metric-metric_id" placeholder="process_pressure_bar" value={value.metric_id} onChange={(event) => update({ metric_id: event.target.value })} />
            </Field>
            <Field label="Unit" description="Unit returned by the provider for this metric." error={errors.unit}>
              <Input id="metric-unit" placeholder="bar" value={value.unit} onChange={(event) => update({ unit: event.target.value })} />
            </Field>
          </div>
          <div className="mt-4">
            <Field label="Metric source" description="Configured source used to retrieve this metric." error={errors.source_id}>
              <Select id="metric-source_id" aria-label="Metric source" value={value.source_id} disabled={unavailable} onChange={(event) => {
                const choice = sources.find((source) => source.id === event.target.value)
                update({ source_id: event.target.value, adapter_type: choice?.adapter_type ?? 'prometheus' }, true)
              }}>
                <option value="">Select configured source</option>
                {sources.map((source) => <option key={`${source.adapter_type}:${source.id}`} value={source.id}>{source.name}</option>)}
              </Select>
            </Field>
          </div>
          <div className="mt-4">
            <Field label="Provider query" description="Provider-native query for the selected metric source." error={errors.query}>
              <Textarea id="metric-query" aria-label="Provider query" placeholder="rate(process_pressure_total[5m])" value={value.query} onChange={(event) => update({ query: event.target.value }, true)} />
            </Field>
          </div>
          <section className="mt-4" aria-label="Metric query preflight">
            <Button type="button" variant="secondary" onClick={validateQuery} disabled={unavailable || !queryReady} aria-busy={preflight.status==='pending'}>Validate query</Button>
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Advisory only: validates the exact query with the selected source over a fixed 15m window. It does not change this draft or block Apply changes.</p>
            <div className="mt-3" aria-live="polite" aria-atomic="true" aria-label="Query validation result"><PreflightResult state={preflight}/></div>
          </section>
          {capabilities.status === 'pending' ? <InlineNotice>Loading configured Metric sources…</InlineNotice> : null}
          {capabilities.status === 'failure' ? <InlineNotice tone="error">Unable to load Metric sources. <button className="font-semibold underline" type="button" onClick={loadCapabilities}>Retry</button></InlineNotice> : null}
          {capabilities.status === 'empty' ? <InlineNotice tone="warning">No Metric source is configured. Metric Lens configuration is unavailable; Alert-only Observation creation remains available.</InlineNotice> : null}
          <section id="metric-objectives" className="mt-7" aria-describedby={errors.objectives ? 'metric-objectives-guidance metric-objectives-error' : 'metric-objectives-guidance'} aria-invalid={Boolean(errors.objectives)}>
            <h3 className="font-semibold">Analysis objectives</h3>
            <p id="metric-objectives-guidance" className="mt-1 text-sm text-[var(--color-text-secondary)]">Choose supported analytical intent in order. Free-text Metric objectives require a backend contract change.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {objectives.map((objective) => <label key={objective} className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm has-[:checked]:border-[var(--color-primary)]">
                <input type="checkbox" aria-invalid={Boolean(errors.objectives)} aria-describedby={errors.objectives ? 'metric-objectives-guidance metric-objectives-error' : 'metric-objectives-guidance'} checked={value.analysis_objectives.includes(objective)} onChange={(event) => setObjectives(event.target.checked ? [...value.analysis_objectives, objective] : value.analysis_objectives.filter((item) => item !== objective))} />
                {objective}
              </label>)}
            </div>
            {errors.objectives ? <p id="metric-objectives-error" className="mt-1 flex items-center gap-1 text-sm text-[var(--color-error)]"><CircleAlert size={15} aria-hidden="true" />{errors.objectives}</p> : null}
          </section>
          <div className="mt-7"><ReferencePeriodsField values={value.reference_periods} onChange={(reference_periods) => update({ reference_periods })} error={errors.references} /></div>
          <div className="mt-7"><InlineNotice tone="info">Persisted-history policy is not available because the current public definition contract has no history field. A retained Metric Lens ID keeps its identity-scoped History continuity in future runs. To begin fresh History, explicitly remove this Lens from the Observation draft and add a new one. Reference periods are configured separately above.</InlineNotice></div>
        </div>
      </div>
    </section>
  )
}
