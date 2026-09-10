import { describe, expect, it } from 'vitest'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunDetail, ObservationRunSummary } from '../runs/types'
import { projectObservationRows, projectRecentFindings, projectRunActivity, projectSummaryCounts, selectFindingCandidates, selectLatestRun } from './projections'

function observation(id: string, name = id): ObservationSummary {
  return { id, name, description: null, objective: 'Observe', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: `/api/v1/observations/${id}` }
}

function run(id: string, observationId: string, status: ObservationRunSummary['status'], analyticalState: ObservationRunSummary['analytical_state'], createdAt: string): ObservationRunSummary {
  return {
    id,
    observation: { id: observationId, name: observationId },
    analysis_window: { from: '2026-09-10T10:00:00Z', to: '2026-09-10T11:00:00Z' },
    status,
    reason: null,
    analytical_state: analyticalState,
    created_at: createdAt,
    started_at: createdAt,
    finished_at: status === 'pending' || status === 'running' ? null : createdAt,
    duration_seconds: status === 'pending' || status === 'running' ? null : 12,
    href: `/api/v1/observation-runs/${id}`,
  }
}

function detail(summary: ObservationRunSummary, statements: readonly string[]): ObservationRunDetail {
  return {
    summary,
    lens_runs: [],
    relationship_evaluations: [],
    analysis: summary.analytical_state === null ? null : {
      schema_version: '1.0',
      identity: { observation_id: summary.observation.id, observation_run_id: summary.id },
      overall_state: summary.analytical_state,
      findings: statements.map((statement, index) => ({ id: `${summary.id}-${index}`, statement, evidence_refs: [] })),
      hypotheses: [{ id: 'hypothesis', statement: 'Not a finding', supported_by: [], knowledge_refs: [] }],
      limitations: [],
    },
    report: null,
  }
}

describe('Overview projections', () => {
  it('keeps active, significant, and failed counts independent for mixed latest states', () => {
    const definitions = ['active', 'failed-significant', 'cancelled', 'never'].map((id) => observation(id))
    const runs = [
      run('active-run', 'active', 'running', null, '2026-09-10T14:00:00Z'),
      run('failed-run', 'failed-significant', 'failed', 'significant_findings_present', '2026-09-10T13:00:00Z'),
      run('cancelled-run', 'cancelled', 'cancelled', 'uncertain', '2026-09-10T12:00:00Z'),
    ]

    expect(projectSummaryCounts(definitions, runs)).toEqual({
      configuredObservations: 4,
      activeObservations: 1,
      observationsWithSignificantFindings: 1,
      observationsWithFailedExecution: 1,
    })
  })

  it('uses newest-first history, caps row history, and orders never-run definitions last', () => {
    const definitions = [observation('never-first'), observation('older'), observation('newer'), observation('never-second')]
    const olderRuns = Array.from({ length: 8 }, (_, index) => run(`older-${index}`, 'older', 'completed', null, `2026-09-10T${String(12 - index).padStart(2, '0')}:00:00Z`))
    const newest = run('newest', 'newer', 'completed', 'no_significant_findings', '2026-09-10T20:00:00Z')
    const rows = projectObservationRows(definitions, [newest, ...olderRuns])

    expect(rows.map((row) => row.observation.id)).toEqual(['newer', 'older', 'never-first', 'never-second'])
    expect(rows[1]?.recentRuns.map((item) => item.id)).toEqual(['older-0', 'older-1', 'older-2', 'older-3', 'older-4', 'older-5', 'older-6'])
    expect(rows[2]?.latestRun).toBeNull()
    expect(selectLatestRun('missing', [newest])).toBeNull()
  })

  it('bounds analyzed candidates, preserves their order, and surfaces only Observation findings', () => {
    const runs = Array.from({ length: 7 }, (_, index) => run(`run-${index}`, `observation-${index}`, 'completed', index === 1 ? null : 'uncertain', `2026-09-10T${String(20 - index).padStart(2, '0')}:00:00Z`))
    const candidates = selectFindingCandidates(runs)
    const details = new Map(candidates.map(({ run: candidate }, index) => [candidate.id, detail(candidate, index === 0 ? ['first', 'second', 'third'] : ['fourth', 'fifth', 'sixth'])]))

    expect(candidates.map(({ run: candidate }) => candidate.id)).toEqual(['run-0', 'run-2', 'run-3', 'run-4', 'run-5'])
    expect(projectRecentFindings(candidates, details).map((finding) => finding.statement)).toEqual(['first', 'second', 'third', 'fourth', 'fifth'])
  })

  it('represents only fourteen newest runs in chronological order with exact execution states', () => {
    const statuses: ObservationRunSummary['status'][] = ['pending', 'running', 'completed', 'failed', 'cancelled']
    const runs = Array.from({ length: 16 }, (_, index) => run(`run-${index}`, 'observation', statuses[index % statuses.length]!, null, `2026-09-10T${String(23 - index).padStart(2, '0')}:00:00Z`))
    const activity = projectRunActivity(runs)

    expect(activity).toHaveLength(14)
    expect(activity.map((item) => item.observationRunId)).toEqual(['run-13', 'run-12', 'run-11', 'run-10', 'run-9', 'run-8', 'run-7', 'run-6', 'run-5', 'run-4', 'run-3', 'run-2', 'run-1', 'run-0'])
    expect(new Set(activity.map((item) => item.status))).toEqual(new Set(statuses))
  })
})
