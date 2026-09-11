import { RunApiError, type ApiErrorEnvelope } from '../runs/types'
import type { OverviewRuntimeFeed } from './types'

const baseUrl = '/api/v1'

/** Retrieves the resilient newest-first runtime projection used only by Overview. */
export async function getOverviewRuntime(signal?: AbortSignal): Promise<OverviewRuntimeFeed> {
  const response = await fetch(`${baseUrl}/overview-runtime`, { signal })
  if (!response.ok) {
    let payload: ApiErrorEnvelope | undefined
    try { payload = await response.json() as ApiErrorEnvelope } catch { /* retain a safe generic failure */ }
    throw new RunApiError(response.status, payload?.code ?? 'request_failed', payload?.message ?? `Request failed (${response.status}).`, payload?.field)
  }
  return response.json() as Promise<OverviewRuntimeFeed>
}
