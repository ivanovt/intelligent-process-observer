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

  it('renders only well-formed strong emphasis as semantic text and leaves malformed markers inert', () => {
    render(<SafeMarkdownReport content={'**Finding 1** has `**literal-id**` and **missing end\n\n***unsupported***'} />)
    expect(screen.getByText('Finding 1').tagName).toBe('STRONG')
    expect(screen.getByText('**literal-id**').tagName).toBe('CODE')
    expect(screen.queryByRole('strong', { name: /missing end|unsupported/ })).toBeNull()
    expect(screen.getByText(/\*\*missing end/)).toBeTruthy()
    expect(screen.getByText(/\*\*\*unsupported\*\*\*/)).toBeTruthy()
  })

  it('preserves document order in the safe fallback parser', () => {
    expect(parseSafeMarkdown('first\n\n## second\n\n- third').map((block) => block.kind)).toEqual(['paragraph', 'heading', 'list'])
  })

  it('renders the readable report structure with a flat technical appendix', () => {
    render(<SafeMarkdownReport content={'# Observation report\n\nObjective summary: Assess cooling stability.\n\nObserved UTC window: 2026-09-09T09:00:00Z to 2026-09-09T10:00:00Z.\n\n## Findings\n\n### 1. Cooling temperature increased\n\nThe current observation increased during the observed window.\n\n## Technical appendix\n\n- Finding 1 source ID: `finding-1`\n- Metric result · `lens-metric` · `evidence.current`'} />)

    expect(screen.getByRole('heading', { name: 'Observation report' })).toBeTruthy()
    expect(screen.getByText('Objective summary: Assess cooling stability.')).toBeTruthy()
    expect(screen.getByText('Observed UTC window: 2026-09-09T09:00:00Z to 2026-09-09T10:00:00Z.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: '1. Cooling temperature increased' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Technical appendix' })).toBeTruthy()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('finding-1').tagName).toBe('CODE')
    expect(screen.getByText('lens-metric').tagName).toBe('CODE')
  })
})
