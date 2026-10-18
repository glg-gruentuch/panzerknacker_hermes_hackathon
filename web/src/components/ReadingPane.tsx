import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Alignment, Comparison, Passage } from '../api/types'
import { KINDS, VERDICTS, VERDICT_ORDER } from '../lib/kinds'
import { locate, segment } from '../lib/segments'
import { Icon, UnderlineSample, VerdictIcon } from './Icon'
import styles from './ReadingPane.module.css'

export type Side = 'britannica' | 'wikipedia'
type OldView = 'summary' | 'original' | 'scan'

/** Ask the pane to scroll to a passage and flash it. `nonce` lets the same passage be asked for twice. */
export interface PassageFocus {
  passageId: string
  nonce: number
}

interface Props {
  comparison: Comparison
  activeId: string | null
  onActivate: (id: string | null) => void
  focus: PassageFocus | null
  narrow: boolean
  side: Side
  onSideChange: (side: Side) => void
}

interface Bridge {
  left: { y: number; out: boolean }
  right: { y: number; out: boolean }
  verdict: Alignment['verdict']
}

const sideOf = (passageId: string): Side => (passageId.startsWith('W') ? 'wikipedia' : 'britannica')

const OLD_VIEWS: { id: OldView; label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'original', label: 'Original text' },
  { id: 'scan', label: 'Page scan' },
]

export function ReadingPane({ comparison: c, activeId, onActivate, focus, narrow, side, onSideChange }: Props) {
  const paneRef = useRef<HTMLDivElement>(null)
  const seamRef = useRef<HTMLDivElement>(null)
  const leftRef = useRef<HTMLDivElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [bridge, setBridge] = useState<Bridge | null>(null)
  const [seamX, setSeamX] = useState<[number, number]>([0, 0])
  const [oldView, setOldView] = useState<OldView>('summary')

  const byId = useMemo(() => new Map(c.alignments.map((a) => [a.id, a])), [c.alignments])
  const active = activeId ? (byId.get(activeId) ?? null) : null
  const shownId = hoverId ?? activeId

  // Draw one line across the seam, between the two halves of the hovered or selected pair.
  const measure = useCallback(() => {
    const pane = paneRef.current
    const seam = seamRef.current
    const L = leftRef.current
    const R = rightRef.current
    const a = shownId ? byId.get(shownId) : undefined
    if (narrow || !pane || !seam || !L || !R || !a?.britannica || !a.wikipedia || oldView !== 'summary') {
      setBridge(null)
      return
    }
    const p = pane.getBoundingClientRect()
    const s = seam.getBoundingClientRect()
    // Inset so the end dots clear the passage numbers in the gutter.
    setSeamX([s.left - p.left + 4, s.right - p.left - 4])
    const end = (body: HTMLElement) => {
      const el = body.querySelector<HTMLElement>(`[data-align="${a.id}"]`)
      if (!el) return null
      const box = body.getBoundingClientRect()
      const r = el.getClientRects()[0] ?? el.getBoundingClientRect()
      const y = r.top + r.height / 2
      const clamped = Math.min(Math.max(y, box.top + 10), box.bottom - 10)
      return { y: clamped - p.top, out: clamped !== y }
    }
    const left = end(L)
    const right = end(R)
    setBridge(left && right ? { left, right, verdict: a.verdict } : null)
  }, [byId, shownId, narrow, oldView])

  useLayoutEffect(() => {
    measure()
  }, [measure])

  useEffect(() => {
    let frame = 0
    const schedule = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(measure)
    }
    const L = leftRef.current
    const R = rightRef.current
    L?.addEventListener('scroll', schedule, { passive: true })
    R?.addEventListener('scroll', schedule, { passive: true })
    const ro = new ResizeObserver(schedule)
    if (paneRef.current) ro.observe(paneRef.current)
    document.fonts?.ready.then(schedule)
    return () => {
      cancelAnimationFrame(frame)
      L?.removeEventListener('scroll', schedule)
      R?.removeEventListener('scroll', schedule)
      ro.disconnect()
    }
  }, [measure])

  // Selecting a pair brings both halves into view, in the Summary.
  useEffect(() => {
    if (!activeId) return
    setOldView('summary')
    requestAnimationFrame(() => {
      for (const body of [leftRef.current, rightRef.current]) {
        const el = body?.querySelector<HTMLElement>(`[data-align="${activeId}"]`)
        if (body && el) revealIn(body, el)
      }
    })
  }, [activeId, side, narrow])

  // Citation jumps from the agent. Each request (nonce) is handled once; on a
  // narrow screen we first switch to the right column and handle it on the re-run.
  const handled = useRef(-1)
  useEffect(() => {
    if (!focus || handled.current === focus.nonce) return
    const target = sideOf(focus.passageId)
    if (narrow && target !== side) {
      onSideChange(target)
      return
    }
    handled.current = focus.nonce
    setOldView('summary')
    requestAnimationFrame(() => {
      const body = target === 'britannica' ? leftRef.current : rightRef.current
      const el = body?.querySelector<HTMLElement>(`[data-pid="${focus.passageId}"]`)
      if (!body || !el) return
      revealIn(body, el)
      el.classList.remove(styles.flash)
      void el.offsetWidth
      el.classList.add(styles.flash)
    })
  }, [focus, narrow, side, onSideChange])

  const markProps = { byId, activeId, shownId, onHover: setHoverId, onActivate }
  const index = active ? c.alignments.indexOf(active) : -1
  const step = (delta: number) => {
    const n = c.alignments.length
    if (n === 0) return
    const from = index < 0 ? (delta > 0 ? -1 : 0) : index
    onActivate(c.alignments[(from + delta + n) % n].id)
  }

  const b = c.britannica

  return (
    <div ref={paneRef} className={`${styles.pane} ${narrow ? styles.narrow : ''}`}>
      <article className={styles.col} aria-label={`Britannica, ${b.year}`} hidden={narrow && side !== 'britannica'}>
        <header className={styles.head}>
          <h2 className={styles.headword}>{b.headword}</h2>
          <p className={`${styles.meta} num`}>
            Britannica, {b.edition.toLowerCase()}, {b.year}
          </p>
          <div className={styles.views} role="tablist" aria-label="How to show the Britannica page">
            {OLD_VIEWS.map((v) => (
              <button key={v.id} type="button" role="tab" aria-selected={oldView === v.id} onClick={() => setOldView(v.id)}>
                {v.label}
              </button>
            ))}
          </div>
        </header>
        <div ref={leftRef} className={styles.body} tabIndex={0} aria-label={`Britannica ${OLD_VIEWS.find((v) => v.id === oldView)!.label}`}>
          {oldView === 'summary' && (
            <>
              <Passages passages={b.passages} side="britannica" headword={b.headword} {...markProps} />
              <p className={styles.note}>The entry, cleaned from the parsed page. Passage numbers are what the agent cites.</p>
            </>
          )}
          {oldView === 'original' && (
            <>
              <p className={styles.noteTop}>Everything Nemotron Parse read from the page, unedited.</p>
              <div className={styles.raw}>{b.rawText}</div>
            </>
          )}
          {oldView === 'scan' && <Scan comparison={c} />}
        </div>
      </article>

      <div ref={seamRef} className={styles.seam} aria-hidden="true" />

      <article className={styles.col} aria-label="Wikipedia" hidden={narrow && side !== 'wikipedia'}>
        {c.wikipedia ? (
          <>
            <header className={styles.head}>
              <h2 className={styles.title}>{c.wikipedia.title}</h2>
              <p className={`${styles.meta} num`}>
                Wikipedia, {formatDate(c.wikipedia.dateModified)}{' '}
                <a href={c.wikipedia.url} target="_blank" rel="noreferrer" className={styles.ext} aria-label="Open the article on Wikipedia">
                  <Icon name="external" size={13} />
                </a>
              </p>
            </header>
            <div ref={rightRef} className={styles.body} tabIndex={0} aria-label="Wikipedia text">
              <Passages passages={c.wikipedia.passages} side="wikipedia" {...markProps} />
            </div>
          </>
        ) : (
          <NoCounterpart comparison={c} />
        )}
      </article>

      {bridge && (
        <svg className={styles.bridges} aria-hidden="true">
          <path
            className={styles.bridge}
            d={`M${seamX[0]},${bridge.left.y} C${(seamX[0] + seamX[1]) / 2},${bridge.left.y} ${(seamX[0] + seamX[1]) / 2},${bridge.right.y} ${seamX[1]},${bridge.right.y}`}
            strokeDasharray={bridge.left.out || bridge.right.out ? '3 4' : undefined}
          />
          <circle cx={seamX[0]} cy={bridge.left.y} r="3.5" style={{ fill: bridge.verdict ? `var(--${bridge.verdict}-line)` : 'var(--ink)' }} />
          <circle cx={seamX[1]} cy={bridge.right.y} r="3.5" className={styles.dotNow} />
        </svg>
      )}

      {c.alignments.length > 0 && (
        <BridgeBar alignment={active} index={index} total={c.alignments.length} narrow={narrow} side={side} year={b.year} onStep={step} onClose={() => onActivate(null)} onShow={onSideChange} />
      )}
    </div>
  )
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function revealIn(body: HTMLElement, el: HTMLElement) {
  const b = body.getBoundingClientRect()
  const r = el.getBoundingClientRect()
  if (r.top >= b.top + 24 && r.bottom <= b.bottom - 24) return
  const top = body.scrollTop + (r.top - b.top) - body.clientHeight / 3
  body.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
}

interface MarkProps {
  byId: Map<string, Alignment>
  activeId: string | null
  shownId: string | null
  onHover: (id: string | null) => void
  onActivate: (id: string | null) => void
}

function Passages({ passages, side, headword, ...marks }: { passages: Passage[]; side: Side; headword?: string } & MarkProps) {
  const anchors = useMemo(() => {
    const byPassage = new Map<string, { quote: string; key: string }[]>()
    for (const a of marks.byId.values()) {
      const anchor = side === 'britannica' ? a.britannica : a.wikipedia
      if (!anchor) continue
      const list = byPassage.get(anchor.passageId) ?? []
      list.push({ quote: anchor.quote, key: a.id })
      byPassage.set(anchor.passageId, list)
    }
    return byPassage
  }, [marks.byId, side])

  const out: ReactNode[] = []
  let section: string | undefined
  for (const p of passages) {
    if (p.section && p.section !== section) {
      section = p.section
      const isLead = side === 'wikipedia' ? p.section === 'Introduction' : p.section === headword
      if (!isLead) {
        out.push(
          <h3 key={`h-${p.id}`} className={side === 'britannica' ? styles.subentry : styles.section}>
            {p.section}
          </h3>,
        )
      }
    }
    const spans = locate(p.text, anchors.get(p.id) ?? [])
    out.push(
      <p key={p.id} className={styles.passage} data-pid={p.id}>
        <span className={`${styles.pid} num`}>{p.id}</span>
        {segment(p.text, spans).map((s, i) => (s.key === null ? s.text : <Mark key={i} id={s.key} text={s.text} side={side} {...marks} />))}
      </p>,
    )
  }
  return <div className={side === 'britannica' ? styles.caslon : styles.modern}>{out}</div>
}

function Mark({ id, text, side, byId, activeId, shownId, onHover, onActivate }: { id: string; text: string; side: Side } & MarkProps) {
  const a = byId.get(id)
  if (!a) return text
  // Old claims carry their verdict; modern phrases stay neutral, because they are the reference.
  const tone = side === 'britannica' && a.verdict ? a.verdict : 'neutral'
  const label = a.verdict ? VERDICTS[a.verdict].label : KINDS[a.kind].label
  const toggle = () => onActivate(activeId === id ? null : id)
  return (
    <mark
      data-align={id}
      data-tone={tone}
      className={`${styles.mark} ${shownId === id ? styles.on : ''}`}
      role="button"
      tabIndex={0}
      aria-pressed={activeId === id}
      title={`${label}: ${a.label}`}
      onMouseEnter={() => onHover(id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(id)}
      onBlur={() => onHover(null)}
      onClick={toggle}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          toggle()
        }
      }}
    >
      {text}
      {side === 'britannica' && <span className="visually-hidden">, {label}</span>}
    </mark>
  )
}

interface BarProps {
  alignment: Alignment | null
  index: number
  total: number
  narrow: boolean
  side: Side
  year: number
  onStep: (delta: number) => void
  onClose: () => void
  onShow: (side: Side) => void
}

function BridgeBar({ alignment: a, index, total, narrow, side, year, onStep, onClose, onShow }: BarProps) {
  if (!a) {
    return (
      <div className={styles.bar}>
        <ul className={styles.legend} aria-label="What the underlines mean">
          {VERDICT_ORDER.map((v) => (
            <li key={v}>
              <UnderlineSample verdict={v} />
              {VERDICTS[v].label}
            </li>
          ))}
        </ul>
        <button type="button" className="btn" onClick={() => onStep(1)}>
          Step through {total} claims <Icon name="arrow" size={14} />
        </button>
      </div>
    )
  }
  const other: Side = side === 'britannica' ? 'wikipedia' : 'britannica'
  const otherAnchor = other === 'britannica' ? a.britannica : a.wikipedia
  return (
    <div className={`${styles.bar} ${styles.barActive}`} role="status" aria-live="polite">
      <div className={styles.barText}>
        <p className={styles.barHead}>
          {a.verdict ? (
            <span className={styles.verdict} data-tone={a.verdict}>
              <VerdictIcon verdict={a.verdict} />
              {VERDICTS[a.verdict].label}
            </span>
          ) : (
            <span className={styles.verdict}>{KINDS[a.kind].label}</span>
          )}
          <span className={styles.barLabel}>{a.label}</span>
          {a.verdict && <span className={styles.kind}>{KINDS[a.kind].label}</span>}
        </p>
        <p className={styles.barNote}>{a.note}</p>
        {narrow && otherAnchor && (
          <p className={styles.barOther}>
            <span className="num">{other === 'britannica' ? year : 'Today'}:</span> “{otherAnchor.quote}”{' '}
            <button type="button" className={styles.linkBtn} onClick={() => onShow(other)}>
              Show
            </button>
          </p>
        )}
      </div>
      <div className={styles.barNav}>
        <button type="button" className="btn btn-quiet btn-icon" onClick={() => onStep(-1)} aria-label="Previous claim">
          <Icon name="prev" />
        </button>
        <span className="num">
          {index + 1} / {total}
        </span>
        <button type="button" className="btn btn-quiet btn-icon" onClick={() => onStep(1)} aria-label="Next claim">
          <Icon name="next" />
        </button>
        <button type="button" className="btn btn-quiet btn-icon" onClick={onClose} aria-label="Close">
          <Icon name="close" />
        </button>
      </div>
    </div>
  )
}

function Scan({ comparison: c }: { comparison: Comparison }) {
  const b = c.britannica
  if (b.imageUrl) {
    return (
      <figure className={styles.scan}>
        <img src={b.imageUrl} alt={`Page scan: ${b.headword}, ${b.edition} ${b.year}`} />
        <figcaption>{b.meta}</figcaption>
      </figure>
    )
  }
  return (
    <div className={styles.scanEmpty}>
      <p>The page scan appears here once the backend sends an image for this page.</p>
      <p className={styles.scanMeta}>{b.meta}</p>
    </div>
  )
}

function NoCounterpart({ comparison: c }: { comparison: Comparison }) {
  return (
    <div className={styles.none}>
      <h2 className={styles.title}>No clear modern counterpart</h2>
      <p>
        No Wikipedia article is a credible match for this {c.britannica.year} entry, so nothing is compared. The closest candidates, with their rerank
        scores (0.5 needed):
      </p>
      <ul className={styles.noneList}>
        {c.candidates.map((k) => (
          <li key={k.title}>
            <a href={k.url} target="_blank" rel="noreferrer">
              {k.title}
            </a>
            <span className="num">{k.rerankScore.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
