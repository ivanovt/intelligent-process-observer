import { CircleAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { Button, Field, FormSideRail, InlineNotice, Input, Select, Textarea, ValidationSummary, type ValidationIssue } from '../../components/ui'
import { ReferencePeriodsField } from './configuration'
import { generateObservationChildId, newMetric, useObservationDraft, validateMetric, type DraftErrors, type DraftMetric } from './draft'
import type { MetricObjective } from './types'

const objectives:MetricObjective[]=['spike','drift','oscillation']

/** Edits one aggregate-owned Metric Lens using only current capability choices. */
export function MetricLensEditorPage(){const {key='new'}=useParams();const {draft}=useObservationDraft();if(!draft)return <Navigate to="/observations/new" replace state={{draftLost:true}}/>;const existing=key==='new'?undefined:draft.lenses.find(item=>item.clientKey===key);if(key!=='new'&&!existing)return <Navigate to="/observations/new" replace state={{draftLost:true}}/>;return <MetricLensEditorForm key={key} routeKey={key} seed={existing?structuredClone(existing):newMetric(crypto.randomUUID())}/>}
function MetricLensEditorForm({ routeKey, seed }: { routeKey: string; seed: DraftMetric }) {
  const navigate = useNavigate()
  const { draft, upsertMetric, capabilities, loadCapabilities, cancelCapabilities } = useObservationDraft()
  const [value, setValue] = useState(seed)
  const [errors, setErrors] = useState<DraftErrors>({})
  const summaryRef = useRef<HTMLDivElement>(null)

  useEffect(() => () => cancelCapabilities(), [cancelCapabilities])
  useEffect(() => {
    if (capabilities.status === 'idle') loadCapabilities()
  }, [capabilities.status, loadCapabilities])
  useEffect(() => { if (Object.keys(errors).length) summaryRef.current?.focus() }, [errors])

  if (!draft) return null

  const sources = capabilities.capabilities?.metric.flatMap((adapter) => adapter.sources.map((source) => ({ ...source, adapter_type: adapter.adapter_type }))) ?? []
  const update = (patch: Partial<DraftMetric>) => setValue((current) => ({ ...current, ...patch }))
  const generateId = () => {
    if (!value.id && value.name.trim()) update({ id: generateObservationChildId(value.name, 'metric', draft.lenses.map((item) => item.id), Date.now()) })
  }
  const setObjectives = (next: MetricObjective[]) => update({ analysis_objectives: next })
  const apply = () => {
    const next = validateMetric(value, draft.lenses)
    setErrors(next)
    if (!Object.keys(next).length && capabilities.status === 'success') {
      upsertMetric(value, routeKey)
      navigate('/observations/new')
    }
  }
  const unavailable = capabilities.status !== 'success'
  const issues: ValidationIssue[] = Object.entries(errors).map(([path, message]) => ({ message, to: path === 'objectives' ? '#metric-objectives' : path === 'references' ? '#reference-periods' : `#metric-${path}` }))

  return (
    <section className="mx-auto max-w-6xl">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <header className="mb-3">
          <p className="text-sm text-[var(--color-text-secondary)]">Observations / Create / Metric Lens</p>
          <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Metric Lens Configuration</h1>
          <p className="mt-2 text-[var(--color-text-secondary)]">Configure one metric perspective. Analysis scope remains one metric per Lens.</p>
        </header>
        <FormSideRail
          className="lg:col-start-2 lg:row-span-2 lg:row-start-1"
          actions={<>
            <Button variant="secondary" onClick={() => navigate('/observations/new')}>Cancel</Button>
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
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Field label="Lens ID" description="Generated from the initial name and kept stable; unique among Metric Lenses in this Observation." error={errors.id}>
              <Input id="metric-id" placeholder="Generated after entering a name" value={value.id} readOnly />
            </Field>
            <Field label="Name" description="Human-readable name shown in this Observation." error={errors.name}>
              <Input id="metric-name" placeholder="Cooling pressure" value={value.name} onChange={(event) => update({ name: event.target.value })} onBlur={generateId} />
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
                update({ source_id: event.target.value, adapter_type: choice?.adapter_type ?? 'prometheus' })
              }}>
                <option value="">Select configured source</option>
                {sources.map((source) => <option key={`${source.adapter_type}:${source.id}`} value={source.id}>{source.name}</option>)}
              </Select>
            </Field>
          </div>
          <div className="mt-4">
            <Field label="Provider query" description="Provider-native query for the selected metric source." error={errors.query}>
              <Textarea id="metric-query" aria-label="Provider query" placeholder="rate(process_pressure_total[5m])" value={value.query} onChange={(event) => update({ query: event.target.value })} />
            </Field>
          </div>
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
          <div className="mt-7"><InlineNotice tone="info">Persisted-history policy is not available because the current public definition contract has no history field. Reference periods are configured separately above.</InlineNotice></div>
        </div>
      </div>
    </section>
  )
}
