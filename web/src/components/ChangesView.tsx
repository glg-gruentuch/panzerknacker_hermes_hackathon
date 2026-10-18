import type { Alignment, Comparison, TermFrequency, Verdict } from '../api/types'
import { KINDS, VERDICTS, VERDICT_ORDER } from '../lib/kinds'
import { thenName } from '../lib/when'
import { Icon, VerdictIcon } from './Icon'
import styles from './ChangesView.module.css'

interface Props {
  comparison: Comparison
  /** Open the side-by-side view with this claim selected. */
  onShow: (alignmentId: string) => void
}

/** Sections in the order the handoff fixes: counts, claims, quantities, vocabulary, obsolete terms, coverage. */
export function ChangesView({ comparison: c, onShow }: Props) {
  const then = thenName(c.britannica)
  return (
    <div className={styles.view}>
      <Counts comparison={c} />

      {c.alignments &&
        VERDICT_ORDER.map((v) => {
          const items = c.alignments!.filter((a) => a.verdict === v)
          if (items.length === 0) return null
          return (
            <section key={v} className={styles.group} aria-labelledby={`group-${v}`}>
              <h3 id={`group-${v}`} className={styles.groupHead} data-tone={v}>
                <VerdictIcon verdict={v} />
                {VERDICTS[v].label} <span className={`${styles.count} num`}>{items.length}</span>
              </h3>
              <ul className={styles.claims}>
                {items.map((a) => (
                  <Claim key={a.id} alignment={a} then={then} onShow={onShow} />
                ))}
              </ul>
            </section>
          )
        })}

      <Quantities comparison={c} />

      <div className={styles.charts}>
        <Vocabulary comparison={c} />
        <Obsolete comparison={c} />
      </div>

      <Coverage comparison={c} />
    </div>
  )
}

function Pending({ what }: { what: string }) {
  return (
    <p className={styles.pending}>
      <Icon name="pending" size={14} /> {what} pending: this stage has not run for this entry yet.
    </p>
  )
}

function Counts({ comparison: c }: { comparison: Comparison }) {
  if (c.alignments === null) {
    return (
      <section className={styles.summary}>
        <h2 className={styles.headline}>Claims pending</h2>
        <Pending what="Claim alignment" />
      </section>
    )
  }
  const total = c.alignments.length
  const count = (v: Verdict) => c.alignments!.filter((a) => a.verdict === v).length
  if (total === 0) {
    return (
      <section className={styles.summary}>
        <h2 className={styles.headline}>No claims were extracted from this entry.</h2>
      </section>
    )
  }
  const headline =
    count('contradicts') > 0
      ? `${count('contradicts')} of ${total} claims contradict the Wikipedia article.`
      : count('agrees') > 0
        ? `${count('agrees')} of ${total} claims agree with the Wikipedia article.`
        : count('differs') > 0
          ? `${count('differs')} of ${total} claims differ from the Wikipedia article.`
          : `None of the ${total} claims appear in the Wikipedia article.`
  const words = c.alignments.filter((a) => a.kind === 'reworded').length
  const knowledge = c.alignments.filter((a) => a.kind && KINDS[a.kind].family === 'knowledge').length
  return (
    <section className={styles.summary} aria-labelledby="summary-title">
      <h2 id="summary-title" className={styles.headline}>
        {headline}
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
        Wikipedia is a comparison source, not ground truth: these verdicts say whether the two texts agree, not which one is right.
        {words + knowledge > 0 && ` Of the tagged differences, ${words} are new words for the same idea and ${knowledge} are new knowledge.`}
      </p>
    </section>
  )
}

function Claim({ alignment: a, then, onShow }: { alignment: Alignment; then: string; onShow: (id: string) => void }) {
  const title = a.label ?? (a.claimType ? `${a.claimType[0].toUpperCase()}${a.claimType.slice(1)} claim` : 'Claim')
  return (
    <li>
      <button type="button" className={styles.claim} onClick={() => onShow(a.id)} disabled={!a.britannica && !a.wikipedia}>
        <span className={styles.claimHead}>
          <span className={styles.claimLabel}>{title}</span>
          {a.kind && <span className={styles.kind}>{KINDS[a.kind].label}</span>}
          {a.downgraded && <span className={styles.kind}>Lowered: the model’s Wikipedia quote was not in the article</span>}
        </span>
        <span className={styles.then}>
          <span className={`${styles.when} num`}>{then}</span>
          {a.britannica ? <q>{a.britannica.quote}</q> : <span className={styles.absent}>Quote not located in a passage</span>}
        </span>
        <span className={styles.now}>
          <span className={styles.when}>Wikipedia</span>
          {a.wikipedia ? <q>{a.wikipedia.quote}</q> : <span className={styles.absent}>Not in the article</span>}
        </span>
        {a.explanation && (
          <span className={styles.note}>
            <span className="inference-tag">Inference</span> {a.explanation}
          </span>
        )}
      </button>
    </li>
  )
}

/** Quantity claims: the Britannica value and unit next to Wikipedia's. */
function Quantities({ comparison: c }: { comparison: Comparison }) {
  if (c.alignments === null) return null
  const rows = c.alignments.filter((a) => a.quantity)
  return (
    <section className={styles.block} aria-labelledby="quantity-title">
      <h3 id="quantity-title" className={styles.blockTitle}>
        Quantity drift
      </h3>
      {rows.length === 0 ? (
        <p className={styles.blockSub}>No quantity claims in this entry.</p>
      ) : (
        <table className={`${styles.stats} num`}>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col">{thenName(c.britannica)}</th>
              <th scope="col">Wikipedia</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <th scope="row">{a.label ?? a.britannica?.quote ?? 'Quantity'}</th>
                <td>
                  {a.quantity!.britannica.value} {a.quantity!.britannica.unit}
                </td>
                <td>{a.quantity!.wikipedia ? `${a.quantity!.wikipedia.value} ${a.quantity!.wikipedia.unit}` : 'No figure'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

function Vocabulary({ comparison: c }: { comparison: Comparison }) {
  const v = c.vocabulary
  return (
    <section className={styles.block} aria-labelledby="vocab-title">
      <h3 id="vocab-title" className={styles.blockTitle}>
        Distinctive vocabulary
      </h3>
      {!v ? (
        <Pending what="Vocabulary" />
      ) : (
        <>
          <p className={styles.blockSub}>Words each text uses more than the other (log-odds), per 1,000 words. Both lists share one scale.</p>
          <div className={styles.vocabCols}>
            <TermList title={thenName(c.britannica)} terms={v.britannica} max={scale(v)} serif />
            {c.wikipedia && <TermList title="Wikipedia" terms={v.wikipedia} max={scale(v)} />}
          </div>
          {v.shared.length > 0 && (
            <p className={styles.shared}>
              <span className={styles.sharedLabel}>In both: </span>
              {v.shared.join(', ')}
            </p>
          )}
        </>
      )}
    </section>
  )
}

const scale = (v: NonNullable<Comparison['vocabulary']>) => Math.max(0.1, ...v.britannica.map((t) => t.per1k), ...v.wikipedia.map((t) => t.per1k))

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

function Obsolete({ comparison: c }: { comparison: Comparison }) {
  return (
    <section className={styles.block} aria-labelledby="obsolete-title">
      <h3 id="obsolete-title" className={styles.blockTitle}>
        Obsolete terms
      </h3>
      {c.obsoleteTerms === null ? (
        <Pending what="Obsolete terms" />
      ) : c.obsoleteTerms.length === 0 ? (
        <p className={styles.blockSub}>Every Britannica term also appears in the article.</p>
      ) : (
        <>
          <p className={styles.blockSub}>Britannica terms that never appear in the Wikipedia article, after long-s normalization.</p>
          <p className={styles.obsolete}>{c.obsoleteTerms.join(', ')}</p>
        </>
      )}
    </section>
  )
}

/** One segment per Wikipedia section: filled when a claim aligned to it. */
function Coverage({ comparison: c }: { comparison: Comparison }) {
  const rows = c.sectionCoverage
  return (
    <section className={styles.block} aria-labelledby="coverage-title">
      <h3 id="coverage-title" className={styles.blockTitle}>
        Section coverage
      </h3>
      {rows === null ? (
        <Pending what="Section coverage" />
      ) : rows.length === 0 ? (
        <p className={styles.blockSub}>The article has no sections to cover.</p>
      ) : (
        <>
          <p className={styles.blockSub}>
            {rows.filter((r) => r.covered).length} of {rows.length} Wikipedia sections have at least one aligned claim.
          </p>
          <div className={styles.coverBar} role="img" aria-label={rows.map((r) => `${r.section}: ${r.covered ? 'covered' : 'not covered'}`).join(', ')}>
            {rows.map((r) => (
              <span key={r.section} className={styles.coverSeg} data-covered={r.covered} title={`${r.section}: ${r.covered ? `${r.claims ?? 'some'} claims` : 'no claims'}`} />
            ))}
          </div>
          <ul className={styles.coverList}>
            {rows.map((r) => (
              <li key={r.section} data-covered={r.covered}>
                <span className={styles.coverKey} data-covered={r.covered} aria-hidden="true" />
                {r.section}
                {r.claims !== null && <span className={`${styles.count} num`}> {r.claims}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
