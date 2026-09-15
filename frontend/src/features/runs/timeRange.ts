/** A clock is injected so range resolution is deterministic and both endpoints share one instant. */
export type Clock = () => Date

export const relativePresets = [
  { id: '5m', label: 'Last 5 minutes', milliseconds: 5 * 60_000 },
  { id: '15m', label: 'Last 15 minutes', milliseconds: 15 * 60_000 },
  { id: '30m', label: 'Last 30 minutes', milliseconds: 30 * 60_000 },
  { id: '1h', label: 'Last 1 hour', milliseconds: 60 * 60_000 },
  { id: '3h', label: 'Last 3 hours', milliseconds: 3 * 60 * 60_000 },
  { id: '6h', label: 'Last 6 hours', milliseconds: 6 * 60 * 60_000 },
  { id: '12h', label: 'Last 12 hours', milliseconds: 12 * 60 * 60_000 },
  { id: '24h', label: 'Last 24 hours', milliseconds: 24 * 60 * 60_000 },
  { id: '2d', label: 'Last 2 days', milliseconds: 2 * 24 * 60 * 60_000 },
  { id: '7d', label: 'Last 7 days', milliseconds: 7 * 24 * 60 * 60_000 },
] as const

export type RelativePresetId = (typeof relativePresets)[number]['id']
export type TimeRangeInput =
  | { kind: 'preset'; preset: RelativePresetId }
  | { kind: 'expressions'; from: string; to: string }
  | { kind: 'absolute'; from: string; to: string }

export type ResolvedTimeRange = { from: string; to: string }
export type TimeRangeResolution = { ok: true; value: ResolvedTimeRange } | { ok: false; error: string }

const expressionOffsets: Readonly<Record<string, number>> = { now: 0, 'now-15m': 15 * 60_000, 'now-1h': 60 * 60_000 }

/** Resolves an approved relative preset, expression, or absolute UTC range against one captured instant. */
export function resolveTimeRange(input: TimeRangeInput, clock: Clock): TimeRangeResolution {
  const now = clock()
  if (Number.isNaN(now.getTime())) return { ok: false, error: 'The current time is unavailable. Try again.' }

  if (input.kind === 'preset') {
    const preset = relativePresets.find((candidate) => candidate.id === input.preset)
    if (!preset) return { ok: false, error: 'Choose one of the supported relative ranges.' }
    return validateResolvedRange(new Date(now.getTime() - preset.milliseconds), now, now)
  }

  if (input.kind === 'expressions') {
    const fromOffset = expressionOffsets[input.from]
    const toOffset = expressionOffsets[input.to]
    if (fromOffset === undefined || toOffset === undefined) {
      return { ok: false, error: 'Use exactly now, now-15m, or now-1h for both range expressions.' }
    }
    return validateResolvedRange(new Date(now.getTime() - fromOffset), new Date(now.getTime() - toOffset), now)
  }

  const from = parseAbsoluteUtc(input.from)
  const to = parseAbsoluteUtc(input.to)
  if (!from || !to) return { ok: false, error: 'Enter valid UTC date-times for From and To.' }
  return validateResolvedRange(from, to, now)
}

/** Validates a concrete range before it crosses the public launch boundary. */
export function validateResolvedRange(from: Date, to: Date, now: Date): TimeRangeResolution {
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) {
    return { ok: false, error: 'Enter valid UTC date-times for From and To.' }
  }
  if (from.getTime() >= to.getTime()) return { ok: false, error: 'From must be earlier than To.' }
  if (to.getTime() > now.getTime()) return { ok: false, error: 'To cannot be in the future.' }
  return { ok: true, value: { from: from.toISOString(), to: to.toISOString() } }
}

const absoluteUtcPattern = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/

/** Parses the zone-less datetime-local control value as a UTC calendar date-time. */
function parseAbsoluteUtc(value: string): Date | undefined {
  const match = absoluteUtcPattern.exec(value)
  if (!match) return undefined

  const [, yearText, monthText, dayText, hourText, minuteText, secondText] = match
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const hour = Number(hourText)
  const minute = Number(minuteText)
  const second = secondText === undefined ? 0 : Number(secondText)
  const date = new Date(0)
  date.setUTCFullYear(year, month - 1, day)
  date.setUTCHours(hour, minute, second, 0)

  if (
    year < 1
    || date.getUTCFullYear() !== year
    || date.getUTCMonth() !== month - 1
    || date.getUTCDate() !== day
    || date.getUTCHours() !== hour
    || date.getUTCMinutes() !== minute
    || date.getUTCSeconds() !== second
  ) return undefined

  return date
}
