import { useState, type ReactNode } from 'react'
import type { Comparison } from '../api/types'
import { MATCH_LABEL, MatchMark } from './MatchMark'
import styles from './MatchStrip.module.css'

const fmt = (n: number) => n.toFixed(2)

/**
 * The toolbar above the texts: view tabs on the left, how sure the pairing is on
 * the right. Details (scores, reasons, other candidates) open underneath; a
 * doubtful match opens them by default so the uncertainty is never hidden.
 */
export function MatchStrip({ comparison: c, children, actions }: { comparison: Comparison; children: ReactNode; actions?: ReactNode }) {
  const doubtful = c.match.strength !== 'strong'
  const [open, setOpen] = useState(doubtful)
  const gap = c.wikipedia ? new Date(c.wikipedia.dateModified).getFullYear() - c.britannica.year : null

  return (
    <section className={styles.wrap} aria-label="View and match">
      <div className={styles.row}>
        {children}
        <div className={styles.summary}>
          <span className={styles.strength}>
            <MatchMark strength={c.match.strength} />
            {MATCH_LABEL[c.match.strength]}
          </span>
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
          <table className={styles.table}>
            <caption className="visually-hidden">Wikipedia articles scored for this page</caption>
            <thead>
              <tr>
                <th scope="col">Article</th>
                <th scope="col">Embedding</th>
                <th scope="col">Rerank</th>
              </tr>
            </thead>
            <tbody>
              {c.wikipedia && (
                <tr className={styles.chosen}>
                  <td>
                    {c.wikipedia.title} <span className={styles.tag}>matched</span>
                  </td>
                  <td className="num">{fmt(c.match.embedScore)}</td>
                  <td className="num">{fmt(c.match.rerankScore)}</td>
                </tr>
              )}
              {c.candidates.map((k) => (
                <tr key={k.title}>
                  <td>
                    <a href={k.url} target="_blank" rel="noreferrer">
                      {k.title}
                    </a>
                  </td>
                  <td className="num">{fmt(k.embedScore)}</td>
                  <td className="num">{fmt(k.rerankScore)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className={styles.foot}>Embedding: Nemotron-3-Embed-VL. Rerank: Nemotron 3-Rerank-VL; a pair needs 0.5 to be compared.</p>
        </div>
      )}
    </section>
  )
}
