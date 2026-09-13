import type { ObservationResponse, SemanticDescriptor } from './types'
import type { DraftErrors, ObservationDraft } from './draft'
import type { ReactNode } from 'react'
import { Activity, BellRing, CheckCircle2, CircleAlert, GitFork, Hash, Target, TriangleAlert, type LucideIcon } from 'lucide-react'

type ReviewDefinition=Pick<ObservationDraft,'name'|'description'|'objective'|'lenses'|'alert_lenses'|'relationships'|'knowledge_scope'>

/** Renders a read-only, ordered configuration review without changing the draft. */
export function DefinitionReview({definition,mode='create',liveErrors={},explicitErrors={}}:{definition:ReviewDefinition;mode?:'create'|'edit';liveErrors?:DraftErrors;explicitErrors?:DraftErrors}) {
  const remaining=Object.values(liveErrors)
  const explicitCount=Object.keys(explicitErrors).length
  const appearsComplete=remaining.length===0
  const action=mode==='edit'?'save changes':'create',status=explicitCount?{icon:<CircleAlert size={16} aria-hidden="true"/>,text:`${explicitCount} submitted issue${explicitCount===1?'':'s'} remain`,tone:'text-[var(--color-error)]'}:appearsComplete?{icon:<CheckCircle2 size={16} aria-hidden="true"/>,text:`Ready to ${action}`,tone:'text-[var(--color-success)]'}:{icon:<TriangleAlert size={16} aria-hidden="true"/>,text:'Complete required details',tone:'text-[var(--color-warning)]'}
  return <section aria-labelledby="review-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
    <div className="flex flex-wrap items-baseline justify-between gap-2"><div><h2 id="review-heading">Review</h2><p className="mt-1 text-sm text-[var(--color-text-secondary)]">Verify the aggregate that will be submitted with {mode==='edit'?'Save changes':'Create Observation'}.</p></div><p className={`flex items-center gap-1 text-sm font-medium ${status.tone}`}>{status.icon}{status.text}</p></div>
    {explicitCount?<p className="mt-3 text-sm text-[var(--color-text-secondary)]">{appearsComplete?`Values appear complete. ${mode==='edit'?'Save again':'Create again'} to confirm them.`:`Correct the highlighted values, then ${mode==='edit'?'save':'create'} again to revalidate.`}</p>:remaining.length?<p className="mt-3 text-sm text-[var(--color-text-secondary)]">Complete the required details before {mode==='edit'?'saving changes':'creating this Observation'}.</p>:<p className="mt-3 text-sm text-[var(--color-text-secondary)]">All currently required definition fields are complete.</p>}
    <ReviewGeneral definition={definition}/>
    <section className="mt-5 border-t border-[var(--color-border)] pt-4"><h3 className="font-semibold">Knowledge scope</h3><p className="mt-2 text-sm text-[var(--color-text-secondary)]">Retrieval context only; it is not Lens evidence.</p>{definition.knowledge_scope ? <><DefinitionList label="Service IDs" values={definition.knowledge_scope.service_ids}/><DefinitionValue label="Service version" value={definition.knowledge_scope.service_version ?? 'None'}/></> : <p className="mt-2 text-sm text-[var(--color-text-secondary)]">No knowledge scope is set.</p>}</section>
    <ReviewGroup title="Metric lenses" empty="No Metric lenses configured.">{definition.lenses.map((lens,index)=><article key={lens.clientKey} className="definition-review-card"><p className="font-semibold">{index+1}. <strong>{lens.name||'Unnamed Metric Lens'}</strong> <span className="font-normal text-[var(--color-text-secondary)]">· Metric</span></p><DefinitionValue label="ID" value={lens.id||'Not set'}/><DefinitionValue label="Description" value={lens.description??'None'}/><DefinitionValue label="Type / adapter" value={`${lens.type} / ${lens.adapter_type}`}/><DefinitionValue label="Source ID" value={lens.source_id||'Not set'}/><DefinitionValue label="Metric ID" value={lens.metric_id||'Not set'}/><DefinitionValue label="Query" value={lens.query||'Not set'}/><DefinitionValue label="Unit" value={lens.unit||'Not set'}/><DefinitionList label="Analysis objectives" values={lens.analysis_objectives}/><DefinitionList label="Reference periods" values={lens.reference_periods}/></article>)}</ReviewGroup>
    <ReviewGroup title="Alert lenses" empty="No Alert lenses configured.">{definition.alert_lenses.map((lens,index)=><article key={lens.clientKey} className="definition-review-card"><p className="font-semibold">{index+1}. <strong>{lens.name||'Unnamed Alert Lens'}</strong> <span className="font-normal text-[var(--color-text-secondary)]">· Alert</span></p><DefinitionValue label="ID" value={lens.id||'Not set'}/><DefinitionValue label="Description" value={lens.description??'None'}/><DefinitionValue label="Type / source" value={`${lens.type} / ${lens.source}`}/><DefinitionValue label="Selector query" value={lens.selector.query||'Not set'} preserveWhitespace/><DefinitionList label="Analysis objectives" values={lens.analysis_objectives}/><DefinitionList label="Reference periods" values={lens.reference_periods}/></article>)}</ReviewGroup>
    <ReviewGroup title="Relationships" empty="No Relationships configured.">{definition.relationships.map((relationship,index)=><article key={relationship.clientKey} className="definition-review-card"><p className="font-semibold">{index+1}. <strong>{relationship.name||'Unnamed Relationship'}</strong> <span className="font-normal text-[var(--color-text-secondary)]">· Relationship</span></p><DefinitionValue label="ID" value={relationship.id||'Not set'}/><DefinitionValue label="Description" value={relationship.description??'None'}/><DefinitionList label="Participants" values={relationship.participants}/><DescriptorMap title="Conditions" values={relationship.conditions} empty="Always applicable."/><DescriptorMap title="Expected" values={relationship.expected} empty="No expectations configured."/></article>)}</ReviewGroup>
  </section>
}

/** Renders the complete read-only response projection used by inspection and review. */
export function DefinitionInspection({definition}:{definition:ObservationResponse}) {
  return <div className="space-y-8">
    <section aria-labelledby="definition-overview-heading" className="grid overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xs lg:grid-cols-[minmax(0,1fr)_21rem]">
      <div className="p-6 sm:p-7">
        <div className="flex items-center gap-2 text-[var(--color-primary)]"><Target size={18} aria-hidden="true"/><h2 id="definition-overview-heading" className="text-sm font-semibold uppercase tracking-wide">Observation objective</h2></div>
        <p className="mt-3 max-w-3xl text-lg font-medium leading-7">{definition.objective}</p>
        <dl className="mt-6 grid gap-4 border-t border-[var(--color-border)] pt-5 sm:grid-cols-[minmax(0,1fr)_9rem]">
          <OverviewValue icon={Hash} label="Definition ID" value={definition.id}/>
          <OverviewValue label="Schema version" value={String(definition.schema_version)}/>
          <OverviewValue label="Knowledge scope" value={definition.knowledge_scope?.service_ids.join(', ') || 'None'}/>
        </dl>
      </div>
      <aside aria-label="Definition composition" className="border-t border-[var(--color-border)] bg-[var(--color-surface-muted)] p-6 lg:border-l lg:border-t-0">
        <h2 className="text-sm font-semibold">Definition composition</h2>
        <dl className="mt-4 grid grid-cols-3 gap-3 lg:grid-cols-1">
          <CompositionCount icon={Activity} label="Metric lenses" count={definition.lenses.length}/>
          <CompositionCount icon={BellRing} label="Alert lenses" count={definition.alert_lenses.length}/>
          <CompositionCount icon={GitFork} label="Relationships" count={definition.relationships.length}/>
        </dl>
      </aside>
    </section>

    <InspectionSection icon={Activity} title="Metric lenses" count={definition.lenses.length} description="Metrics evaluated by this Observation." empty="No Metric lenses configured.">
      {definition.lenses.map((lens,index)=><article key={lens.id} className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xs">
        <InspectionCardHeader index={index} name={lens.name} kind="Metric" description={lens.description}/>
        <div className="grid gap-x-6 gap-y-5 p-5 sm:grid-cols-2">
          <CompactValue label="ID" value={lens.id}/><CompactValue label="Type / adapter" value={`${lens.type} / ${lens.adapter_type}`}/>
          <CompactValue label="Source ID" value={lens.source_id}/><CompactValue label="Metric ID" value={lens.metric_id}/>
          <CompactValue label="Unit" value={lens.unit}/><ChipList label="Reference periods" values={lens.reference_periods}/>
          <CodeValue label="Query" value={lens.query}/><ChipList label="Analysis objectives" values={lens.analysis_objectives}/>
        </div>
      </article>)}
    </InspectionSection>

    <InspectionSection icon={BellRing} title="Alert lenses" count={definition.alert_lenses.length} description="Provider-native alert selections evaluated by this Observation." empty="No Alert lenses configured.">
      {definition.alert_lenses.map((lens,index)=><article key={lens.id} className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xs">
        <InspectionCardHeader index={index} name={lens.name} kind="Alert" description={lens.description}/>
        <div className="grid gap-x-6 gap-y-5 p-5 sm:grid-cols-2">
          <CompactValue label="ID" value={lens.id}/><CompactValue label="Type / source" value={`${lens.type} / ${lens.source}`}/>
          <CodeValue label="Selector query" value={lens.selector.query}/><ChipList label="Reference periods" values={lens.reference_periods}/>
          <div className="sm:col-span-2"><ChipList label="Analysis objectives" values={lens.analysis_objectives}/></div>
        </div>
      </article>)}
    </InspectionSection>

    <InspectionSection icon={GitFork} title="Relationships" count={definition.relationships.length} description="Metric-only expectations evaluated across configured lenses." empty="No Relationships configured.">
      {definition.relationships.map((relationship,index)=><article key={relationship.id} className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xs">
        <InspectionCardHeader index={index} name={relationship.name} kind="Relationship" description={relationship.description}/>
        <div className="p-5"><div className="grid gap-5 sm:grid-cols-2"><CompactValue label="ID" value={relationship.id}/><ChipList label="Participants" values={relationship.participants}/></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><DescriptorMap title="Conditions" values={relationship.conditions} empty="Always applicable."/><DescriptorMap title="Expected" values={relationship.expected} empty="No expectations configured."/></div></div>
      </article>)}
    </InspectionSection>
  </div>
}

function OverviewValue({icon:Icon,label,value}:{icon?:LucideIcon;label:string;value:string}) { return <div className="min-w-0"><dt className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">{Icon?<Icon size={13} aria-hidden="true"/>:null}{label}</dt><dd className="mt-1 break-all font-mono text-sm text-[var(--color-text-primary)]">{value}</dd></div> }
function CompositionCount({icon:Icon,label,count}:{icon:LucideIcon;label:string;count:number}) { return <div className="flex min-w-0 items-center gap-3"><span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-surface)] text-[var(--color-primary)] shadow-xs"><Icon size={17} aria-hidden="true"/></span><div className="flex min-w-0 flex-col"><dt className="order-2 truncate text-xs text-[var(--color-text-secondary)]">{label}</dt><dd className="order-1 text-lg font-semibold tabular-nums">{count}</dd></div></div> }
function InspectionSection({children,count,description,empty,icon:Icon,title}:{children:ReactNode[];count:number;description:string;empty:string;icon:LucideIcon;title:string}) { return <section aria-labelledby={`inspection-${title.toLowerCase().replaceAll(' ','-')}`}><div className="mb-4 flex items-start gap-3"><span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-[color-mix(in_srgb,var(--color-primary),transparent_91%)] text-[var(--color-primary)]"><Icon size={18} aria-hidden="true"/></span><div><div className="flex items-center gap-2"><h2 id={`inspection-${title.toLowerCase().replaceAll(' ','-')}`} className="text-lg font-semibold">{title}</h2><span className="rounded-full bg-[var(--color-surface-muted)] px-2 py-0.5 text-xs font-semibold tabular-nums text-[var(--color-text-secondary)]">{count}</span></div><p className="mt-0.5 text-sm text-[var(--color-text-secondary)]">{description}</p></div></div>{children.length?<div className="grid gap-4 xl:grid-cols-2">{children}</div>:<div className="rounded-xl border border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface)] px-5 py-7 text-center text-sm text-[var(--color-text-secondary)]">{empty}</div>}</section> }
function InspectionCardHeader({description,index,kind,name}:{description:string|null;index:number;kind:string;name:string}) { return <header className="border-b border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-surface-muted),white_42%)] px-5 py-4"><div className="flex min-w-0 items-center gap-2"><span className="text-xs font-semibold tabular-nums text-[var(--color-text-secondary)]">{String(index+1).padStart(2,'0')}</span><h3 className="min-w-0 break-words font-semibold">{name}</h3><span className="ml-auto shrink-0 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-0.5 text-xs font-medium text-[var(--color-text-secondary)]">{kind}</span></div>{description?<p className="mt-2 whitespace-pre-wrap text-sm leading-5 text-[var(--color-text-secondary)]">{description}</p>:<p className="mt-2 text-sm italic text-[var(--color-text-secondary)]">No description provided.</p>}</header> }
function CompactValue({label,value}:{label:string;value:string}) { return <dl className="min-w-0"><dt className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">{label}</dt><dd className="mt-1 break-words text-sm">{value}</dd></dl> }
function CodeValue({label,value}:{label:string;value:string}) { return <dl className="min-w-0 sm:col-span-2"><dt className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">{label}</dt><dd className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3 py-2 font-mono text-sm">{value}</dd></dl> }
function ChipList({label,values}:{label:string;values:string[]}) { return <dl className="min-w-0"><dt className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">{label}</dt><dd className="mt-2 flex flex-wrap gap-1.5">{label==='Reference periods'&&values.length?<span className="sr-only">References: {values.join(', ')}</span>:null}{values.length?values.map((value,index)=><span key={`${value}-${index}`} className="max-w-full break-words rounded-md border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-2 py-1 text-xs">{value}</span>):<span className="text-sm text-[var(--color-text-secondary)]">None</span>}</dd></dl> }

function ReviewGeneral({definition}:{definition:ReviewDefinition}) { return <section className="mt-5 border-t border-[var(--color-border)] pt-4"><h3 className="font-semibold">General</h3><DefinitionValue label="Name" value={definition.name||'Not set'}/><DefinitionValue label="Description" value={definition.description||'None'}/><DefinitionValue label="Objective" value={definition.objective||'Not set'}/></section> }
function ReviewGroup({title,empty,children}:{title:string;empty:string;children:ReactNode[]}) { return <section className="mt-5 border-t border-[var(--color-border)] pt-4"><p className="font-semibold">{title}</p>{children.length?<div className="mt-3 space-y-3">{children}</div>:<p className="mt-2 text-sm text-[var(--color-text-secondary)]">{empty}</p>}</section> }
function DefinitionValue({label,value,preserveWhitespace=false}:{label:string;value:string;preserveWhitespace?:boolean}) { return <p className="mt-2 text-sm"><span className="font-medium">{label}:</span> <span className={preserveWhitespace?'whitespace-pre-wrap':''}>{value}</span></p> }
function DefinitionList({label,values}:{label:string;values:string[]}) { return <div className="mt-2 text-sm"><span className="font-medium">{label}:</span>{values.length?<><span className="sr-only"> {values.join(', ')}</span>{label==='Reference periods'?<p>References: {values.join(', ')}</p>:null}<ol className="ml-5 list-decimal">{values.map((value,index)=><li key={`${value}-${index}`} className="whitespace-pre-wrap">{value}</li>)}</ol></>:<span> None</span>}</div> }
function DescriptorMap({title,values,empty}:{title:string;values:Record<string,SemanticDescriptor>;empty:string}) { const entries=Object.entries(values).sort(([left],[right])=>left.localeCompare(right));return <section className="text-sm"><h4 className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-secondary)]">{title}</h4>{entries.length?<dl className="mt-2 space-y-2">{entries.map(([lens,descriptor])=><div key={lens} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3"><dt className="font-medium">{lens}</dt><dd className="mt-1 text-[var(--color-text-secondary)]">{descriptorText(descriptor)}</dd></div>)}</dl>:<p className="mt-2 text-[var(--color-text-secondary)]">{empty}</p>}</section> }
function descriptorText(descriptor:SemanticDescriptor) { return [descriptor.trend?.direction?`trend.direction: ${descriptor.trend.direction}`:null,descriptor.trend?.rate?`trend.rate: ${descriptor.trend.rate}`:null,descriptor.variability?.state?`variability.state: ${descriptor.variability.state}`:null].filter(Boolean).join(' · ') }
