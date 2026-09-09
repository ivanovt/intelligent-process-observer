import type { AnalyticalState, ExecutionStatus } from '../../features/runs/types'

const executionPresentation: Record<ExecutionStatus, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-pending)]' },
  running: { label: 'Running', className: 'border-[var(--color-info-border)] bg-[var(--color-info-surface)] text-[var(--color-execution-running)]' },
  completed: { label: 'Completed', className: 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-execution-completed)]' },
  failed: { label: 'Failed', className: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-execution-failed)]' },
  cancelled: { label: 'Cancelled', className: 'border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-execution-cancelled)]' },
}

const analysisPresentation: Record<AnalyticalState, { label: string; className: string }> = {
  no_significant_findings: { label: 'No significant findings', className: 'border-[var(--color-success-border)] bg-[var(--color-success-surface)] text-[var(--color-analysis-no-findings)]' },
  uncertain: { label: 'Uncertain', className: 'border-[var(--color-warning-border)] bg-[var(--color-warning-surface)] text-[var(--color-analysis-uncertain)]' },
  significant_findings_present: { label: 'Significant findings present', className: 'border-[var(--color-error-border)] bg-[var(--color-error-surface)] text-[var(--color-analysis-significant)]' },
}

const badgeClassName = 'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold leading-4'

/** Shows an ObservationRun lifecycle value without implying any analytical result. */
export function ExecutionStatusBadge({ status }: { status: ExecutionStatus }) {
  const presentation = executionPresentation[status]
  return <span aria-label={`Execution status: ${presentation.label}`} className={`${badgeClassName} ${presentation.className}`}>{presentation.label}</span>
}

/** Shows an analytical conclusion independently from execution, including its absence. */
export function AnalyticalStateBadge({ state }: { state: AnalyticalState | null }) {
  if (state === null) return <span aria-label="Analytical state: unavailable" className={`${badgeClassName} border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)]`}>Analysis unavailable</span>
  const presentation = analysisPresentation[state]
  return <span aria-label={`Analytical state: ${presentation.label}`} className={`${badgeClassName} ${presentation.className}`}>{presentation.label}</span>
}
