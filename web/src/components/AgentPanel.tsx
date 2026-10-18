import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { ChatResponse, Comparison, Grounding, Passage, Verdict } from '../api/types'
import type { ChatMessage } from '../lib/useAgentChat'
import { Icon, VerdictIcon } from './Icon'
import styles from './AgentPanel.module.css'

interface Props {
  comparison: Comparison
  messages: ChatMessage[]
  pending: boolean
  onAsk: (question: string) => void
  onClear: () => void
  onCite: (passageId: string) => void
  /** Docked on the side: fold the panel away. */
  onCollapse?: () => void
  /** Shown as a drawer: close it. */
  onClose?: () => void
}

/** How well the sources back an answer, in the same red / yellow / green as the claims. */
const GROUNDING: Record<Grounding, { label: string; verdict: Verdict }> = {
  supported: { label: 'Supported by the sources', verdict: 'correct' },
  partial: { label: 'Partly supported', verdict: 'partly' },
  unsupported: { label: 'Not supported by the sources', verdict: 'wrong' },
}

export function AgentPanel({ comparison: c, messages, pending, onAsk, onClear, onCite, onCollapse, onClose }: Props) {
  const [draft, setDraft] = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  const passages = useMemo(() => {
    const all = [...c.britannica.passages, ...(c.wikipedia?.passages ?? [])]
    return new Map(all.map((p) => [p.id, p]))
  }, [c])

  const asked = new Set(messages.flatMap((m) => (m.role === 'user' ? [m.content] : [])))
  const suggestions = c.suggestedQuestions.filter((q) => !asked.has(q))

  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTo({ top: log.scrollHeight, behavior: 'smooth' })
  }, [messages.length, pending])

  const send = (q: string) => {
    if (!q.trim() || pending) return
    onAsk(q)
    setDraft('')
  }

  return (
    <section className={styles.panel} aria-label="Ask the agent">
      <header className={styles.head}>
        <div className={styles.headText}>
          <h2 className={styles.title}>Ask the agent</h2>
          <p className={styles.model}>Hermes Agent, Nemotron 3.5 Super VL</p>
        </div>
        {messages.length > 0 && (
          <button type="button" className="btn btn-quiet" onClick={onClear}>
            Clear
          </button>
        )}
        {onCollapse && (
          <button type="button" className="btn btn-quiet btn-icon" onClick={onCollapse} aria-label="Hide the agent">
            <Icon name="panelHide" />
          </button>
        )}
        {onClose && (
          <button type="button" className="btn btn-quiet btn-icon" onClick={onClose} aria-label="Close the agent">
            <Icon name="close" />
          </button>
        )}
      </header>

      <div ref={logRef} className={styles.log} aria-live="polite">
        {messages.length === 0 && (
          <p className={styles.intro}>
            Ask how the {c.britannica.year} entry and {c.wikipedia ? 'Wikipedia' : 'modern sources'} differ. Answers cite passages, B for Britannica and W for
            Wikipedia; select one to see it in the text.
          </p>
        )}

        {messages.map((m) =>
          m.role === 'user' ? (
            <p key={m.id} className={styles.user}>
              {m.content}
            </p>
          ) : m.role === 'agent' ? (
            <Answer key={m.id} response={m.response} passages={passages} onCite={onCite} />
          ) : (
            <div key={m.id} className={styles.error} role="alert">
              <p className={styles.errorHead} data-tone="wrong">
                <VerdictIcon verdict="wrong" />
                The agent did not answer
              </p>
              <p>{m.content}</p>
              <button type="button" className="btn" onClick={() => send(m.question)} disabled={pending}>
                Ask again
              </button>
            </div>
          ),
        )}

        {pending && (
          <p className={styles.thinking} role="status">
            Searching both sources
          </p>
        )}

        {suggestions.length > 0 && !pending && (
          <div className={styles.suggestions}>
            <h3 className={styles.suggestHead}>{messages.length === 0 ? 'Try asking' : 'Also worth asking'}</h3>
            {suggestions.map((q) => (
              <button key={q} type="button" className={styles.suggestion} onClick={() => send(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
      </div>

      <form
        className={styles.composer}
        onSubmit={(e) => {
          e.preventDefault()
          send(draft)
        }}
      >
        <label htmlFor="agent-question" className="visually-hidden">
          Question for the agent
        </label>
        <textarea
          id="agent-question"
          className={styles.input}
          value={draft}
          rows={2}
          placeholder={`Ask about ${c.topic.label.toLowerCase()}, then and now`}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send(draft)
            }
          }}
        />
        <button type="submit" className="btn btn-primary" disabled={!draft.trim() || pending}>
          Ask
        </button>
      </form>
    </section>
  )
}

function Answer({ response: r, passages, onCite }: { response: ChatResponse; passages: Map<string, Passage>; onCite: (id: string) => void }) {
  const cited = r.citations.filter((cit) => passages.has(cit.passageId))
  const g = GROUNDING[r.grounding]
  return (
    <article className={styles.answer}>
      <p className={styles.grounding} data-tone={g.verdict}>
        <VerdictIcon verdict={g.verdict} />
        {g.label}
      </p>

      <AnswerText text={r.answer} passages={passages} onCite={onCite} />

      {cited.length > 0 && (
        <details className={styles.more}>
          <summary>Evidence, {cited.length} passages</summary>
          <ul className={styles.evidence}>
            {cited.map((cit) => {
              const p = passages.get(cit.passageId)!
              return (
                <li key={cit.id}>
                  <Cite id={cit.id} passage={p} onCite={onCite} />
                  <span className={styles.evidenceText}>{p.text}</span>
                  {cit.rerankScore !== null && <span className={`${styles.score} num`}>Rerank {cit.rerankScore.toFixed(2)}</span>}
                </li>
              )
            })}
          </ul>
        </details>
      )}

      {r.trace.length > 0 && (
        <details className={styles.more}>
          <summary>How this answer was made</summary>
          <ol className={styles.trace}>
            {r.trace.map((t) => (
              <li key={t.step}>
                <span className={styles.traceStep}>{t.step}</span>
                <span className={styles.traceModel}>{t.model}</span>
                <span className={styles.traceDetail}>
                  {t.detail}
                  {t.ms !== null && `, ${t.ms} ms`}
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  )
}

/** Paragraphs on blank lines, "- " lines as a list, [B2]/[W5] markers as citation chips. */
function AnswerText({ text, passages, onCite }: { text: string; passages: Map<string, Passage>; onCite: (id: string) => void }) {
  const inline = (line: string): ReactNode[] =>
    line.split(/(\[[BW]\d+\])/g).map((part, i) => {
      const m = part.match(/^\[([BW]\d+)\]$/)
      if (!m) return part
      return <Cite key={i} id={m[1]} passage={passages.get(m[1])} onCite={onCite} />
    })

  return (
    <div className={styles.text}>
      {text.split(/\n{2,}/).map((block, i) => {
        const lines = block.split('\n')
        if (lines.every((l) => l.startsWith('- '))) {
          return (
            <ul key={i}>
              {lines.map((l, j) => (
                <li key={j}>{inline(l.slice(2))}</li>
              ))}
            </ul>
          )
        }
        return <p key={i}>{inline(block)}</p>
      })}
    </div>
  )
}

function Cite({ id, passage, onCite }: { id: string; passage: Passage | undefined; onCite: (id: string) => void }) {
  if (!passage) {
    return (
      <span className={`${styles.cite} ${styles.missing} num`} title="This passage is not on the page">
        {id}
      </span>
    )
  }
  return (
    <button type="button" className={`${styles.cite} num`} title={passage.text} onClick={() => onCite(passage.id)} aria-label={`Show passage ${id}`}>
      {id}
    </button>
  )
}
