import { afterEach, describe, expect, it, vi } from 'vitest'
import { updateObservation } from './api'
import type { ObservationCreate, ObservationResponse } from './types'

const payload:ObservationCreate={name:'Cooling health',description:null,objective:'Observe cooling',lenses:[],alert_lenses:[],relationships:[]}
const canonical={id:'observation-1',schema_version:1,href:'/api/v1/observations/observation-1',...payload} as ObservationResponse

describe('Observation aggregate update API',()=>{
  afterEach(()=>vi.unstubAllGlobals())
  it('uses one exact aggregate PUT request with the serializable mutable payload',async()=>{
    const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify(canonical),{status:200}))
    vi.stubGlobal('fetch',fetchMock)
    await expect(updateObservation('observation/1',payload)).resolves.toEqual(canonical)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/observations/observation%2F1',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
  })
})
