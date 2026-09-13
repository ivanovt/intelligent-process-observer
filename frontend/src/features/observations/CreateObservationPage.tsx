import { Activity, ArrowDown, ArrowUp, BellRing, CheckCircle2, CircleAlert, GitFork, Pencil, Plus, SlidersHorizontal, Trash2, TriangleAlert } from 'lucide-react'
import { Children, useEffect, useRef, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ActionLink, Button, Field, FormSideRail, InlineNotice, Input, PageHeader, Textarea, ValidationSummary, type ValidationIssue } from '../../components/ui'
import { createObservation, updateObservation } from './api'
import { serializeDraft, useObservationDraft, validateDraft, type DraftErrors, type ObservationDraft } from './draft'
import { DefinitionReview } from './DefinitionReview'
import { KnowledgeScopeField } from './KnowledgeScopeField'
import { ApiError } from './types'

const configurationSections = [['general', 'General'], ['knowledge-scope', 'Knowledge scope'], ['metric-lenses', 'Metric lenses'], ['alert-lenses', 'Alert lenses'], ['relationships', 'Relationships'], ['review', 'Review']] as const
type ConfigurationSectionId = (typeof configurationSections)[number][0]
type NormalizedIssue = ValidationIssue & { path: string; section: ConfigurationSectionId }
const sectionActivationOffset = 160

function sectionForPath(path: string): ConfigurationSectionId {
  if (['name', 'description', 'objective'].includes(path)) return 'general'
  if (path.startsWith('knowledge_scope')) return 'knowledge-scope'
  if (path.startsWith('lenses.')) return 'metric-lenses'
  if (path.startsWith('alert_lenses.')) return 'alert-lenses'
  if (path.startsWith('relationships.')) return 'relationships'
  return 'review'
}

function normalizeIssues(errors: DraftErrors, draft: ObservationDraft): NormalizedIssue[] {
  return Object.entries(errors).map(([path, message]) => {
    const section = sectionForPath(path)
    if (['name', 'description', 'objective'].includes(path)) return { path, message, section, to: `#general-${path}`, linkLabel: `Correct ${path}` }
    const match = /^(lenses|alert_lenses|relationships)\.(\d+)(?:\.|$)/.exec(path)
    if (!match) return { path, message, section, to: `#${section}`, linkLabel: `Go to ${section === 'review' ? 'Review' : section}` }
    const index = Number(match[2])
    const item = match[1] === 'lenses' ? draft.lenses[index] : match[1] === 'alert_lenses' ? draft.alert_lenses[index] : draft.relationships[index]
    if (!item) return { path, message, section, to: `#${section}`, linkLabel: `Go to ${section}` }
    const kind = match[1] === 'lenses' ? 'Metric Lens' : match[1] === 'alert_lenses' ? 'Alert Lens' : 'Relationship'
    return { path, message: `${kind} “${item.name || item.id || 'unnamed'}”: ${message}`, section, to: `${section}/${item.clientKey}`, linkLabel: `Correct ${kind}` }
  })
}

/** Renders the aggregate-owned Observation creation and validation flow. */
export function CreateObservationPage() {
  const { draft, mode, targetId, explicitErrors: errors, fresh, clear, setExplicitErrors, updateGeneral, updateKnowledgeScope, removeChild, moveChild } = useObservationDraft()
  const navigate = useNavigate()
  const location = useLocation()
  const [failure, setFailure] = useState('')
  const [pending, setPending] = useState(false)
  const [activeSection, setActiveSection] = useState<ConfigurationSectionId>('general')
  const animationFrame = useRef<number | null>(null)
  const summaryRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (!draft && mode === 'create') fresh() }, [draft, fresh, mode])
  useEffect(() => {
    if (!draft) return
    const setCurrentSection = (next: ConfigurationSectionId) => setActiveSection((current) => current === next ? current : next)
    const updateActiveSection = () => {
      animationFrame.current = null
      if (window.scrollY <= 0) return setCurrentSection('general')
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 1) return setCurrentSection('review')
      setCurrentSection(configurationSections.reduce<ConfigurationSectionId>((last, [id]) => {
        const section = document.getElementById(id)
        return section && section.getBoundingClientRect().top <= sectionActivationOffset ? id : last
      }, 'general'))
    }
    const scheduleUpdate = () => { if (animationFrame.current === null) animationFrame.current = window.requestAnimationFrame(updateActiveSection) }
    scheduleUpdate()
    window.addEventListener('scroll', scheduleUpdate, { passive: true })
    window.addEventListener('resize', scheduleUpdate)
    return () => { window.removeEventListener('scroll', scheduleUpdate); window.removeEventListener('resize', scheduleUpdate); if (animationFrame.current !== null) window.cancelAnimationFrame(animationFrame.current) }
  }, [draft])
  useEffect(() => { if (Object.keys(errors).length) summaryRef.current?.focus() }, [errors])
  if (!draft) return null

  const submit = async () => {
    if (pending) return
    const next = validateDraft(draft)
    setExplicitErrors(next)
    setFailure('')
    if (Object.keys(next).length) return
    setPending(true)
    try {
      const created = mode === 'edit' && targetId ? await updateObservation(targetId, serializeDraft(draft)) : await createObservation(serializeDraft(draft))
      clear()
      navigate(`/observations/${created.id}`, { replace: true, state: { [mode === 'edit' ? 'updated' : 'created']: true } })
    } catch (error) {
      const api = error instanceof ApiError ? error : null
      if (api?.field) setExplicitErrors({ [api.field]: api.message })
      else setFailure(api?.status === 404 && mode === 'edit' ? 'This Observation definition is no longer available. Your draft is retained.' : api?.message ?? `Unable to ${mode === 'edit' ? 'update' : 'create'} the Observation definition.`)
    } finally { setPending(false) }
  }

  const issues = normalizeIssues(errors, draft)
  const issueCounts = issues.reduce<Partial<Record<ConfigurationSectionId, number>>>((counts, issue) => ({ ...counts, [issue.section]: (counts[issue.section] ?? 0) + 1 }), {})
  const liveErrors = validateDraft(draft)
  const hasLens = draft.lenses.length + draft.alert_lenses.length > 0
  return <section className="mx-auto max-w-6xl"><div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
    <PageHeader className="mb-3" eyebrow={`Observations / ${mode === 'edit' ? 'Edit' : 'Create'}`} title={mode === 'edit' ? 'Edit Observation' : 'Create Observation'} description="Configure one validated Observation Definition." />
    <FormSideRail className="lg:col-start-2 lg:row-span-2 lg:row-start-1" actions={<><Button variant="secondary" disabled={pending} onClick={() => { clear(); navigate(mode === 'edit' && targetId ? `/observations/${targetId}` : '/observations') }}>Cancel</Button><Button onClick={submit} disabled={pending}><CheckCircle2 size={17} aria-hidden="true" />{pending ? (mode === 'edit' ? 'Saving…' : 'Creating…') : (mode === 'edit' ? 'Save changes' : 'Create Observation')}</Button></>}>
      <DefinitionSummary mode={mode} metricCount={draft.lenses.length} alertCount={draft.alert_lenses.length} relationshipCount={draft.relationships.length} explicitIssueCount={issues.length} hasLens={hasLens} isReady={!Object.keys(liveErrors).length} />
    </FormSideRail>
    <div className="min-w-0">
      {location.state?.draftLost ? <InlineNotice tone="info">Your previous draft is unavailable. Your unapplied local changes were unavailable, so the persisted definition was reloaded.</InlineNotice> : null}
      {failure ? <div className="mb-5"><InlineNotice tone="error">{failure}</InlineNotice></div> : null}
      {issues.length ? <div className="mb-5"><ValidationSummary ref={summaryRef} issues={issues} title={`Observation cannot be ${mode === 'edit' ? 'saved' : 'created'}`} /></div> : null}
      <div className="grid min-w-0 gap-5 lg:grid-cols-[180px_minmax(0,1fr)]"><ConfigurationNav activeSection={activeSection} onActivate={setActiveSection} issueCounts={issueCounts} /><div className="space-y-5">
        <section id="general" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6"><SectionHeading icon={<SlidersHorizontal size={18} aria-hidden="true" />} title="General" description="Name the Observation and state the outcome it should observe." /><div className="mt-5 space-y-4">
          <Field label="Name" description="Human-readable name for this Observation Definition." error={errors.name}><Input id="general-name" placeholder="Cooling system health" value={draft.name} onChange={(event) => updateGeneral({ ...draft, name: event.target.value })} /></Field>
          <Field label="Description (optional)" description="Optional context that explains this Observation." error={errors.description}><Textarea id="general-description" placeholder="Monitors cooling-system operating conditions." value={draft.description} onChange={(event) => updateGeneral({ ...draft, description: event.target.value })} /></Field>
          <Field label="Objective" description="Outcome this Observation should evaluate." error={errors.objective}><Textarea id="general-objective" placeholder="Detect unexpected cooling pressure changes." value={draft.objective} onChange={(event) => updateGeneral({ ...draft, objective: event.target.value })} /></Field>
        </div></section>
        <KnowledgeScopeField draft={draft} onChange={updateKnowledgeScope} errors={errors} />
        <ConfigurationSection id="metric-lenses" icon={<Activity size={18} aria-hidden="true" />} title="Metric lenses" description="Configure the individual metrics this Observation evaluates." addTo="metric-lenses/new" addLabel="Add Metric Lens">{draft.lenses.map((metric, index) => <DraftRow key={metric.clientKey} name={metric.name || 'Unnamed Metric Lens'} to={`metric-lenses/${metric.clientKey}`} errors={childErrors(errors, 'lenses', index)} onRemove={() => removeChild('metric', metric.clientKey)} onMove={(direction) => moveChild('metric', metric.clientKey, direction)} canMoveUp={index > 0} canMoveDown={index < draft.lenses.length - 1} />)}</ConfigurationSection>
        <ConfigurationSection id="alert-lenses" icon={<BellRing size={18} aria-hidden="true" />} title="Alert lenses" description="Configure provider-native alert selectors for this Observation." addTo="alert-lenses/new" addLabel="Add Alert Lens">{draft.alert_lenses.map((alert, index) => <DraftRow key={alert.clientKey} name={alert.name || 'Unnamed Alert Lens'} to={`alert-lenses/${alert.clientKey}`} errors={childErrors(errors, 'alert_lenses', index)} onRemove={() => removeChild('alert', alert.clientKey)} onMove={(direction) => moveChild('alert', alert.clientKey, direction)} canMoveUp={index > 0} canMoveDown={index < draft.alert_lenses.length - 1} />)}</ConfigurationSection>
        <ConfigurationSection id="relationships" icon={<GitFork size={18} aria-hidden="true" />} title="Relationships" description="Engineer-defined current-state rules over Metric Lenses only." addTo="relationships/new" addLabel="Add Relationship">{draft.relationships.map((relationship, index) => <DraftRow key={relationship.clientKey} name={relationship.name || 'Unnamed Relationship'} to={`relationships/${relationship.clientKey}`} errors={childErrors(errors, 'relationships', index)} onRemove={() => removeChild('relationship', relationship.clientKey)} onMove={(direction) => moveChild('relationship', relationship.clientKey, direction)} canMoveUp={index > 0} canMoveDown={index < draft.relationships.length - 1} />)}</ConfigurationSection>
        <div id="review"><DefinitionReview definition={draft} mode={mode} liveErrors={liveErrors} explicitErrors={errors} /></div>
      </div></div>
    </div>
  </div></section>
}

function ConfigurationNav({ activeSection, onActivate, issueCounts }: { activeSection: ConfigurationSectionId; onActivate: (section: ConfigurationSectionId) => void; issueCounts: Partial<Record<ConfigurationSectionId, number>> }) { return <nav aria-label="Configuration sections" className="hidden h-fit self-start rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 lg:sticky lg:top-6 lg:block"><p className="px-3 pb-2 text-sm font-semibold">Configuration</p><div className="grid gap-1">{configurationSections.map(([target, label]) => { const isActive = activeSection === target; const count = issueCounts[target]; return <a key={target} href={`#${target}`} aria-current={isActive ? 'location' : undefined} onClick={() => onActivate(target)} className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] ${isActive ? 'bg-[color-mix(in_srgb,var(--color-primary)_12%,transparent)] font-semibold text-[var(--color-primary)]' : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-text-primary)]'}`}><span>{label}</span>{count ? <span aria-label={`${count} issue${count === 1 ? '' : 's'}`} className="rounded-full bg-[var(--color-error-surface)] px-1.5 py-0.5 text-xs font-semibold text-[var(--color-error)]">{count}</span> : null}</a> })}</div></nav> }
function childErrors(errors: DraftErrors, collection: 'lenses' | 'alert_lenses' | 'relationships', index: number) { const root=`${collection}.${index}`; return Object.entries(errors).filter(([path]) => path === root || path.startsWith(`${root}.`)).map(([, message]) => message) }
function SectionHeading({ icon, title, description }: { icon: ReactNode; title: string; description?: string }) { return <><h2 className="flex items-center gap-2 font-semibold text-[var(--color-text-primary)]"><span className="text-[var(--color-primary)]">{icon}</span>{title}</h2>{description ? <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{description}</p> : null}</> }
function ConfigurationSection({ id, icon, title, description, addTo, addLabel, children }: { id: string; icon: ReactNode; title: string; description: string; addTo: string; addLabel: string; children: ReactNode }) { return <section id={id} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6"><SectionHeading icon={icon} title={title} description={description} /><ActionLink to={addTo} variant="secondary" className="mt-5 w-fit"><Plus size={17} aria-hidden="true" />{addLabel}</ActionLink>{Children.count(children) > 0 ? <div className="mt-4 space-y-2">{children}</div> : null}</section> }
function DraftRow({ canMoveDown, canMoveUp, errors, name, onMove, onRemove, to }: { canMoveDown:boolean;canMoveUp:boolean;errors: string[]; name: string; onMove:(direction:-1|1)=>void;onRemove:()=>void;to: string }) { const errorId=`${to.replace(/[^a-z0-9]/gi,'-')}-error`,styles=`flex min-h-12 items-center justify-between gap-3 rounded-lg border py-1 pl-3 pr-1 text-sm ${errors.length?'border-[var(--color-error-border)] bg-[var(--color-error-surface)]':'border-[var(--color-border)] bg-[var(--color-surface-muted)]'}`; return <><p className={styles}><span className="min-w-0 truncate font-medium text-[var(--color-text-primary)]" title={name}>{name}</span><ActionLink aria-describedby={errors.length?errorId:undefined} to={to} variant="ghost" className="px-3" aria-label={`Edit ${name}`}><Pencil size={16} aria-hidden="true" />Edit</ActionLink></p>{errors.length?<p id={errorId} className="-mt-1 mb-2 flex items-center gap-1 text-xs text-[var(--color-error)]"><CircleAlert size={14} aria-hidden="true"/>{errors.join(' ')}</p>:null}<div className="mt-1 flex justify-end gap-1"><Button type="button" variant="ghost" className="size-9 min-h-9 px-0" aria-label={`Move ${name} up`} disabled={!canMoveUp} onClick={()=>onMove(-1)}><ArrowUp size={15} aria-hidden="true"/></Button><Button type="button" variant="ghost" className="size-9 min-h-9 px-0" aria-label={`Move ${name} down`} disabled={!canMoveDown} onClick={()=>onMove(1)}><ArrowDown size={15} aria-hidden="true"/></Button><Button type="button" variant="ghost" className="size-9 min-h-9 px-0" aria-label={`Remove ${name}`} onClick={onRemove}><Trash2 size={15} aria-hidden="true"/></Button></div></> }
function DefinitionSummary({ mode, metricCount, alertCount, relationshipCount, explicitIssueCount, hasLens, isReady }: { mode:'create'|'edit';metricCount: number; alertCount: number; relationshipCount: number; explicitIssueCount: number; hasLens: boolean; isReady: boolean }) { const action=mode==='edit'?'save':'create',status = explicitIssueCount ? { icon: <CircleAlert size={17} aria-hidden="true" />, message: `${explicitIssueCount} issue${explicitIssueCount === 1 ? '' : 's'} need attention.`, tone: 'text-[var(--color-error)]' } : !hasLens ? { icon: <TriangleAlert size={17} aria-hidden="true" />, message: 'Add at least one Lens to continue.', tone: 'text-[var(--color-warning)]' } : isReady ? { icon: <CheckCircle2 size={17} aria-hidden="true" />, message: `Ready to ${action}.`, tone: 'text-[var(--color-success)]' } : { icon: <TriangleAlert size={17} aria-hidden="true" />, message: 'Complete required details.', tone: 'text-[var(--color-warning)]' }; const rows = [{ icon: <Activity size={17} aria-hidden="true" />, label: 'Metric lenses', count: metricCount }, { icon: <BellRing size={17} aria-hidden="true" />, label: 'Alert lenses', count: alertCount }, { icon: <GitFork size={17} aria-hidden="true" />, label: 'Relationships', count: relationshipCount }]; return <aside aria-label="Definition Summary" className="h-fit rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6"><h2 className="font-semibold">Definition Summary</h2><dl className="mt-4 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">{rows.map((row) => <div key={row.label} className="flex items-center justify-between gap-3 py-3"><dt className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">{row.icon}{row.label}<span className="sr-only">{`${row.label}: ${row.count}`}</span></dt><dd className="font-semibold tabular-nums">{row.count}</dd></div>)}</dl><div role="status" className={`mt-4 flex items-start gap-2 text-sm font-medium ${status.tone}`}>{status.icon}<p>{status.message}</p></div></aside> }
