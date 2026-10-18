import type {
  Alignment,
  ChangeKind,
  ClaimType,
  Comparison,
  MatchStrength,
  ScanBlock,
  SectionCoverage,
  TextFix,
  TopicSummary,
  Verdict,
  WikipediaCandidate,
} from './types'

// Maps what the backend sends (src/nemotron_challenge/web_adapter.py) onto the
// UI's model in types.ts. The backend may lag behind the contract, so every
// field is read defensively: a missing value becomes null ("pending"), never a
// made-up default.

type Raw = Record<string, unknown>

const obj = (v: unknown): Raw => (v && typeof v === 'object' ? (v as Raw) : {})
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null)
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : [])

const VERDICTS: Verdict[] = ['agrees', 'differs', 'contradicts', 'not_in_wikipedia']
const STRENGTHS: MatchStrength[] = ['strong', 'partial', 'none', 'pending']
const CLAIM_TYPES: ClaimType[] = ['definition', 'quantity', 'place', 'date', 'cause', 'practice']
const KINDS: ChangeKind[] = ['retained', 'reworded', 'revised', 'dropped']

const pick = <T extends string>(v: unknown, allowed: T[]): T | null => (allowed.includes(v as T) ? (v as T) : null)

/** True when the backend's `pending` notes mention a stage. */
const pendingFor = (raw: Raw, word: string) => list(raw.pending).some((p) => typeof p === 'string' && p.toLowerCase().includes(word))

export function toTopic(v: unknown): TopicSummary {
  const t = obj(v)
  const headword = str(t.headword)
  const label = str(t.label) ?? headword ?? 'Untitled entry'
  const verdicts = obj(t.verdicts)
  return {
    slug: str(t.slug) ?? label,
    entryId: str(t.entryId) ?? str(t.entry_id) ?? undefined,
    label,
    headword,
    fragment: typeof t.fragment === 'boolean' ? t.fragment : !headword,
    edition: str(t.edition) ?? 'Not recorded',
    year: num(t.year),
    match: pick(t.match, STRENGTHS) ?? 'pending',
    wikipediaTitle: str(t.wikipediaTitle),
    area: (str(t.area) as TopicSummary['area']) ?? null,
    teaser: str(t.teaser),
    verdicts: t.verdicts
      ? {
          agrees: num(verdicts.agrees) ?? 0,
          differs: num(verdicts.differs) ?? 0,
          contradicts: num(verdicts.contradicts) ?? 0,
          not_in_wikipedia: num(verdicts.not_in_wikipedia) ?? 0,
        }
      : null,
  }
}

function toCandidate(v: unknown): WikipediaCandidate {
  const c = obj(v)
  return {
    title: str(c.title) ?? '',
    url: str(c.url) ?? '',
    bm25Rank: num(c.bm25Rank),
    embedSimilarity: num(c.embedSimilarity) ?? num(c.embedScore),
    embedRank: num(c.embedRank),
    // The backend's rerankScore is the raw reranker logit.
    rerankLogit: num(c.rerankLogit) ?? num(c.rerankScore),
    rerankRank: num(c.rerankRank),
  }
}

function toAlignment(v: unknown, index: number): Alignment {
  const a = obj(v)
  const anchor = (x: unknown) => {
    const o = obj(x)
    const passageId = str(o.passageId)
    const quote = str(o.quote)
    return passageId && quote ? { passageId, quote } : null
  }
  const claimType = pick(a.claimType ?? a.type, CLAIM_TYPES)
  const label = str(a.label)
  const q = obj(a.quantity)
  const value = str(a.value) ?? (num(a.value) !== null ? String(a.value) : null)
  return {
    id: str(a.id) ?? `a${index + 1}`,
    verdict: pick(a.verdict, VERDICTS) ?? 'not_in_wikipedia',
    claimType,
    // The backend repeats the claim type as the label; show a label only when it says more.
    label: label && label !== claimType ? label : null,
    britannica: anchor(a.britannica),
    wikipedia: anchor(a.wikipedia),
    explanation: str(a.explanation) ?? str(obj(a.explanation).text) ?? str(a.note) ?? '',
    downgraded: a.downgraded === true,
    quantity: a.quantity
      ? {
          britannica: { value: String(obj(q.britannica).value ?? ''), unit: String(obj(q.britannica).unit ?? '') },
          wikipedia: q.wikipedia ? { value: String(obj(q.wikipedia).value ?? ''), unit: String(obj(q.wikipedia).unit ?? '') } : null,
        }
      : value
        ? { britannica: { value, unit: str(a.unit) ?? '' }, wikipedia: null }
        : null,
    scores: a.scores ? { embed: num(obj(a.scores).embed), rerank: num(obj(a.scores).rerank) } : null,
    kind: pick(a.kind, KINDS),
  }
}

function toCoverage(raw: Raw): SectionCoverage[] | null {
  if (Array.isArray(raw.sectionCoverage)) {
    return raw.sectionCoverage.map((v) => {
      const s = obj(v)
      const claims = num(s.claims)
      return { section: str(s.section) ?? 'Article', covered: s.covered === true || (claims ?? 0) > 0, claims }
    })
  }
  // Older backend shape: { topic, britannica: share of claims, wikipedia: 1 when covered }.
  if (Array.isArray(raw.coverage) && raw.coverage.length && !pendingFor(raw, 'coverage')) {
    return raw.coverage.map((v) => {
      const s = obj(v)
      return { section: str(s.topic) ?? 'Article', covered: (num(s.wikipedia) ?? 0) > 0, claims: null }
    })
  }
  return null
}

export function toComparison(v: unknown, blocks: { pageHeader: string | null; blocks: ScanBlock[] } | null, threshold: number | null): Comparison {
  const raw = obj(v)
  const topic = toTopic(raw.topic)
  const b = obj(raw.britannica)
  const w = raw.wikipedia ? obj(raw.wikipedia) : null
  const m = obj(raw.match)
  const quality = b.quality ? obj(b.quality) : null
  const normalized = b.normalized ? obj(b.normalized) : null
  const claimsPending = raw.alignments == null || pendingFor(raw, 'claims')
  const vocab = raw.vocabulary ? obj(raw.vocabulary) : null

  return {
    query: str(raw.query) ?? '',
    topic,
    britannica: {
      entryId: str(b.entryId) ?? topic.entryId ?? null,
      pageId: str(b.pageId) ?? '',
      scanSha256: str(b.scanSha256),
      headword: str(b.headword),
      fragment: typeof b.fragment === 'boolean' ? b.fragment : topic.fragment,
      edition: str(b.edition) ?? topic.edition,
      year: num(b.year),
      volume: str(b.volume) ?? '',
      meta: str(b.meta) ?? '',
      pageHeader: str(b.pageHeader) ?? blocks?.pageHeader ?? null,
      imageUrl: str(b.imageUrl),
      blocks: Array.isArray(b.blocks) ? toBlocks({ blocks: b.blocks }).blocks : (blocks?.blocks ?? []),
      sourceUrl: str(b.sourceUrl),
      rawText: str(b.rawText) ?? '',
      normalized: normalized ? { text: str(normalized.text) ?? '', fixes: list(normalized.fixes) as TextFix[] } : null,
      passages: list(b.passages).map((p, i) => ({ id: str(obj(p).id) ?? `B${i + 1}`, section: str(obj(p).section) ?? undefined, text: str(obj(p).text) ?? '' })),
      quality: quality
        ? { dictionaryShare: num(quality.dictionaryShare), issues: list(quality.issues).filter((x): x is string => typeof x === 'string'), pdfUrl: str(quality.pdfUrl) }
        : null,
    },
    wikipedia: w
      ? {
          identifier: str(w.identifier) ?? '',
          revisionId: str(w.revisionId) ?? (num(w.revisionId) !== null ? String(w.revisionId) : null),
          title: str(w.title) ?? '',
          url: str(w.url) ?? '',
          revisionUrl: str(w.revisionUrl),
          dateModified: str(w.dateModified) ?? '',
          // Wikipedia text is CC BY-SA 4.0 unless the backend says otherwise.
          license: str(w.license) ?? 'CC BY-SA 4.0',
          passages: list(w.passages).map((p, i) => ({ id: str(obj(p).id) ?? `W${i + 1}`, section: str(obj(p).section) ?? undefined, text: str(obj(p).text) ?? '' })),
        }
      : null,
    match: {
      strength: pick(m.strength, STRENGTHS) ?? topic.match,
      rerankLogit: num(m.rerankLogit) ?? num(m.rerankScore),
      threshold: num(m.threshold) ?? threshold,
      reasons: list(m.reasons).filter((x): x is string => typeof x === 'string'),
    },
    candidates: list(raw.candidates).map(toCandidate),
    alignments: claimsPending ? null : list(raw.alignments).map(toAlignment),
    vocabulary:
      vocab && !pendingFor(raw, 'vocabulary')
        ? {
            britannica: list(vocab.britannica) as NonNullable<Comparison['vocabulary']>['britannica'],
            wikipedia: list(vocab.wikipedia) as NonNullable<Comparison['vocabulary']>['wikipedia'],
            shared: list(vocab.shared).filter((x): x is string => typeof x === 'string'),
          }
        : null,
    obsoleteTerms: Array.isArray(raw.obsoleteTerms)
      ? raw.obsoleteTerms.map((t) => (Array.isArray(t) ? String(t[0]) : String(t)))
      : null,
    sectionCoverage: toCoverage(raw),
    suggestedQuestions: list(raw.suggestedQuestions).filter((x): x is string => typeof x === 'string'),
  }
}

/** The page blocks route: { pageHeader, blocks: [{ class, text, bbox }] }. */
export function toBlocks(v: unknown): { pageHeader: string | null; blocks: ScanBlock[] } {
  const raw = obj(v)
  return {
    pageHeader: str(raw.pageHeader),
    blocks: list(raw.blocks)
      .map((x) => obj(x))
      .filter((x) => Array.isArray(x.bbox) && x.bbox.length === 2)
      .map((x) => ({ kind: str(x.class) ?? str(x.kind) ?? 'Text', text: str(x.text) ?? '', bbox: x.bbox as ScanBlock['bbox'] })),
  }
}
