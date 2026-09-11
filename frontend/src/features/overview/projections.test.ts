import { describe, expect, it } from 'vitest'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunDetail, ObservationRunSummary } from '../runs/types'
import { filterObservationRows, projectObservationRows, projectRecentFindings, projectRunActivity, projectSummaryCounts, selectFindingCandidates, selectLatestRun } from './projections'
import type { OverviewRuntimeItem } from './types'

function observation(id: string, name = id, description: string | null = null): ObservationSummary {
  return { id, name, description, objective: 'Observe', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: `/api/v1/observations/${id}` }
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

function available(summary: ObservationRunSummary): OverviewRuntimeItem {
  return { availability: 'available', summary }
}

function limited(id: string, observationId: string, status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | null, createdAt: string): OverviewRuntimeItem {
  return {
    availability: 'limited',
    id,
    observation: { id: observationId, name: observationId },
    created_at: createdAt,
    status,
    started_at: null,
    finished_at: null,
    duration_seconds: null,
    analytical_state: null,
    limitation_code: 'runtime_projection_invalid',
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
  it('keeps every analytical state, active work, and failed execution independent', () => {
    const definitions = ['active', 'failed-significant', 'cancelled', 'no-findings', 'unavailable', 'never'].map((id) => observation(id))
    const runs = [
      run('active-run', 'active', 'running', null, '2026-09-10T14:00:00Z'),
      run('failed-run', 'failed-significant', 'failed', 'significant_findings_present', '2026-09-10T13:00:00Z'),
      run('cancelled-run', 'cancelled', 'cancelled', 'uncertain', '2026-09-10T12:00:00Z'),
      run('no-findings-run', 'no-findings', 'completed', 'no_significant_findings', '2026-09-10T11:00:00Z'),
      run('unavailable-run', 'unavailable', 'completed', null, '2026-09-10T10:00:00Z'),
    ]

    expect(projectSummaryCounts(definitions, runs.map(available))).toEqual({
      configuredObservations: 6,
      activeObservations: 1,
      observationsWithNoSignificantFindings: 1,
      observationsWithUncertainAnalysis: 1,
      observationsWithSignificantFindings: 1,
      observationsWithFailedExecution: 1,
      observationsWithLimitedCurrentRuntime: 0,
    })
  })

  it('uses newest-first history, caps row history, and orders never-run definitions last', () => {
    const definitions = [observation('never-first'), observation('older'), observation('newer'), observation('never-second')]
    const olderRuns = Array.from({ length: 8 }, (_, index) => run(`older-${index}`, 'older', 'completed', null, `2026-09-10T${String(12 - index).padStart(2, '0')}:00:00Z`))
    const newest = run('newest', 'newer', 'completed', 'no_significant_findings', '2026-09-10T20:00:00Z')
    const rows = projectObservationRows(definitions, [newest, ...olderRuns].map(available))

    expect(rows.map((row) => row.observation.id)).toEqual(['newer', 'older', 'never-first', 'never-second'])
    expect(rows[1]?.recentRuns.map((item) => item.availability === 'available' ? item.summary.id : item.id)).toEqual(['older-0', 'older-1', 'older-2', 'older-3', 'older-4', 'older-5', 'older-6'])
    expect(rows[2]?.latestRun).toBeNull()
    expect(selectLatestRun('missing', [available(newest)])).toBeNull()
  })

  it('filters rows by trimmed case-insensitive name or description without changing order', () => {
    const rows = projectObservationRows(
      [
        observation('alpha', 'Alpha pressure', 'Primary loop'),
        observation('beta', 'Beta', 'Contains PRESSURE history'),
        observation('gamma', 'Gamma'),
      ],
      [],
    )

    expect(filterObservationRows(rows, ' pressure ').map((row) => row.observation.id)).toEqual(['alpha', 'beta'])
    expect(filterObservationRows(rows, 'GAMMA').map((row) => row.observation.id)).toEqual(['gamma'])
    expect(filterObservationRows(rows, '').map((row) => row.observation.id)).toEqual(['alpha', 'beta', 'gamma'])
    expect(filterObservationRows(rows, '   ')).toBe(rows)
    expect(filterObservationRows(rows, 'no match')).toEqual([])
  })

  it('bounds analyzed candidates, preserves their order, and surfaces only Observation findings', () => {
    const runs = Array.from({ length: 7 }, (_, index) => run(`run-${index}`, `observation-${index}`, 'completed', index === 1 ? null : 'uncertain', `2026-09-10T${String(20 - index).padStart(2, '0')}:00:00Z`))
    const candidates = selectFindingCandidates(runs.map(available))
    const details = new Map(candidates.map(({ run: candidate }, index) => [candidate.id, detail(candidate, index === 0 ? ['first', 'second', 'third'] : ['fourth', 'fifth', 'sixth'])]))

    expect(candidates.map(({ run: candidate }) => candidate.id)).toEqual(['run-0', 'run-2', 'run-3', 'run-4', 'run-5'])
    expect(projectRecentFindings(candidates, details).map((finding) => finding.statement)).toEqual(['first', 'second', 'third', 'fourth', 'fifth'])
  })

  it('represents only fourteen newest runs in chronological order with exact execution states', () => {
    const statuses: ObservationRunSummary['status'][] = ['pending', 'running', 'completed', 'failed', 'cancelled']
    const runs = Array.from({ length: 16 }, (_, index) => run(`run-${index}`, 'observation', statuses[index % statuses.length]!, null, `2026-09-10T${String(23 - index).padStart(2, '0')}:00:00Z`))
    const activity = projectRunActivity(runs.map(available))

    expect(activity).toHaveLength(14)
    expect(activity.map((item) => item.observationRunId)).toEqual(['run-13', 'run-12', 'run-11', 'run-10', 'run-9', 'run-8', 'run-7', 'run-6', 'run-5', 'run-4', 'run-3', 'run-2', 'run-1', 'run-0'])
    expect(new Set(activity.map((item) => item.status))).toEqual(new Set(statuses))
  })

  it('keeps a newest limited item current, preserves safe execution data, and never falls back to stale analysis', () => {
    const olderAvailable = run('older', 'observation', 'completed', 'significant_findings_present', '2026-09-10T10:00:00Z')
    const newestLimited = limited('newest', 'observation', 'failed', '2026-09-10T11:00:00Z')
    const items = [newestLimited, available(olderAvailable)]

    expect(projectSummaryCounts([observation('observation')], items)).toEqual({
      configuredObservations: 1,
      activeObservations: 0,
      observationsWithNoSignificantFindings: 0,
      observationsWithUncertainAnalysis: 0,
      observationsWithSignificantFindings: 0,
      observationsWithFailedExecution: 1,
      observationsWithLimitedCurrentRuntime: 1,
    })
    expect(projectObservationRows([observation('observation')], items)[0]?.latestRun).toBe(newestLimited)
    expect(selectFindingCandidates(items).map(({ run: candidate }) => candidate.id)).toEqual(['older'])
  })

  it('retains all fourteen newest available-or-limited activity positions without inventing unavailable status', () => {
    const items = Array.from({ length: 16 }, (_, index) => index === 2
      ? limited(`limited-${index}`, 'observation', null, `2026-09-10T${String(23 - index).padStart(2, '0')}:00:00Z`)
      : available(run(`available-${index}`, 'observation', 'completed', null, `2026-09-10T${String(23 - index).padStart(2, '0')}:00:00Z`)),
    )
    const activity = projectRunActivity(items)

    expect(activity).toHaveLength(14)
    expect(activity.map((item) => item.observationRunId)).toContain('limited-2')
    expect(activity.find((item) => item.observationRunId === 'limited-2')).toMatchObject({ availability: 'limited', status: null })
  })
})
