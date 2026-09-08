import { useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { Button, Field, FormSideRail, InlineNotice, Input, Textarea, ValidationSummary, type ValidationIssue } from '../../components/ui'
import { AnalysisObjectivesField, ReferencePeriodsField } from './configuration'
import { generateObservationChildId, newAlert, useObservationDraft, validateAlert, type DraftAlert, type DraftErrors } from './draft'

/** Edits an aggregate-owned, provider-native Alert Lens draft. */
export function AlertLensEditorPage() {
  const { key = 'new' } = useParams()
  const { draft } = useObservationDraft()
  if (!draft) return <Navigate to="/observations/new" replace state={{ draftLost: true }} />

  const existing = key === 'new' ? undefined : draft.alert_lenses.find((item) => item.clientKey === key)
  if (key !== 'new' && !existing) return <Navigate to="/observations/new" replace state={{ draftLost: true }} />

  return <AlertLensEditorForm key={key} routeKey={key} seed={existing ? structuredClone(existing) : newAlert(crypto.randomUUID())} />
}

function AlertLensEditorForm({ routeKey, seed }: { routeKey: string; seed: DraftAlert }) {
  const navigate = useNavigate()
  const { draft, upsertAlert } = useObservationDraft()
  const [value, setValue] = useState(seed)
  const [errors, setErrors] = useState<DraftErrors>({})
  const summaryRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (Object.keys(errors).length) summaryRef.current?.focus() }, [errors])

  if (!draft) return null

  const update = (patch: Partial<DraftAlert>) => setValue((current) => ({ ...current, ...patch }))
  const generateId = () => {
    if (!value.id && value.name.trim()) update({ id: generateObservationChildId(value.name, 'alert', draft.alert_lenses.map((item) => item.id), Date.now()) })
  }
  const issues: ValidationIssue[] = Object.entries(errors).map(([path, message]) => ({ message, to: path === 'objectives' ? '#analysis-objectives' : path === 'references' ? '#reference-periods' : `#alert-${path}` }))
  const apply = () => {
    const next = validateAlert(value, draft.alert_lenses)
    setErrors(next)
    if (Object.keys(next).length === 0) {
      upsertAlert(value, routeKey)
      navigate('/observations/new')
    }
  }

  return (
    <section className="mx-auto max-w-6xl">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <header className="mb-3">
          <p className="text-sm text-[var(--color-text-secondary)]">Observations / Create / Alert Lens</p>
          <h1 className="mt-1 text-[28px] font-semibold tracking-tight">Alert Lens Configuration</h1>
          <p className="mt-2 text-[var(--color-text-secondary)]">Configure a bounded provider-native alert perspective inside the Observation Definition.</p>
        </header>
        <FormSideRail
          className="lg:col-start-2 lg:row-span-2 lg:row-start-1"
          actions={<>
            <Button variant="secondary" onClick={() => navigate('/observations/new')}>Cancel</Button>
            <Button onClick={apply}>Apply changes</Button>
          </>}
        >
          <aside className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <h2 className="text-lg font-semibold">Alert Lens semantics</h2>
            <p className="mt-4 text-sm leading-6 text-[var(--color-text-secondary)]">Selector defines which alerts belong to the Lens. LensRun defines when they are observed. Lifecycle status remains analytical data.</p>
            <div className="mt-4"><InlineNotice tone="info">Saved into the Observation draft. No standalone Alert Lens resource is created.</InlineNotice></div>
          </aside>
        </FormSideRail>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          {issues.length ? <div className="mb-5"><ValidationSummary ref={summaryRef} issues={issues} title="Alert Lens changes cannot be applied" /></div> : null}
          <h2 className="text-lg font-semibold">Lens identity</h2>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Field label="Lens ID" description="Generated from the initial name and kept stable inside this Observation." error={errors.id}>
              <Input id="alert-id" placeholder="Generated after entering a name" value={value.id} readOnly />
            </Field>
            <Field label="Name" description="Human-readable Lens name shown throughout the interface." error={errors.name}>
              <Input id="alert-name" placeholder="Release alerts" value={value.name} onChange={(event) => update({ name: event.target.value })} onBlur={generateId} />
            </Field>
          </div>
          <div className="mt-4">
            <Field label="Description (optional)" description="Optional context explaining which alert behavior this Lens observes." error={errors.description}>
              <Textarea id="alert-description" placeholder="Tracks release-blocking alerts for the service." value={value.description ?? ''} onChange={(event) => update({ description: event.target.value === '' ? null : event.target.value })} />
            </Field>
          </div>
          <div className="mt-6">
            <Field label="Source" description="Configured alert provider used to retrieve this Lens's alerts.">
              <Input value="Jira Track and Release" disabled />
            </Field>
          </div>
          <div className="mt-6">
            <Field label="Provider selector" description="Enter the provider-native selector exactly as the provider expects. It defines which alerts belong to this Lens and is preserved without parsing, rewriting, or added runtime predicates." error={errors.query}>
              <Textarea id="alert-query" aria-label="Provider selector" placeholder="project = REL" value={value.selector.query} onChange={(event) => update({ selector: { query: event.target.value } })} />
            </Field>
          </div>
          <div className="mt-7"><AnalysisObjectivesField values={value.analysis_objectives} onChange={(analysis_objectives) => update({ analysis_objectives })} error={errors.objectives} /></div>
          <div className="mt-7"><ReferencePeriodsField values={value.reference_periods} onChange={(reference_periods) => update({ reference_periods })} error={errors.references} /></div>
        </div>
      </div>
    </section>
  )
}
