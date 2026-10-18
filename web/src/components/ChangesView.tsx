import type { Alignment, Comparison, TermFrequency, Verdict } from '../api/types'
import { KINDS, VERDICTS, VERDICT_ORDER } from '../lib/kinds'
import { VerdictIcon } from './Icon'
import styles from './ChangesView.module.css'

interface Props {
  comparison: Comparison
  /** Open the side-by-side view with this claim selected. */
  onShow: (alignmentId: string) => void
}

const pct = (n: number) => `${Math.round(n * 100)}%`

export function ChangesView({ comparison: c, onShow }: Props) {
  const year = c.britannica.year
  const judged = c.alignments.filter((a) => a.verdict !== null)
  const added = c.alignments.filter((a) => a.verdict === null)

  return (
    <div className={styles.view}>
      {judged.length > 0 ? <Verdicts comparison={c} /> : <NoClaims comparison={c} />}

      {VERDICT_ORDER.map((v) => {
        const items = judged.filter((a) => a.verdict === v)
        if (items.length === 0) return null
        return (
          <section key={v} className={styles.group} aria-labelledby={`group-${v}`}>
            <h3 id={`group-${v}`} className={styles.groupHead} data-tone={v}>
              <VerdictIcon verdict={v} />
              {VERDICTS[v].label} <span className={`${styles.count} num`}>{items.length}</span>
            </h3>
            <ul className={styles.claims}>
              {items.map((a) => (
                <Claim key={a.id} alignment={a} year={year} onShow={onShow} />
              ))}
            </ul>
          </section>
        )
      })}

      {added.length > 0 && (
        <section className={styles.group} aria-labelledby="group-added">
          <h3 id="group-added" className={styles.groupHead}>
            New since {year} <span className={`${styles.count} num`}>{added.length}</span>
          </h3>
          <ul className={styles.claims}>
            {added.map((a) => (
              <Claim key={a.id} alignment={a} year={year} onShow={onShow} />
            ))}
          </ul>
        </section>
      )}

      <div className={styles.charts}>
        <Vocabulary comparison={c} />
        <Coverage comparison={c} />
      </div>

      <Stats comparison={c} />
    </div>
  )
}

/** The headline: how much of the old entry holds up, then how much of the change is wording. */
function Verdicts({ comparison: c }: { comparison: Comparison }) {
  const judged = c.alignments.filter((a) => a.verdict !== null)
  const count = (v: Verdict) => judged.filter((a) => a.verdict === v).length
  const wrong = count('wrong')
  const words = c.alignments.filter((a) => a.kind === 'reworded').length
  const knowledge = c.alignments.filter((a) => KINDS[a.kind].family === 'knowledge').length
  const year = c.britannica.year

  return (
    <section className={styles.summary} aria-labelledby="summary-title">
      <h2 id="summary-title" className={styles.headline}>
        {wrong === 0
          ? `Every claim from ${year} we checked still holds, at least in part.`
          : `${wrong} of ${judged.length} claims from ${year} are wrong by today’s knowledge.`}
      </h2>
      <div className={styles.stack} role="img" aria-label={VERDICT_ORDER.map((v) => `${VERDICTS[v].label}: ${count(v)}`).join(', ')}>
        {VERDICT_ORDER.filter((v) => count(v) > 0).map((v) => (
          <span key={v} className={styles.segment} data-tone={v} style={{ flexGrow: count(v) }} title={`${VERDICTS[v].label}: ${count(v)}`} />
        ))}
      </div>
      <ul className={styles.legend}>
        {VERDICT_ORDER.map((v) => (
          <li key={v} data-tone={v}>
            <VerdictIcon verdict={v} />
            {VERDICTS[v].label} <b className="num">{count(v)}</b>
          </li>
        ))}
      </ul>
      <p className={styles.split}>
        Of the differences, {words} {words === 1 ? 'is' : 'are'} new words for the same idea and {knowledge} {knowledge === 1 ? 'is' : 'are'} new knowledge.
      </p>
    </section>
  )
}

function NoClaims({ comparison: c }: { comparison: Comparison }) {
  return (
    <section className={styles.summary}>
      <h2 className={styles.headline}>No claims could be checked.</h2>
      <p className={styles.split}>
        {c.wikipedia
          ? 'The two texts were matched, but no claim on one page has a counterpart on the other.'
          : `There is no credible Wikipedia counterpart for this ${c.britannica.year} entry, so only its own words and topics are shown.`}
      </p>
    </section>
  )
}

function Claim({ alignment: a, year, onShow }: { alignment: Alignment; year: number; onShow: (id: string) => void }) {
  return (
    <li>
      <button type="button" className={styles.claim} onClick={() => onShow(a.id)}>
        <span className={styles.claimHead}>
          <span className={styles.claimLabel}>{a.label}</span>
          <span className={styles.kind}>{KINDS[a.kind].label}</span>
        </span>
        <span className={styles.then}>
          <span className={`${styles.when} num`}>{year}</span>
          {a.britannica ? <q>{a.britannica.quote}</q> : <span className={styles.absent}>Not mentioned</span>}
        </span>
        <span className={styles.now}>
          <span className={styles.when}>Today</span>
          {a.wikipedia ? <q>{a.wikipedia.quote}</q> : <span className={styles.absent}>Not mentioned</span>}
        </span>
        <span className={styles.note}>{a.note}</span>
      </button>
    </li>
  )
}

function Vocabulary({ comparison: c }: { comparison: Comparison }) {
  const v = c.vocabulary
  const max = Math.max(0.1, ...v.britannica.map((t) => t.per1k), ...v.wikipedia.map((t) => t.per1k))
  return (
    <section className={styles.block} aria-labelledby="vocab-title">
      <h3 id="vocab-title" className={styles.blockTitle}>
        Words that mark each text
      </h3>
      <p className={styles.blockSub}>Uses per 1,000 words. Both lists share one scale.</p>
      <div className={styles.vocabCols}>
        <TermList title={String(c.britannica.year)} terms={v.britannica} max={max} serif />
        {c.wikipedia && <TermList title="Today" terms={v.wikipedia} max={max} />}
      </div>
      {v.shared.length > 0 && (
        <p className={styles.shared}>
          <span className={styles.sharedLabel}>In both: </span>
          {v.shared.join(', ')}
        </p>
      )}
    </section>
  )
}

function TermList({ title, terms, max, serif }: { title: string; terms: TermFrequency[]; max: number; serif?: boolean }) {
  return (
    <table className={styles.terms}>
      <caption className="num">{title}</caption>
      <thead className="visually-hidden">
        <tr>
          <th scope="col">Word</th>
          <th scope="col">Per 1,000 words</th>
          <th scope="col">Uses</th>
        </tr>
      </thead>
      <tbody>
        {terms.map((t) => (
          <tr key={t.term} title={`${t.term}: used ${t.count} times, ${t.per1k} per 1,000 words`}>
            <th scope="row" className={serif ? styles.termSerif : styles.term}>
              {t.term}
            </th>
            <td className={styles.barCell}>
              <span className={styles.bar} style={{ width: `${(t.per1k / max) * 100}%` }} />
              <span className="visually-hidden">{t.per1k}</span>
            </td>
            <td className={`${styles.value} num`}>{t.count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Butterfly bars: the old text grows left, today grows right. An empty ring means the topic is missing. */
function Coverage({ comparison: c }: { comparison: Comparison }) {
  const max = Math.max(0.01, ...c.coverage.flatMap((r) => [r.britannica, r.wikipedia]))
  return (
    <section className={styles.block} aria-labelledby="coverage-title">
      <h3 id="coverage-title" className={styles.blockTitle}>
        What each text covers
      </h3>
      <p className={styles.blockSub}>Share of each text by topic. A ring means the topic is missing.</p>
      <table className={styles.coverage}>
        <caption className="visually-hidden">Share of each text by topic</caption>
        <thead>
          <tr>
            <th scope="col" className={`${styles.covSide} num`}>
              {c.britannica.year}
            </th>
            <th scope="col" className="visually-hidden">
              Topic
            </th>
            <th scope="col" className={styles.covSideRight}>
              {c.wikipedia ? 'Today' : ''}
            </th>
          </tr>
        </thead>
        <tbody>
          {c.coverage.map((r) => (
            <tr key={r.topic}>
              <td className={styles.covLeft} title={`${c.britannica.year}: ${pct(r.britannica)}`}>
                {r.britannica > 0 ? <span className={styles.bar} style={{ width: `${(r.britannica / max) * 100}%` }} /> : <span className={styles.zero} />}
                <span className="visually-hidden">{pct(r.britannica)}</span>
              </td>
              <th scope="row" className={styles.covTopic}>
                {r.topic}
              </th>
              <td className={styles.covRight} title={`Today: ${pct(r.wikipedia)}`}>
                {c.wikipedia && (r.wikipedia > 0 ? <span className={styles.bar} style={{ width: `${(r.wikipedia / max) * 100}%` }} /> : <span className={styles.zero} />)}
                <span className="visually-hidden">{pct(r.wikipedia)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Stats({ comparison: c }: { comparison: Comparison }) {
  const b = c.stats.britannica
  const w = c.stats.wikipedia
  const rows: [string, number, number | undefined][] = [
    ['Words', b.words, w?.words],
    ['Sentences', b.sentences, w?.sentences],
    ['Words per sentence', b.avgSentenceLength, w?.avgSentenceLength],
    ['Distinct terms', b.distinctTerms, w?.distinctTerms],
  ]
  return (
    <section className={styles.block} aria-labelledby="stats-title">
      <h3 id="stats-title" className={styles.blockTitle}>
        The texts themselves
      </h3>
      {w && (
        <p className={styles.blockSub}>
          Sentences {w.avgSentenceLength < b.avgSentenceLength ? 'got shorter' : 'got longer'}: {b.avgSentenceLength} words on average in {c.britannica.year},{' '}
          {w.avgSentenceLength} today.
        </p>
      )}
      <table className={`${styles.stats} num`}>
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">Measure</span>
            </th>
            <th scope="col">{c.britannica.year}</th>
            <th scope="col">Today</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, then, now]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td>{then}</td>
              <td>{now ?? '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
