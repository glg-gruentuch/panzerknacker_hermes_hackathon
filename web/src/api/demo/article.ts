import type {
  Alignment,
  BritannicaPage,
  ChatResponse,
  CoverageRow,
  MatchInfo,
  TopicSummary,
  WikipediaArticle,
  WikipediaCandidate,
} from '../types'

// One article file in web/articles/<slug>.json. Add an article by adding a file;
// the site finds it by itself. Verdict counts, vocabulary and text stats are
// computed from the file in demo/index.ts, so the file does not carry them.
// web/articles/README.md explains each field for the team.

export interface ArticleFile {
  /** True for invented demo text. The header shows "Demo data" while any article has it. */
  demo?: boolean
  summary: Omit<TopicSummary, 'verdicts' | 'demo'>
  /** Other words a search can use to find this article, e.g. "tuberculosis". */
  aliases?: string[]
  britannica: BritannicaPage
  wikipedia: WikipediaArticle | null
  match: MatchInfo
  candidates: WikipediaCandidate[]
  alignments: Alignment[]
  coverage: CoverageRow[]
  suggestedQuestions: string[]
  /** Scripted answers for the demo chat, keyed by the exact question. */
  answers?: Record<string, Omit<ChatResponse, 'trace'>>
}

const AREAS = ['infectious-disease', 'anatomy', 'geology', 'natural-sciences', 'astronomy']
const KEYS = ['demo', 'summary', 'aliases', 'britannica', 'wikipedia', 'match', 'candidates', 'alignments', 'coverage', 'suggestedQuestions', 'answers']

type Obj = Record<string, unknown>
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)

/**
 * Checks one article file. Returns one plain sentence per problem, empty when
 * the file is fine. `slug` is the file name without ".json".
 */
export function validateArticle(slug: string, data: unknown): string[] {
  const errors: string[] = []
  const fail = (path: string, problem: string) => errors.push(`${path}: ${problem}`)

  const str = (o: Obj, key: string, path: string, opts: { nullable?: boolean; optional?: boolean } = {}) => {
    const v = o[key]
    if (v === undefined && opts.optional) return
    if (v === null && opts.nullable) return
    if (typeof v !== 'string' || !v.trim()) fail(`${path}.${key}`, opts.nullable ? 'must be text or null' : 'must be non-empty text')
  }
  const num = (o: Obj, key: string, path: string, range?: [number, number]) => {
    const v = o[key]
    if (typeof v !== 'number' || !Number.isFinite(v)) return fail(`${path}.${key}`, 'must be a number')
    if (range && (v < range[0] || v > range[1])) fail(`${path}.${key}`, `must be between ${range[0]} and ${range[1]}`)
  }
  const oneOf = (o: Obj, key: string, path: string, values: (string | null)[]) => {
    if (!values.includes(o[key] as string | null)) fail(`${path}.${key}`, `must be one of ${values.map((v) => JSON.stringify(v)).join(', ')}`)
  }
  const texts = (v: unknown, path: string) => {
    if (!Array.isArray(v) || v.some((s) => typeof s !== 'string' || !s.trim())) fail(path, 'must be a list of non-empty texts')
  }
  const passages = (v: unknown, path: string, prefix: 'B' | 'W'): Map<string, string> => {
    const byId = new Map<string, string>()
    if (!Array.isArray(v) || v.length === 0) {
      fail(path, 'must be a non-empty list of passages')
      return byId
    }
    v.forEach((p: unknown, i) => {
      const at = `${path}[${i}]`
      if (!isObj(p)) return fail(at, 'must be an object with "id" and "text"')
      str(p, 'id', at)
      str(p, 'text', at)
      str(p, 'section', at, { optional: true })
      const id = p.id as string
      if (typeof id !== 'string') return
      if (!new RegExp(`^${prefix}\\d+$`).test(id)) fail(`${at}.id`, `must look like ${prefix}1, ${prefix}2, …`)
      if (byId.has(id)) fail(`${at}.id`, `"${id}" is used twice`)
      byId.set(id, String(p.text ?? ''))
    })
    return byId
  }
  const anchor = (v: unknown, path: string, side: Map<string, string>) => {
    if (v === null) return
    if (!isObj(v)) return fail(path, 'must be null or an object with "passageId" and "quote"')
    str(v, 'passageId', path)
    str(v, 'quote', path)
    const text = side.get(v.passageId as string)
    if (text === undefined) fail(`${path}.passageId`, `"${String(v.passageId)}" is not a passage on this side`)
    else if (typeof v.quote === 'string' && !text.includes(v.quote)) fail(`${path}.quote`, `is not an exact part of passage ${String(v.passageId)}`)
  }

  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug)) fail('file name', 'use lowercase letters, digits and hyphens only, e.g. "animal-spirits.json"')
  if (!isObj(data)) return [...errors, 'the file must hold one JSON object']

  for (const key of Object.keys(data)) if (!KEYS.includes(key)) fail(key, `is not a known field (known: ${KEYS.join(', ')})`)
  if (data.demo !== undefined && typeof data.demo !== 'boolean') fail('demo', 'must be true or false')

  // summary
  const s = data.summary
  if (!isObj(s)) fail('summary', 'is missing')
  else {
    str(s, 'slug', 'summary')
    if (typeof s.slug === 'string' && s.slug !== slug) fail('summary.slug', `must match the file name ("${slug}")`)
    for (const key of ['label', 'headword', 'edition']) str(s, key, 'summary')
    num(s, 'year', 'summary', [1700, 1900])
    oneOf(s, 'match', 'summary', ['strong', 'partial', 'none'])
    str(s, 'wikipediaTitle', 'summary', { nullable: true })
    oneOf(s, 'area', 'summary', [...AREAS, null])
    str(s, 'teaser', 'summary', { nullable: true })
  }
  if (data.aliases !== undefined) texts(data.aliases, 'aliases')

  // britannica
  let bIds = new Map<string, string>()
  const b = data.britannica
  if (!isObj(b)) fail('britannica', 'is missing')
  else {
    for (const key of ['pageId', 'headword', 'edition', 'volume', 'meta', 'rawText']) str(b, key, 'britannica')
    num(b, 'year', 'britannica', [1700, 1900])
    str(b, 'imageUrl', 'britannica', { nullable: true })
    str(b, 'sourceUrl', 'britannica', { nullable: true })
    bIds = passages(b.passages, 'britannica.passages', 'B')
    if (isObj(s) && typeof s.teaser === 'string' && bIds.size && ![...bIds.values()].some((t) => t.includes(s.teaser as string))) {
      fail('summary.teaser', 'must be quoted exactly from one of the Britannica passages')
    }
  }

  // wikipedia
  let wIds = new Map<string, string>()
  const w = data.wikipedia
  if (w !== null) {
    if (!isObj(w)) fail('wikipedia', 'must be null or an article object')
    else {
      for (const key of ['identifier', 'title', 'url', 'dateModified']) str(w, key, 'wikipedia')
      wIds = passages(w.passages, 'wikipedia.passages', 'W')
    }
  }

  // match and candidates
  const m = data.match
  if (!isObj(m)) fail('match', 'is missing')
  else {
    oneOf(m, 'strength', 'match', ['strong', 'partial', 'none'])
    num(m, 'embedScore', 'match', [0, 1])
    num(m, 'rerankScore', 'match', [0, 1])
    texts(m.reasons, 'match.reasons')
  }
  if (!Array.isArray(data.candidates)) fail('candidates', 'must be a list (it can be empty)')
  else
    data.candidates.forEach((c: unknown, i) => {
      const at = `candidates[${i}]`
      if (!isObj(c)) return fail(at, 'must be an object')
      str(c, 'title', at)
      str(c, 'url', at)
      num(c, 'embedScore', at, [0, 1])
      num(c, 'rerankScore', at, [0, 1])
    })

  // alignments
  if (!Array.isArray(data.alignments)) fail('alignments', 'must be a list (it can be empty)')
  else {
    const seen = new Set<string>()
    data.alignments.forEach((a: unknown, i) => {
      const at = `alignments[${i}]`
      if (!isObj(a)) return fail(at, 'must be an object')
      str(a, 'id', at)
      if (seen.has(a.id as string)) fail(`${at}.id`, `"${String(a.id)}" is used twice`)
      seen.add(a.id as string)
      oneOf(a, 'kind', at, ['retained', 'reworded', 'revised', 'dropped', 'added'])
      oneOf(a, 'verdict', at, ['correct', 'partly', 'wrong', null])
      str(a, 'label', at)
      str(a, 'note', at)
      anchor(a.britannica, `${at}.britannica`, bIds)
      anchor(a.wikipedia, `${at}.wikipedia`, wIds)
      if (a.britannica === null && a.wikipedia === null) fail(at, 'needs a Britannica or a Wikipedia anchor')
    })
  }

  // coverage and questions
  if (!Array.isArray(data.coverage)) fail('coverage', 'must be a list (it can be empty)')
  else
    data.coverage.forEach((c: unknown, i) => {
      const at = `coverage[${i}]`
      if (!isObj(c)) return fail(at, 'must be an object')
      str(c, 'topic', at)
      num(c, 'britannica', at, [0, 1])
      num(c, 'wikipedia', at, [0, 1])
    })
  texts(data.suggestedQuestions, 'suggestedQuestions')

  // scripted answers
  if (data.answers !== undefined) {
    if (!isObj(data.answers)) fail('answers', 'must be an object keyed by question')
    else
      for (const [q, r] of Object.entries(data.answers)) {
        const at = `answers["${q}"]`
        if (!isObj(r)) {
          fail(at, 'must be an object')
          continue
        }
        str(r, 'answer', at)
        oneOf(r, 'grounding', at, ['supported', 'partial', 'unsupported'])
        if (!Array.isArray(r.citations)) fail(`${at}.citations`, 'must be a list')
        else
          r.citations.forEach((c: unknown, i) => {
            const id = isObj(c) ? (c.passageId as string) : undefined
            if (!id || !(bIds.has(id) || wIds.has(id))) fail(`${at}.citations[${i}].passageId`, `"${String(id)}" is not a passage in this article`)
          })
      }
  }

  return errors
}

const normalise = (s: string) => s.toLowerCase().replace(/[^a-z]+/g, ' ').trim()

/**
 * Checks every article file, including clashes between files: two articles
 * with the same label or search alias. Returns the problems per slug; a slug
 * with no entry is fine.
 */
export function validateArticles(files: [slug: string, data: unknown][]): Map<string, string[]> {
  const problems = new Map<string, string[]>()
  const owner = new Map<string, string>()
  for (const [slug, data] of files) {
    const errors = validateArticle(slug, data)
    if (!errors.length) {
      const a = data as ArticleFile
      for (const name of [a.summary.label, ...(a.aliases ?? [])]) {
        const key = normalise(name)
        const other = owner.get(key)
        if (other && other !== slug) errors.push(`"${name}": ${other}.json already uses this label or alias`)
        else owner.set(key, slug)
      }
    }
    if (errors.length) problems.set(slug, errors)
  }
  return problems
}
