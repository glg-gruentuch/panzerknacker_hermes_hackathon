import type { Passage, TermFrequency } from '../types'

// Small text statistics so mock comparisons get real vocabulary numbers.
// The backend computes its own; this only exists so the UI has honest data offline.

const STOPWORDS = new Set(
  `a about above after again against all also am an and any are as at be because been before being below between both but by
  can could did do does doing down during each either even ever every few for from further had has have having he her here
  hers him his how i if in into is it its itself just made make many may more most much must my no nor not now of off often
  on once one only or other our out over own same shall she should so some such than that the their them then there these
  they this those through thus to too under until up upon very was we were what when where whence which while who whom why
  will with within without would you your whose yet itself thence therefore being called called also only per its it's
  about part parts several some times first around rest thought found among used known given became become like
  rather least last left whether`.split(/\s+/),
)

export function tokens(text: string): string[] {
  return (text.toLowerCase().match(/[a-zæœ]+(?:-[a-zæœ]+)*/g) ?? []).filter((w) => w.length > 2 && !STOPWORDS.has(w))
}

function counts(passages: Passage[]): { freq: Map<string, number>; total: number } {
  const freq = new Map<string, number>()
  let total = 0
  for (const p of passages) {
    total += (p.text.match(/[A-Za-zæœ]+/g) ?? []).length
    for (const t of tokens(p.text)) freq.set(t, (freq.get(t) ?? 0) + 1)
  }
  return { freq, total }
}

/**
 * Terms that mark `a` against `b`: first those missing from `b` entirely,
 * then those used at a clearly higher rate. `skip` drops the topic's own words.
 */
function distinctive(a: ReturnType<typeof counts>, b: ReturnType<typeof counts>, limit: number, skip: Set<string>): TermFrequency[] {
  const rows: (TermFrequency & { lift: number; absent: boolean })[] = []
  for (const [term, count] of a.freq) {
    if (skip.has(term)) continue
    const per1k = (count / a.total) * 1000
    const other = ((b.freq.get(term) ?? 0) / Math.max(1, b.total)) * 1000
    const lift = per1k - other
    if (lift > 0) rows.push({ term, count, per1k: Math.round(per1k * 10) / 10, lift, absent: !b.freq.has(term) })
  }
  rows.sort((x, y) => Number(y.absent) - Number(x.absent) || y.count - x.count || y.lift - x.lift || x.term.localeCompare(y.term))
  return rows.slice(0, limit).map(({ term, count, per1k }) => ({ term, count, per1k }))
}

export function vocabulary(britannica: Passage[], wikipedia: Passage[] | null, topicWords: string[] = []) {
  const b = counts(britannica)
  const w = counts(wikipedia ?? [])
  const skip = new Set(topicWords.flatMap((t) => tokens(t)))
  const shared = [...b.freq.keys()]
    .filter((t) => w.freq.has(t))
    .sort((x, y) => Math.min(b.freq.get(y)!, w.freq.get(y)!) - Math.min(b.freq.get(x)!, w.freq.get(x)!) || x.localeCompare(y))
    .slice(0, 14)
  return {
    britannica: distinctive(b, w, 10, skip),
    wikipedia: wikipedia ? distinctive(w, b, 10, skip) : [],
    shared,
  }
}

/** Passages ranked by how many question terms they contain. A stand-in for embed + rerank. */
export function keywordRank(question: string, passages: Passage[]): { passage: Passage; score: number }[] {
  const q = new Set(tokens(question).map(stem))
  if (q.size === 0) return []
  return passages
    .map((passage) => {
      const hits = new Set(tokens(passage.text).map(stem).filter((t) => q.has(t)))
      return { passage, score: hits.size / q.size }
    })
    .filter((r) => r.score > 0)
    .sort((x, y) => y.score - x.score)
}

function stem(word: string): string {
  return word.replace(/(ies|es|s|ed|ing)$/, '')
}
