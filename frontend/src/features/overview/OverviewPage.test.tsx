import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { OverviewContent } from './OverviewPage'
import type { OverviewDataCoordinator, OverviewSourceState } from './useOverviewData'
import type { ObservationSummary } from '../observations/types'
import type { ObservationRunDetail, ObservationRunSummary } from '../runs/types'
import type { OverviewRuntimeFeed, OverviewRuntimeItem } from './types'

const definitions: readonly ObservationSummary[] = [
  { id: 'observation-a', name: 'Cooling system', description: 'Cooling process monitoring.', objective: 'Observe cooling', schema_version: 1, lenses: [{ id: 'metric', name: 'Temperature', type: 'metric', href: '/metric' }], alert_lenses: [], relationships: [], href: '/api/v1/observations/observation-a' },
  { id: 'observation-b', name: 'Feed pump', description: null, objective: 'Observe feed', schema_version: 1, lenses: [], alert_lenses: [{ id: 'alert', name: 'Pump alert', type: 'alert', href: '/alert' }], relationships: [], href: '/api/v1/observations/observation-b' },
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

function runtimeFeed(items: readonly ObservationRunSummary[]): OverviewRuntimeFeed {
  const runtimeItems: readonly OverviewRuntimeItem[] = items.map((summary) => ({ availability: 'available', summary }))
  return { schema_version: '1.0', items: runtimeItems, limited_run_count: 0 }
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
    runHistory: source(runtimeFeed(runs)),
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
    renderOverview(coordinator({ runHistory: source(runtimeFeed([activeWithElapsedDuration])) }))

    expect(screen.getByText('In progress')).toBeTruthy()
    expect(screen.queryByText('2m 5s')).toBeNull()
  })

  it('shows independent mixed-state summary counts, ordered rows, semantic badges, seven accessible history markers, and stable navigation', () => {
    renderOverview()

    const summary = screen.getByLabelText('Overview summary')
    expect(summary.textContent).toContain('Configured Observations3')
    expect(summary.textContent).toContain('Active Observations1')
    expect(summary.textContent).toContain('No significant findings0')
    expect(summary.textContent).toContain('Uncertain analysis0')
    expect(summary.textContent).toContain('Significant findings1')
    expect(summary.textContent).toContain('Failed executions1')
    expect(summary.firstElementChild?.className).toContain('sm:grid-cols-2')
    expect(summary.firstElementChild?.className).toContain('md:grid-cols-3')
    expect(summary.firstElementChild?.className).toContain('xl:grid-cols-6')
    const significantCard = screen.getByText('Significant findings').closest('article')
    const failedCard = screen.getByText('Failed executions').closest('article')
    expect(significantCard?.className).toContain('bg-[var(--color-surface)]')
    expect(failedCard?.className).toContain('bg-[var(--color-surface)]')
    expect(within(significantCard!).getByText('1').className).toContain('text-[var(--color-analysis-significant)]')
    expect(within(failedCard!).getByText('1').className).toContain('text-[var(--color-execution-failed)]')
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
    renderOverview(coordinator({ runHistory: source<OverviewRuntimeFeed>(null, new Error('runtime unavailable')), findingCandidates: [], findingDetails: { data: new Map(), errors: new Map(), loadingRunIds: new Set() } }))

    expect(screen.getByText('Runtime data is unavailable. Observation definitions remain visible below.')).toBeTruthy()
    expect(screen.getAllByText('Runtime unavailable')).toHaveLength(15)
    expect(screen.queryByText('Not run yet')).toBeNull()
    const summary = screen.getByLabelText('Overview summary')
    expect(summary.textContent).toContain('Configured Observations3')
    expect(summary.textContent).toContain('Active ObservationsUnavailable')
    expect(summary.textContent).toContain('No significant findingsUnavailable')
    expect(summary.textContent).toContain('Uncertain analysisUnavailable')
    expect(summary.textContent).toContain('Significant findingsUnavailable')
    expect(summary.textContent).toContain('Failed executionsUnavailable')
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

  it('uses the wide primary grid, stacks the semantic sections in content order, and describes client receipt time honestly', () => {
    const refreshTime = new Date('2026-09-10T12:34:00Z')
    renderOverview(coordinator({ lastSuccessfulRefreshAt: refreshTime }))

    expect(screen.getByTestId('overview-primary-grid').className).toContain('xl:grid-cols-')
    expect(screen.getByTestId('observations-collection').compareDocumentPosition(screen.getByLabelText('Overview insights')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText(/Last refreshed locally at/)).toBeTruthy()
    expect(screen.getByLabelText(/Last refresh was received by this client/)).toBeTruthy()
    expect(screen.queryByText(/snapshot/i)).toBeNull()
  })

  it('filters only already-loaded Observation rows and restores them with the accessible clear action', async () => {
    const user = userEvent.setup()
    renderOverview()
    const summaryBefore = screen.getByLabelText('Overview summary').textContent
    await user.type(screen.getByRole('textbox', { name: 'Search Observations' }), '  feed ')

    const list = screen.getByRole('list', { name: 'Observations' })
    expect(list.textContent).toContain('Feed pump')
    expect(list.textContent).not.toContain('Cooling system')
    expect(screen.getByText('Persisted Observation finding.')).toBeTruthy()
    expect(screen.getByLabelText('Overview summary').textContent).toBe(summaryBefore)

    await user.clear(screen.getByRole('textbox', { name: 'Search Observations' }))
    await user.type(screen.getByRole('textbox', { name: 'Search Observations' }), 'no result')
    expect(screen.getByText(/No Observations match/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Clear search' }))
    expect(screen.getByRole('list', { name: 'Observations' }).textContent).toContain('Cooling system')
  })

  it('wraps long unbroken Observation identity content without truncating its accessible text', () => {
    const longName = 'CoolingSystemWithoutWhitespaceThatMustWrapInsideTheMonitoringGrid'
    const longDescription = 'LongDescriptionWithoutWhitespaceThatMustWrapInsteadOfWideningThePage'
    renderOverview(coordinator({ definitions: source([{ ...definitions[0], name: longName, description: longDescription }]), runHistory: source(runtimeFeed([runs[0]])) }))

    const nameLink = screen.getByRole('link', { name: longName })
    expect(nameLink.textContent).toBe(longName)
    expect(nameLink.className).toContain('min-w-0')
    expect(nameLink.className).toContain('break-words')
    const description = screen.getByText(longDescription)
    expect(description.textContent).toBe(longDescription)
    expect(description.className).toContain('min-w-0')
    expect(description.className).toContain('break-words')
  })

  it('keeps all five exact recent-run markers focusable and distinguishes completed from cancelled without partial', () => {
    const pending = run('run-pending', 'observation-a', 'Cooling system', 'pending', null, '2026-09-09T03:00:00Z', null)
    renderOverview(coordinator({ runHistory: source(runtimeFeed([pending, ...runs])) }))

    for (const status of ['pending', 'running', 'completed', 'failed', 'cancelled']) {
      expect(screen.getAllByRole('button', { name: new RegExp(`Recent run: .*execution status ${status}`) }).length).toBeGreaterThan(0)
    }
    expect(screen.getAllByRole('button', { name: /execution status completed/ })[0]?.textContent).toBe('C')
    expect(screen.getByRole('button', { name: /execution status cancelled/ }).textContent).toBe('X')
    expect(screen.queryByRole('button', { name: /execution status partial/ })).toBeNull()
  })

  it('keeps limited current fields local, preserves valid failure, and discloses bounded findings coverage', () => {
    const limited: OverviewRuntimeItem = { availability: 'limited', id: 'limited-current', observation: { id: 'observation-a', name: 'Cooling system' }, created_at: '2026-09-09T14:00:00Z', status: 'failed', started_at: null, finished_at: null, duration_seconds: null, analytical_state: null, limitation_code: 'runtime_projection_invalid', href: '/api/v1/observation-runs/limited-current' }
    const feed: OverviewRuntimeFeed = { schema_version: '1.0', items: [limited, { availability: 'available', summary: runs[0] }], limited_run_count: 1 }
    renderOverview(coordinator({ runHistory: source(feed), findingCandidates: [{ run: runs[0] }] }))

    expect(screen.getByText('Runtime coverage limited:')).toBeTruthy()
    expect(screen.getByText('Runtime data limited')).toBeTruthy()
    expect(screen.getByLabelText('Execution status: Failed')).toBeTruthy()
    expect(screen.getByLabelText('Analytical state: Analysis unavailable')).toBeTruthy()
    expect(screen.getByText('Runtime coverage is limited for 1 run; only available analyzed runs are inspected.')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Recent run: .*runtime data limited; execution status failed/i })).toBeTruthy()
  })

  it('labels Metric, Alert, mixed, and legacy composition icons without assigning runtime meaning', () => {
    const mixed = { ...definitions[0], id: 'mixed', name: 'Mixed', alert_lenses: [{ id: 'alert-mixed', name: 'Mixed alert', type: 'alert' as const, href: '/alert' }] }
    renderOverview(coordinator({ definitions: source([...definitions, mixed]), runHistory: source(runtimeFeed([])), findingCandidates: [] }))

    for (const label of ['Metric Lens composition', 'Alert Lens composition', 'Mixed Metric and Alert Lens composition', 'Legacy or empty Lens composition']) expect(screen.getByLabelText(label)).toBeTruthy()
  })
})
