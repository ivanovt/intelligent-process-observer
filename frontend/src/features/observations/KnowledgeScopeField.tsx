import { Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button, Field, Input, InlineNotice } from '../../components/ui'
import { suggestKnowledgeScope } from './api'
import type { ObservationDraft } from './draft'
import type { KnowledgeScope } from './types'

function revision(draft: ObservationDraft) { return JSON.stringify(draft) }
function suggestionPayload(draft: ObservationDraft) { return { name: draft.name, description: draft.description || null, objective: draft.objective, lenses: [...draft.lenses, ...draft.alert_lenses].map(({ name, description }) => ({ name, description })) } }

/** Edits optional retrieval context and requests advice only after an explicit operator action. */
export function KnowledgeScopeField({ draft, onChange }: { draft: ObservationDraft; onChange: (scope: KnowledgeScope | null) => void }) {
  const [serviceId, setServiceId] = useState(''), [version, setVersion] = useState(draft.knowledge_scope?.service_version ?? ''), [suggestion, setSuggestion] = useState<string[] | null>(null), [notice, setNotice] = useState(''), [pending, setPending] = useState(false)
  const active = useRef<AbortController | null>(null), current = useRef(revision(draft)), revisionValue = revision(draft)
  useEffect(() => { current.current = revisionValue }, [revisionValue])
  useEffect(() => () => active.current?.abort(), [])
  const scope = draft.knowledge_scope
  const setScope = (service_ids: string[], service_version = version) => {
    if (!service_ids.length) {
      setVersion('')
      onChange(null)
      return
    }
    onChange({ service_ids, service_version: service_version.trim() || null })
  }
  const add = () => { const next = serviceId.trim(); if (!next || scope?.service_ids.includes(next)) return; setScope([...(scope?.service_ids ?? []), next]); setServiceId('') }
  const updateVersion = (next: string) => { setVersion(next); if (scope) setScope(scope.service_ids, next) }
  const requestSuggestion = async () => {
    active.current?.abort(); const controller = new AbortController(), requested = current.current; active.current = controller; setPending(true); setSuggestion(null); setNotice('')
    try { const result = await suggestKnowledgeScope(suggestionPayload(draft), controller.signal); if (controller.signal.aborted || current.current !== requested) return; if (!result.service_ids.length) setNotice('No knowledge scope suggestion is available. You can continue with an explicit scope or none.'); else setSuggestion(result.service_ids) }
    catch { if (!controller.signal.aborted && current.current === requested) setNotice('No knowledge scope suggestion is available. You can continue with an explicit scope or none.') }
    finally { if (active.current === controller) { active.current = null; setPending(false) } }
  }
  const accept = () => { if (!suggestion) return; setScope([...new Set([...(scope?.service_ids ?? []), ...suggestion])]); setSuggestion(null) }
  return <section id="knowledge-scope" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">Knowledge scope</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Optional retrieval context for approved knowledge. It is not Observation evidence or an execution setting.</p></div><Button type="button" variant="secondary" disabled={pending} onClick={requestSuggestion}><Sparkles size={17} aria-hidden="true" />{pending ? 'Suggesting…' : 'Suggest knowledge scope'}</Button></div><div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"><Field label="Service ID"><Input value={serviceId} aria-describedby="knowledge-service-id-help" onChange={event => setServiceId(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); add() } }} placeholder="mprm-server" /></Field><Button type="button" variant="secondary" className="w-full sm:w-auto" onClick={add}>Add service</Button></div><p id="knowledge-service-id-help" className="mt-1.5 text-xs text-[var(--color-text-secondary)]">Add canonical service IDs explicitly.</p>{scope?.service_ids.length ? <ul aria-label="Selected knowledge services" className="mt-3 flex flex-wrap gap-2">{scope.service_ids.map(id => <li key={id} className="flex items-center gap-1 rounded-full border border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] px-2.5 py-1 text-sm text-[var(--color-warning)]">{id}<button type="button" aria-label={`Remove ${id}`} onClick={() => setScope(scope.service_ids.filter(item => item !== id))}><X size={15} aria-hidden="true" /></button></li>)}</ul> : <p className="mt-3 text-sm text-[var(--color-text-secondary)]">No knowledge scope is set. Only globally applicable knowledge can be retrieved.</p>}<div className="mt-4 max-w-md"><Field label="Shared service version (optional)" description="One label applies to all selected services; leave it blank to include all versions."><Input value={version} onChange={event => updateVersion(event.target.value)} placeholder="2.x" disabled={!scope?.service_ids.length} /></Field></div>{suggestion ? <div className="mt-4 rounded-lg border border-[var(--color-info-border)] bg-[var(--color-info-surface)] p-4"><p className="text-sm text-[var(--color-info)]">Suggested knowledge scope: {suggestion.join(', ')}</p><div className="mt-3 flex gap-2"><Button type="button" onClick={accept}>Accept suggestion</Button><Button type="button" variant="secondary" onClick={() => setSuggestion(null)}>Dismiss</Button></div></div> : null}{notice ? <div className="mt-4"><InlineNotice tone="info">{notice}</InlineNotice></div> : null}</section>
}
