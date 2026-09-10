import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Link } from 'react-router-dom'
import type { ExecutionStatus } from '../../features/runs/types'
import type { RunActivityItem } from '../../features/overview/projections'

const executionStatuses: readonly ExecutionStatus[] = ['pending', 'running', 'completed', 'failed', 'cancelled']

const statusPresentation: Record<ExecutionStatus, { label: string; color: string }> = {
  pending: { label: 'Pending', color: 'var(--color-execution-pending)' },
  running: { label: 'Running', color: 'var(--color-execution-running)' },
  completed: { label: 'Completed', color: 'var(--color-execution-completed)' },
  failed: { label: 'Failed', color: 'var(--color-execution-failed)' },
  cancelled: { label: 'Cancelled', color: 'var(--color-execution-cancelled)' },
}

/** Renders bounded chronological ObservationRun execution history without analytical-state inference. */
export function RunActivityChart({ activity }: { activity: readonly RunActivityItem[] }) {
  const displayedActivity = [...activity].sort((left, right) => Date.parse(left.createdAt) - Date.parse(right.createdAt)).slice(-14)
  const counts = countStatuses(displayedActivity)
  const chartData = displayedActivity.map((item) => ({
    label: formatActivityTime(item.createdAt),
    pending: item.status === 'pending' ? 1 : 0,
    running: item.status === 'running' ? 1 : 0,
    completed: item.status === 'completed' ? 1 : 0,
    failed: item.status === 'failed' ? 1 : 0,
    cancelled: item.status === 'cancelled' ? 1 : 0,
  }))

  return (
    <section aria-labelledby="run-activity-heading" className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xs">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="run-activity-heading" className="text-xl font-semibold">Run Activity</h2>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">The fourteen newest Observation runs, displayed in chronological order.</p>
        </div>
        <Link className="text-sm font-semibold text-[var(--color-primary)] underline underline-offset-2" to="/runs">View all Runs</Link>
      </div>

      {displayedActivity.length === 0 ? <p className="mt-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">No Observation runs exist yet.</p> : <>
        <ul aria-label="Execution status legend" className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm">
          {executionStatuses.map((status) => <li key={status} className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: statusPresentation[status].color }} />{statusPresentation[status].label}</li>)}
        </ul>
        <div aria-label="Run activity counts" className="mt-4 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-2 py-1 font-semibold">{displayedActivity.length} represented runs</span>
          {executionStatuses.map((status) => <span key={status} className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1"><span className="font-semibold">{statusPresentation[status].label}</span> {counts[status]}</span>)}
        </div>
        <p className="sr-only">Run activity status counts: {executionStatuses.map((status) => `${statusPresentation[status].label}: ${counts[status]}`).join('; ')}.</p>
        <ol className="sr-only" aria-label="Chronological run activity">{displayedActivity.map((item) => <li key={item.observationRunId}>{formatActivityTime(item.createdAt)}: execution status {item.status}</li>)}</ol>
        <div className="mt-4 h-64" role="img" aria-label="Run activity chart showing exact ObservationRun execution statuses">
          <ResponsiveContainer height="100%" width="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: -24, bottom: 8 }}>
              <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" fontSize={12} interval="preserveStartEnd" tickLine={false} />
              <YAxis allowDecimals={false} domain={[0, 1]} fontSize={12} tickCount={2} tickLine={false} />
              <Tooltip />
              {executionStatuses.map((status) => <Bar key={status} dataKey={status} fill={statusPresentation[status].color} name={statusPresentation[status].label} stackId="execution" />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </>}
    </section>
  )
}

function countStatuses(activity: readonly RunActivityItem[]) {
  return activity.reduce<Record<ExecutionStatus, number>>((counts, item) => ({ ...counts, [item.status]: counts[item.status] + 1 }), {
    pending: 0,
    running: 0,
    completed: 0,
    failed: 0,
    cancelled: 0,
  })
}

function formatActivityTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unavailable time' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
