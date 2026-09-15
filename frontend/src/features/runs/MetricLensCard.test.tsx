import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MetricLensCard } from './MetricLensCard'
import type { FailedMetricRunResult, InsufficientMetricRunResult, ObservationRunLensRun, UsableMetricRunResult } from './types'

const usableResult: UsableMetricRunResult = {
  schema_version: '1.0', lens_type: 'metric', identity: { observation_id: 'observation-1', observation_run_id: 'run-1', lens_id: 'metric-1', lens_run_id: 'lens-run-1', metric_ref: 'cooling_temperature', unit: '°C' }, status: { state: 'partial' }, data_quality: 'good', analysis_window: { from: '2026-09-09T09:00:00Z', to: '2026-09-09T10:00:00Z' }, reason: { code: 'reference_unavailable', component: 'reference_periods' },
  current_state: { trend: { direction: 'increasing', rate: 'moderate' }, variability: { state: 'high' }, spike: null, oscillation: null, stuck_signal: null },
  reference_periods: [{ offset: '1d', analysis_window: { from: '2026-09-08T09:00:00Z', to: '2026-09-08T10:00:00Z' }, level: { relation: 'higher' }, trend: { direction: 'increasing', rate: 'moderate', direction_relation: 'same', rate_relation: 'faster' }, variability: { state: 'low', relation: 'lower' } }],
  history: { direction: 'stable', pattern: 'sustained', run_ids: ['previous-run-1', 'previous-run-2'] },
  evidence: { current: { mean: 2.28, std: 0.4, min: 1.8, max: 2.9, slope: 0.00000042, spike: null, oscillation: null, stuck_signal: null }, reference_periods: [{ offset: '1d', analysis_window: { from: '2026-09-08T09:00:00Z', to: '2026-09-08T10:00:00Z' }, mean: 1.04, std: 0.2, min: 0.8, max: 1.2, slope: 0.02, relative_level_change: 0.7456 }], history: { level_change_tolerance: 0.1, classifiable_transitions: 2, unknown_transitions: 0, increasing_transitions: 0, decreasing_transitions: 0, stable_transitions: 2, direction_changes: 0 } },
}

function lens(result: ObservationRunLensRun['result'], status: ObservationRunLensRun['status'], reason: ObservationRunLensRun['reason'] = null): ObservationRunLensRun {
  return { id: 'lens-run-1', lens_id: 'metric-1', lens_type: 'metric', status, reason, started_at: '2026-09-09T09:00:00Z', finished_at: null, duration_seconds: null, result }
}

describe('MetricLensCard', () => {
  it('orders usable partial evidence without inventing missing reference periods', () => {
    render(<MetricLensCard lens={lens(usableResult, 'partial')} selected={false} onSelect={vi.fn()} />)

    expect(screen.getByText('cooling_temperature')).toBeTruthy()
    expect(screen.getByText('Data quality: good')).toBeTruthy()
    expect(screen.getByText('Partial')).toBeTruthy()
    expect(screen.getByText('Trend direction')).toBeTruthy()
    expect(screen.getByText('Trend rate')).toBeTruthy()
    expect(screen.getByText('Variability')).toBeTruthy()
    expect(screen.getByText('Mean')).toBeTruthy()
    expect(screen.getByText('Range')).toBeTruthy()
    expect(screen.getByText('Slope')).toBeTruthy()
    expect(screen.getByText('1d returned')).toBeTruthy()
    expect(screen.getByText('stable / sustained')).toBeTruthy()
    expect(screen.queryByText('7d returned')).toBeNull()
    expect(screen.getByText(/Limitation: reference_unavailable/)).toBeTruthy()
    expect(Array.from(document.querySelectorAll('svg')).every((icon) => icon.getAttribute('aria-hidden') === 'true')).toBe(true)
    expect(document.querySelector('.lucide-trending-up')).toBeTruthy()
  })

  it('keeps the full card summary readable in its stable scanning order in a split-width column', () => {
    render(<div style={{ width: '520px' }}><MetricLensCard lens={lens({ ...usableResult, identity: { ...usableResult.identity, metric_ref: 'cooling_temperature_return_line_with_a_long_provider_reference' } }, 'partial')} selected={false} onSelect={vi.fn()} /></div>)

    const card = screen.getByRole('button', { name: /cooling_temperature_return_line_with_a_long_provider_reference/i })
    const semanticState = screen.getByLabelText('Current semantic state')
    const evidenceSummary = screen.getByLabelText('Evidence summary')
    const semanticLabels = ['Trend direction', 'Trend rate', 'Variability'].map((label) => screen.getByText(label))
    const evidenceLabels = ['Mean', 'Range', 'Slope', 'Reference availability', 'Persisted History'].map((label) => screen.getByText(label))

    expect(card).toBeTruthy()
    expect(semanticLabels.every((label) => semanticState.contains(label))).toBe(true)
    expect(evidenceLabels.every((label) => evidenceSummary.contains(label))).toBe(true)
    expect(semanticState.compareDocumentPosition(evidenceSummary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    for (let index = 1; index < evidenceLabels.length; index += 1) {
      expect(evidenceLabels[index - 1].compareDocumentPosition(evidenceLabels[index]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
  })

  it('shows completed-insufficient and failed variants as unavailable without numerical evidence', () => {
    const insufficient: InsufficientMetricRunResult = { schema_version: '1.0', lens_type: 'metric', identity: usableResult.identity, status: { state: 'completed' }, data_quality: 'insufficient', analysis_window: usableResult.analysis_window }
    const { rerender } = render(<MetricLensCard lens={lens(insufficient, 'completed')} selected={false} onSelect={vi.fn()} />)
    expect(screen.getByText('Current semantic state: unavailable')).toBeTruthy()
    expect(screen.getByText('Current Metric data was insufficient for usable evidence.')).toBeTruthy()
    expect(screen.queryByText('Mean')).toBeNull()

    const failed: FailedMetricRunResult = { schema_version: '1.0', lens_type: 'metric', identity: usableResult.identity, status: { state: 'failed', error: { code: 'current_metric_acquisition_failed', message: 'Current metric data acquisition failed.' } }, analysis_window: usableResult.analysis_window }
    rerender(<MetricLensCard lens={lens(failed, 'failed')} selected={false} onSelect={vi.fn()} />)
    expect(screen.getByText('Failed')).toBeTruthy()
    expect(screen.getByText('Current Metric evidence was unavailable. Current metric data acquisition failed.')).toBeTruthy()
    expect(screen.queryByText('Data quality: good')).toBeNull()
    expect(screen.queryByText('Mean')).toBeNull()
  })

  it('keeps artifact-free lifecycle cards honest and selectable', () => {
    const onSelect = vi.fn()
    render(<MetricLensCard lens={lens(null, 'running', { code: 'awaiting_provider', component: 'acquisition' })} selected onSelect={onSelect} />)

    const card = screen.getByRole('button', { name: /metric-1.*Running/i })
    expect(card.getAttribute('aria-label')).toBeNull()
    expect(card.getAttribute('aria-pressed')).toBe('true')
    card.click()
    expect(onSelect).toHaveBeenCalledOnce()
    expect(screen.getByText('This Lens is still progressing; no result artifact is durable yet.')).toBeTruthy()
    expect(screen.getByText('Duration: In progress')).toBeTruthy()
    expect(screen.queryByText('Unit: °C')).toBeNull()
    expect(screen.queryByText('Mean')).toBeNull()
  })
})
