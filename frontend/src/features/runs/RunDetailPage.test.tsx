import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RunDetailPage } from './RunDetailPage'
import type { AlertRunResult, MetricRunResult, ObservationRunDetail, UsableMetricRunResult } from './types'

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

  it('lists mixed Metric outcomes in response order, starts closed, switches by LensRun ID, dismisses detail, and opens Observation analysis', async () => {
    const current = detail()
    const partial: UsableMetricRunResult = { ...metricResult, identity: { ...metricResult.identity, lens_id: 'metric-partial', lens_run_id: 'lens-partial', metric_ref: 'partial_temperature' }, status: { state: 'partial' }, reason: { code: 'reference_unavailable', component: 'reference_periods' } }
    const insufficient: MetricRunResult = { schema_version: '1.0', lens_type: 'metric', identity: { ...metricResult.identity, lens_id: 'metric-insufficient', lens_run_id: 'lens-insufficient', metric_ref: 'insufficient_pressure' }, status: { state: 'completed' }, data_quality: 'insufficient', analysis_window: metricResult.analysis_window }
    const failed: MetricRunResult = { schema_version: '1.0', lens_type: 'metric', identity: { ...metricResult.identity, lens_id: 'metric-failed', lens_run_id: 'lens-failed', metric_ref: 'failed_flow' }, status: { state: 'failed', error: { code: 'current_metric_acquisition_failed', message: 'Current metric data acquisition failed.' } }, analysis_window: metricResult.analysis_window }
    renderDetail({ ...current, lens_runs: [
      { ...current.lens_runs[0], id: 'lens-partial', lens_id: 'metric-partial', status: 'partial', reason: partial.reason!, result: partial },
      { ...current.lens_runs[0], id: 'lens-insufficient', lens_id: 'metric-insufficient', status: 'completed', reason: null, result: insufficient },
      { ...current.lens_runs[0], id: 'lens-failed', lens_id: 'metric-failed', status: 'failed', reason: { code: 'current_metric_acquisition_failed', component: 'metric_acquisition' }, result: failed },
      { ...current.lens_runs[0], id: 'lens-running', lens_id: 'metric-running', status: 'running', reason: null, result: null },
      current.lens_runs[1],
    ] })
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('4 Metric Lenses · 0 selected')).toBeTruthy()
    expect(screen.queryByLabelText(/Metric Lens detail:/)).toBeNull()
    expect(screen.queryByText('Select a Metric Lens to inspect its durable result.')).toBeNull()
    expect(screen.getByText('partial_temperature')).toBeTruthy()
    expect(screen.getByText('insufficient_pressure')).toBeTruthy()
    expect(screen.getByText('failed_flow')).toBeTruthy()
    expect(screen.getByText('metric-running')).toBeTruthy()
    expect(screen.getByText(/Data quality: insufficient/)).toBeTruthy()
    expect(screen.getByText(/Current metric data acquisition failed/)).toBeTruthy()
    expect(screen.getByText(/current_metric_acquisition_failed/)).toBeTruthy()
    expect(screen.getByText(/still progressing; no result artifact/)).toBeTruthy()
    const failedCard = screen.getByRole('button', { name: /failed_flow/ })
    await userEvent.click(failedCard)
    expect(screen.getByText('4 Metric Lenses · 1 selected')).toBeTruthy()
    const inlineDetail = screen.getByLabelText('Metric Lens detail: lens-failed')
    expect(failedCard.parentElement?.contains(inlineDetail)).toBe(true)
    expect(document.activeElement).toBe(inlineDetail)
    expect(screen.queryByText('Current numerical evidence')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss Metric Lens detail' }))
    expect(screen.queryByLabelText(/Metric Lens detail:/)).toBeNull()
    expect(screen.getByText('4 Metric Lenses · 0 selected')).toBeTruthy()
    expect(document.activeElement).toBe(failedCard)
    await userEvent.click(screen.getByRole('button', { name: /partial_temperature/ }))
    await userEvent.click(screen.getByRole('button', { name: 'View Observation analysis' }))
    expect(screen.getByRole('tab', { name: 'Analysis' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByText('Possible explanation')).toBeTruthy()
  })

  it('keeps a selected Metric LensRun through refresh, closes on selected-ID loss without auto-selecting when it reappears, and retains the closed state after a failed refresh', async () => {
    const current = detail()
    const second = { ...current.lens_runs[0], id: 'lens-second', lens_id: 'metric-second', result: { ...metricResult, identity: { ...metricResult.identity, lens_id: 'metric-second', lens_run_id: 'lens-second', metric_ref: 'return_temperature' } } }
    const firstSnapshot = { ...current, lens_runs: [current.lens_runs[0], second, current.lens_runs[1]] }
    const secondSnapshot = { ...firstSnapshot, lens_runs: [{ ...firstSnapshot.lens_runs[0], result: { ...metricResult, evidence: { ...metricResult.evidence, current: { ...metricResult.evidence.current, mean: 5 } } } }, second, current.lens_runs[1]] }
    const fallbackSnapshot = { ...current, lens_runs: [current.lens_runs[0], current.lens_runs[1]] }
    const reappearedSnapshot = { ...current, lens_runs: [current.lens_runs[0], second, current.lens_runs[1]] }
    const fetchMock = vi.fn().mockResolvedValueOnce(response(firstSnapshot)).mockResolvedValueOnce(response(secondSnapshot)).mockResolvedValueOnce(response(fallbackSnapshot)).mockResolvedValueOnce(response(reappearedSnapshot)).mockRejectedValueOnce(new Error('offline'))
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/runs/run']}><Routes><Route path="/runs/:observationRunId" element={<RunDetailPage />} /></Routes></MemoryRouter>)
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    await userEvent.click(screen.getByRole('button', { name: /return_temperature/ }))
    expect(screen.getByLabelText('Metric Lens detail: lens-second')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(screen.getByLabelText('Metric Lens detail: lens-second')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(screen.queryByLabelText(/Metric Lens detail:/)).toBeNull()
    expect(screen.getByText('1 Metric Lens · 0 selected')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
    expect(screen.queryByLabelText(/Metric Lens detail:/)).toBeNull()
    expect(screen.getByText('2 Metric Lenses · 0 selected')).toBeTruthy()
    const lastUpdated = screen.getByText(/^Last updated /).textContent
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(screen.getByText(/Showing the last successful run detail/)).toBeTruthy())
    expect(screen.queryByLabelText(/Metric Lens detail:/)).toBeNull()
    expect(screen.getByText(/^Last updated /).textContent).toBe(lastUpdated)
  })

  it('keeps the Metric pane closed across a successful refresh until the user explicitly selects a card', async () => {
    const current = detail()
    const refreshed = { ...current, lens_runs: [{ ...current.lens_runs[0], result: { ...metricResult, evidence: { ...metricResult.evidence, current: { ...metricResult.evidence.current, mean: 5 } } } }, current.lens_runs[1]] }
    const fetchMock = vi.fn().mockResolvedValueOnce(response(current)).mockResolvedValueOnce(response(refreshed))
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/runs/run']}><Routes><Route path="/runs/:observationRunId" element={<RunDetailPage />} /></Routes></MemoryRouter>)
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.queryByLabelText(/Metric Lens detail:/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(screen.queryByLabelText(/Metric Lens detail:/)).toBeNull()
    expect(screen.getByText('1 Metric Lens · 0 selected')).toBeTruthy()
  })

  it('keeps the selected detail in a viewport-anchored side pane at the 1170px desktop threshold', async () => {
    const matchMedia = vi.fn().mockImplementation((query: string) => ({ matches: query === '(min-width: 1170px)', addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    vi.stubGlobal('matchMedia', matchMedia)
    renderDetail()
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    await userEvent.click(screen.getByRole('button', { name: /cooling_temperature/ }))
    const results = screen.getByLabelText('Metric Lens results')
    const detail = screen.getByLabelText('Metric Lens detail: lens-metric')
    expect(results.contains(detail)).toBe(false)
    expect(matchMedia).toHaveBeenCalledWith('(min-width: 1170px)')
    expect(detail.parentElement?.className).toContain('min-[1170px]:grid-cols-[minmax(0,1.8fr)_minmax(17rem,1fr)]')
    expect(detail.className).toContain('min-[1170px]:sticky')
    expect(detail.className).toContain('min-[1170px]:max-h-[calc(100dvh-2rem)]')
    expect(detail.className).toContain('min-[1170px]:overflow-y-auto')
    expect(document.activeElement).toBe(detail)
  })

  it('describes a cancelled Metric Lens without a start or duration as unavailable rather than in progress', async () => {
    const current = detail()
    renderDetail({ ...current, lens_runs: [{ ...current.lens_runs[0], status: 'cancelled', started_at: null, finished_at: null, duration_seconds: null, result: null }, current.lens_runs[1]] })
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('Not started')).toBeTruthy()
    expect(screen.getByText('Duration: Unavailable')).toBeTruthy()
    expect(screen.queryByText('Duration: In progress')).toBeNull()
    expect(screen.getByText('This Lens was cancelled before a result artifact was produced.')).toBeTruthy()
  })

  it.each([
    ['running', 'Execution is still progressing; this artifact has not been produced yet.'],
    ['failed', 'Execution failed before this artifact was produced.'],
    ['cancelled', 'Execution was cancelled before this artifact was produced.'],
    ['completed', 'This run legitimately produced an empty collection for this section.'],
  ] as const)('keeps the %s empty Metric collection lifecycle meaning and refresh time', async (status, message) => {
    const current = detail()
    renderDetail({ ...current, summary: { ...current.summary, status }, lens_runs: current.lens_runs.filter((lens) => lens.lens_type !== 'metric') })
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('0 Metric Lenses · 0 selected')).toBeTruthy()
    expect(screen.getByText(message)).toBeTruthy()
    expect(screen.getByText(/^Last updated /)).toBeTruthy()
  })

  it('renders type-specific Metric and Alert evidence without provider query/configuration', async () => {
    renderDetail()
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Metrics' }))
    expect(screen.getByText('Data quality: good')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: /cooling_temperature/ }))
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
    await userEvent.click(screen.getByRole('button', { name: /cooling_temperature/ }))
    expect(screen.getByText('Optional analysis')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: present')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: unknown')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: absent')).toBeTruthy()
    expect(screen.getByText('Symmetric relative change')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Persisted History' })).toBeTruthy()
    expect(screen.getAllByText('4.200e-7')).toHaveLength(2)
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
    await userEvent.click(screen.getByRole('button', { name: /metric-1/ }))
    expect(screen.getByText('Lens execution failed')).toBeTruthy()
    expect(screen.getByText('no_usable_metric_data')).toBeTruthy()
    expect(screen.getByText('metrics_pipeline')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toContain('Lens execution failed')
    const unavailable = screen.getByText('This Lens finished before a result artifact was produced.').closest('[role="status"]')
    expect(unavailable?.className).toContain('color-surface-muted')
  })

  it('keeps relationship applicability separate from state and traceability types distinct', async () => {
    renderDetail()
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Relationships' }))
    expect(screen.getByText('Applicability: applicable')).toBeTruthy()
    expect(screen.getByText('Evaluation state: inconsistent')).toBeTruthy()
    await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    const references = screen.getByText('References').closest('details')
    expect(references).not.toBeNull()
    expect(references?.open).toBe(false)
    await userEvent.click(screen.getByText('References'))
    expect(references?.open).toBe(true)
    expect(screen.getByText(/Metric result · lens-metric · evidence.current/)).toBeTruthy()
    expect(screen.getByText(/Relationship evaluation · relationship-1 · expectations\[0\]/)).toBeTruthy()
    expect(screen.getByText(/Knowledge · manual: section 4/)).toBeTruthy()
    await userEvent.click(screen.getByText(/Metric result · lens-metric/))
    expect(screen.getAllByText('Resolved value:').length).toBeGreaterThan(0)
    expect(screen.queryByText(/root cause|recommendation|confidence/i)).toBeNull()
  })

  it('emphasizes a finding brief before its first colon in summary and analysis views', async () => {
    const current = detail()
    const statement = 'Device connectivity: Connected devices remained stable.'
    renderDetail({ ...current, analysis: { ...current.analysis!, findings: [{ id: 'named-finding', statement, evidence_refs: [] }] } })
    await screen.findByText((_content, element) => element?.tagName === 'P' && element.textContent === statement)
    expect(screen.getByText('Device connectivity:').tagName).toBe('STRONG')
    await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === statement).textContent).toBe(statement)
    expect(screen.getByText('Device connectivity:').tagName).toBe('STRONG')
  })

  it('groups only evidence and relationship controls under each finding references disclosure', async () => {
    const current = detail()
    renderDetail({ ...current, analysis: { ...current.analysis!, findings: [{ id: 'two-locators', statement: 'Two exact values remain inspectable', evidence_refs: [{ source_type: 'metric_result', source_id: 'lens-metric', locator: ['evidence', 'current', 'mean'] }, { source_type: 'metric_result', source_id: 'lens-metric', locator: ['current_state', 'trend', 'direction'] }] }, { id: 'no-references', statement: 'No reference finding', evidence_refs: [] }] } })
    await screen.findByText('Run summary')
    await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    expect(screen.getAllByText('References')).toHaveLength(1)
    const references = screen.getByText('References').closest('details')!
    expect(references.open).toBe(false)
    await userEvent.click(screen.getByText('References'))
    expect(within(references).getByText(/Metric result · lens-metric · evidence.current.mean/)).toBeTruthy()
    expect(within(references).getByText(/Metric result · lens-metric · current_state.trend.direction/)).toBeTruthy()
    const controls = references.querySelectorAll('details')
    expect(controls).toHaveLength(2)
    expect([...controls].every((control) => !control.open)).toBe(true)
  })

  it('keeps Summary cards aligned to their own content height', async () => {
    renderDetail()
    await screen.findByText('Run summary')
    const summaryGrid = screen.getByText('Run summary').closest('article')?.parentElement
    expect(summaryGrid?.className).toContain('items-start')
  })

  it('links a recognized historical citation to its immutable version without substituting a newer approval', async () => {
    const current = detail()
    renderDetail({ ...current, analysis: { ...current.analysis!, hypotheses: [{ ...current.analysis!.hypotheses[0], knowledge_refs: [{ source_id: 'knowledge-document:123e4567-e89b-12d3-a456-426614174000:v1', reference: 'pdf:page:7:chunk:2' }] }] } })
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Analysis' }))
    const citation = screen.getByRole('link', { name: /Knowledge · knowledge-document/ })
    expect(citation.getAttribute('href')).toBe('/knowledge?document=123e4567-e89b-12d3-a456-426614174000&version=1&reference=pdf%3Apage%3A7%3Achunk%3A2')
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
    const unavailable = screen.getByText(expected).closest('[role="status"]')
    expect(unavailable?.className).toContain(state.status === 'running' ? 'color-info' : 'color-surface-muted')
  })

  it('keeps a failed run alert distinct from neutral missing sections', async () => {
    const current = detail()
    renderDetail({ ...current, summary: { ...current.summary, status: 'failed', reason: { code: 'no_usable_lens_results', component: 'usable_results_gate' } }, relationship_evaluations: [], report: null })
    await screen.findByText('Run summary')
    expect(screen.getByRole('alert').textContent).toContain('Execution failed')
    await userEvent.click(screen.getByRole('tab', { name: 'Relationships' }))
    const relationships = screen.getByText('Execution failed before this artifact was produced.').closest('[role="status"]')
    expect(relationships?.className).toContain('color-surface-muted')
    await userEvent.click(screen.getByRole('tab', { name: 'Report' }))
    const report = screen.getByText('Execution failed before the report was produced.').closest('[role="status"]')
    expect(report?.className).toContain('color-surface-muted')
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

  it('copies the exact readable persisted Markdown while presenting it as a safe document', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    const reportContent = '# Observation report\n\nObjective summary: Assess cooling stability.\n\nObserved UTC window: 2026-09-09T09:00:00Z to 2026-09-09T10:00:00Z.\n\n## Findings\n\n### **1. Cooling temperature increased**\n\nThe current observation increased during the observed window.\n\n## Technical appendix\n\n- Finding 1 source ID: `finding-1`\n- Metric result · `lens-metric` · `evidence.current`'
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    const current = detail()
    renderDetail({ ...current, report: { ...current.report!, content: reportContent } })
    await screen.findByText('Run summary'); await userEvent.click(screen.getByRole('tab', { name: 'Report' })); await userEvent.click(screen.getByRole('button', { name: 'Copy Markdown' }))
    expect(writeText).toHaveBeenCalledWith(reportContent)
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Observation report' }).tagName).toBe('H1')
    expect(screen.getByRole('heading', { name: '1. Cooling temperature increased' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: '1. Cooling temperature increased' }).querySelector('strong')?.textContent).toBe('1. Cooling temperature increased')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('finding-1').tagName).toBe('CODE')
  })
})
