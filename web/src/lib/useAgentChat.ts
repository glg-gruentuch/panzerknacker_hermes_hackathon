import { useCallback, useState } from 'react'
import { api } from '../api/client'
import type { ChatResponse, ChatTurn } from '../api/types'

export type ChatMessage =
  | { id: number; role: 'user'; content: string }
  | { id: number; role: 'agent'; response: ChatResponse }
  | { id: number; role: 'error'; content: string; question: string }

let nextId = 1

/** Chat history per topic, so switching topics and back keeps the conversation. */
export function useAgentChat() {
  const [threads, setThreads] = useState<Record<string, ChatMessage[]>>({})
  const [pending, setPending] = useState<string | null>(null)

  const ask = useCallback(
    async (topic: string, question: string) => {
      const q = question.trim()
      if (!q || pending) return
      const history = (threads[topic] ?? []).flatMap<ChatTurn>((m) =>
        m.role === 'user' ? [{ role: 'user', content: m.content }] : m.role === 'agent' ? [{ role: 'agent', content: m.response.answer }] : [],
      )
      const push = (m: ChatMessage) => setThreads((t) => ({ ...t, [topic]: [...(t[topic] ?? []), m] }))
      push({ id: nextId++, role: 'user', content: q })
      setPending(topic)
      try {
        const response = await api.ask({ topic, question: q, history })
        push({ id: nextId++, role: 'agent', response })
      } catch (err) {
        push({ id: nextId++, role: 'error', content: err instanceof Error ? err.message : 'The agent did not respond.', question: q })
      } finally {
        setPending(null)
      }
    },
    [pending, threads],
  )

  const clear = useCallback((topic: string) => setThreads((t) => ({ ...t, [topic]: [] })), [])

  return { threads, pending, ask, clear }
}
