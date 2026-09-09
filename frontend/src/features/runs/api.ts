import { RunApiError, type ApiErrorEnvelope, type ObservationRunDetail, type ObservationRunLaunchRequest, type ObservationRunSummary } from './types'

const baseUrl = '/api/v1'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, options)
  if (!response.ok) {
    let payload: ApiErrorEnvelope | undefined
    try { payload = await response.json() as ApiErrorEnvelope } catch { /* retain a safe generic failure */ }
    throw new RunApiError(response.status, payload?.code ?? 'request_failed', payload?.message ?? `Request failed (${response.status}).`, payload?.field)
  }
  return response.json() as Promise<T>
}

/** Retrieves the complete newest-first ObservationRun history without pagination. */
export function listObservationRuns(signal?: AbortSignal) { return request<ObservationRunSummary[]>('/observation-runs', { signal }) }
/** Retrieves one coherent public run-detail aggregate by stable run identity. */
export function getObservationRun(observationRunId: string, signal?: AbortSignal) { return request<ObservationRunDetail>(`/observation-runs/${encodeURIComponent(observationRunId)}`, { signal }) }
/** Submits one concrete UTC time window for server-owned asynchronous run launch. */
export function launchObservationRun(payload: ObservationRunLaunchRequest, signal?: AbortSignal) { return request<ObservationRunSummary>('/observation-runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal }) }
