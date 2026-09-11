import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { RunActivityChart } from './RunActivityChart'
import type { RunActivityItem } from '../../features/overview/projections'

function activity(id: number, status: RunActivityItem['status']): RunActivityItem {
  return { observationRunId: `run-${id}`, observationId: 'observation-a', createdAt: `2026-09-${String(id).padStart(2, '0')}T10:00:00Z`, availability: 'available', status }
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
    expect(screen.getByText('Run activity status counts: Pending: 2; Running: 3; Completed: 3; Failed: 3; Cancelled: 3; Limited: 0; Unavailable status: 0.')).toBeTruthy()
    const visibleCounts = screen.getByLabelText('Run activity counts')
    expect(visibleCounts.textContent).toContain('14 represented runs')
    expect(visibleCounts.textContent).toContain('Pending 2')
    expect(visibleCounts.textContent).toContain('Running 3')
    expect(visibleCounts.textContent).toContain('Completed 3')
    expect(visibleCounts.textContent).toContain('Failed 3')
    expect(visibleCounts.textContent).toContain('Cancelled 3')
    expect(visibleCounts.textContent).toContain('Limited 0')
    expect(visibleCounts.textContent).not.toContain('Partial')
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

  it('keeps a limited item without status in chronological activity as unavailable rather than an execution state', () => {
    const items: readonly RunActivityItem[] = [
      { observationRunId: 'available', observationId: 'observation-a', createdAt: '2026-09-10T10:00:00Z', availability: 'available', status: 'completed' },
      { observationRunId: 'limited', observationId: 'observation-a', createdAt: '2026-09-10T11:00:00Z', availability: 'limited', status: null },
    ]
    render(<MemoryRouter><RunActivityChart activity={items} /></MemoryRouter>)

    expect(screen.getByLabelText('Execution status legend').textContent).toContain('Unavailable')
    expect(screen.getByLabelText('Run activity counts').textContent).toContain('Limited 1')
    expect(screen.getByLabelText('Run activity counts').textContent).toContain('Unavailable status 1')
    expect(screen.getByLabelText('Chronological run activity').textContent).toContain('runtime data limited; execution status unavailable')
    expect(screen.queryByText('Partial')).toBeNull()
  })
})
