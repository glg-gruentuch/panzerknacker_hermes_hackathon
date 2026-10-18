import type { AgentCase, ChatRequest, ChatResponse, Comparison, Meta, TopicSummary } from './types'
import * as demo from './demo'

/** "demo" serves built-in demo data; "live" calls the backend at /api. */
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
    throw new ApiError(0, 'The backend is not reachable. Check that it is running and VITE_BACKEND_URL points at it.')
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

export const api = {
  topics(): Promise<TopicSummary[]> {
    if (API_MODE === 'demo') return demo.topics()
    return request<{ topics: TopicSummary[] }>('/topics').then((r) => r.topics)
  },

  /** Resolves to null when nothing in the index matches the query. */
  async compare(query: string): Promise<Comparison | null> {
    if (API_MODE === 'demo') return demo.compare(query)
    try {
      return await request<Comparison>(`/compare?q=${encodeURIComponent(query)}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) return null
      throw err
    }
  },

  ask(body: ChatRequest): Promise<ChatResponse> {
    if (API_MODE === 'demo') return demo.ask(body)
    return request<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify(body) })
  },

  cases(): Promise<AgentCase[]> {
    if (API_MODE === 'demo') return demo.cases()
    return request<{ cases: AgentCase[] }>('/cases').then((r) => r.cases)
  },

  meta(): Promise<Meta> {
    if (API_MODE === 'demo') return demo.meta()
    return request<Meta>('/meta')
  },
}
