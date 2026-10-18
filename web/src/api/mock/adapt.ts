import type { Alignment, Comparison, ExtractionQuality, SectionCoverage, TextFix, TopicSummary, Verdict, WikipediaCandidate } from '../types'
import realScan from './page-0013-50049db49e8b.jpg'
import realEntry from './real-entry.json'
import type { MockTopic } from './topics'
import { tokens, vocabulary } from './text'

// Converts the sample topics to the API contract, and serves one real entry
// (page 13, a SHIP-BUILDING fragment) built from the committed Parse output.

const VERDICT: Record<'correct' | 'partly' | 'wrong', Verdict> = { correct: 'agrees', partly: 'differs', wrong: 'contradicts' }

/** OCR misreadings the sample pages contain. The backend uses its own normalizer. */
const TYPOS: Record<string, string> = { frefh: 'fresh', pnrging: 'purging', tliis: 'this', vefsels: 'vessels', fractical: 'Practical' }

/**
 * Long-s and line-break normalization, recording each fix as a range in the
 * output so the Normalized view can mark it.
 */
export function normalize(raw: string): { text: string; fixes: TextFix[] } {
  const fixes: TextFix[] = []
  let out = ''
  let last = 0
  const re = /([A-Za-zſæœ]+)-\n\s*([A-Za-zſæœ]+)|([A-Za-zſæœ]+)|(\n)/g
  for (const m of raw.matchAll(re)) {
    out += raw.slice(last, m.index)
    if (m[1]) {
      const joined = clean(m[1] + m[2])
      fixes.push({ start: out.length, end: out.length + joined.length, original: m[0] })
      out += joined
    } else if (m[3]) {
      const fixed = clean(m[3])
      if (fixed !== m[3]) fixes.push({ start: out.length, end: out.length + fixed.length, original: m[3] })
      out += fixed
    } else {
      // A line break inside a paragraph becomes a space; paragraph breaks stay.
      const next = raw[m.index + 1]
      out += next === ' ' || next === '\n' || raw[m.index - 1] === '\n' ? '\n' : ' '
    }
    last = m.index + m[0].length
  }
  out += raw.slice(last)
  return { text: out, fixes }
}

function clean(word: string): string {
  const s = word.replace(/ſ/g, 's')
  return TYPOS[s.toLowerCase()] ?? s
}

function quality(rawText: string, fixes: TextFix[]): ExtractionQuality {
  const words = (rawText.match(/[A-Za-zſ]+/g) ?? []).length
  const longS = fixes.filter((f) => f.original.includes('ſ')).length
  const typos = fixes.filter((f) => !f.original.includes('ſ') && !f.original.includes('\n'))
  const issues = [
    ...(longS ? [`${longS} words printed with the long s (ſ); normalized to s.`] : []),
    ...typos.map((f) => `OCR read “${f.original}”; normalized.`),
  ]
  return {
    // Sample data: words that needed no fix. The backend measures against a dictionary.
    dictionaryShare: words ? Math.round((1 - (longS + typos.length) / words) * 1000) / 1000 : null,
    issues,
    pdfUrl: null,
  }
}

/** Mock funnel: ranks derived from the sample scores, so the table has something to show. */
function funnel(t: MockTopic): WikipediaCandidate[] {
  const all = [
    ...(t.wikipedia ? [{ title: t.wikipedia.title, url: t.wikipedia.url, embedScore: t.match.embedScore, rerankScore: t.match.rerankScore }] : []),
    ...t.candidates,
  ]
  const rank = (key: 'embedScore' | 'rerankScore') => {
    const order = [...all].sort((a, b) => b[key] - a[key])
    return (title: string) => order.findIndex((c) => c.title === title) + 1
  }
  const embedRank = rank('embedScore')
  const rerankRank = rank('rerankScore')
  // BM25 favours exact title words, so shorter titles rank higher in this sample.
  const bm25 = [...all].sort((a, b) => a.title.length - b.title.length)
  return all
    .map((c) => ({
      title: c.title,
      url: c.url,
      bm25Rank: bm25.findIndex((x) => x.title === c.title) + 1,
      embedSimilarity: c.embedScore,
      embedRank: embedRank(c.title),
      rerankLogit: logit(c.rerankScore),
      rerankRank: rerankRank(c.title),
    }))
    .sort((a, b) => a.rerankRank - b.rerankRank)
}

const logit = (p: number) => Math.round(Math.log(p / (1 - p)) * 100) / 100

function claims(t: MockTopic): Alignment[] {
  return t.alignments
    .filter((a) => a.britannica)
    .map((a) => ({
      id: a.id,
      verdict: a.wikipedia ? VERDICT[a.verdict ?? 'partly'] : 'not_in_wikipedia',
      claimType: a.quantity ? 'quantity' : null,
      label: a.label,
      britannica: a.britannica!,
      wikipedia: a.wikipedia,
      explanation: a.note,
      downgraded: false,
      quantity: a.quantity ?? null,
      scores: null,
      kind: a.kind === 'added' ? null : a.kind,
    }))
}

function sectionCoverage(t: MockTopic, list: Alignment[]): SectionCoverage[] | null {
  if (!t.wikipedia) return null
  const sectionOf = new Map(t.wikipedia.passages.map((p) => [p.id, p.section ?? 'Introduction']))
  const sections = [...new Set(t.wikipedia.passages.map((p) => p.section ?? 'Introduction'))]
  return sections.map((section) => ({
    section,
    covered: list.some((a) => a.wikipedia && sectionOf.get(a.wikipedia.passageId) === section),
    claims: list.filter((a) => a.wikipedia && sectionOf.get(a.wikipedia.passageId) === section).length,
  }))
}

function obsoleteTerms(t: MockTopic): string[] | null {
  if (!t.wikipedia) return null
  const today = new Set(t.wikipedia.passages.flatMap((p) => tokens(p.text)))
  const old = [...new Set(t.britannica.passages.flatMap((p) => tokens(normalize(p.text).text)))]
  const skip = new Set(tokens(`${t.summary.label} ${t.summary.headword}`))
  return old.filter((w) => !today.has(w) && !skip.has(w)).slice(0, 24)
}

export function summaryOf(t: MockTopic): TopicSummary {
  const list = claims(t)
  const count = (v: Verdict) => list.filter((a) => a.verdict === v).length
  return {
    ...t.summary,
    fragment: false,
    verdicts: list.length ? { agrees: count('agrees'), differs: count('differs'), contradicts: count('contradicts'), not_in_wikipedia: count('not_in_wikipedia') } : null,
  }
}

export function comparisonOf(t: MockTopic, query: string): Comparison {
  const list = claims(t)
  const normalized = normalize(t.britannica.rawText)
  const firstLine = t.britannica.rawText.split('\n')[0].trim()
  const candidates = funnel(t)
  return {
    query,
    topic: summaryOf(t),
    britannica: {
      ...t.britannica,
      entryId: `sample:${t.summary.slug}`,
      scanSha256: null,
      fragment: false,
      pageHeader: firstLine.length < 60 ? firstLine.replace(/\s{2,}/g, '  ') : null,
      blocks: [],
      normalized,
      quality: quality(t.britannica.rawText, normalized.fixes),
    },
    wikipedia: t.wikipedia && {
      ...t.wikipedia,
      revisionId: 'sample',
      revisionUrl: t.wikipedia.url,
      license: 'CC BY-SA 4.0',
    },
    match: {
      strength: t.match.strength,
      rerankLogit: logit(t.match.rerankScore),
      threshold: 0,
      reasons: t.match.reasons,
    },
    candidates,
    alignments: list,
    vocabulary: vocabulary(t.britannica.passages, t.wikipedia?.passages ?? null, [t.summary.label, t.summary.headword, t.wikipedia?.title ?? '']),
    obsoleteTerms: obsoleteTerms(t),
    sectionCoverage: sectionCoverage(t, list),
    suggestedQuestions: t.suggestedQuestions,
  }
}

// The real entry: page 13, which continues SHIP-BUILDING from a page outside the sample.
// Everything here comes from committed artifacts; matching and claims are pending.

const REAL_SUMMARY: TopicSummary = {
  slug: realEntry.entryId,
  label: 'Ship-building (fragment, page 13)',
  headword: null,
  fragment: true,
  edition: realEntry.edition,
  year: realEntry.year,
  match: 'pending',
  wikipediaTitle: null,
  area: null,
  teaser: null,
  verdicts: null,
}

export const REAL_ALIASES = ['ship-building', 'ship building', 'shipbuilding', 'fragment', 'page 13', realEntry.entryId]

export const realSummary = (): TopicSummary => REAL_SUMMARY

export function realComparison(query: string): Comparison {
  const normalized = normalize(realEntry.passages.map((p) => p.text).join('\n\n'))
  return {
    query,
    topic: REAL_SUMMARY,
    britannica: {
      entryId: realEntry.entryId,
      pageId: realEntry.pageId,
      scanSha256: realEntry.scanSha256,
      headword: null,
      fragment: true,
      edition: realEntry.edition,
      year: realEntry.year,
      volume: realEntry.volume,
      meta: realEntry.meta,
      pageHeader: realEntry.pageHeader,
      imageUrl: realScan,
      blocks: realEntry.blocks.map((b) => ({ kind: b.kind, text: b.text, bbox: [[b.bbox[0][0], b.bbox[0][1]], [b.bbox[1][0], b.bbox[1][1]]] })),
      sourceUrl: null,
      rawText: realEntry.rawText,
      normalized,
      passages: realEntry.passages,
      quality: realEntry.quality,
    },
    wikipedia: null,
    match: { strength: 'pending', rerankLogit: null, threshold: null, reasons: ['Matching has not run for this page yet.'] },
    candidates: [],
    alignments: null,
    vocabulary: null,
    obsoleteTerms: null,
    sectionCoverage: null,
    suggestedQuestions: [],
  }
}
