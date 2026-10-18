// The contract between this UI and the backend (src/nemotron_challenge/api.py).
// API.md documents the same shapes; keep the two in step.
// A field set to null means "pending": that stage has not run for this entry yet.

/** The subject areas the landing page groups articles into. Defined in src/config/areas.ts. */
export type AreaSlug = 'infectious-disease' | 'anatomy' | 'geology' | 'natural-sciences'

/** pending: matching has not run · none: no candidate passed the rerank threshold. */
export type MatchStrength = 'strong' | 'partial' | 'none' | 'pending'

/**
 * How a Britannica claim compares with the matched Wikipedia article.
 * Wikipedia is a comparison source, not ground truth, so these describe agreement, not correctness.
 */
export type Verdict = 'agrees' | 'differs' | 'contradicts' | 'not_in_wikipedia'

export type VerdictCounts = Record<Verdict, number>

/** A Britannica entry the index can answer for. */
export interface TopicSummary {
  /** Stable id used in links. */
  slug: string
  /** The pipeline's entry_id, when the backend sends it. Static mode needs it to find the comparison file. */
  entryId?: string
  /** What the user types, e.g. "Blood". For a fragment, a short description such as "Fragment, page 13". */
  label: string
  /** Britannica headword as printed, e.g. "BLOOD". Null for a fragment. */
  headword: string | null
  /** True when the text continues an entry that started on a page outside the sample. */
  fragment: boolean
  /** "Not recorded" until the backend reads it from the dataset. */
  edition: string
  year: number | null
  match: MatchStrength
  /** Title of the best Wikipedia match, or null when there is none (yet). */
  wikipediaTitle: string | null
  /** Subject area for the landing page. Null keeps the entry out of the subject lists (search still finds it). */
  area: AreaSlug | null
  /** One short sentence from the Britannica entry, quoted exactly from the OCR text. */
  teaser: string | null
  /** Claim verdict counts. Null while claims are pending. */
  verdicts: VerdictCounts | null
}

/** One retrievable chunk of text. Ids are stable: B1, B2… for Britannica, W1, W2… for Wikipedia. */
export interface Passage {
  id: string
  /** Section heading the passage sits under (Wikipedia), or the sub-entry (Britannica). */
  section?: string
  text: string
}

/** A box on the scan, in fractions of the image size: [[x0, y0], [x1, y1]]. Nemotron Parse's format. */
export type BBox = [[number, number], [number, number]]

/** One block Nemotron Parse found on the page. */
export interface ScanBlock {
  /** Parse class: Text, Page-header, Section-header, Caption, … */
  kind: string
  text: string
  bbox: BBox
}

/** A normalization edit, as a range in `normalized.text` and what the OCR had there. */
export interface TextFix {
  start: number
  end: number
  original: string
}

export interface ExtractionQuality {
  /** Share of words found in a dictionary after normalization, 0 to 1. */
  dictionaryShare: number | null
  /** Known OCR problems on this page, in plain words. */
  issues: string[]
  /** The compiled LaTeX PDF for this page in the static site. */
  pdfUrl: string | null
}

export interface BritannicaPage {
  entryId: string | null
  /** Page id; the backend sends the scan file stem, e.g. page-0013-50049db49e8b. */
  pageId: string
  scanSha256: string | null
  /** Null for a fragment. */
  headword: string | null
  fragment: boolean
  edition: string
  year: number | null
  volume: string
  /** Raw `meta` string from the dataset, shown for provenance. */
  meta: string
  /** The running head Parse found at the top of the page, if any. */
  pageHeader: string | null
  /** Page scan, e.g. /api/scans/<page_id>.jpg. */
  imageUrl: string | null
  /** Parse blocks with boxes, so the UI can box a selected quote on the scan. Empty when unknown. */
  blocks: ScanBlock[]
  /** Link to the page on digital.nls.uk, if known. */
  sourceUrl: string | null
  /** Everything Nemotron Parse read off the page, unedited. Shown as "Original text". */
  rawText: string
  /** The entry after long-s and OCR normalization, with each fix marked. Null while pending. */
  normalized: { text: string; fixes: TextFix[] } | null
  /** The entry, cleaned and split into passages. Shown as "Summary"; the agent cites these ids. */
  passages: Passage[]
  quality: ExtractionQuality | null
}

export interface WikipediaArticle {
  /** Wikipedia page id. */
  identifier: string
  /** Null until the backend sends it. */
  revisionId: string | null
  title: string
  url: string
  /** Permanent link to the exact revision compared. Null until the backend sends it. */
  revisionUrl: string | null
  /** Date of the revision. ISO date. */
  dateModified: string
  /** Licence of the article text, e.g. "CC BY-SA 4.0". */
  license: string
  passages: Passage[]
}

/** One candidate article and how each retrieval step ranked it. Null where a step did not see it. */
export interface WikipediaCandidate {
  title: string
  url: string
  bm25Rank: number | null
  embedSimilarity: number | null
  embedRank: number | null
  rerankLogit: number | null
  rerankRank: number | null
}

export interface MatchInfo {
  strength: MatchStrength
  /** Rerank logit of the chosen article. */
  rerankLogit: number | null
  /** MATCH_LOGIT_THRESHOLD: the logit a candidate needs to count as a match. */
  threshold: number | null
  /** Plain-language reasons the pair was matched (or why the match is doubtful). */
  reasons: string[]
}

/**
 * Optional tag: how a claim moved between the texts.
 * retained = same wording, reworded = new words (language), revised = new knowledge, dropped = gone today.
 */
export type ChangeKind = 'retained' | 'reworded' | 'revised' | 'dropped'

export type ClaimType = 'definition' | 'quantity' | 'place' | 'date' | 'cause' | 'practice'

export interface Anchor {
  passageId: string
  /** Exact substring of the passage text to highlight. */
  quote: string
}

export interface Quantity {
  value: string
  unit: string
}

/** One Britannica claim and how it compares with Wikipedia. */
export interface Alignment {
  id: string
  verdict: Verdict
  claimType: ClaimType | null
  /** Short name for the claim. Optional; the UI falls back to the claim type. */
  label: string | null
  /** Null when the quote could not be located in a passage. */
  britannica: Anchor | null
  /** Null when the verdict is not_in_wikipedia. */
  wikipedia: Anchor | null
  /** Model-written explanation. Always shown as an inference. */
  explanation: string
  /** True when the model's Wikipedia quote failed the substring check and the verdict was lowered to not_in_wikipedia. */
  downgraded: boolean
  /** Values for quantity claims. */
  quantity: { britannica: Quantity; wikipedia: Quantity | null } | null
  /** Embedder and reranker scores of the Wikipedia paragraph. */
  scores: { embed: number | null; rerank: number | null } | null
  kind: ChangeKind | null
}

export interface TermFrequency {
  term: string
  count: number
  /** Occurrences per 1,000 words. */
  per1k: number
}

export interface SectionCoverage {
  section: string
  /** True when at least one claim aligned to a paragraph in this section. */
  covered: boolean
  /** How many claims aligned there. Null when the backend reports only covered or not. */
  claims: number | null
}

export interface Comparison {
  query: string
  topic: TopicSummary
  britannica: BritannicaPage
  /** Null when no article is a credible counterpart, or matching is pending. */
  wikipedia: WikipediaArticle | null
  match: MatchInfo
  /** Every candidate the funnel saw, best first. */
  candidates: WikipediaCandidate[]
  /** Null while the claims stage is pending. */
  alignments: Alignment[] | null
  /** Distinctive vocabulary from the compare stage (log-odds). Null while pending. */
  vocabulary: {
    britannica: TermFrequency[]
    wikipedia: TermFrequency[]
    shared: string[]
  } | null
  /** Britannica terms with zero frequency in the article, after long-s normalization. Null while pending. */
  obsoleteTerms: string[] | null
  /** Each Wikipedia section, and how many claims aligned to it. Null while pending. */
  sectionCoverage: SectionCoverage[] | null
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
  /** True when this is a recorded run (static mode, or Hermes failed and the backend returned the closest one). */
  recorded?: boolean
  /** Where the recorded run is stored, e.g. artifacts/agent/runs/<id>. */
  runDir?: string
  /** Why the live agent did not answer, when the backend fell back to a recorded run. */
  error?: string
}

/** A recorded agent run, offered as a question in static mode. */
export interface RecordedRun {
  question: string
  topic?: string
  answer: string
  citations?: Citation[]
  grounding?: Grounding
  trace: TraceStep[]
  runDir: string
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
  /** Model and store rows, exactly as the backend lists them. */
  models: ModelInfo[]
  sample: { size: number; method: string }
  /** MATCH_LOGIT_THRESHOLD on the reranker's raw logit. Null until the backend sends it. */
  matchLogitThreshold?: number | null
}
