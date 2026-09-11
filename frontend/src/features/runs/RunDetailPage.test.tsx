import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RunDetailPage } from './RunDetailPage'
import type { AlertRunResult, ObservationRunDetail, UsableMetricRunResult } from './types'

const metricResult: UsableMetricRunResult = { schema_version: '1.0', lens_type: 'metric', identity: { observation_id: 'observation', observation_run_id: 'run', lens_id: 'metric-1', lens_run_id: 'lens-metric', metric_ref: 'cooling_temperature', unit: '°C' }, status: { state: 'completed' }, analysis_window: { from: '2026-09-09T09:00:00Z', to: '2026-09-09T10:00:00Z' }, data_quality: 'good', current_state: { trend: { direction: 'increasing', rate: 'moderate' }, variability: { state: 'low' }, spike: null, oscillation: null, stuck_signal: null }, reference_periods: null, history: null, evidence: { current: { mean: 4, std: 1, min: 2, max: 6, slope: 0.3, spike: null, oscillation: null, stuck_signal: null }, reference_periods: null, history: null } }
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
    expect(screen.getAllByLabelText('Execution status: Failed')).toHaveLength(1)
    expect(screen.getAllByLabelText('Analytical state: Significant findings present')).toHaveLength(1)
    expect(screen.queryByText('Reason: report_failed · report_generation')).toBeNull()
    const failure = screen.getByRole('alert')
    expect(failure.textContent).toContain('Execution failed')
    expect(failure.textContent).toContain('report_failed')
    expect(failure.textContent).toContain('report_generation')
    expect(screen.getByText('2 of 2 Lens runs completed.')).toBeTruthy()
    expect(screen.getByText('Observed evidence')).toBeTruthy()
    expect(screen.queryByText(/partial ObservationRun/i)).toBeNull()
  })

  it('keeps run-header execution and analytical truth visible outside Summary', async () => {
    const current = detail()
    renderDetail({ ...current, summary: { ...current.summary, status: 'failed', reason: { code: 'report_failed', component: 'report_generation' } } })
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    const header = screen.getByRole('heading', { name: 'Cooling plant' }).closest('header')
    expect(header).not.toBeNull()
    const headerContent = within(header!)
    expect(headerContent.queryByText('Started')).toBeNull()
    expect(headerContent.queryByText('Finished')).toBeNull()
    expect(headerContent.getByText('Analysis window')).toBeTruthy()
    expect(headerContent.getByText('Run')).toBeTruthy()
    expect(headerContent.getByText('Duration')).toBeTruthy()
    expect(headerContent.getByText('1m 1s')).toBeTruthy()
    expect(headerContent.getByLabelText('Execution status: Failed')).toBeTruthy()
    expect(headerContent.getByLabelText('Analytical state: Significant findings present')).toBeTruthy()
    expect(headerContent.getByRole('alert').textContent).toContain('The report could not be produced.')
    expect(headerContent.getByText(/report_failed/)).toBeTruthy()
    expect(headerContent.getByText(/report_generation/)).toBeTruthy()
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
    expect(screen.getByText('Current numerical evidence')).toBeTruthy()
    expect(screen.getByText('Metric: cooling_temperature')).toBeTruthy()
    expect(screen.getAllByText('Unavailable in this result.')).toHaveLength(5)
    expect(document.body.textContent).not.toContain('[object Object]')
    await userEvent.click(screen.getByRole('tab', { name: 'Alerts' }))
    expect(screen.getByText('CPU alert')).toBeTruthy()
    expect(screen.getByText('Repeated CPU alert')).toBeTruthy()
    expect(document.body.textContent).not.toContain('selector.query')
  })

  it('keeps optional Metric states, reference means, and history semantically distinct', async () => {
    const enriched: UsableMetricRunResult = { ...metricResult, current_state: { ...metricResult.current_state, spike: { state: 'present' }, oscillation: { state: 'unknown' }, stuck_signal: { state: 'absent' } }, reference_periods: [{ offset: '1d', analysis_window: metricResult.analysis_window, level: { relation: 'higher' }, trend: { direction: 'increasing', rate: 'moderate', direction_relation: 'same', rate_relation: 'same' }, variability: { state: 'low', relation: 'similar' } }], history: { direction: 'increasing', pattern: 'sustained', run_ids: ['earlier-run'] }, evidence: { ...metricResult.evidence, current: { ...metricResult.evidence.current, slope: 0.00000042, spike: { method: 'modified_z', detected_sample_count: 1, detected_timestamps: ['2026-09-09T09:10:00Z'], max_abs_modified_z: 4 }, oscillation: { deadband: 0.1, significant_residual_count: 2, sign_change_count: 3, sign_change_ratio: 0.4 }, stuck_signal: { repeated_value: 2, longest_run_sample_count: 4, longest_run_share: 0.5 } }, reference_periods: [{ offset: '1d', analysis_window: metricResult.analysis_window, mean: 1.04, std: 0.2, min: 0.8, max: 1.2, slope: 0.02, relative_level_change: 0.7456 }], history: { level_change_tolerance: 0.1, classifiable_transitions: 1, unknown_transitions: 0, increasing_transitions: 1, decreasing_transitions: 0, stable_transitions: 0, direction_changes: 0 } } }
    const current = detail(); renderDetail({ ...current, lens_runs: [{ ...current.lens_runs[0], result: enriched }, current.lens_runs[1]] })
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('Optional analysis')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: present')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: unknown')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: absent')).toBeTruthy()
    expect(screen.getByText('Symmetric relative change')).toBeTruthy()
    expect(screen.getByText('Persisted History')).toBeTruthy()
    expect(screen.getByText('4.200e-7')).toBeTruthy()
    expect(document.body.textContent).not.toContain('74.56% higher')
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

  it('separates a Lens failure reason from its unavailable result artifact', async () => {
    const current = detail()
    renderDetail({ ...current, lens_runs: [{ ...current.lens_runs[0], status: 'failed', reason: { code: 'no_usable_metric_data', component: 'metrics_pipeline' }, result: null }, current.lens_runs[1]] })
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('Lens execution failed')).toBeTruthy()
    expect(screen.getByText('no_usable_metric_data')).toBeTruthy()
    expect(screen.getByText('metrics_pipeline')).toBeTruthy()
    expect(screen.getByText('This Lens finished before a result artifact was produced.')).toBeTruthy()
  })

  it('keeps relationship applicability separate from state and traceability types distinct', async () => {
    renderDetail()
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Relationships' }))
    expect(screen.getByText('Applicability: applicable')).toBeTruthy()
    expect(screen.getByText('Evaluation state: inconsistent')).toBeTruthy()
    await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    expect(screen.getByText(/Metric result · lens-metric · evidence.current/)).toBeTruthy()
    expect(screen.getByText(/Relationship evaluation · relationship-1 · expectations\[0\]/)).toBeTruthy()
    expect(screen.getByText(/Knowledge · manual: section 4/)).toBeTruthy()
    await userEvent.click(screen.getByText(/Metric result · lens-metric/))
    expect(screen.getAllByText('Resolved value:').length).toBeGreaterThan(0)
    expect(screen.queryByText(/root cause|recommendation|confidence/i)).toBeNull()
  })

  it('keeps a finding visible when its traceability cannot be resolved locally', async () => {
    const current = detail()
    renderDetail({ ...current, analysis: { ...current.analysis!, findings: [{ id: 'missing-source', statement: 'Still visible finding', evidence_refs: [{ source_type: 'metric_result', source_id: 'missing-run', locator: ['__proto__'] }] }] } })
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    expect(screen.getByText('Still visible finding')).toBeTruthy()
    await userEvent.click(screen.getByText(/Metric result · missing-run/))
    expect(screen.getByText('Traceability unavailable in this run.')).toBeTruthy()
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
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' })); expect(screen.getByText('No report is available for this completed run.')).toBeTruthy()
    first.unmount(); const second = renderDetail({ ...current, report: { ...current.report!, content: '' } }); await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' })); expect(screen.getByText('This completed run produced an empty report.')).toBeTruthy(); second.unmount()
  })

  it('presents a missing run with a route back to Runs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ code: 'not_found', message: 'missing' }, 404)))
    render(<MemoryRouter initialEntries={['/runs/nope']}><Routes><Route path="/runs/:observationRunId" element={<RunDetailPage />} /></Routes></MemoryRouter>)
    expect(await screen.findByText('Run not found')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Back to Runs' }).getAttribute('href')).toBe('/runs')
  })

  it('copies exact persisted Markdown while presenting it as a safe document', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    renderDetail()
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' })); await userEvent.click(screen.getByRole('button', { name: 'Copy Markdown' }))
    expect(writeText).toHaveBeenCalledWith('# Durable report')
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Durable report' }).tagName).toBe('H1')
  })
})
