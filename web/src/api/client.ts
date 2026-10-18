import type { AgentCase, ChatRequest, ChatResponse, Comparison, Meta, RecordedRun, TopicSummary } from './types'
import { toBlocks, toComparison, toTopic } from './normalize'

/**
 * live:   the FastAPI backend at /api (the default).
 * static: exported JSON files next to the app (deliverables/website/app/data/), no server.
 * mock:   built-in sample data, only when VITE_API_MODE=mock. Other builds leave it out.
 */
export const API_MODE: 'live' | 'static' | 'mock' =
  import.meta.env.VITE_API_MODE === 'mock' ? 'mock' : import.meta.env.VITE_API_MODE === 'static' ? 'static' : 'live'

// Vite replaces VITE_API_MODE at build time, so this import is dropped from live and static builds.
const loadMock = () => (import.meta.env.VITE_API_MODE === 'mock' ? import('./mock') : Promise.reject(new Error('Mock data is not in this build.')))

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  } catch {
    throw new ApiError(
      0,
      API_MODE === 'static'
        ? 'The data files did not load. Check that the app/data folder was exported next to the app.'
        : 'The backend is not reachable. Check that it is running and VITE_BACKEND_URL points at it.',
    )
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`.trim()
    try {
      const body = (await res.json()) as { detail?: string; error?: string }
      message = body.detail ?? body.error ?? message
    } catch {
      // Not JSON. A bare 502 to 504 here comes from the dev proxy: the backend is down.
      if (res.status >= 502 && res.status <= 504) {
        message = `The backend did not answer (${res.status}). Check that it is running and VITE_BACKEND_URL points at it.`
      }
    }
    throw new ApiError(res.status, message)
  }
  return (await res.json()) as T
}

const live = <T>(path: string, init?: RequestInit) => fetchJson<T>(`/api${path}`, init)

// Static mode reads files relative to the page, so the app works under any base path.
const cache = new Map<string, Promise<unknown>>()
const file = <T>(path: string): Promise<T> => {
  if (!cache.has(path)) cache.set(path, fetchJson<T>(`data/${path}`).catch((e) => (cache.delete(path), Promise.reject(e))))
  return cache.get(path) as Promise<T>
}

/** The file name the export uses for an entry: every character outside [A-Za-z0-9_-] becomes "_". */
export const exportName = (entryId: string) => entryId.replace(/[^A-Za-z0-9_-]/g, '_')

let metaPromise: Promise<Meta> | null = null

export const api = {
  async topics(): Promise<TopicSummary[]> {
    if (API_MODE === 'mock') return (await loadMock()).topics()
    const body = API_MODE === 'static' ? await file<{ topics: unknown[] }>('topics.json') : await live<{ topics: unknown[] }>('/topics')
    return (body.topics ?? []).map(toTopic)
  },

  /** Resolves to null when nothing in the index matches the query. */
  async compare(query: string): Promise<Comparison | null> {
    if (API_MODE === 'mock') return (await loadMock()).compare(query)
    const threshold = (await api.meta().catch(() => null))?.matchLogitThreshold ?? null
    if (API_MODE === 'static') return staticCompare(query, threshold)
    let raw: unknown
    try {
      raw = await live<unknown>(`/compare?q=${encodeURIComponent(query)}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null
      throw err
    }
    if (!raw) return null
    const pageId = (raw as { britannica?: { pageId?: string } }).britannica?.pageId
    const blocks = pageId ? await live<unknown>(`/scans/${encodeURIComponent(pageId)}.json`).then(toBlocks, () => null) : null
    return toComparison(raw, blocks, threshold)
  },

  async ask(body: ChatRequest): Promise<ChatResponse> {
    if (API_MODE === 'mock') return (await loadMock()).ask(body)
    if (API_MODE === 'static') {
      const runs = await api.recordedRuns()
      const run = runs.find((r) => r.question.trim().toLowerCase() === body.question.trim().toLowerCase())
      if (!run) throw new ApiError(404, 'This static site only has recorded runs. Pick one of the recorded questions.')
      return { answer: run.answer, citations: run.citations ?? [], grounding: run.grounding ?? 'partial', trace: run.trace ?? [], recorded: true, runDir: run.runDir }
    }
    return live<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify(body) })
  },

  /** Recorded agent runs. Static mode offers these instead of free text. */
  async recordedRuns(): Promise<RecordedRun[]> {
    if (API_MODE !== 'static') return []
    const body = await file<{ runs?: RecordedRun[] } | RecordedRun[]>('chat-recorded.json').catch(() => [])
    return Array.isArray(body) ? body : (body.runs ?? [])
  },

  async cases(): Promise<AgentCase[]> {
    if (API_MODE === 'mock') return (await loadMock()).cases()
    const body = API_MODE === 'static' ? await file<{ cases: AgentCase[] }>('cases.json') : await live<{ cases: AgentCase[] }>('/cases')
    return body.cases ?? []
  },

  meta(): Promise<Meta> {
    if (API_MODE === 'mock') return loadMock().then((m) => m.meta())
    metaPromise ??= (API_MODE === 'static' ? file<Meta>('meta.json') : live<Meta>('/meta')).catch((e) => {
      metaPromise = null
      throw e
    })
    return metaPromise
  },
}

/** Static search: topics.json in the browser (headword and title, case-insensitive), then the entry's file. */
async function staticCompare(query: string, threshold: number | null): Promise<Comparison | null> {
  const q = query.trim().toLowerCase()
  if (!q) return null
  const topics = await api.topics()
  const fields = (t: TopicSummary) => [t.slug, t.entryId ?? '', t.label, t.headword ?? '', t.wikipediaTitle ?? ''].map((s) => s.toLowerCase())
  const topic =
    topics.find((t) => fields(t).includes(q)) ??
    topics.find((t) => fields(t).some((f) => f.startsWith(q))) ??
    topics.find((t) => fields(t).some((f) => f.includes(q)))
  if (!topic) return null
  const index = await file<Record<string, string>>('compare/index.json')
  const name = index[topic.entryId ?? ''] ?? index[topic.slug] ?? (topic.entryId ? `${exportName(topic.entryId)}.json` : null)
  if (!name) return null
  const raw = await file<unknown>(`compare/${name}`)
  const c = toComparison(raw, null, threshold)
  // The static site ships every scan in deliverables/website/assets/scans/, next to app/.
  const scan = c.britannica.imageUrl?.match(/^\/api\/scans\/(.+)$/)
  if (scan) c.britannica.imageUrl = `../assets/scans/${scan[1]}`
  return c
}
