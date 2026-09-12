import type { ReactNode } from 'react'
import { parseSafeMarkdown, type SafeMarkdownBlock } from './safeMarkdown'

const escapable = new Set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')

/** Renders the deterministic report Markdown subset with text-only React children. */
export function SafeMarkdownReport({ content }: { content: string }) {
  return <div className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-5 text-sm leading-6">{parseSafeMarkdown(content).map((block, index) => <MarkdownBlock key={index} block={block} />)}</div>
}

function MarkdownBlock({ block }: { block: SafeMarkdownBlock }) {
  if (block.kind === 'heading') { const Tag = `h${block.level}` as keyof React.JSX.IntrinsicElements; return <Tag className={block.level === 1 ? 'text-2xl font-semibold' : block.level === 2 ? 'text-xl font-semibold' : 'text-base font-semibold'}>{inlineText(block.text)}</Tag> }
  if (block.kind === 'blockquote') return <blockquote className="border-l-4 border-[var(--color-border-strong)] pl-4 text-[var(--color-text-secondary)]"><p className="whitespace-pre-wrap">{inlineText(block.text)}</p></blockquote>
  if (block.kind === 'list') return <ul className="list-disc space-y-1 pl-5">{block.items.map((item, index) => <li key={index}>{inlineText(item)}</li>)}</ul>
  return <p className="whitespace-pre-wrap">{inlineText(block.text)}</p>
}

function inlineText(text: string): ReactNode {
  const parts: ReactNode[] = []
  let cursor = 0
  let key = 0
  while (cursor < text.length) {
    const opening = text.indexOf('`', cursor)
    if (opening === -1) { parts.push(decodeRendererEscapes(text.slice(cursor))); break }
    if (opening > cursor) parts.push(decodeRendererEscapes(text.slice(cursor, opening)))
    const run = /^`+/.exec(text.slice(opening))![0]
    const closing = text.indexOf(run, opening + run.length)
    if (closing === -1) { parts.push(decodeRendererEscapes(text.slice(opening))); break }
    parts.push(<code key={key++} className="rounded bg-[var(--color-surface)] px-1 py-0.5 font-mono text-[0.9em]">{text.slice(opening + run.length, closing)}</code>)
    cursor = closing + run.length
  }
  return <>{parts}</>
}

function decodeRendererEscapes(value: string) { let output = ''; for (let index = 0; index < value.length; index += 1) { if (value[index] === '\\' && index + 1 < value.length && escapable.has(value[index + 1])) { output += value[index + 1]; index += 1 } else output += value[index] } return output }
