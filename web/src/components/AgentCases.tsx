import { useEffect, useState } from 'react'
import { API_MODE, api } from '../api/client'
import type { AgentCase } from '../api/types'
import { VerdictIcon } from './Icon'
import styles from './Pages.module.css'

/** The six documented agent runs: three that work, three that fail. A section of the Data and models page. */
export function AgentCases({ onReplay }: { onReplay: (c: AgentCase) => void }) {
  const [cases, setCases] = useState<AgentCase[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.cases().then(setCases, (e: unknown) => setError(e instanceof Error ? e.message : 'The cases did not load.'))
  }, [])

  return (
    <section id="agent-cases" className={styles.block} aria-labelledby="src-cases">
      <h2 id="src-cases" className={styles.blockTitle}>
        Agent cases
      </h2>
      <p className={styles.lede}>Three questions the agent answers well, and three where it fails, with what each failure shows about the pipeline.</p>
      {API_MODE === 'demo' && <p className={styles.notice}>These six are placeholders in the right format. The backend replaces them with real runs.</p>}
      {error && <p className={styles.notice}>{error}</p>}
      {!cases && !error && <p className={styles.lede}>Loading the cases…</p>}

      {cases && (
        <div className={styles.columns}>
          {(['success', 'failure'] as const).map((outcome) => (
            <section key={outcome} aria-labelledby={`cases-${outcome}`}>
              <h3 id={`cases-${outcome}`} className={styles.colHead} data-tone={outcome === 'success' ? 'correct' : 'wrong'}>
                <VerdictIcon verdict={outcome === 'success' ? 'correct' : 'wrong'} />
                {outcome === 'success' ? 'Works' : 'Fails'}
              </h3>
              <ol className={styles.caseList}>
                {cases
                  .filter((c) => c.outcome === outcome)
                  .map((c) => (
                    <li key={c.id} className={styles.case}>
                      <p className={styles.caseTopic}>{c.topic}</p>
                      <h4 className={styles.caseTitle}>{c.title}</h4>
                      <p className={styles.question}>“{c.question}”</p>
                      <p className={styles.excerpt}>{c.answerExcerpt}</p>
                      <dl className={styles.dl}>
                        <dt>{outcome === 'success' ? 'Why it worked' : 'What went wrong'}</dt>
                        <dd>{c.diagnosis}</dd>
                        <dt>What it shows</dt>
                        <dd>{c.lesson}</dd>
                      </dl>
                      <button type="button" className="btn" onClick={() => onReplay(c)}>
                        Replay this case
                      </button>
                    </li>
                  ))}
              </ol>
            </section>
          ))}
        </div>
      )}
    </section>
  )
}
