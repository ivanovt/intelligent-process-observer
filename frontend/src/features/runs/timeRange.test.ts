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

  it('resolves the exact absolute UTC example without browser-local interpretation', () => {
    const clock = vi.fn(() => new Date('2026-09-10T18:00:00.000Z'))
    expect(resolveTimeRange({ kind: 'absolute', from: '2026-09-10T10:00:00', to: '2026-09-10T17:00:00' }, clock)).toEqual({
      ok: true,
      value: { from: '2026-09-10T10:00:00.000Z', to: '2026-09-10T17:00:00.000Z' },
    })
    expect(clock).toHaveBeenCalledOnce()
  })

  it('preserves supplied second precision and treats minute precision as zero seconds', () => {
    const clock = () => new Date('2026-09-10T18:00:00.000Z')
    expect(resolveTimeRange({ kind: 'absolute', from: '2026-09-10T10:00', to: '2026-09-10T17:00:45' }, clock)).toEqual({
      ok: true,
      value: { from: '2026-09-10T10:00:00.000Z', to: '2026-09-10T17:00:45.000Z' },
    })
  })

  it('rejects missing, malformed, and impossible absolute UTC endpoints', () => {
    const clock = () => new Date('2026-09-10T18:00:00.000Z')
    for (const input of [
      { from: '', to: '2026-09-10T17:00:00' },
      { from: '2026-09-10T10:00:00', to: '' },
      { from: '2026-09-10 10:00:00', to: '2026-09-10T17:00:00' },
      { from: '2026-02-29T10:00:00', to: '2026-09-10T17:00:00' },
      { from: '2026-09-10T10:00:00Z', to: '2026-09-10T17:00:00' },
    ]) {
      expect(resolveTimeRange({ kind: 'absolute', ...input }, clock)).toEqual({ ok: false, error: 'Enter valid UTC date-times for From and To.' })
    }
  })

  it('applies the shared ordering and future validation to absolute UTC windows', () => {
    const clock = () => new Date('2026-09-10T17:00:00.000Z')
    expect(resolveTimeRange({ kind: 'absolute', from: '2026-09-10T17:00:00', to: '2026-09-10T17:00:00' }, clock)).toEqual({ ok: false, error: 'From must be earlier than To.' })
    expect(resolveTimeRange({ kind: 'absolute', from: '2026-09-10T17:00:00', to: '2026-09-10T10:00:00' }, clock)).toEqual({ ok: false, error: 'From must be earlier than To.' })
    expect(resolveTimeRange({ kind: 'absolute', from: '2026-09-10T10:00:00', to: '2026-09-10T17:00:01' }, clock)).toEqual({ ok: false, error: 'To cannot be in the future.' })
  })
})
