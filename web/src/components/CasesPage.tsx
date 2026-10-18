import { useEffect, useState } from 'react'
import { API_MODE, api } from '../api/client'
import type { AgentCase } from '../api/types'
import { VerdictIcon } from './Icon'
import styles from './Pages.module.css'

/** The six documented agent runs: three that work, three that fail. */
export function CasesPage({ onReplay }: { onReplay: (c: AgentCase) => void }) {
  const [cases, setCases] = useState<AgentCase[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.cases().then(setCases, (e: unknown) => setError(e instanceof Error ? e.message : 'The cases did not load.'))
  }, [])

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>Agent cases</h1>
      <p className={styles.lede}>Three questions the agent answers well, and three where it fails, with what each failure shows about the pipeline.</p>
      {API_MODE === 'mock' && <p className={styles.notice}>These six are placeholders in the right format. The backend replaces them with real runs.</p>}
      {cases && cases.length > 0 && cases.every((c) => !c.question) && (
        <p className={styles.notice}>Case studies are pending: these are the raw agent runs, before the six cases are written up.</p>
      )}
      {error && <p className={styles.notice}>{error}</p>}
      {!cases && !error && <p className={styles.lede}>Loading the cases…</p>}

      {cases && (
        <div className={styles.columns}>
          {(['success', 'failure'] as const).map((outcome) => (
            <section key={outcome} aria-labelledby={`cases-${outcome}`}>
              <h2 id={`cases-${outcome}`} className={styles.colHead} data-tone={outcome === 'success' ? 'agrees' : 'contradicts'}>
                <VerdictIcon verdict={outcome === 'success' ? 'agrees' : 'contradicts'} />
                {outcome === 'success' ? 'Works' : 'Fails'}
              </h2>
              <ol className={styles.caseList}>
                {cases
                  .filter((c) => c.outcome === outcome)
                  .map((c) => (
                    <li key={c.id} className={styles.case}>
                      <p className={styles.caseTopic}>{c.topic}</p>
                      <h3 className={styles.caseTitle}>{c.title}</h3>
                      {c.question && <p className={styles.question}>“{c.question}”</p>}
                      <p className={styles.excerpt}>{c.answerExcerpt}</p>
                      <dl className={styles.dl}>
                        <dt>{outcome === 'success' ? 'Why it worked' : 'What went wrong'}</dt>
                        <dd>{c.diagnosis}</dd>
                        <dt>What it shows</dt>
                        <dd>{c.lesson}</dd>
                      </dl>
                      {c.question && c.topic && (
                        <button type="button" className="btn" onClick={() => onReplay(c)}>
                          Replay this case
                        </button>
                      )}
                    </li>
                  ))}
              </ol>
            </section>
          ))}
        </div>
      )}
    </main>
  )
}
