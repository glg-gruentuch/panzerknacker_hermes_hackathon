import type { AgentCase, ChatRequest, ChatResponse, Comparison, Meta, TopicSummary, TraceStep } from '../types'
import { MOCK_TOPICS, type MockTopic } from './topics'
import { REAL_ALIASES, comparisonOf, realComparison, realSummary, summaryOf } from './adapt'
import { keywordRank } from './text'

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

const normalise = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

function find(query: string): MockTopic | undefined {
  const q = normalise(query)
  if (!q) return undefined
  return (
    MOCK_TOPICS.find((t) => t.summary.slug === q.replace(/ /g, '-') || t.aliases.some((a) => normalise(a) === q)) ??
    MOCK_TOPICS.find((t) => t.aliases.some((a) => normalise(a).startsWith(q) || q.startsWith(normalise(a))))
  )
}

const isReal = (query: string) => {
  const q = normalise(query)
  return q.length > 2 && REAL_ALIASES.some((a) => normalise(a) === q || normalise(a).startsWith(q))
}

export async function topics(): Promise<TopicSummary[]> {
  await wait(150)
  return [...MOCK_TOPICS.map(summaryOf), realSummary()]
}

export async function compare(query: string): Promise<Comparison | null> {
  await wait(450)
  if (isReal(query)) return realComparison(query)
  const t = find(query)
  return t ? comparisonOf(t, query) : null
}

const MOCK_TRACE: TraceStep[] = [
  { step: 'Embed question', model: 'nvidia/llama-nemotron-embed-vl-1b-v2', detail: 'Mock: skipped', ms: null },
  { step: 'Rerank passages', model: 'nvidia/llama-nemotron-rerank-vl-1b-v2', detail: 'Mock: skipped', ms: null },
  { step: 'Write answer', model: 'nvidia/Nemotron-3.5-Super-VL via Hermes Agent', detail: 'Mock: canned answer', ms: null },
]

export async function ask(req: ChatRequest): Promise<ChatResponse> {
  await wait(900 + Math.random() * 600)
  const t = find(req.topic)
  if (!t) {
    return {
      answer: 'There is no matched Wikipedia article for this entry yet, so the agent has nothing to compare it with.',
      citations: [],
      grounding: 'unsupported',
      trace: MOCK_TRACE,
    }
  }

  const canned = Object.entries(t.answers).find(([q]) => normalise(q) === normalise(req.question))
  if (canned) return { ...canned[1], trace: MOCK_TRACE }

  // Unscripted question: quote the best keyword match from each side.
  const b = keywordRank(req.question, t.britannica.passages)[0]
  const w = t.wikipedia ? keywordRank(req.question, t.wikipedia.passages)[0] : undefined
  if (!b && !w) {
    return {
      answer: `Neither source has a passage that matches this question. Try one of the suggested questions, or ask about something the ${t.summary.year} entry discusses.`,
      citations: [],
      grounding: 'unsupported',
      trace: MOCK_TRACE,
    }
  }
  const parts: string[] = []
  if (b) parts.push(`The ${t.summary.year} Britannica entry says: "${b.passage.text}" [${b.passage.id}]`)
  else parts.push(`The ${t.summary.year} Britannica entry has nothing on this.`)
  if (w) parts.push(`Wikipedia says: "${w.passage.text}" [${w.passage.id}]`)
  else if (t.wikipedia) parts.push('Wikipedia has nothing on this.')
  parts.push('Mock mode: this answer quotes the closest keyword matches. With the backend running, the agent writes the comparison.')
  return {
    answer: parts.join('\n\n'),
    citations: [b, w]
      .filter((r) => r !== undefined)
      .map((r) => ({
        id: r.passage.id,
        source: r.passage.id.startsWith('B') ? 'britannica' : 'wikipedia',
        passageId: r.passage.id,
        rerankScore: null,
      })),
    grounding: 'partial',
    trace: MOCK_TRACE.map((s) => (s.step === 'Write answer' ? { ...s, detail: 'Mock: quoted keyword matches' } : s)),
  }
}

// Placeholders that show the shape of the six documented cases. Replace them
// with real runs: the challenge asks for 3 successes and 3 failures.
const CASES: AgentCase[] = [
  {
    id: 'success-1',
    outcome: 'success',
    title: 'Contagion reversed',
    topic: 'Consumption',
    question: 'Did people in 1842 think consumption was contagious?',
    answerExcerpt: 'Mostly not, in Britain… Wikipedia states that the disease spreads through the air, and that Robert Koch identified the bacterium in 1882.',
    diagnosis: 'Retrieval found the one passage on each side that discusses contagion (B5, W3) and the reranker put both first, even though the titles differ.',
    lesson: 'The pipeline works when each source states the claim plainly in a single passage.',
  },
  {
    id: 'success-2',
    outcome: 'success',
    title: 'What 1797 got wrong',
    topic: 'Blood',
    question: 'What did people in 1797 get wrong about blood?',
    answerExcerpt: 'Three claims in the 1797 entry no longer hold: blood made from chyle, heat from fermentation, bloodletting as routine treatment.',
    diagnosis: 'Each wrong claim was paired with the modern passage that replaces it, and every sentence carries a citation.',
    lesson: 'Broad "what changed" questions work when the page is short and the match is strong.',
  },
  {
    id: 'success-3',
    outcome: 'success',
    title: 'Same word, different thing',
    topic: 'Smallpox',
    question: "Is 'inoculation' in 1778 the same thing as a vaccine today?",
    answerExcerpt: 'No. In 1778 "inoculation" meant ingrafting real smallpox matter, which still killed some patients. The first vaccine used cowpox instead.',
    diagnosis: 'The agent separated a word that survived from a practice that changed, citing both sides.',
    lesson: 'With both texts in view, the agent can tell a change in language from a change in knowledge.',
  },
  {
    id: 'failure-1',
    outcome: 'failure',
    title: 'Wrong article retrieved',
    topic: 'Animal spirits',
    question: 'What is the modern view of animal spirits?',
    answerExcerpt: 'Today "animal spirits" describes the emotions and instincts that drive economic decisions…',
    diagnosis: 'The question embedding matched the economics article on the shared title. The reranker scored it 0.12, but the agent answered from it anyway.',
    lesson: 'Answers must respect the rerank threshold, and queries should include the Britannica passage text, not just the headword.',
  },
  {
    id: 'failure-2',
    outcome: 'failure',
    title: '"The last century" misread',
    topic: 'Blood',
    question: 'When was blood transfusion first tried?',
    answerExcerpt: 'According to the 1797 entry, transfusion was first attempted in the 18th century…',
    diagnosis: 'Written in 1797, "the last century" means the 1600s. The agent read the relative date from today\'s point of view.',
    lesson: "Give each passage its publication year in the prompt, and resolve relative dates when the page is parsed.",
  },
  {
    id: 'failure-3',
    outcome: 'failure',
    title: 'Missed because of the long s',
    topic: 'Smallpox',
    question: 'How was smallpox treated in 1778?',
    answerExcerpt: 'The 1778 entry does not describe a treatment for smallpox…',
    diagnosis: 'The page prints "ſ" (long s), so the parsed text read "frefh air" and "purging" came out garbled. The treatment passage never reached the top results.',
    lesson: 'Normalise ſ to s and common OCR confusions before embedding.',
  },
]

export async function cases(): Promise<AgentCase[]> {
  await wait(200)
  return CASES
}

export async function meta(): Promise<Meta> {
  await wait(100)
  return {
    datasets: [
      {
        name: 'Encyclopaedia Britannica Illustrated',
        source: 'National Library of Scotland, via Hugging Face',
        url: 'https://huggingface.co/datasets/NationalLibraryOfScotland/encyclopaedia_britannica_illustrated',
        version: 'Revision 309f765 (2,573 page scans, 1768–1860)',
        downloaded: 'Not recorded yet',
      },
      {
        name: 'Wikipedia Structured Contents',
        source: 'Wikimedia Foundation, via Kaggle',
        url: 'https://www.kaggle.com/datasets/wikimedia-foundation/wikipedia-structured-contents',
        version: 'Not recorded yet',
        downloaded: 'Not recorded yet',
      },
    ],
    models: [
      { role: 'Reads the page scans', name: 'nvidia/nemotron-3.5-parse', host: 'Organisers’ shared endpoint' },
      { role: 'Embeds passages and questions', name: 'nvidia/llama-nemotron-embed-vl-1b-v2', host: 'Nebius AI Cloud' },
      { role: 'Reranks candidates', name: 'nvidia/llama-nemotron-rerank-vl-1b-v2', host: 'Nebius AI Cloud' },
      { role: 'Answers questions', name: 'nvidia/Nemotron-3.5-Super-VL via Hermes Agent', host: 'Nebius Token Factory' },
    ],
    matchLogitThreshold: 0,
    sample: { size: 100, method: 'Random, without replacement, from all 2,573 scans with seed 20261016 (src/nemotron_challenge/resources/britannica-manifest.json).' },
  }
}
