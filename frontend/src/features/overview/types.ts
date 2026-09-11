import type { ExecutionStatus, ObservationRunSummary, RunObservation } from '../runs/types'

/** A complete strict run summary admitted to the resilient Overview feed. */
export interface AvailableOverviewRuntimeItem {
  readonly availability: 'available'
  readonly summary: ObservationRunSummary
}

/** The safe field-level fallback for one run that cannot form a strict summary. */
export interface LimitedOverviewRuntimeItem {
  readonly availability: 'limited'
  readonly id: string
  readonly observation: RunObservation
  readonly created_at: string
  readonly status: ExecutionStatus | null
  readonly started_at: string | null
  readonly finished_at: string | null
  readonly duration_seconds: number | null
  readonly analytical_state: null
  readonly limitation_code: 'runtime_projection_invalid'
  readonly href: string
}

/** One safely projected runtime record in the Overview-specific feed. */
export type OverviewRuntimeItem = AvailableOverviewRuntimeItem | LimitedOverviewRuntimeItem

/** The versioned, newest-first Overview runtime response envelope. */
export interface OverviewRuntimeFeed {
  readonly schema_version: '1.0'
  readonly items: readonly OverviewRuntimeItem[]
  readonly limited_run_count: number
}
