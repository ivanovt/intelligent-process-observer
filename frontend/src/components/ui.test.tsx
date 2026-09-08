import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Field, InlineNotice, Input, Select, Textarea, ValidationSummary } from './ui'

describe('Field', () => {
  it('keeps guidance and validation distinct while preserving an existing control description', () => {
    render(
      <>
        <span id="existing-description">Existing control context</span>
        <Field label="Metric ID" description="Identifier expected by the metric provider." error="Metric ID is required.">
          <Input aria-describedby="existing-description" />
        </Field>
      </>,
    )

    const input = screen.getByLabelText('Metric ID')
    const descriptions = input.getAttribute('aria-describedby')?.split(' ')

    expect(descriptions).toHaveLength(3)
    expect(document.getElementById(descriptions?.[0] ?? '')?.textContent).toBe('Existing control context')
    expect(document.getElementById(descriptions?.[1] ?? '')?.textContent).toBe('Identifier expected by the metric provider.')
    expect(document.getElementById(descriptions?.[2] ?? '')?.textContent).toBe('Metric ID is required.')
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('Metric ID is required.').querySelector('svg')).toBeTruthy()
  })

  it('supports native input, textarea, and select controls without overriding explicit validity', () => {
    render(
      <>
        <Field label="Name" description="Human-readable name shown in the interface."><Input /></Field>
        <Field label="Provider query" error="A provider query is required."><Textarea aria-invalid={false} /></Field>
        <Field label="Metric source" description="Configured source used to retrieve this metric."><Select><option>Primary source</option></Select></Field>
      </>,
    )

    const name = screen.getByLabelText('Name')
    const query = screen.getByLabelText('Provider query')
    const source = screen.getByLabelText('Metric source')

    expect(name.getAttribute('aria-describedby')).toBeTruthy()
    expect(query.getAttribute('aria-invalid')).toBe('false')
    expect(query.getAttribute('aria-describedby')).toBeTruthy()
    expect(source.getAttribute('aria-describedby')).toBeTruthy()
  })
})

describe('feedback primitives', () => {
  it('uses all notice tones and makes local validation links scroll to and focus their target', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><InlineNotice tone="info">Information</InlineNotice><InlineNotice tone="warning">Warning</InlineNotice><InlineNotice tone="error">Failure</InlineNotice><InlineNotice tone="success">Success</InlineNotice><ValidationSummary issues={[{ message: 'Name is required.', to: '#name', linkLabel: 'Correct name' }]} /><Input id="name" aria-label="Target name" /></MemoryRouter>)
    expect(screen.getAllByRole('status')).toHaveLength(3)
    expect(screen.getAllByRole('alert')).toHaveLength(2)
    const target = screen.getByRole('textbox', { name: 'Target name' })
    const scrollIntoView = vi.fn()
    target.scrollIntoView = scrollIntoView
    await user.click(screen.getByRole('link', { name: 'Correct name' }))
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center' })
    expect(document.activeElement).toBe(target)
    expect(screen.getByRole('alert', { name: 'Issues need attention' }).getAttribute('tabindex')).toBe('-1')
  })
})
