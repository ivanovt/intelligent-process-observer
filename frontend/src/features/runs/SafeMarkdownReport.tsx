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
  return <>{inlineNodes(text, { current: 0 })}</>
}

function inlineNodes(text: string, key: { current: number }, allowStrong = true): ReactNode[] {
  const parts: ReactNode[] = []
  let cursor = 0
  while (cursor < text.length) {
    const delimiter = findNextDelimiter(text, cursor, allowStrong)
    if (delimiter === null) { parts.push(decodeRendererEscapes(text.slice(cursor))); break }
    if (delimiter.index > cursor) parts.push(decodeRendererEscapes(text.slice(cursor, delimiter.index)))
    if (delimiter.kind === 'code') {
      const closing = findCodeClosingDelimiter(text, delimiter.index, delimiter.marker)
      if (closing === -1) { parts.push(decodeRendererEscapes(text.slice(delimiter.index))); break }
      parts.push(<code key={key.current++} className="rounded bg-[var(--color-surface)] px-1 py-0.5 font-mono text-[0.9em]">{text.slice(delimiter.index + delimiter.marker.length, closing)}</code>)
      cursor = closing + delimiter.marker.length
      continue
    }
    const closing = findStrongClosingDelimiter(text, delimiter.index + delimiter.marker.length)
    if (closing === -1 || closing === delimiter.index + delimiter.marker.length) { parts.push(decodeRendererEscapes(text.slice(delimiter.index))); break }
    parts.push(<strong key={key.current++}>{inlineNodes(text.slice(delimiter.index + delimiter.marker.length, closing), key, false)}</strong>)
    cursor = closing + delimiter.marker.length
  }
  return parts
}

function findNextDelimiter(text: string, start: number, allowStrong: boolean) {
  for (let index = start; index < text.length; index += 1) {
    if (text[index] === '`' && !isEscaped(text, index)) return { kind: 'code' as const, index, marker: /^`+/.exec(text.slice(index))![0] }
    if (allowStrong && text.startsWith('**', index) && isStrongDelimiter(text, index)) return { kind: 'strong' as const, index, marker: '**' }
  }
  return null
}

function findCodeClosingDelimiter(text: string, opening: number, marker: string) {
  let candidate = text.indexOf(marker, opening + marker.length)
  while (candidate !== -1) {
    if (!isEscaped(text, candidate)) return candidate
    candidate = text.indexOf(marker, candidate + marker.length)
  }
  return -1
}

function findStrongClosingDelimiter(text: string, start: number) {
  let candidate = text.indexOf('**', start)
  while (candidate !== -1) {
    if (isStrongDelimiter(text, candidate)) return candidate
    candidate = text.indexOf('**', candidate + 2)
  }
  return -1
}

function isStrongDelimiter(text: string, index: number) { return !isEscaped(text, index) && text[index - 1] !== '*' && text[index + 2] !== '*' }

function isEscaped(text: string, index: number) { let slashCount = 0; for (let cursor = index - 1; cursor >= 0 && text[cursor] === '\\'; cursor -= 1) slashCount += 1; return slashCount % 2 === 1 }

function decodeRendererEscapes(value: string) { let output = ''; for (let index = 0; index < value.length; index += 1) { if (value[index] === '\\' && index + 1 < value.length && escapable.has(value[index + 1])) { output += value[index + 1]; index += 1 } else output += value[index] } return output }
