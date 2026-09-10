import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { OverviewContent } from './OverviewPage'
import type { OverviewDataCoordinator, OverviewSourceState } from './useOverviewData'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunDetail, ObservationRunSummary } from '../runs/types'

const definitions: readonly ObservationSummary[] = [
  { id: 'observation-a', name: 'Cooling system', description: 'Cooling process monitoring.', objective: 'Observe cooling', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/observation-a' },
  { id: 'observation-b', name: 'Feed pump', description: null, objective: 'Observe feed', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/observation-b' },
  { id: 'observation-c', name: 'Never run', description: null, objective: 'Observe idle equipment', schema_version: 1, lenses: [], alert_lenses: [], relationships: [], href: '/api/v1/observations/observation-c' },
]

const runs: readonly ObservationRunSummary[] = [
  run('run-failed-significant', 'observation-a', 'Cooling system', 'failed', 'significant_findings_present', '2026-09-09T12:00:00Z'),
  run('run-running', 'observation-b', 'Feed pump', 'running', null, '2026-09-09T11:00:00Z'),
  run('run-previous-1', 'observation-a', 'Cooling system', 'completed', 'no_significant_findings', '2026-09-09T10:00:00Z'),
  run('run-previous-2', 'observation-a', 'Cooling system', 'cancelled', null, '2026-09-09T09:00:00Z'),
  run('run-previous-3', 'observation-a', 'Cooling system', 'completed', 'uncertain', '2026-09-09T08:00:00Z'),
  run('run-previous-4', 'observation-a', 'Cooling system', 'completed', null, '2026-09-09T07:00:00Z'),
  run('run-previous-5', 'observation-a', 'Cooling system', 'completed', null, '2026-09-09T06:00:00Z'),
  run('run-previous-6', 'observation-a', 'Cooling system', 'completed', null, '2026-09-09T05:00:00Z'),
  run('run-previous-7', 'observation-a', 'Cooling system', 'completed', null, '2026-09-09T04:00:00Z'),
]

function run(id: string, observationId: string, name: string, status: ObservationRunSummary['status'], analyticalState: ObservationRunSummary['analytical_state'], createdAt: string, durationSeconds: number | null = status === 'running' ? null : 60): ObservationRunSummary {
  return { id, observation: { id: observationId, name }, analysis_window: { from: createdAt, to: createdAt }, status, reason: null, analytical_state: analyticalState, created_at: createdAt, started_at: createdAt, finished_at: status === 'running' ? null : createdAt, duration_seconds: durationSeconds, href: `/api/v1/observation-runs/${id}` }
}

function source<T>(data: T | null, error: unknown = null): OverviewSourceState<T> {
  return { data, error, loading: false, refreshing: false }
}

function detail(runSummary: ObservationRunSummary, findings: readonly { id: string; statement: string }[]): ObservationRunDetail {
  return {
    summary: runSummary,
    lens_runs: [{ id: 'alert-lens-run', lens_id: 'alert-lens', lens_type: 'alert', status: 'completed', reason: null, started_at: runSummary.created_at, finished_at: runSummary.created_at, duration_seconds: 1, result: { schema_version: '1.0', identity: { observation_id: runSummary.observation.id, observation_run_id: runSummary.id, lens_id: 'alert-lens', lens_run_id: 'alert-lens-run' }, lens_type: 'alert', status: 'completed', analysis_window: runSummary.analysis_window, alerts: [], alert_activity: { record_count: 0, occurrence_count: 0 }, status_distribution: { active: 0, resolved: 0, unknown: 0 }, duration_statistics: null, provider_importance_distribution: null, comparisons: [], findings: [{ id: 'lens-finding', statement: 'Do not surface this Lens-local finding.', evidence_refs: [] }], overall_importance: 'none' } }],
    relationship_evaluations: [],
    analysis: { schema_version: '1.0', identity: { observation_id: runSummary.observation.id, observation_run_id: runSummary.id }, overall_state: runSummary.analytical_state ?? 'uncertain', findings: findings.map((finding) => ({ ...finding, evidence_refs: [] })), hypotheses: [{ id: 'hypothesis-only', statement: 'Do not surface this hypothesis.', supported_by: [], knowledge_refs: [] }], limitations: [] },
    report: { observation_id: runSummary.observation.id, observation_run_id: runSummary.id, generated_at: runSummary.created_at, format: 'markdown', content: 'Do not surface this report.' },
  }
}

function coordinator(overrides: Partial<OverviewDataCoordinator> = {}): OverviewDataCoordinator {
  const findingCandidates = [{ run: runs[0] }, { run: runs[1] }, { run: runs[2] }, { run: runs[4] }]
  return {
    definitions: source(definitions),
    runHistory: source(runs),
    findingCandidates,
    findingDetails: { data: new Map([[runs[0].id, detail(runs[0], [{ id: 'finding-a', statement: 'Persisted Observation finding.' }])], [runs[2].id, detail(runs[2], [])], [runs[4].id, detail(runs[4], [])]]), errors: new Map(), loadingRunIds: new Set(), },
    lastSuccessfulRefreshAt: null,
    refresh: () => undefined,
    ...overrides,
  }
}

function renderOverview(data = coordinator()) {
  return render(<MemoryRouter><OverviewContent data={data} /></MemoryRouter>)
}

describe('OverviewContent', () => {
  it('labels an active latest run as in progress even when its summary includes elapsed duration', () => {
    const activeWithElapsedDuration = run('elapsed-running', 'observation-b', 'Feed pump', 'running', null, '2026-09-09T13:00:00Z', 125)
    renderOverview(coordinator({ runHistory: source([activeWithElapsedDuration]) }))

    expect(screen.getByText('In progress')).toBeTruthy()
    expect(screen.queryByText('2m 5s')).toBeNull()
  })

  it('shows independent mixed-state summary counts, ordered rows, semantic badges, seven accessible history markers, and stable navigation', () => {
    renderOverview()

    const summary = screen.getByLabelText('Overview summary')
    expect(within(summary).getByText('Configured Observations').parentElement?.textContent).toContain('3')
    expect(within(summary).getByText('Active Observations').parentElement?.textContent).toContain('1')
    expect(within(summary).getByText('Significant findings').parentElement?.textContent).toContain('1')
    expect(within(summary).getByText('Failed executions').parentElement?.textContent).toContain('1')
    const list = screen.getByRole('list', { name: 'Observations' })
    expect(list.textContent).toMatch(/Cooling system[\s\S]*Feed pump[\s\S]*Never run/)
    expect(screen.getByLabelText('Execution status: Failed')).toBeTruthy()
    expect(screen.getAllByLabelText('Analytical state: Significant findings present')).toHaveLength(2)
    expect(screen.getByText('In progress')).toBeTruthy()
    expect(screen.getByText('Not run yet')).toBeTruthy()
    expect(within(list.getElementsByTagName('li')[0]).getAllByLabelText(/^Recent run:/)).toHaveLength(7)
    expect(screen.getByRole('link', { name: 'Cooling system' }).getAttribute('href')).toBe('/observations/observation-a')
    expect(screen.getByRole('link', { name: 'Open latest run run-failed-significant' }).getAttribute('href')).toBe('/runs/run-failed-significant')
  })

  it('shows only persisted Observation-level findings, preserves owning run links, and never promotes a hypothesis, report, Lens-local value, or failure into a finding', () => {
    renderOverview()

    expect(screen.getByText('Persisted Observation finding.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Open source run run-failed-significant' }).getAttribute('href')).toBe('/runs/run-failed-significant')
    expect(screen.queryByText('Do not surface this hypothesis.')).toBeNull()
    expect(screen.queryByText('Do not surface this report.')).toBeNull()
    expect(screen.queryByText('Do not surface this Lens-local finding.')).toBeNull()
    expect(screen.queryByText('analysis_failed')).toBeNull()
  })

  it('keeps successful definitions visible but makes runtime-derived values explicitly unavailable when runtime history has not loaded', () => {
    renderOverview(coordinator({ runHistory: source<readonly ObservationRunSummary[]>(null, new Error('runtime unavailable')), findingCandidates: [], findingDetails: { data: new Map(), errors: new Map(), loadingRunIds: new Set() } }))

    expect(screen.getByText('Runtime data is unavailable. Observation definitions remain visible below.')).toBeTruthy()
    expect(screen.getAllByText('Runtime unavailable')).toHaveLength(3)
    expect(screen.queryByText('Not run yet')).toBeNull()
    expect(screen.getByText('Recent Findings are unavailable because run history is unavailable.')).toBeTruthy()
    expect(screen.getByText('Run Activity is unavailable because run history is unavailable.')).toBeTruthy()
  })

  it('uses a bounded, honest empty statement and keeps successful findings visible with scoped incomplete detail feedback', () => {
    const empty = renderOverview(coordinator({ findingDetails: { data: new Map([[runs[0].id, detail(runs[0], [])]]), errors: new Map(), loadingRunIds: new Set() } }))
    expect(screen.getByText('No findings are present in the five latest analyzed runs.')).toBeTruthy()
    empty.unmount()

    renderOverview(coordinator({ findingDetails: { data: new Map([[runs[0].id, detail(runs[0], [{ id: 'finding-a', statement: 'Persisted Observation finding.' }])]]), errors: new Map([[runs[2].id, new Error('unavailable')]]), loadingRunIds: new Set() } }))
    expect(screen.getByText('Recent Findings are incomplete because one or more eligible run details could not be loaded.')).toBeTruthy()
    expect(screen.getByText('Persisted Observation finding.')).toBeTruthy()
    expect(screen.queryByText('No findings are present in the five latest analyzed runs.')).toBeNull()
  })
})
