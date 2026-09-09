import { describe, expect, it, vi } from 'vitest'
import { relativePresets, resolveTimeRange, validateResolvedRange } from './timeRange'

const instant = new Date('2026-09-09T12:00:00.000Z')

describe('resolveTimeRange', () => {
  it('resolves every approved relative preset from one injected UTC instant', () => {
    for (const preset of relativePresets) {
      const clock = vi.fn(() => instant)
      const result = resolveTimeRange({ kind: 'preset', preset: preset.id }, clock)
      expect(result).toEqual({ ok: true, value: { from: new Date(instant.getTime() - preset.milliseconds).toISOString(), to: instant.toISOString() } })
      expect(clock).toHaveBeenCalledOnce()
    }
  })

  it('resolves both supported expression endpoints against one captured instant', () => {
    const clock = vi.fn(() => instant)
    expect(resolveTimeRange({ kind: 'expressions', from: 'now-15m', to: 'now' }, clock)).toEqual({ ok: true, value: { from: '2026-09-09T11:45:00.000Z', to: '2026-09-09T12:00:00.000Z' } })
    expect(clock).toHaveBeenCalledOnce()
  })

  it('accepts each approved expression where it creates a forward finite range', () => {
    expect(resolveTimeRange({ kind: 'expressions', from: 'now-1h', to: 'now-15m' }, () => instant).ok).toBe(true)
    expect(resolveTimeRange({ kind: 'expressions', from: 'now-1h', to: 'now' }, () => instant).ok).toBe(true)
    expect(validateResolvedRange(new Date('2026-09-09T11:00:00Z'), new Date('2026-09-09T12:01:00Z'), instant)).toEqual({ ok: false, error: 'To cannot be in the future.' })
  })

  it('accepts only the exact closed expression vocabulary and validates ordering', () => {
    for (const expression of ['now-5m', ' now', 'NOW', '2026-09-09T12:00:00Z', 'now-1d']) {
      const result = resolveTimeRange({ kind: 'expressions', from: expression, to: 'now' }, () => instant)
      expect(result.ok).toBe(false)
    }
    expect(resolveTimeRange({ kind: 'expressions', from: 'now', to: 'now' }, () => instant)).toEqual({ ok: false, error: 'From must be earlier than To.' })
    expect(resolveTimeRange({ kind: 'expressions', from: 'now', to: 'now-1h' }, () => instant)).toEqual({ ok: false, error: 'From must be earlier than To.' })
  })
})
