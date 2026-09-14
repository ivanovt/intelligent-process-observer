import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DefinitionReview } from './DefinitionReview'
import { hydrateDraft, serializeDraft, validateDraft } from './draft'
import type { ObservationResponse } from './types'

const response: ObservationResponse = {
  id: 'observation-1',
  name: 'Cooling health',
  description: null,
  objective: 'Observe cooling',
  operational_context: null,
  schema_version: 1,
  lenses: [],
  alert_lenses: [{
    id: 'cooling-alerts',
    name: 'Cooling alerts',
    type: 'alert',
    href: '/api/v1/observations/observation-1/alert-lenses/cooling-alerts',
    description: null,
    source: 'jira_track_and_release',
    selector: { query: 'project = COOL' },
    analysis_objectives: [],
    reference_periods: [],
    observation_href: '/api/v1/observations/observation-1',
  }],
  relationships: [],
  href: '/api/v1/observations/observation-1',
  knowledge_scope: {
    services: [
      { service_id: 'mprm-server', service_version: '1.0' },
      { service_id: 'gateway', service_version: null },
    ],
  },
}

describe('per-service knowledge scope draft', () => {
  it('hydrates and serializes independently versioned services without mutating the response', () => {
    const draft = hydrateDraft(response)
    expect(serializeDraft(draft).knowledge_scope).toEqual(response.knowledge_scope)
    draft.knowledge_scope!.services[0].service_version = '2.0'
    expect(response.knowledge_scope!.services[0].service_version).toBe('1.0')
    expect(serializeDraft(draft).knowledge_scope).toEqual({
      services: [
        { service_id: 'mprm-server', service_version: '2.0' },
        { service_id: 'gateway', service_version: null },
      ],
    })
  })

  it('pairs each service with its own version in review and rejects a blank version', () => {
    const draft = hydrateDraft(response)
    render(<DefinitionReview definition={draft} />)
    expect(screen.getByText('mprm-server · 1.0')).toBeTruthy()
    expect(screen.getByText('gateway · all versions')).toBeTruthy()
    draft.knowledge_scope!.services[1].service_version = ' '
    expect(validateDraft(draft)['knowledge_scope.services.1.service_version']).toBe('Version cannot be blank.')
  })
})
