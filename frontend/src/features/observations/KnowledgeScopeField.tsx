import { Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button, Field, Input, InlineNotice } from '../../components/ui'
import { suggestKnowledgeScope } from './api'
import type { DraftErrors, ObservationDraft } from './draft'
import type { KnowledgeScope, KnowledgeServiceScope } from './types'

function revision(draft: ObservationDraft) { return JSON.stringify(draft) }
function suggestionPayload(draft: ObservationDraft) {
  return {
    name: draft.name,
    description: draft.description || null,
    objective: draft.objective,
    lenses: [...draft.lenses, ...draft.alert_lenses].map(({ name, description }) => ({ name, description })),
  }
}

/** Edits each service's optional retrieval version without changing other scope entries. */
export function KnowledgeScopeField({ draft, onChange, errors = {} }: {
  draft: ObservationDraft
  onChange: (scope: KnowledgeScope | null) => void
  errors?: DraftErrors
}) {
  const [serviceId, setServiceId] = useState('')
  const [suggestion, setSuggestion] = useState<string[] | null>(null)
  const [notice, setNotice] = useState('')
  const [pending, setPending] = useState(false)
  const active = useRef<AbortController | null>(null)
  const current = useRef(revision(draft))
  const revisionValue = revision(draft)
  useEffect(() => { current.current = revisionValue }, [revisionValue])
  useEffect(() => () => active.current?.abort(), [])

  const services = draft.knowledge_scope?.services ?? []
  const setServices = (next: KnowledgeServiceScope[]) => onChange(next.length ? { services: next } : null)
  const addService = () => {
    const next = serviceId.trim()
    if (!next || services.some((service) => service.service_id === next)) return
    setServices([...services, { service_id: next, service_version: null }])
    setServiceId('')
  }
  const updateVersion = (index: number, value: string) => setServices(
    services.map((service, position) => position === index
      ? { ...service, service_version: value === '' ? null : value }
      : service),
  )
  const removeService = (index: number) => setServices(
    services.filter((_, position) => position !== index),
  )
  const requestSuggestion = async () => {
    active.current?.abort()
    const controller = new AbortController()
    const requested = current.current
    active.current = controller
    setPending(true)
    setSuggestion(null)
    setNotice('')
    try {
      const result = await suggestKnowledgeScope(suggestionPayload(draft), controller.signal)
      if (controller.signal.aborted || current.current !== requested) return
      if (result.service_ids.length) setSuggestion(result.service_ids)
      else setNotice('No knowledge scope suggestion is available. You can continue with an explicit scope or none.')
    } catch {
      if (!controller.signal.aborted && current.current === requested) {
        setNotice('No knowledge scope suggestion is available. You can continue with an explicit scope or none.')
      }
    } finally {
      if (active.current === controller) {
        active.current = null
        setPending(false)
      }
    }
  }
  const accept = () => {
    if (!suggestion) return
    const selected = new Set(services.map((service) => service.service_id))
    const additions = suggestion.filter((id) => !selected.has(id))
      .map((service_id) => ({ service_id, service_version: null }))
    if (additions.length) setServices([...services, ...additions])
    setSuggestion(null)
  }

  return <section id="knowledge-scope" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="font-semibold">Knowledge scope</h2>
        <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Optional retrieval context for approved knowledge. It is not Observation evidence or an execution setting.</p>
      </div>
      <Button type="button" variant="secondary" disabled={pending} onClick={requestSuggestion}>
        <Sparkles size={17} aria-hidden="true" />{pending ? 'Suggesting…' : 'Suggest knowledge scope'}
      </Button>
    </div>
    <div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
      <Field label="Service ID"><Input value={serviceId} aria-describedby="knowledge-service-id-help" onChange={(event) => setServiceId(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addService() } }} placeholder="mprm-server" /></Field>
      <Button type="button" variant="secondary" className="w-full sm:w-auto" onClick={addService}>Add service</Button>
    </div>
    <p id="knowledge-service-id-help" className="mt-1.5 text-xs text-[var(--color-text-secondary)]">Add canonical service IDs explicitly. Each service can have its own optional version.</p>
    {services.length ? <ul aria-label="Selected knowledge services" className="mt-3 space-y-3">
      {services.map((service, index) => <li key={service.service_id} className="rounded-lg border border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] p-4">
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 break-words font-medium text-[var(--color-warning)]">{service.service_id}</p>
          <Button type="button" variant="ghost" aria-label={'Remove ' + service.service_id} onClick={() => removeService(index)}><X size={16} aria-hidden="true" />Remove</Button>
        </div>
        <div className="mt-3 max-w-sm">
          <Field label={'Version for ' + service.service_id + ' (optional)'} description="Leave blank to include all approved versions tagged for this service." error={errors['knowledge_scope.services.' + index + '.service_version']}>
            <Input value={service.service_version ?? ''} onChange={(event) => updateVersion(index, event.target.value)} placeholder="2.x" />
          </Field>
        </div>
      </li>)}
    </ul> : <p className="mt-3 text-sm text-[var(--color-text-secondary)]">No knowledge scope is set. Only globally applicable knowledge can be retrieved.</p>}
    {suggestion ? <div className="mt-4 rounded-lg border border-[var(--color-info-border)] bg-[var(--color-info-surface)] p-4">
      <p className="text-sm text-[var(--color-info)]">Suggested knowledge scope: {suggestion.join(', ')}</p>
      <div className="mt-3 flex gap-2"><Button type="button" onClick={accept}>Accept suggestion</Button><Button type="button" variant="secondary" onClick={() => setSuggestion(null)}>Dismiss</Button></div>
    </div> : null}
    {notice ? <div className="mt-4"><InlineNotice tone="info">{notice}</InlineNotice></div> : null}
  </section>
}
