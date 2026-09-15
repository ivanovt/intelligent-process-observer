import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricResultPresentation } from './metricPresentation'
import type { UsableMetricRunResult } from './types'

const result: UsableMetricRunResult = {
  schema_version: '1.0',
  lens_type: 'metric',
  identity: { observation_id: 'observation', observation_run_id: 'run', lens_id: 'metric-1', lens_run_id: 'lens-run-1', metric_ref: 'cooling_temperature', unit: '°C' },
  status: { state: 'partial' },
  reason: { code: 'reference_unavailable', component: 'reference_periods' },
  analysis_window: { from: '2026-09-09T09:00:00Z', to: '2026-09-09T10:00:00Z' },
  data_quality: 'good',
  current_state: { trend: { direction: 'increasing', rate: 'moderate' }, variability: { state: 'high' }, spike: { state: 'present' }, oscillation: { state: 'absent' }, stuck_signal: { state: 'unknown' } },
  reference_periods: [{ offset: '1d', analysis_window: { from: '2026-09-08T09:00:00Z', to: '2026-09-08T10:00:00Z' }, level: { relation: 'higher' }, trend: { direction: 'increasing', rate: 'moderate', direction_relation: 'same', rate_relation: 'faster' }, variability: { state: 'low', relation: 'lower' } }],
  history: null,
  evidence: {
    current: { mean: 2.28, std: 0.4, min: 1.8, max: 2.9, slope: 0.00000042, spike: { method: 'modified_z', detected_sample_count: 1, detected_timestamps: ['2026-09-09T09:10:00Z'], max_abs_modified_z: 4 }, oscillation: { deadband: 0.1, significant_residual_count: 2, sign_change_count: 1, sign_change_ratio: 0.5 }, stuck_signal: { repeated_value: 2.4, longest_run_sample_count: 2, longest_run_share: 0.4 } },
    reference_periods: [{ offset: '1d', analysis_window: { from: '2026-09-08T09:00:00Z', to: '2026-09-08T10:00:00Z' }, mean: 1.04, std: 0.2, min: 0.8, max: 1.2, slope: 0.02, relative_level_change: 0.7456 }],
    history: null,
  },
}

describe('MetricResultPresentation', () => {
  it('keeps usable evidence perspectives and optional states distinct', () => {
    render(<MetricResultPresentation result={result} reason={{ code: 'reference_unavailable', component: 'reference_periods' }} />)

    expect(screen.getByText('Current semantic state')).toBeTruthy()
    expect(screen.getByText('Current numerical evidence')).toBeTruthy()
    expect(screen.getByText('4.200e-7')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: present')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: absent')).toBeTruthy()
    expect(screen.getByText((_content, element) => element?.tagName === 'P' && element.textContent === 'State: unknown')).toBeTruthy()
    expect(screen.getByText('Symmetric relative change')).toBeTruthy()
    expect(screen.getAllByText('2.28')).toHaveLength(2)
    expect(screen.getByText('1.04')).toBeTruthy()
    expect(screen.getByText('Trend direction relation')).toBeTruthy()
    expect(screen.getByText('Trend rate relation')).toBeTruthy()
    expect(screen.getByText('Variability relation')).toBeTruthy()
    expect(screen.getByText('faster')).toBeTruthy()
    expect(screen.getByText('lower')).toBeTruthy()
    expect(screen.getByText('Unavailable in this result.')).toBeTruthy()
    expect(document.body.textContent).not.toContain('74.56% increase')
    expect(document.body.textContent).not.toContain('Time series')
  })

  it('keeps null optional and reference sections unavailable without inventing evidence', () => {
    render(<MetricResultPresentation result={{ ...result, current_state: { ...result.current_state, spike: null }, reference_periods: null, evidence: { ...result.evidence, current: { ...result.evidence.current, spike: null }, reference_periods: null } }} reason={{ code: 'reference_unavailable', component: 'reference_periods' }} />)

    expect(screen.getByText('Reference-period comparison is limited: reference_unavailable.')).toBeTruthy()
    expect(screen.queryByText('Reference period: 7d')).toBeNull()
    expect(screen.getByText('Spike analysis').parentElement?.textContent).toContain('Unavailable in this result.')
    expect(screen.getByText('Persisted History')).toBeTruthy()
    expect(screen.getAllByText('Unavailable in this result.')).toHaveLength(2)
  })
})
