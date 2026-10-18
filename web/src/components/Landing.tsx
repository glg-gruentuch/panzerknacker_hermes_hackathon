import { useEffect, useMemo, useState } from 'react'
import { API_MODE, api } from '../api/client'
import type { MatchStrength, TopicSummary } from '../api/types'
import { AREAS, HERO_PLATE, type Plate } from '../config/areas'
import { VERDICTS, VERDICT_ORDER } from '../lib/kinds'
import { editionLine } from '../lib/when'
import { Headword } from './Headword'
import { Icon, VerdictIcon } from './Icon'
import { MATCH_LABEL, MatchMark } from './MatchMark'
import styles from './Landing.module.css'

interface Props {
  topics: TopicSummary[]
  input: string
  onInput: (v: string) => void
  onSearch: (q: string) => void
}

/** How many entries a list shows before pointing to search. */
const LIST_LIMIT = 6

/** A list on the landing page: a subject, or (until entries carry subjects) a match strength. */
interface Group {
  key: string
  label: string
  blurb: string
  plate: Plate
  /** Slugs to show with their teaser and verdicts. */
  featured: string[]
  topics: TopicSummary[]
}

const STRENGTH_GROUPS: { strength: MatchStrength; label: string; blurb: string }[] = [
  { strength: 'strong', label: 'Clear matches', blurb: 'The reranker is confident the Wikipedia article covers the same subject.' },
  { strength: 'partial', label: 'Partial matches', blurb: 'An article passed the threshold, with less certainty. Check the evidence.' },
  { strength: 'none', label: 'No clear counterpart', blurb: 'No article passed the rerank threshold. These entries show the uncertainty.' },
]

/** Entries with a headword first, fragments after. */
const byHeadword = (a: TopicSummary, b: TopicSummary) => Number(!a.headword) - Number(!b.headword)

/** Every plate the backdrop can show, once each. */
const PLATES: Plate[] = [HERO_PLATE, ...AREAS.map((a) => a.plate)].filter((p, i, all) => all.findIndex((q) => q.slug === p.slug) === i)

export function Landing({ topics, input, onInput, onSearch }: Props) {
  const [open, setOpen] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [source, setSource] = useState<{ commit: string } | null>(null)
  useEffect(() => {
    api.source().then(setSource, () => setSource(null))
  }, [])
  // Suggest a word that is really in the index: the first clearly matched headword.
  const example = useMemo(() => {
    const same = (x: TopicSummary) => !!x.headword && x.headword.toLowerCase() === x.wikipediaTitle?.toLowerCase()
    const t = topics.find((x) => x.match === 'strong' && same(x)) ?? topics.find((x) => x.match === 'strong' && x.headword) ?? topics.find((x) => x.headword)
    return t?.headword ? t.headword[0] + t.headword.slice(1).toLowerCase() : 'Blood'
  }, [topics])

  // Subjects when the entries carry them; otherwise the real index by match strength.
  const groups = useMemo<Group[]>(() => {
    const subjects = AREAS.map((area) => {
      const rank = (t: TopicSummary) => {
        const i = area.featured.indexOf(t.slug)
        return i < 0 ? area.featured.length : i
      }
      const inArea = topics.filter((t) => t.area === area.slug).sort((x, y) => rank(x) - rank(y))
      return { key: area.slug, label: area.label, blurb: area.blurb, plate: area.plate, featured: area.featured, topics: inArea }
    })
    if (subjects.some((g) => g.topics.length > 0)) return subjects
    return STRENGTH_GROUPS.map((g) => ({
      key: g.strength,
      label: g.label,
      blurb: g.blurb,
      plate: HERO_PLATE,
      featured: [],
      topics: topics.filter((t) => t.match === g.strength).sort(byHeadword),
    })).filter((g) => g.topics.length > 0)
  }, [topics])
  const bySubject = groups.some((g) => AREAS.some((area) => area.slug === g.key))
  const plate = groups.find((g) => g.key === (preview ?? open))?.plate ?? HERO_PLATE

  return (
    <main className={styles.landing}>
      <div className={styles.backdrop} aria-hidden="true">
        {PLATES.map((p) => (
          <img key={p.slug} src={p.src} width={p.width} height={p.height} alt="" className={styles.plate} data-on={p.slug === plate.slug} />
        ))}
      </div>

      <div className={styles.scroll}>
        <div className={styles.content}>
          <section className={styles.hero} aria-label="Search">
            <Headword topics={topics} value={input} onChange={onInput} onSubmit={onSearch} size="hero" autoFocus example={example} />
            <p className={styles.lede}>
              Compare a medical entry from the Encyclopaedia Britannica of 1768–1860 with today’s Wikipedia, claim by claim. Each old claim is underlined by
              whether Wikipedia{' '}
              <span className={styles.sample} data-tone="contradicts">
                contradicts
              </span>
              ,{' '}
              <span className={styles.sample} data-tone="differs">
                differs from
              </span>{' '}
              or{' '}
              <span className={styles.sample} data-tone="agrees">
                agrees with
              </span>{' '}
              it.
            </p>
            {source && (
              <p className={styles.sampleNote}>
                These are the pipeline’s saved results from commit <span className="num">{source.commit.slice(0, 7)}</span>. Stages that have not run show
                as pending, and the agent panel replays recorded runs.
              </p>
            )}
            {API_MODE === 'mock' && (
              <p className={styles.sampleNote}>
                This copy of the site runs on sample data. Its Britannica passages are written for the demo, not read from the scans, and its comparisons
                are examples.
              </p>
            )}
          </section>

          <section className={styles.subjects} aria-labelledby="subjects-title">
            <h2 id="subjects-title" className={styles.subjectsTitle}>
              {bySubject ? 'Or browse a subject' : `Or browse the index: ${topics.length} entries`}
            </h2>
            <ul className={styles.areas}>
              {groups.map((group) => (
                <Subject
                  key={group.key}
                  group={group}
                  open={open === group.key}
                  onToggle={() => setOpen((cur) => (cur === group.key ? null : group.key))}
                  onPreview={(on) => setPreview(on ? group.key : null)}
                  onSearch={onSearch}
                />
              ))}
            </ul>
          </section>
        </div>
      </div>

      <p className={styles.credit} aria-live="polite">
        {credit(plate)}
      </p>
    </main>
  )
}

interface SubjectProps {
  group: Group
  open: boolean
  onToggle: () => void
  onPreview: (on: boolean) => void
  onSearch: (q: string) => void
}

function Subject({ group, open, onToggle, onPreview, onSearch }: SubjectProps) {
  const { topics } = group
  const listId = `subject-${group.key}`
  const shown = topics.slice(0, LIST_LIMIT)
  return (
    <li className={styles.area} data-open={open}>
      <button
        type="button"
        className={styles.areaButton}
        aria-expanded={open}
        aria-controls={listId}
        onClick={onToggle}
        onMouseEnter={() => onPreview(true)}
        onMouseLeave={() => onPreview(false)}
        onFocus={() => onPreview(true)}
        onBlur={() => onPreview(false)}
      >
        <span className={styles.areaLabel}>{group.label}</span>
        <span className={`${styles.areaCount} num`}>
          {topics.length} {topics.length === 1 ? 'entry' : 'entries'}
        </span>
        <span className={styles.chevron} aria-hidden="true">
          <Icon name="next" size={14} />
        </span>
        <span className={styles.areaBlurb}>{group.blurb}</span>
      </button>

      <div id={listId} className={styles.articles} hidden={!open}>
        {topics.length === 0 ? (
          <p className={styles.empty}>No articles are tagged with this subject yet. Search above to find any page in the index.</p>
        ) : (
          <ul className={styles.articleList}>
            {shown.map((t) =>
              group.featured.includes(t.slug) ? (
                <Featured key={t.slug} topic={t} onSearch={onSearch} />
              ) : (
                <Compact key={t.slug} topic={t} onSearch={onSearch} />
              ),
            )}
          </ul>
        )}
        {topics.length > LIST_LIMIT && (
          <p className={styles.more}>
            {topics.length - LIST_LIMIT} more. Search above to find them.
          </p>
        )}
      </div>
    </li>
  )
}

function Featured({ topic: t, onSearch }: { topic: TopicSummary; onSearch: (q: string) => void }) {
  return (
    <li>
      <button type="button" className={styles.featured} onClick={() => onSearch(t.slug)}>
        <span className={styles.headword}>{t.headword ?? t.label}</span>
        <span className={`${styles.meta} num`}>
          {editionLine(t)}
          {t.wikipediaTitle && <> · today “{t.wikipediaTitle}”</>}
        </span>
        {t.teaser && <q className={styles.teaser}>{t.teaser}</q>}
        <span className={styles.featuredFoot}>
          <Verdicts topic={t} />
          <span className={styles.open}>
            Compare <Icon name="arrow" size={14} />
          </span>
        </span>
      </button>
    </li>
  )
}

function Compact({ topic: t, onSearch }: { topic: TopicSummary; onSearch: (q: string) => void }) {
  return (
    <li>
      <button type="button" className={styles.compact} onClick={() => onSearch(t.slug)}>
        <span className={styles.headword}>{t.headword ?? t.label}</span>
        <span className={`${styles.meta} num`}>{editionLine(t)}</span>
        <Verdicts topic={t} />
      </button>
    </li>
  )
}

/** Wrong, partly correct and correct counts, each with its icon. */
function Verdicts({ topic: t }: { topic: TopicSummary }) {
  if (!t.verdicts) {
    return (
      <span className={styles.verdicts}>
        <MatchMark strength={t.match} />
        {t.match === 'none' ? 'No clear modern counterpart' : MATCH_LABEL[t.match]}
      </span>
    )
  }
  const v = t.verdicts
  const label = VERDICT_ORDER.map((k) => `${v[k]} ${VERDICTS[k].label.toLowerCase()}`).join(', ')
  return (
    <span className={styles.verdicts} aria-label={label} title={label}>
      {VERDICT_ORDER.map((k) => (
        <span key={k} className={`${styles.count} num`} data-tone={k}>
          <VerdictIcon verdict={k} size={12} />
          {v[k]}
        </span>
      ))}
    </span>
  )
}

/** "Anatomy. Encyclopaedia Britannica, seventh edition, volume 2. National Library of Scotland, CC0." */
function credit(p: Plate): string {
  const edition = p.meta.match(/(\w+) edition/i)?.[1]
  const volume = p.meta.match(/Volume ([\w ]+?)(?:,| -|$)/)?.[1]
  const where = [edition && `${edition.toLowerCase()} edition`, volume && `volume ${volume}`].filter(Boolean).join(', ')
  return `${p.title}. Encyclopaedia Britannica${where ? `, ${where}` : ''}. National Library of Scotland, CC0.`
}
