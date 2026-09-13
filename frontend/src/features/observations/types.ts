export interface LensReference { id:string; name:string; type:'metric'; href:string }
export interface AlertLensReference { id:string; name:string; type:'alert'; href:string }
export interface RelationshipReference { id:string; name:string; href:string }
export interface ObservationSummary { id:string; name:string; description:string|null; objective:string; schema_version:number; lenses:LensReference[]; alert_lenses:AlertLensReference[]; relationships:RelationshipReference[]; href:string }
export interface MetricLens extends LensReference { description:string|null; metric_id:string; adapter_type:'prometheus'; source_id:string; query:string; unit:string; analysis_objectives:string[]; reference_periods:string[]; observation_href:string }
export interface AlertLens extends AlertLensReference { description:string|null; source:'jira_track_and_release'; selector:{query:string}; analysis_objectives:string[]; reference_periods:string[]; observation_href:string }
export interface Relationship extends RelationshipReference { description:string|null; participants:string[]; conditions:Record<string,SemanticDescriptor>; expected:Record<string,SemanticDescriptor>; observation_href:string }
export interface ObservationResponse extends Omit<ObservationSummary,'lenses'|'alert_lenses'|'relationships'> { lenses:MetricLens[]; alert_lenses:AlertLens[]; relationships:Relationship[]; knowledge_scope?:KnowledgeScope|null }
/** One service's independently optional knowledge-applicability version. */
export interface KnowledgeServiceScope { service_id:string; service_version:string|null }
/** Optional retrieval-only service scope attached to an Observation aggregate. */
export interface KnowledgeScope { services:KnowledgeServiceScope[] }
/** Public aggregate-create shape, deliberately separate from client draft state. */
export interface AlertLensCreate { id:string; name:string; description:string|null; type:'alert'; source:'jira_track_and_release'; selector:{query:string}; analysis_objectives:string[]; reference_periods:string[] }
/** Public Metric Lens create shape. */
export interface MetricLensCreate { id:string; name:string; description:string|null; type:'metric'; metric_id:string; adapter_type:'prometheus'; source_id:string; query:string; unit:string; analysis_objectives:MetricObjective[]; reference_periods:string[] }
export type MetricObjective='spike'|'drift'|'oscillation'
/** A supported qualitative current-state descriptor for one Metric Lens. */
export interface SemanticDescriptor { trend?:{direction?:'increasing'|'decreasing'|'stable';rate?:'slow'|'moderate'|'fast'}; variability?:{state:'low'|'moderate'|'high'} }
/** Public aggregate-owned Relationship create shape. */
export interface RelationshipCreate { id:string; name:string; description:string|null; participants:string[]; conditions:Record<string,SemanticDescriptor>; expected:Record<string,SemanticDescriptor> }
/** The non-secret credential metadata that may be displayed for a Prometheus source. */
export type PrometheusCredentialProjection =
  | { type: 'bearer_token' }
  | { type: 'basic_auth'; username: string }
/** The complete safe configuration projection for one Prometheus source. */
export interface PrometheusSourceConfiguration { id:string; name:string; base_url?:string; credentials:PrometheusCredentialProjection }
/** One Prometheus source made available for Metric Lens configuration. */
export interface PrometheusSourceCapability { id:string; name:string; configuration:PrometheusSourceConfiguration }
/** A supported Metric adapter and its ordered source capabilities. */
export interface PrometheusMetricCapability { adapter_type:'prometheus'; sources:PrometheusSourceCapability[] }
/** Available acquisition sources supplied by the definition API. */
export interface DefinitionCapabilities { metric:PrometheusMetricCapability[] }
/** Public Observation creation request. */
export interface ObservationCreate { name:string; description:string|null; objective:string; lenses:MetricLensCreate[]; alert_lenses:AlertLensCreate[]; relationships:RelationshipCreate[]; knowledge_scope?:KnowledgeScope|null }
/** Transient text projection permitted for an explicit scope suggestion. */
export interface KnowledgeScopeSuggestionRequest { name:string; description:string|null; objective:string; lenses:{name:string;description:string|null}[] }
/** Catalog-backed advisory scope returned without persistence. */
export interface KnowledgeScopeSuggestionResponse { service_ids:string[] }
export interface ApiErrorEnvelope { code:string; message:string; field?:string }
export class ApiError extends Error { readonly status:number; readonly code:string; readonly field?:string; constructor(status:number,code:string,message:string,field?:string) { super(message); this.status=status; this.code=code; this.field=field } }
/** The fixed, non-persisting candidate sent to the Metric query preflight endpoint. */
export interface MetricPreflightRequest { source_id:string; query:string; validation_window:{duration:'15m'} }
/** One typed sample returned when a Metric query resolves to one series. */
export interface MetricPreflightSample { timestamp:string; value:number|null; value_status:'finite'|'nan'|'positive_infinity'|'negative_infinity' }
/** A successful Metric preflight result for exactly one time series. */
export interface MetricPreflightSuccess { valid:true; resolved_start:string; resolved_end:string; step_seconds:number; labels:Record<string,string>; samples:MetricPreflightSample[]; warnings:string[] }
/** A non-persisting Metric preflight result that did not resolve to one series. */
export interface MetricPreflightFailure { valid:false; code:string; message:string; series_count:number|null; label_sets:Record<string,string>[]; warnings:string[] }
/** The discriminated response contract of the Metric query preflight endpoint. */
export type MetricPreflightResponse=MetricPreflightSuccess|MetricPreflightFailure
