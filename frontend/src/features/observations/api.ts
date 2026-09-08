import { ApiError, type ApiErrorEnvelope, type ObservationResponse, type ObservationSummary } from './types'
const baseUrl='/api/v1'
async function request<T>(path:string,signal?:AbortSignal):Promise<T> { const response=await fetch(`${baseUrl}${path}`,{signal}); if(!response.ok) { let payload:ApiErrorEnvelope|undefined; try { payload=await response.json() as ApiErrorEnvelope } catch { /* generic error */ } throw new ApiError(response.status,payload?.code??'request_failed',payload?.message??`Request failed (${response.status}).`,payload?.field) } return response.json() as Promise<T> }
/** Retrieves compact Observation definitions. */ export function listObservations(signal?:AbortSignal) { return request<ObservationSummary[]>('/observations',signal) }
/** Retrieves one complete, read-only Observation definition. */ export function getObservation(id:string,signal?:AbortSignal) { return request<ObservationResponse>(`/observations/${encodeURIComponent(id)}`,signal) }
