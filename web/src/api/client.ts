import type { AgentCase, ChatRequest, ChatResponse, Comparison, Meta, TopicSummary } from './types'
import * as demo from './demo'

/**
 * "demo" serves built-in demo data. "live" reads the pipeline's JSON files
 * from /data/ (topics, compare, cases, meta) and sends chat to /api/chat.
 */
export const API_MODE: 'demo' | 'live' = import.meta.env.VITE_API_MODE === 'live' ? 'live' : 'demo'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'The chat backend is not reachable. Check that it is running.')
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`.trim()
    try {
      const body = (await res.json()) as { detail?: string; error?: string }
      message = body.detail ?? body.error ?? message
    } catch {
      // Not JSON. A bare 502–504 here comes from the dev proxy: the backend is down.
      if (res.status >= 502 && res.status <= 504) {
        message = `The backend did not answer (${res.status}). Check that it is running and VITE_BACKEND_URL points at it.`
      }
    }
    throw new ApiError(res.status, message)
  }
  return (await res.json()) as T
}

const DATA = `${import.meta.env.BASE_URL}data`

/**
 * Reads one of the pipeline's JSON files from public/data/. Cloudflare can
 * answer a missing file with index.html, so a non-JSON reply counts as missing.
 */
async function readData<T>(file: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${DATA}/${file}`)
  } catch {
    throw new ApiError(0, `The site could not load data/${file}. Check your connection.`)
  }
  if (!res.ok || !res.headers.get('Content-Type')?.includes('json')) {
    throw new ApiError(res.ok ? 404 : res.status, `The site has no data/${file}. Export the pipeline results to web/public/data/ and deploy again.`)
  }
  return (await res.json()) as T
}

const normalise = (s: string) => s.toLowerCase().replace(/[^a-z]+/g, ' ').trim()

let topicsFile: Promise<TopicSummary[]> | undefined
function allTopics(): Promise<TopicSummary[]> {
  topicsFile ??= readData<{ topics: TopicSummary[] }>('topics.json').then(
    (r) => r.topics,
    (err) => {
      topicsFile = undefined // let the next call try again
      throw err
    },
  )
  return topicsFile
}

/** Finds the topic a search means: exact slug, label or headword first, then a prefix match. */
function findTopic(topics: TopicSummary[], query: string): TopicSummary | undefined {
  const q = normalise(query)
  if (!q) return undefined
  const names = (t: TopicSummary) => [t.slug, t.label, t.headword].map(normalise)
  return (
    topics.find((t) => names(t).includes(q)) ??
    topics.find((t) => names(t).some((n) => n.startsWith(q) || q.startsWith(n)))
  )
}

export const api = {
  topics(): Promise<TopicSummary[]> {
    if (API_MODE === 'demo') return demo.topics()
    return allTopics()
  },

  /** Resolves to null when nothing in the index matches the query. */
  async compare(query: string): Promise<Comparison | null> {
    if (API_MODE === 'demo') return demo.compare(query)
    const topic = findTopic(await allTopics(), query)
    if (!topic) return null
    const comparison = await readData<Comparison>(`compare/${encodeURIComponent(topic.slug)}.json`)
    return { ...comparison, query }
  },

  ask(body: ChatRequest): Promise<ChatResponse> {
    if (API_MODE === 'demo') return demo.ask(body)
    return request<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify(body) })
  },

  cases(): Promise<AgentCase[]> {
    if (API_MODE === 'demo') return demo.cases()
    return readData<{ cases: AgentCase[] }>('cases.json').then((r) => r.cases)
  },

  meta(): Promise<Meta> {
    if (API_MODE === 'demo') return demo.meta()
    return readData<Meta>('meta.json')
  },
}
