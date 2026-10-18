import { useState, type ReactNode } from 'react'
import type { Comparison, WikipediaCandidate } from '../api/types'
import { Icon } from './Icon'
import { MATCH_LABEL, MatchMark } from './MatchMark'
import styles from './MatchStrip.module.css'

const fixed = (n: number | null, digits = 2) => (n === null ? '–' : n.toFixed(digits))
const rank = (n: number | null) => (n === null ? '–' : String(n))

/** How far the reranker moved a candidate from its BM25 position. */
function change(c: WikipediaCandidate): string {
  if (c.bm25Rank === null || c.rerankRank === null) return '–'
  const d = c.bm25Rank - c.rerankRank
  return d > 0 ? `up ${d}` : d < 0 ? `down ${-d}` : 'same'
}

/**
 * The toolbar above the texts: view tabs on the left, how sure the pairing is on
 * the right. Details show the retrieval funnel (BM25, embedder, reranker) for
 * every candidate. A partial match opens them by default.
 */
export function MatchStrip({ comparison: c, children, actions }: { comparison: Comparison; children: ReactNode; actions?: ReactNode }) {
  // A partial match opens its evidence by default. With no match, the right column already lists the candidates.
  const [open, setOpen] = useState(c.match.strength === 'partial')
  const w = c.wikipedia
  const wikiYear = w?.dateModified ? new Date(w.dateModified).getFullYear() : NaN
  const gap = c.britannica.year !== null && Number.isFinite(wikiYear) ? wikiYear - c.britannica.year : null
  const ranksMissing = c.candidates.length > 0 && c.candidates.every((k) => k.bm25Rank === null && k.rerankRank === null)

  return (
    <section className={styles.wrap} aria-label="View and match">
      <div className={styles.row}>
        {children}
        <div className={styles.summary}>
          <span className={styles.strength}>
            <MatchMark strength={c.match.strength} />
            {MATCH_LABEL[c.match.strength]}
          </span>
          {c.match.rerankLogit !== null && (
            <span className={`${styles.gap} num`} title="Raw reranker logit of the chosen article">
              logit {c.match.rerankLogit.toFixed(2)}
              {c.match.threshold !== null && ` · threshold ${c.match.threshold}`}
            </span>
          )}
          {gap !== null && <span className={`${styles.gap} num`}>{gap} years apart</span>}
          <button type="button" className={styles.details} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            Details
          </button>
          {actions}
        </div>
      </div>

      {open && (
        <div className={styles.panel}>
          <ul className={styles.reasons}>
            {c.match.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {c.candidates.length > 0 ? (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <caption className="visually-hidden">Retrieval funnel for this entry</caption>
                <thead>
                  <tr>
                    <th scope="col">Candidate</th>
                    <th scope="col">BM25 rank</th>
                    <th scope="col">Embed rank</th>
                    <th scope="col">Similarity</th>
                    <th scope="col">Rerank rank</th>
                    <th scope="col">Logit</th>
                    <th scope="col">Change</th>
                  </tr>
                </thead>
                <tbody>
                  {c.candidates.map((k) => {
                    const chosen = w !== null && k.title === w.title
                    return (
                      <tr key={k.title} className={chosen ? styles.chosen : undefined}>
                        <td>
                          <a href={k.url} target="_blank" rel="noreferrer">
                            {k.title}
                          </a>
                          {chosen && <span className={styles.tag}>matched</span>}
                        </td>
                        <td className="num">{rank(k.bm25Rank)}</td>
                        <td className="num">{rank(k.embedRank)}</td>
                        <td className="num">{fixed(k.embedSimilarity, 3)}</td>
                        <td className="num">{rank(k.rerankRank)}</td>
                        <td className="num">{fixed(k.rerankLogit)}</td>
                        <td className="num">{change(k)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className={styles.pendingLine}>
              <Icon name="pending" size={14} /> {c.match.strength === 'pending' ? 'Matching pending: no candidates yet.' : 'No candidates were recorded for this entry.'}
            </p>
          )}
          <p className={styles.foot}>
            {ranksMissing && 'Funnel ranks pending: the backend does not send them yet. '}
            Embedder nvidia/llama-nemotron-embed-vl-1b-v2 (cosine similarity). Reranker nvidia/llama-nemotron-rerank-vl-1b-v2 (raw logit; higher is
            better).
            {c.match.threshold !== null ? ` A candidate needs a logit of ${c.match.threshold} or more to count as a match.` : ' The match threshold is pending.'}
            {w && (
              <>
                {' '}
                Wikipedia text: {w.license}
                {w.revisionUrl && (
                  <>
                    ,{' '}
                    <a href={w.revisionUrl} target="_blank" rel="noreferrer">
                      revision {w.revisionId}
                    </a>
                  </>
                )}
                .
              </>
            )}
          </p>
        </div>
      )}
    </section>
  )
}
