/** Formats finite Metric values for scanning while preserving small non-zero values. */
export function formatMetricNumber(value: number): string {
  if (!Number.isFinite(value)) return 'Unavailable'
  if (Object.is(value, -0)) return '0'
  const absolute = Math.abs(value)
  if (absolute !== 0 && (absolute < 0.0001 || absolute >= 1_000_000)) return value.toExponential(3)
  return new Intl.NumberFormat(undefined, { maximumSignificantDigits: 5 }).format(value)
}
