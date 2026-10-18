import type { MatchStrength, TopicSummary } from '../api/types'
import { Headword } from './Headword'
import { MATCH_LABEL, MatchMark } from './MatchMark'
import styles from './Landing.module.css'

interface Props {
  topics: TopicSummary[]
  input: string
  onInput: (v: string) => void
  onSearch: (q: string) => void
}

const STRENGTHS: MatchStrength[] = ['strong', 'partial', 'none']

export function Landing({ topics, input, onInput, onSearch }: Props) {
  return (
    <main className={styles.landing}>
      <div className={styles.hero}>
        <Headword topics={topics} value={input} onChange={onInput} onSubmit={onSearch} size="hero" autoFocus />
        <p className={styles.lede}>
          Compare a medical entry from the Encyclopaedia Britannica of 1768–1860 with today’s Wikipedia, claim by claim. Each old claim is underlined as{' '}
          <span className={styles.sample} data-tone="wrong">
            wrong
          </span>
          ,{' '}
          <span className={styles.sample} data-tone="partly">
            partly correct
          </span>{' '}
          or{' '}
          <span className={styles.sample} data-tone="correct">
            correct
          </span>
          .
        </p>
      </div>

      {topics.length > 0 && (
        <section className={styles.index} aria-labelledby="index-title">
          <h2 id="index-title" className={styles.indexTitle}>
            In the index <span className={`${styles.count} num`}>{topics.length} pages</span>
          </h2>
          <div className={styles.groups}>
            {STRENGTHS.map((s) => {
              const list = topics.filter((t) => t.match === s)
              if (list.length === 0) return null
              return (
                <div key={s}>
                  <h3 className={styles.groupTitle}>
                    <MatchMark strength={s} />
                    {MATCH_LABEL[s]}
                  </h3>
                  <ul className={styles.list}>
                    {list.map((t) => (
                      <li key={t.slug}>
                        <button type="button" className={styles.entry} onClick={() => onSearch(t.label)}>
                          <span className={styles.entryHead}>{t.headword}</span>
                          <span className={`${styles.entryMeta} num`}>
                            {t.edition}, {t.year}
                          </span>
                          <span className={styles.entryTo}>{t.wikipediaTitle ?? 'No match'}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        </section>
      )}
    </main>
  )
}
