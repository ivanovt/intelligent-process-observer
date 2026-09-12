import { describe, expect, it } from 'vitest'
import { formatMetricNumber } from './metricFormatting'

describe('formatMetricNumber', () => {
  it('keeps a small non-zero slope visible without mutating its meaning', () => {
    expect(formatMetricNumber(0.00000042)).toBe('4.200e-7')
  })

  it('formats scan values and avoids negative zero', () => {
    expect(formatMetricNumber(12.345678)).toBe('12.346')
    expect(formatMetricNumber(-0)).toBe('0')
    expect(formatMetricNumber(Number.NaN)).toBe('Unavailable')
  })
})
