import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RunDetailPage } from './RunDetailPage'
import type { AlertRunResult, MetricRunResult, ObservationRunDetail } from './types'

const metricResult: MetricRunResult = { schema_version: '1.0', lens_type: 'metric', identity: { observation_id: 'observation', observation_run_id: 'run', lens_id: 'metric-1', lens_run_id: 'lens-metric' }, status: { state: 'completed' }, analysis_window: { from: '2026-09-09T09:00:00Z', to: '2026-09-09T10:00:00Z' }, data_quality: 'good', current_state: { trend: { direction: 'increasing', rate: 'moderate' }, variability: { state: 'low' } }, reference_periods: null, evidence: { current: { mean: 4, std: 1, min: 2, max: 6, slope: 0.3 }, reference_periods: null } }
const alertResult: AlertRunResult = { schema_version: '1.0', lens_type: 'alert', identity: { observation_id: 'observation', observation_run_id: 'run', lens_id: 'alert-1', lens_run_id: 'lens-alert' }, status: 'completed', analysis_window: { from: '2026-09-09T09:00:00Z', to: '2026-09-09T10:00:00Z' }, alerts: [{ id: 'alert', title: 'CPU alert', description: 'Needs review', started_at: '2026-09-09T09:10:00Z', ended_at: null, duration_seconds: 60, status: { normalized: 'active', source: 'OPEN' }, provider_importance: { type: 'priority', value: 'P1' }, occurrence_count: 1, source_ref: 'OPS-1' }], alert_activity: { record_count: 1, occurrence_count: 1 }, status_distribution: { active: 1, resolved: 0, unknown: 0 }, duration_statistics: { min_seconds: 60, max_seconds: 60, average_seconds: 60 }, provider_importance_distribution: { type: 'priority', values: { P1: 1 } }, comparisons: [], findings: [{ id: 'alert-finding', statement: 'Repeated CPU alert', evidence_refs: ['alert'] }], overall_importance: 'high' }

function detail(overrides: Partial<ObservationRunDetail> = {}): ObservationRunDetail {
  return { summary: { id: 'run', observation: { id: 'observation', name: 'Cooling plant' }, analysis_window: { from: '2026-09-09T09:00:00Z', to: '2026-09-09T10:00:00Z' }, status: 'completed', reason: null, analytical_state: 'significant_findings_present', created_at: '2026-09-09T10:01:00Z', started_at: '2026-09-09T10:01:00Z', finished_at: '2026-09-09T10:02:00Z', duration_seconds: 61, href: '/api/v1/observation-runs/run' }, lens_runs: [{ id: 'lens-metric', lens_id: 'metric-1', lens_type: 'metric', status: 'completed', reason: null, started_at: '2026-09-09T10:01:00Z', finished_at: '2026-09-09T10:02:00Z', duration_seconds: 61, result: metricResult }, { id: 'lens-alert', lens_id: 'alert-1', lens_type: 'alert', status: 'completed', reason: null, started_at: '2026-09-09T10:01:00Z', finished_at: '2026-09-09T10:02:00Z', duration_seconds: 61, result: alertResult }], relationship_evaluations: [{ relationship_id: 'relationship-1', name: 'Flow follows pressure', description: null, applicability: 'applicable', state: 'inconsistent', conditions: [{ lens_id: 'metric-1', property: 'trend.direction', expected: 'increasing', observed: 'increasing', match: true }], expectations: [{ lens_id: 'metric-1', property: 'variability.state', expected: 'low', observed: 'high', match: false }] }], analysis: { schema_version: '1.0', identity: { observation_id: 'observation', observation_run_id: 'run' }, overall_state: 'significant_findings_present', limitations: [{ code: 'partial_lens_analysis', lens_id: 'alert-1', lens_type: 'alert', component: 'agent' }], findings: [{ id: 'finding-1', statement: 'Observed evidence', evidence_refs: [{ source_type: 'metric_result', source_id: 'lens-metric', locator: ['evidence', 'current'] }, { source_type: 'relationship_evaluation', source_id: 'relationship-1', locator: ['expectations', 0] }] }], hypotheses: [{ id: 'hypothesis-1', statement: 'Possible explanation', supported_by: ['finding-1'], knowledge_refs: [{ source_id: 'manual', reference: 'section 4' }] }] }, report: { observation_id: 'observation', observation_run_id: 'run', generated_at: '2026-09-09T10:02:00Z', format: 'markdown', content: '# Durable report' }, ...overrides }
}

function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }) }
function renderDetail(value: ObservationRunDetail = detail()) { vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(value))); return render(<MemoryRouter initialEntries={['/runs/run']}><Routes><Route path="/runs/:observationRunId" element={<RunDetailPage />} /></Routes></MemoryRouter>) }

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('RunDetailPage', () => {
  it('renders the completed header, independent state, progress, safe reason, and summary findings', async () => {
    renderDetail(detail({ summary: { ...detail().summary, status: 'failed', reason: { code: 'report_failed', component: 'report_generation' } } }))
    expect(await screen.findByRole('heading', { name: 'Cooling plant' })).toBeTruthy()
    expect(screen.getByLabelText('Execution status: Failed')).toBeTruthy()
    expect(screen.getByLabelText('Analytical state: Significant findings present')).toBeTruthy()
    expect(screen.getByText('Reason: report_failed · report_generation')).toBeTruthy()
    expect(screen.getByText('2 of 2 Lens runs completed.')).toBeTruthy()
    expect(screen.getByText('Observed evidence')).toBeTruthy()
    expect(screen.queryByText(/partial ObservationRun/i)).toBeNull()
  })

  it('keeps tabs accessible and selected after a manual refresh', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(detail()))
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/runs/run']}><Routes><Route path="/runs/:observationRunId" element={<RunDetailPage />} /></Routes></MemoryRouter>)
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    expect(screen.getByRole('tab', { name: 'Analysis' }).getAttribute('aria-selected')).toBe('true')
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(screen.getByRole('tab', { name: 'Analysis' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByText('Possible explanation')).toBeTruthy()
  })

  it('renders type-specific Metric and Alert evidence without provider query/configuration', async () => {
    renderDetail()
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('Data quality: good')).toBeTruthy()
    expect(screen.getByText('Current evidence')).toBeTruthy()
    await userEvent.click(screen.getByRole('tab', { name: 'Alerts' }))
    expect(screen.getByText('CPU alert')).toBeTruthy()
    expect(screen.getByText('Repeated CPU alert')).toBeTruthy()
    expect(document.body.textContent).not.toContain('selector.query')
  })

  it('renders degraded Metric evidence and a partial LensRun without inventing a run state', async () => {
    const current = detail()
    const degraded = { ...metricResult, data_quality: 'degraded' as const, status: { state: 'partial' as const }, reason: { code: 'optional_analysis_failed', component: 'metrics_agent' } }
    renderDetail({ ...current, lens_runs: [{ ...current.lens_runs[0], status: 'partial', reason: { code: 'optional_analysis_failed', component: 'metrics_agent' }, result: degraded }, current.lens_runs[1]] })
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('Data quality: degraded')).toBeTruthy()
    expect(screen.getByLabelText('Lens execution status: Partial')).toBeTruthy()
    expect(screen.queryByLabelText(/Execution status: Partial/)).toBeNull()
  })

  it('keeps relationship applicability separate from state and traceability types distinct', async () => {
    renderDetail()
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Relationships' }))
    expect(screen.getByText('Applicability: applicable')).toBeTruthy()
    expect(screen.getByText('Evaluation state: inconsistent')).toBeTruthy()
    await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    expect(screen.getByText(/Evidence · metric_result/)).toBeTruthy()
    expect(screen.getByText(/Relationship · relationship-1/)).toBeTruthy()
    expect(screen.getByText(/Knowledge · manual: section 4/)).toBeTruthy()
    expect(screen.queryByText(/root cause|recommendation|confidence/i)).toBeNull()
  })

  it.each([
    ['progressing', { status: 'running' as const, analysis: null, report: null }, 'Execution is still progressing; the report has not been produced yet.'],
    ['early failure', { status: 'failed' as const, analysis: null, report: null }, 'Execution failed before the report was produced.'],
    ['cancellation', { status: 'cancelled' as const, analysis: null, report: null }, 'Execution was cancelled before the report was produced.'],
  ])('explains %s missing report state exactly', async (_name, state, expected) => {
    const current = detail(); renderDetail({ ...current, summary: { ...current.summary, status: state.status }, analysis: state.analysis, report: state.report })
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' }))
    expect(screen.getByText(expected)).toBeTruthy()
  })

  it('distinguishes post-analysis report absence, genuinely empty report, and empty sections', async () => {
    const current = detail(); const first = renderDetail({ ...current, report: null, relationship_evaluations: [] })
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' })); expect(screen.getByText('No report artifact was persisted for this run.')).toBeTruthy()
    first.unmount(); const second = renderDetail({ ...current, report: { ...current.report!, content: '' } }); await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' })); expect(screen.getByText('The persisted report is genuinely empty.')).toBeTruthy(); second.unmount()
  })

  it('presents a missing run with a route back to Runs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ code: 'not_found', message: 'missing' }, 404)))
    render(<MemoryRouter initialEntries={['/runs/nope']}><Routes><Route path="/runs/:observationRunId" element={<RunDetailPage />} /></Routes></MemoryRouter>)
    expect(await screen.findByText('Run not found')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Back to Runs' }).getAttribute('href')).toBe('/runs')
  })

  it('copies preformatted Markdown without rendering it', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    renderDetail()
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' })); await userEvent.click(screen.getByRole('button', { name: 'Copy Markdown' }))
    expect(writeText).toHaveBeenCalledWith('# Durable report')
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy()
    expect(screen.getByText('# Durable report').tagName).toBe('PRE')
  })
})
