import { useMemo, useState } from 'react'
import type { AreaSlug, TopicSummary } from '../api/types'
import { AREAS, HERO_PLATE, areaOf, type Area, type Plate } from '../config/areas'
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

/** How many articles a subject lists before pointing to search. */
const LIST_LIMIT = 6

/** Every plate the backdrop can show, once each. */
const PLATES: Plate[] = [HERO_PLATE, ...AREAS.map((a) => a.plate)].filter((p, i, all) => all.findIndex((q) => q.slug === p.slug) === i)

export function Landing({ topics, input, onInput, onSearch }: Props) {
  const [open, setOpen] = useState<AreaSlug | null>(null)
  const [preview, setPreview] = useState<AreaSlug | null>(null)
  const plate = areaOf(preview ?? open)?.plate ?? HERO_PLATE

  // Topics per subject: featured ones first, in the order the config lists them.
  const byArea = useMemo(() => {
    const map = new Map<AreaSlug, TopicSummary[]>()
    for (const area of AREAS) {
      const inArea = topics.filter((t) => t.area === area.slug)
      const rank = (t: TopicSummary) => {
        const i = area.featured.indexOf(t.slug)
        return i < 0 ? area.featured.length : i
      }
      map.set(area.slug, [...inArea].sort((a, b) => rank(a) - rank(b)))
    }
    return map
  }, [topics])

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
            <Headword topics={topics} value={input} onChange={onInput} onSubmit={onSearch} size="hero" autoFocus />
            <p className={styles.lede}>
              Compare an entry from the Encyclopaedia Britannica of 1768–1860 with today’s Wikipedia, claim by claim. Each old claim is underlined as{' '}
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
          </section>

          <section className={styles.subjects} aria-labelledby="subjects-title">
            <h2 id="subjects-title" className={styles.subjectsTitle}>
              Or browse a subject
            </h2>
            <ul className={styles.areas}>
              {AREAS.map((area) => (
                <Subject
                  key={area.slug}
                  area={area}
                  topics={byArea.get(area.slug) ?? []}
                  open={open === area.slug}
                  onToggle={() => setOpen((cur) => (cur === area.slug ? null : area.slug))}
                  onPreview={(on) => setPreview(on ? area.slug : null)}
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
  area: Area
  topics: TopicSummary[]
  open: boolean
  onToggle: () => void
  onPreview: (on: boolean) => void
  onSearch: (q: string) => void
}

function Subject({ area, topics, open, onToggle, onPreview, onSearch }: SubjectProps) {
  const listId = `subject-${area.slug}`
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
        <span className={styles.areaLabel}>{area.label}</span>
        <span className={`${styles.areaCount} num`}>
          {topics.length} {topics.length === 1 ? 'article' : 'articles'}
        </span>
        <span className={styles.chevron} aria-hidden="true">
          <Icon name="next" size={14} />
        </span>
        <span className={styles.areaBlurb}>{area.blurb}</span>
      </button>

      <div id={listId} className={styles.articles} hidden={!open}>
        {topics.length === 0 ? (
          <p className={styles.empty}>No articles are tagged with this subject yet. Search above to find any page in the index.</p>
        ) : (
          <ul className={styles.articleList}>
            {shown.map((t) =>
              area.featured.includes(t.slug) ? (
                <Featured key={t.slug} topic={t} onSearch={onSearch} />
              ) : (
                <Compact key={t.slug} topic={t} onSearch={onSearch} />
              ),
            )}
          </ul>
        )}
        {topics.length > LIST_LIMIT && (
          <p className={styles.more}>
            {topics.length - LIST_LIMIT} more in this subject. Search above to find them.
          </p>
        )}
      </div>
    </li>
  )
}

function Featured({ topic: t, onSearch }: { topic: TopicSummary; onSearch: (q: string) => void }) {
  return (
    <li>
      <button type="button" className={styles.featured} onClick={() => onSearch(t.label)}>
        <span className={styles.headword}>{t.headword}</span>
        <span className={`${styles.meta} num`}>
          {t.edition}, {t.year}
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
      <button type="button" className={styles.compact} onClick={() => onSearch(t.label)}>
        <span className={styles.headword}>{t.headword}</span>
        <span className={`${styles.meta} num`}>
          {t.edition}, {t.year}
        </span>
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
  const label = `${v.wrong} wrong, ${v.partly} partly correct, ${v.correct} correct`
  return (
    <span className={styles.verdicts} aria-label={label} title={label}>
      {(['wrong', 'partly', 'correct'] as const).map((k) => (
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
