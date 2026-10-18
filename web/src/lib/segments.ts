export interface Span {
  /** Character range inside the passage text. */
  start: number
  end: number
  key: string
}

export type Segment = { text: string; key: null } | { text: string; key: string }

/**
 * Split `text` into plain and highlighted runs. Each span is placed at the
 * first occurrence of its quote; overlapping spans keep the earlier one.
 */
export function locate(text: string, quotes: { quote: string; key: string }[]): Span[] {
  const spans: Span[] = []
  const lower = text.toLowerCase()
  for (const { quote, key } of quotes) {
    const at = lower.indexOf(quote.toLowerCase())
    if (at >= 0) spans.push({ start: at, end: at + quote.length, key })
  }
  spans.sort((a, b) => a.start - b.start || b.end - a.end)
  const kept: Span[] = []
  for (const s of spans) {
    const last = kept[kept.length - 1]
    if (!last || s.start >= last.end) kept.push(s)
  }
  return kept
}

export function segment(text: string, spans: Span[]): Segment[] {
  const out: Segment[] = []
  let at = 0
  for (const s of spans) {
    if (s.start > at) out.push({ text: text.slice(at, s.start), key: null })
    out.push({ text: text.slice(s.start, s.end), key: s.key })
    at = s.end
  }
  if (at < text.length) out.push({ text: text.slice(at), key: null })
  return out
}
