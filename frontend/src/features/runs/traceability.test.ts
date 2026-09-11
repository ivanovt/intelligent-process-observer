import { describe, expect, it } from 'vitest'
import { formatLocator, resolveTraceability } from './traceability'
import type { EvidenceReference, ObservationRunDetail } from './types'

const detail = { lens_runs: [{ id: 'metric-run', lens_type: 'metric', result: { evidence: { current: { mean: 2.28, values: ['first'] } } } }], relationship_evaluations: [{ relationship_id: 'relationship-1', expectations: [{ observed: 'high' }] }] } as unknown as ObservationRunDetail

describe('run-detail traceability resolver', () => {
  it('resolves metric and relationship paths through own properties and array indices', () => {
    const metric: EvidenceReference = { source_type: 'metric_result', source_id: 'metric-run', locator: ['evidence', 'current', 'values', 0] }
    const relationship: EvidenceReference = { source_type: 'relationship_evaluation', source_id: 'relationship-1', locator: ['expectations', 0, 'observed'] }
    expect(resolveTraceability(detail, metric)).toMatchObject({ available: true, locator: 'evidence.current.values[0]', value: 'first' })
    expect(resolveTraceability(detail, relationship)).toMatchObject({ available: true, locator: 'expectations[0].observed', value: 'high' })
  })

  it('keeps repeated sources distinct by locator and rejects missing or hostile paths', () => {
    const mean: EvidenceReference = { source_type: 'metric_result', source_id: 'metric-run', locator: ['evidence', 'current', 'mean'] }
    const values: EvidenceReference = { source_type: 'metric_result', source_id: 'metric-run', locator: ['evidence', 'current', 'values', 1] }
    const hostile: EvidenceReference = { source_type: 'metric_result', source_id: 'metric-run', locator: ['__proto__'] }
    expect(resolveTraceability(detail, mean)).toMatchObject({ available: true, value: 2.28 })
    expect(resolveTraceability(detail, values)).toMatchObject({ available: false })
    expect(resolveTraceability(detail, hostile)).toMatchObject({ available: false })
    expect(formatLocator(['weird key', 2, 'value'])).toBe('["weird key"][2].value')
  })
})
