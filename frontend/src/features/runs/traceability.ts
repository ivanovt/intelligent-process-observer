import type { EvidenceReference, ObservationRunDetail } from './types'

const forbiddenSegments = new Set(['__proto__', 'prototype', 'constructor'])
const identifierSegment = /^[A-Za-z_$][A-Za-z0-9_$]*$/
const unresolved = Symbol('unresolved')

/** One locally resolved traceability target, or an explicit unavailable outcome. */
export type TraceabilityResolution = { available: true; sourceLabel: string; sourceId: string; locator: string; value: unknown } | { available: false; sourceLabel: string; sourceId: string; locator: string }

/** Resolves a retained public evidence reference without fetching mutable or provider data. */
export function resolveTraceability(detail: ObservationRunDetail, reference: EvidenceReference): TraceabilityResolution {
  const locator = formatLocator(reference.locator)
  const sourceLabel = reference.source_type === 'metric_result' ? 'Metric result' : reference.source_type === 'relationship_evaluation' ? 'Relationship evaluation' : 'Evidence reference'
  if (!isSafeLocator(reference.locator)) return unavailable(sourceLabel, reference.source_id, locator)
  const source = reference.source_type === 'metric_result'
    ? detail.lens_runs.find((run) => run.id === reference.source_id && run.lens_type === 'metric')?.result
    : reference.source_type === 'relationship_evaluation'
      ? detail.relationship_evaluations.find((evaluation) => evaluation.relationship_id === reference.source_id)
      : undefined
  const value = source === undefined || source === null ? undefined : traverseOwn(source, reference.locator)
  return value === unresolved ? unavailable(sourceLabel, reference.source_id, locator) : { available: true, sourceLabel, sourceId: reference.source_id, locator, value }
}

/** Formats a structured locator using familiar dotted keys and decimal array indexes. */
export function formatLocator(locator: readonly (string | number)[]): string {
  if (!locator.length) return '(root)'
  return locator.map((segment, index) => typeof segment === 'number' ? `[${segment}]` : identifierSegment.test(segment) ? `${index === 0 ? '' : '.'}${segment}` : `[${JSON.stringify(segment)}]`).join('')
}

/** Formats a locally resolved public value without interpreting it as markup. */
export function formatResolvedValue(value: unknown) { if (value === null) return 'null'; if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value); try { return JSON.stringify(value) } catch { return '[structured value unavailable]' } }

export function compactTraceabilityId(id: string) { return id.length > 18 ? `${id.slice(0, 12)}…${id.slice(-4)}` : id }
function unavailable(sourceLabel: string, sourceId: string, locator: string): TraceabilityResolution { return { available: false, sourceLabel, sourceId, locator } }
function isSafeLocator(locator: readonly (string | number)[]) { return locator.length > 0 && locator.every((segment) => typeof segment === 'number' ? Number.isInteger(segment) && segment >= 0 : typeof segment === 'string' && segment.length > 0 && !forbiddenSegments.has(segment)) }
function traverseOwn(value: unknown, locator: readonly (string | number)[]): unknown | typeof unresolved { let current: unknown = value; for (const segment of locator) { if (Array.isArray(current)) { if (typeof segment !== 'number' || !Number.isInteger(segment) || segment < 0 || segment >= current.length) return unresolved; current = current[segment]; continue } if (typeof current !== 'object' || current === null || typeof segment !== 'string' || !Object.hasOwn(current, segment)) return unresolved; current = (current as Record<string, unknown>)[segment] } return current }
