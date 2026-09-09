import { describe, expect, it } from 'vitest'
import { insertAcceptanceSnapshot, mergeRunHistory } from './runHistory'
import type { ObservationRunSummary } from './types'

const running: ObservationRunSummary = { id: 'same-run', observation: { id: 'observation', name: 'Observation' }, analysis_window: { from: '2026-09-09T11:00:00Z', to: '2026-09-09T12:00:00Z' }, status: 'running', reason: null, analytical_state: null, created_at: '2026-09-09T12:00:00Z', started_at: '2026-09-09T12:00:00Z', finished_at: null, duration_seconds: null, href: '/api/v1/observation-runs/same-run' }
const completed: ObservationRunSummary = { ...running, status: 'completed', finished_at: '2026-09-09T12:01:00Z', duration_seconds: 60 }

describe('run history merge', () => {
  it('does not regress a durable terminal row when an older running snapshot arrives', () => {
    expect(mergeRunHistory([completed], [running])).toEqual([completed])
    expect(insertAcceptanceSnapshot([completed], running)).toEqual([completed])
  })
})
