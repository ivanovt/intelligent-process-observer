/** One inert block in the deterministic report Markdown subset. */
export type SafeMarkdownBlock = { kind: 'heading'; level: number; text: string } | { kind: 'paragraph'; text: string } | { kind: 'blockquote'; text: string } | { kind: 'list'; items: readonly string[] }

/** Parses only renderer-owned block constructs; all other Markdown remains inert text. */
export function parseSafeMarkdown(content: string): readonly SafeMarkdownBlock[] {
  const lines = content.split('\n')
  const blocks: SafeMarkdownBlock[] = []
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    if (line.trim() === '') { index += 1; continue }
    const heading = /^(#{1,6})[ \t]+(.*)$/.exec(line)
    if (heading) { blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2] }); index += 1; continue }
    if (line.startsWith('>')) { const quote: string[] = []; while (index < lines.length && lines[index].startsWith('>')) { quote.push(lines[index].replace(/^> ?/, '')); index += 1 } blocks.push({ kind: 'blockquote', text: quote.join('\n') }); continue }
    if (/^- /.test(line)) { const items: string[] = []; while (index < lines.length && /^- /.test(lines[index])) { items.push(lines[index].slice(2)); index += 1 } blocks.push({ kind: 'list', items }); continue }
    const paragraph: string[] = [line]; index += 1
    while (index < lines.length && lines[index].trim() !== '' && !/^(#{1,6})[ \t]+/.test(lines[index]) && !lines[index].startsWith('>') && !/^- /.test(lines[index])) { paragraph.push(lines[index]); index += 1 }
    blocks.push({ kind: 'paragraph', text: paragraph.join('\n') })
  }
  return blocks
}
