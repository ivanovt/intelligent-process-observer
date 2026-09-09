/** Lifecycle values admitted by the public ObservationRun summary contract. */
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
/** Observation-level analytical conclusions, deliberately separate from lifecycle. */
export type AnalyticalState = 'no_significant_findings' | 'uncertain' | 'significant_findings_present'
/** A concrete UTC interval accepted by the run API. */
export interface AnalysisWindow { from: string; to: string }
/** The immutable identity/display projection embedded in a run summary. */
export interface RunObservation { id: string; name: string }
/** A compact public lifecycle reason; it intentionally excludes diagnostics. */
export interface StructuredReason { code: string; component: string | null }
/** The compact, safe runtime projection shared by launch and list responses. */
export interface ObservationRunSummary {
  id: string
  observation: RunObservation
  analysis_window: AnalysisWindow
  status: ExecutionStatus
  reason: StructuredReason | null
  analytical_state: AnalyticalState | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  href: string
}
/** The only client-supplied inputs accepted when asking the server to launch a run. */
export interface ObservationRunLaunchRequest { observation_id: string; analysis_window: AnalysisWindow }
/** One lifecycle wrapper in a run-detail response. */
export interface ObservationRunLensRun {
  id: string
  lens_id: string
  lens_type: 'metric' | 'alert'
  status: ExecutionStatus | 'partial'
  reason: StructuredReason | null
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  result: MetricRunResult | AlertRunResult | null
}
/** Shared public identity carried by every versioned Lens analytical result. */
export interface LensResultIdentity { observation_id: string; observation_run_id: string; lens_id: string; lens_run_id: string }
/** The public Metric schema-1.0 result envelope; individual variants stay discriminated by lifecycle/data quality. */
export interface MetricCurrentEvidence { mean: number; std: number; min: number; max: number; slope: number }
/** The usable Metric variants retain their evidence and semantic state. */
export interface UsableMetricRunResult { schema_version: '1.0'; identity: LensResultIdentity; lens_type: 'metric'; status: { state: 'completed' | 'partial' }; data_quality: 'good' | 'degraded'; analysis_window: AnalysisWindow; current_state: { trend: { direction: string; rate: string }; variability: { state: string } }; reference_periods: readonly MetricReferenceComparison[] | null; evidence: { current: MetricCurrentEvidence; reference_periods: readonly MetricReferenceEvidence[] | null }; reason?: StructuredReason }
/** A completed Metric result may truthfully contain no usable current evidence. */
export interface InsufficientMetricRunResult { schema_version: '1.0'; identity: LensResultIdentity; lens_type: 'metric'; status: { state: 'completed' }; data_quality: 'insufficient'; analysis_window: AnalysisWindow }
/** A failed Metric artifact is deliberately traceability-only. */
export interface FailedMetricRunResult { schema_version: '1.0'; identity: LensResultIdentity; lens_type: 'metric'; status: { state: 'failed'; error: { code: string; message: string } }; analysis_window: AnalysisWindow }
export interface MetricReferenceComparison { offset: string; analysis_window: AnalysisWindow; level: { relation: string }; trend: { direction: string; rate: string; direction_relation: string; rate_relation: string }; variability: { state: string; relation: string } }
export interface MetricReferenceEvidence { offset: string; analysis_window: AnalysisWindow; mean: number; std: number; min: number; max: number; slope: number; relative_level_change: number }
export type MetricRunResult = UsableMetricRunResult | InsufficientMetricRunResult | FailedMetricRunResult
/** A safe provider-normalized Alert record, rendered solely as untrusted operational text. */
export interface CanonicalAlertRecord { id: string; title: string; description: string | null; started_at: string; ended_at: string | null; duration_seconds: number; status: { normalized: 'active' | 'resolved' | 'unknown'; source: string }; provider_importance: { type: string; value: string } | null; occurrence_count: number | null; source_ref: string | null }
/** The public Alert schema-1.0 result envelope; individual variants stay discriminated by lifecycle. */
export interface AlertRunResult { schema_version: '1.0'; identity: LensResultIdentity; lens_type: 'alert'; status: 'completed' | 'partial'; analysis_window: AnalysisWindow; alerts: readonly CanonicalAlertRecord[]; alert_activity: { record_count: number; occurrence_count: number }; status_distribution: { active: number; resolved: number; unknown: number }; duration_statistics: { min_seconds: number; max_seconds: number; average_seconds: number } | null; provider_importance_distribution: { type: string; values: Readonly<Record<string, number>> } | null; comparisons: readonly { offset: string; occurrence_comparison: { current: number; reference: number; delta: number; direction: string } }[]; findings: readonly { id: string; statement: string; evidence_refs: readonly string[] }[]; overall_importance: 'none' | 'low' | 'moderate' | 'high' | 'critical'; reason?: StructuredReason }
/** A persisted relationship evaluation, ordered by its server-owned frozen-definition position. */
interface RelationshipEvaluationBase { relationship_id: string; name: string; description: string | null; conditions: readonly RelationshipEvidence[]; expectations: readonly RelationshipEvidence[] }
/** An applicable relationship preserves its independent evaluation state. */
export interface ApplicableRelationshipEvaluation extends RelationshipEvaluationBase { applicability: 'applicable'; state: 'consistent' | 'inconsistent' | 'uncertain' }
/** A relationship whose configured conditions do not apply has no evaluation state. */
export interface NotApplicableRelationshipEvaluation extends RelationshipEvaluationBase { applicability: 'not_applicable' }
/** A relationship whose applicability cannot be determined has no invented state. */
export interface UnknownRelationshipEvaluation extends RelationshipEvaluationBase { applicability: 'unknown' }
/** Exact public relationship-evaluation variants. */
export type RelationshipEvaluation = ApplicableRelationshipEvaluation | NotApplicableRelationshipEvaluation | UnknownRelationshipEvaluation
/** One public relationship evidence item. */
export type RelationshipEvidence = DirectionEvidence | RateEvidence | VariabilityEvidence
/** Evidence for a configured trend direction. */
export interface DirectionEvidence { lens_id: string; property: 'trend.direction'; expected: 'increasing' | 'decreasing' | 'stable'; observed: 'increasing' | 'decreasing' | 'stable' | null; match: boolean | null }
/** Evidence for a configured trend rate. */
export interface RateEvidence { lens_id: string; property: 'trend.rate'; expected: 'slow' | 'moderate' | 'fast'; observed: 'slow' | 'moderate' | 'fast' | 'not_classified' | null; match: boolean | null }
/** Evidence for a configured variability state. */
export interface VariabilityEvidence { lens_id: string; property: 'variability.state'; expected: 'low' | 'moderate' | 'high'; observed: 'low' | 'moderate' | 'high' | null; match: boolean | null }
/** The persisted Observation-level analytical conclusion used by detail. */
export interface ObservationAnalysisResult { schema_version: '1.0'; identity: { observation_id: string; observation_run_id: string }; overall_state: AnalyticalState; findings: readonly ObservationFinding[]; hypotheses: readonly ObservationHypothesis[]; limitations: readonly ObservationLimitation[] }
/** A finding stays grounded in evidence references. */
export interface ObservationFinding { id: string; statement: string; evidence_refs: readonly EvidenceReference[] }
/** A hypothesis remains separate from a finding and references knowledge explicitly. */
export interface ObservationHypothesis { id: string; statement: string; supported_by: readonly string[]; knowledge_refs: readonly KnowledgeReference[] }
/** A small structured limitation attached to an Observation analysis. */
export type ObservationLimitation = MissingLensEvidence | InsufficientLensEvidence | PartialLensAnalysis
/** A stable reference to a declared artifact element. */
export interface EvidenceReference { source_type: 'metric_result' | 'alert_result' | 'relationship_evaluation'; source_id: string; locator: readonly (string | number)[] }
/** An opaque source-backed knowledge reference. */
export interface KnowledgeReference { source_id: string; reference: string }
/** A Lens without usable evidence. */
export interface MissingLensEvidence { code: 'missing_lens_evidence'; lens_id: string; lens_type: 'metric' | 'alert' }
/** A Lens whose available data was insufficient for usable evidence. */
export interface InsufficientLensEvidence { code: 'insufficient_lens_evidence'; lens_id: string; lens_type: 'metric' | 'alert' }
/** A usable Lens whose optional analysis was incomplete. */
export interface PartialLensAnalysis { code: 'partial_lens_analysis'; lens_id: string; lens_type: 'metric' | 'alert'; component: string | null }
/** A presentation-only stored Markdown artifact. */
export interface ObservationReport { observation_id: string; observation_run_id: string; generated_at: string; format: 'markdown'; content: string }
/** One coherent public run-detail aggregate. */
export interface ObservationRunDetail { summary: ObservationRunSummary; lens_runs: readonly ObservationRunLensRun[]; relationship_evaluations: readonly RelationshipEvaluation[]; analysis: ObservationAnalysisResult | null; report: ObservationReport | null }
/** Safe error envelope returned by the backend API. */
export interface ApiErrorEnvelope { code: string; message: string; field?: string }

/** Error preserving only the safe API error fields needed by the feature. */
export class RunApiError extends Error {
  /** HTTP status from the safe API response. */
  readonly status: number
  /** Safe machine-readable API error code. */
  readonly code: string
  /** Optional public field reference supplied by the API. */
  readonly field?: string
  /** Creates an error from a failed public run API response. */
  constructor(status: number, code: string, message: string, field?: string) { super(message); this.status = status; this.code = code; this.field = field }
}
