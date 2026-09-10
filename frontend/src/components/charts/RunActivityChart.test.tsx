import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { RunActivityChart } from './RunActivityChart'
import type { RunActivityItem } from '../../features/overview/projections'

function activity(id: number, status: RunActivityItem['status']): RunActivityItem {
  return { observationRunId: `run-${id}`, observationId: 'observation-a', createdAt: `2026-09-${String(id).padStart(2, '0')}T10:00:00Z`, status }
}

describe('RunActivityChart', () => {
  it('keeps all five exact execution tokens, exposes nonvisual counts, bounds fourteen runs, and links to Runs', () => {
    const items = Array.from({ length: 15 }, (_, index) => activity(index + 1, ['pending', 'running', 'completed', 'failed', 'cancelled'][index % 5] as RunActivityItem['status']))
    render(<MemoryRouter><RunActivityChart activity={items} /></MemoryRouter>)

    const legend = screen.getByLabelText('Execution status legend')
    expect(within(legend).getByText('Pending')).toBeTruthy()
    expect(within(legend).getByText('Running')).toBeTruthy()
    expect(within(legend).getByText('Completed')).toBeTruthy()
    expect(within(legend).getByText('Failed')).toBeTruthy()
    expect(within(legend).getByText('Cancelled')).toBeTruthy()
    expect(screen.getByText('Run activity status counts: Pending: 2; Running: 3; Completed: 3; Failed: 3; Cancelled: 3.')).toBeTruthy()
    const chronology = screen.getByLabelText('Chronological run activity')
    expect(within(chronology).getAllByRole('listitem')).toHaveLength(14)
    expect(chronology.textContent).toContain('Sep 2')
    expect(chronology.textContent).not.toContain('Sep 1,')
    expect(screen.getByRole('img', { name: 'Run activity chart showing exact ObservationRun execution statuses' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'View all Runs' }).getAttribute('href')).toBe('/runs')
    expect(screen.queryByText(/Significant findings present/)).toBeNull()
  })

  it('states explicitly when successful history contains no runs', () => {
    render(<MemoryRouter><RunActivityChart activity={[]} /></MemoryRouter>)
    expect(screen.getByText('No Observation runs exist yet.')).toBeTruthy()
    expect(screen.queryByRole('img')).toBeNull()
  })
})
