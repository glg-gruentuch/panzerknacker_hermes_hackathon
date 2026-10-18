// The contract between this UI and the backend. API.md documents the same
// shapes for the backend team; keep the two in step.

/** The subject areas the landing page groups articles into. Defined in src/config/areas.ts. */
export type AreaSlug = 'infectious-disease' | 'anatomy' | 'geology' | 'natural-sciences'

/** A topic the index can answer for (one of the sampled Britannica pages). */
export interface TopicSummary {
  slug: string
  /** What the user types, e.g. "Blood". */
  label: string
  /** Britannica headword as printed, e.g. "BLOOD". */
  headword: string
  edition: string
  year: number
  match: MatchStrength
  /** Title of the best Wikipedia match, or null when there is none. */
  wikipediaTitle: string | null
  /** Subject area for the landing page. Null keeps the topic out of the subject lists (search still finds it). */
  area: AreaSlug | null
  /** One short, striking sentence from the Britannica entry, quoted exactly. */
  teaser: string | null
  /** How many Britannica claims hold up today. Null when no claims were compared. */
  verdicts: { correct: number; partly: number; wrong: number } | null
}

export type MatchStrength = 'strong' | 'partial' | 'none'

/** One retrievable chunk of text. Ids are stable: B1, B2… for Britannica, W1, W2… for Wikipedia. */
export interface Passage {
  id: string
  /** Section heading the passage sits under (Wikipedia), or the sub-entry (Britannica). */
  section?: string
  text: string
}

export interface BritannicaPage {
  /** NLS page id from the dataset's `id` column. */
  pageId: string
  headword: string
  edition: string
  year: number
  volume: string
  /** Raw `meta` string from the dataset, shown for provenance. */
  meta: string
  /** Page scan. Null in mock mode. */
  imageUrl: string | null
  /** Link to the page on digital.nls.uk, if known. */
  sourceUrl: string | null
  /** Everything Nemotron Parse read off the page, unedited: headers, neighbouring entries, OCR errors and all. */
  rawText: string
  /** The entry itself, cleaned and split into passages. Shown as "Summary". */
  passages: Passage[]
}

export interface WikipediaArticle {
  /** `identifier` from Wikipedia Structured Contents. */
  identifier: string
  title: string
  url: string
  /** `date_modified` of the snapshot used. ISO date. */
  dateModified: string
  passages: Passage[]
}

export interface WikipediaCandidate {
  title: string
  url: string
  /** Cosine similarity from Nemotron-3-Embed-VL, 0–1. */
  embedScore: number
  /** Relevance from Nemotron 3-Rerank-VL, 0–1. */
  rerankScore: number
}

export interface MatchInfo {
  strength: MatchStrength
  embedScore: number
  rerankScore: number
  /** Plain-language reasons the pair was matched (or why the match is doubtful). */
  reasons: string[]
}

/**
 * How one claim moved between the two texts.
 *  retained  =  the same fact, said much the same way
 *  reworded  ≈  the same fact in new words (a change in language)
 *  revised   ≠  the understanding itself changed (a change in knowledge)
 *  dropped   −  only in Britannica
 *  added     +  only in Wikipedia
 */
export type ChangeKind = 'retained' | 'reworded' | 'revised' | 'dropped' | 'added'

/**
 * Does the Britannica claim hold up today?
 *  correct  green   still true
 *  partly   yellow  partly true, or true then but not now
 *  wrong    red     contradicted by current knowledge
 * null for claims that only exist in Wikipedia.
 */
export type Verdict = 'correct' | 'partly' | 'wrong'

export interface Anchor {
  passageId: string
  /** Exact substring of the passage text to highlight. */
  quote: string
}

export interface Alignment {
  id: string
  kind: ChangeKind
  /** How the Britannica claim holds up today. Null when there is no Britannica side. */
  verdict: Verdict | null
  /** Short name for the claim, e.g. "Where blood is made". */
  label: string
  britannica: Anchor | null
  wikipedia: Anchor | null
  /** One or two sentences on what changed. */
  note: string
}

export interface TermFrequency {
  term: string
  count: number
  /** Occurrences per 1,000 words. */
  per1k: number
}

export interface TextStats {
  words: number
  sentences: number
  avgSentenceLength: number
  distinctTerms: number
}

export interface CoverageRow {
  topic: string
  /** Share of each text spent on this topic, 0–1. */
  britannica: number
  wikipedia: number
}

export interface Comparison {
  query: string
  topic: TopicSummary
  britannica: BritannicaPage
  /** Null when no Wikipedia article is a credible counterpart. */
  wikipedia: WikipediaArticle | null
  match: MatchInfo
  /** Other Wikipedia articles that scored, best first. */
  candidates: WikipediaCandidate[]
  alignments: Alignment[]
  vocabulary: {
    /** Terms over-represented in Britannica relative to Wikipedia. */
    britannica: TermFrequency[]
    /** Terms over-represented in Wikipedia relative to Britannica. */
    wikipedia: TermFrequency[]
    shared: string[]
  }
  coverage: CoverageRow[]
  stats: { britannica: TextStats; wikipedia: TextStats | null }
  /** Questions worth asking about this pair. */
  suggestedQuestions: string[]
}

export interface ChatTurn {
  role: 'user' | 'agent'
  content: string
}

export interface ChatRequest {
  topic: string
  question: string
  history: ChatTurn[]
}

export interface Citation {
  /** The marker used in the answer text, e.g. "B2". Same as the passage id. */
  id: string
  source: 'britannica' | 'wikipedia'
  passageId: string
  rerankScore: number | null
}

/** supported: every claim is cited · partial: some claims lack evidence · unsupported: the agent could not answer from the sources. */
export type Grounding = 'supported' | 'partial' | 'unsupported'

export interface TraceStep {
  step: string
  model: string
  detail: string
  ms: number | null
}

export interface ChatResponse {
  /** Plain text. Cite passages inline as [B2] or [W5]. Blank line = new paragraph, "- " = list item. */
  answer: string
  citations: Citation[]
  grounding: Grounding
  trace: TraceStep[]
}

export interface AgentCase {
  id: string
  outcome: 'success' | 'failure'
  title: string
  topic: string
  question: string
  /** What the agent said, abridged. */
  answerExcerpt: string
  /** Why it worked, or what went wrong (wrong retrieval, misread source, no reliable answer). */
  diagnosis: string
  /** What this case shows about the pipeline. */
  lesson: string
}

export interface DatasetInfo {
  name: string
  source: string
  url: string
  /** Revision, version, or snapshot name. */
  version: string
  /** When the team downloaded it. ISO date. */
  downloaded: string
}

export interface ModelInfo {
  role: string
  name: string
  /** Where it runs, e.g. "Nebius Token Factory". */
  host: string
}

export interface Meta {
  datasets: DatasetInfo[]
  models: ModelInfo[]
  sample: { size: number; method: string }
}
