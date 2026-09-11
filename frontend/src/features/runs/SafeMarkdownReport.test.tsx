import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SafeMarkdownReport } from './SafeMarkdownReport'
import { parseSafeMarkdown } from './safeMarkdown'

describe('SafeMarkdownReport', () => {
  it('renders the deterministic subset with inert escaped text and inline code', () => {
    render(<SafeMarkdownReport content={'# Heading\n\n> Model\\_prose\\!\n\n- One\n- `exact-id`'} />)
    expect(screen.getByRole('heading', { name: 'Heading' }).tagName).toBe('H1')
    expect(screen.getByText('Model_prose!').closest('blockquote')).not.toBeNull()
    expect(screen.getByText('exact-id').tagName).toBe('CODE')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('keeps raw HTML, links, malformed code, and unsupported syntax as visible inert text', () => {
    render(<SafeMarkdownReport content={'<img src=x onerror=alert(1)>\n[not active](https://example.test)\n`unterminated\n~~legacy~~'} />)
    expect(screen.getByText(/<img src=x/)).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByText(/`unterminated/)).toBeTruthy()
    expect(screen.getByText(/~~legacy~~/)).toBeTruthy()
  })

  it('preserves document order in the safe fallback parser', () => {
    expect(parseSafeMarkdown('first\n\n## second\n\n- third').map((block) => block.kind)).toEqual(['paragraph', 'heading', 'list'])
  })
})
