export interface LensReference { id:string; name:string; type:'metric'; href:string }
export interface AlertLensReference { id:string; name:string; type:'alert'; href:string }
export interface RelationshipReference { id:string; name:string; href:string }
export interface ObservationSummary { id:string; name:string; description:string|null; objective:string; schema_version:number; lenses:LensReference[]; alert_lenses:AlertLensReference[]; relationships:RelationshipReference[]; href:string }
export interface MetricLens extends LensReference { description:string|null; metric_id:string; adapter_type:'prometheus'; source_id:string; query:string; unit:string; analysis_objectives:string[]; reference_periods:string[]; observation_href:string }
export interface AlertLens extends AlertLensReference { description:string|null; source:'jira_track_and_release'; selector:{query:string}; analysis_objectives:string[]; reference_periods:string[]; observation_href:string }
export interface Relationship extends RelationshipReference { description:string|null; participants:string[]; conditions:Record<string,unknown>; expected:Record<string,unknown>; observation_href:string }
export interface ObservationResponse extends Omit<ObservationSummary,'lenses'|'alert_lenses'|'relationships'> { lenses:MetricLens[]; alert_lenses:AlertLens[]; relationships:Relationship[] }
export interface ApiErrorEnvelope { code:string; message:string; field?:string }
export class ApiError extends Error { readonly status:number; readonly code:string; readonly field?:string; constructor(status:number,code:string,message:string,field?:string) { super(message); this.status=status; this.code=code; this.field=field } }
