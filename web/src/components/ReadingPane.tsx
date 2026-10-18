import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Alignment, Comparison, Passage, ScanBlock, TextFix } from '../api/types'
import { KINDS, VERDICTS, VERDICT_ORDER } from '../lib/kinds'
import { locate, segment } from '../lib/segments'
import { editionLine, thenName } from '../lib/when'
import { Icon, UnderlineSample, VerdictIcon } from './Icon'
import styles from './ReadingPane.module.css'

export type Side = 'britannica' | 'wikipedia'
type OldView = 'summary' | 'normalized' | 'original' | 'scan'

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
  { id: 'normalized', label: 'Normalized' },
  { id: 'original', label: 'Original text' },
  { id: 'scan', label: 'Scan' },
]

const squash = (s: string) => s.toLowerCase().replace(/\s+/g, ' ').trim()

/** The Parse block that holds a piece of text, matched on the text's opening words. */
function blockFor(blocks: ScanBlock[], text: string | undefined): ScanBlock | undefined {
  if (!text) return undefined
  const q = squash(text)
  return blocks.find((b) => squash(b.text).includes(q)) ?? blocks.find((b) => squash(b.text).includes(q.slice(0, 48)))
}

export function ReadingPane({ comparison: c, activeId, onActivate, focus, narrow, side, onSideChange }: Props) {
  const paneRef = useRef<HTMLDivElement>(null)
  const seamRef = useRef<HTMLDivElement>(null)
  const leftRef = useRef<HTMLDivElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [bridge, setBridge] = useState<Bridge | null>(null)
  const [seamX, setSeamX] = useState<[number, number]>([0, 0])
  const [oldView, setOldView] = useState<OldView>('summary')
  const [focusedPassage, setFocusedPassage] = useState<string | null>(null)
  const [qualityOpen, setQualityOpen] = useState(false)

  const alignments = c.alignments ?? []
  const byId = useMemo(() => new Map(alignments.map((a) => [a.id, a])), [alignments])
  const active = activeId ? (byId.get(activeId) ?? null) : null
  const shownId = hoverId ?? activeId
  const b = c.britannica

  // Draw one line across the seam, between the two halves of the hovered or selected pair.
  const measure = useCallback(() => {
    const pane = paneRef.current
    const seam = seamRef.current
    const L = leftRef.current
    const R = rightRef.current
    const a = shownId ? byId.get(shownId) : undefined
    if (narrow || !pane || !seam || !L || !R || !a?.wikipedia || oldView !== 'summary') {
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

  // Selecting a pair brings both halves into view, unless the scan is open (it boxes the claim there).
  useEffect(() => {
    if (!activeId) return
    setOldView((v) => (v === 'scan' ? v : 'summary'))
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
    if (target === 'britannica') setFocusedPassage(focus.passageId)
    setOldView((v) => (v === 'scan' && target === 'britannica' ? v : 'summary'))
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
  const index = active ? alignments.indexOf(active) : -1
  const step = (delta: number) => {
    const n = alignments.length
    if (n === 0) return
    const from = index < 0 ? (delta > 0 ? -1 : 0) : index
    onActivate(alignments[(from + delta + n) % n].id)
  }

  // What the scan view should box: the selected claim, else the last cited passage.
  const boxed = active
    ? blockFor(b.blocks, active.britannica?.quote)
    : blockFor(b.blocks, b.passages.find((p) => p.id === focusedPassage)?.text)

  return (
    <div ref={paneRef} className={`${styles.pane} ${narrow ? styles.narrow : ''}`}>
      <article className={styles.col} aria-label={`Britannica, ${editionLine(b)}`} hidden={narrow && side !== 'britannica'}>
        <header className={styles.head}>
          <h2 className={b.headword ? styles.headword : styles.fragmentTitle}>{b.headword ?? 'Fragment'}</h2>
          {b.quality && (
            <button type="button" className={styles.chip} aria-expanded={qualityOpen} onClick={() => setQualityOpen((o) => !o)}>
              {b.quality.dictionaryShare !== null ? `${Math.round(b.quality.dictionaryShare * 100)}% dictionary words` : 'Extraction'}
              {b.quality.issues.length > 0 && <span className={styles.chipCount}>{b.quality.issues.length} issues</span>}
            </button>
          )}
          <p className={`${styles.meta} num`}>Britannica, {editionLine(b).toLowerCase()}</p>
          <div className={styles.views} role="tablist" aria-label="How to show the Britannica page">
            {OLD_VIEWS.map((v) => (
              <button key={v.id} type="button" role="tab" aria-selected={oldView === v.id} onClick={() => setOldView(v.id)}>
                {v.label}
              </button>
            ))}
          </div>
        </header>
        {qualityOpen && b.quality && (
          <div className={styles.quality}>
            <p>
              {b.quality.dictionaryShare !== null && (
                <>
                  <b className="num">{Math.round(b.quality.dictionaryShare * 100)}%</b> of words are in a dictionary after normalization.{' '}
                </>
              )}
              {b.quality.pdfUrl && (
                <a href={b.quality.pdfUrl} target="_blank" rel="noreferrer">
                  Compiled PDF <Icon name="external" size={12} />
                </a>
              )}
            </p>
            {b.quality.issues.length > 0 ? (
              <ul>
                {b.quality.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            ) : (
              <p className={styles.dim}>No known OCR issues on this page.</p>
            )}
          </div>
        )}
        <div ref={leftRef} className={styles.body} tabIndex={0} aria-label={`Britannica ${OLD_VIEWS.find((v) => v.id === oldView)!.label}`}>
          {b.fragment && (
            <p className={styles.fragmentNote}>
              This text continues an entry that started on an earlier page, outside the sample.
              {b.pageHeader && <> Running head: “{b.pageHeader}”.</>}
            </p>
          )}
          {oldView === 'summary' && (
            <>
              <Passages passages={b.passages} side="britannica" headword={b.headword} {...markProps} />
              <p className={styles.note}>The entry, cleaned from the parsed page. Passage numbers are what the agent cites.</p>
            </>
          )}
          {oldView === 'normalized' &&
            (b.normalized ? (
              <>
                <p className={styles.noteTop}>
                  {b.normalized.fixes.length
                    ? `${b.normalized.fixes.length} long-s and OCR fixes, marked. Point at one to see what the scan had.`
                    : 'No long-s or OCR fixes were needed on this entry.'}
                </p>
                <Normalized text={b.normalized.text} fixes={b.normalized.fixes} />
              </>
            ) : (
              <Pending what="Normalization" />
            ))}
          {oldView === 'original' && (
            <>
              <p className={styles.noteTop}>Everything Nemotron Parse read from the page, unedited.</p>
              <div className={styles.raw}>{b.rawText}</div>
            </>
          )}
          {oldView === 'scan' && <Scan comparison={c} boxed={boxed} claimSelected={!!active} />}
        </div>
      </article>

      <div ref={seamRef} className={styles.seam} aria-hidden="true" />

      <article className={styles.col} aria-label="Wikipedia" hidden={narrow && side !== 'wikipedia'}>
        {c.wikipedia ? (
          <>
            <header className={styles.head}>
              <h2 className={styles.title}>{c.wikipedia.title}</h2>
              <p className={`${styles.meta} num`}>
                Wikipedia,{' '}
                <a href={c.wikipedia.revisionUrl ?? c.wikipedia.url} target="_blank" rel="noreferrer" className={styles.revision}>
                  {c.wikipedia.revisionId ? `revision ${c.wikipedia.revisionId}` : 'revision pending'}
                  <Icon name="external" size={12} />
                </a>
                {c.wikipedia.dateModified && <>, {formatDate(c.wikipedia.dateModified)}</>}
              </p>
            </header>
            <div ref={rightRef} className={styles.body} tabIndex={0} aria-label="Wikipedia text">
              <Passages passages={c.wikipedia.passages} side="wikipedia" {...markProps} />
              <p className={styles.note}>
                Text from Wikipedia, available under {c.wikipedia.license}. Quoted for comparison; the article may have changed since this revision.
              </p>
            </div>
          </>
        ) : c.match.strength === 'pending' ? (
          <MatchPending comparison={c} />
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
          <circle cx={seamX[0]} cy={bridge.left.y} r="3.5" data-tone={bridge.verdict} style={{ fill: 'var(--tone-line)' }} />
          <circle cx={seamX[1]} cy={bridge.right.y} r="3.5" className={styles.dotNow} />
        </svg>
      )}

      <BridgeBar
        comparison={c}
        alignment={active}
        index={index}
        narrow={narrow}
        side={side}
        onStep={step}
        onClose={() => onActivate(null)}
        onShow={onSideChange}
      />
    </div>
  )
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
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

function Passages({ passages, side, headword, ...marks }: { passages: Passage[]; side: Side; headword?: string | null } & MarkProps) {
  const lead = headword ?? undefined
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
      const isLead = side === 'wikipedia' ? p.section === 'Introduction' : p.section === lead || p.section === '(fragment)'
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
  // Old claims carry their verdict; modern phrases stay neutral, because they are the comparison text.
  const tone = side === 'britannica' ? a.verdict : 'neutral'
  const toggle = () => onActivate(activeId === id ? null : id)
  return (
    <mark
      data-align={id}
      data-tone={tone}
      className={`${styles.mark} ${shownId === id ? styles.on : ''}`}
      role="button"
      tabIndex={0}
      aria-pressed={activeId === id}
      title={`${VERDICTS[a.verdict].label}: ${a.label ?? a.claimType ?? 'claim'}`}
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
      {side === 'britannica' && <span className="visually-hidden">, {VERDICTS[a.verdict].label}</span>}
    </mark>
  )
}

/** The normalized entry, with each long-s or OCR fix marked and its original on hover. */
function Normalized({ text, fixes }: { text: string; fixes: TextFix[] }) {
  const out: ReactNode[] = []
  let at = 0
  for (const [i, f] of [...fixes].sort((x, y) => x.start - y.start).entries()) {
    if (f.start < at) continue
    out.push(text.slice(at, f.start))
    out.push(
      <mark key={i} className={styles.fix} title={`The scan reads “${f.original.replace(/\n/g, '⏎')}”`}>
        {text.slice(f.start, f.end)}
        <span className="visually-hidden"> (OCR: {f.original})</span>
      </mark>,
    )
    at = f.end
  }
  out.push(text.slice(at))
  return <div className={styles.raw}>{out}</div>
}

interface BarProps {
  comparison: Comparison
  alignment: Alignment | null
  index: number
  narrow: boolean
  side: Side
  onStep: (delta: number) => void
  onClose: () => void
  onShow: (side: Side) => void
}

function BridgeBar({ comparison: c, alignment: a, index, narrow, side, onStep, onClose, onShow }: BarProps) {
  const total = c.alignments?.length ?? 0
  if (!a) {
    return (
      <div className={styles.bar}>
        {c.alignments === null ? (
          <p className={styles.barHint}>
            <Icon name="pending" size={14} /> Claims pending: this entry has not been compared claim by claim yet.
          </p>
        ) : total === 0 ? (
          <p className={styles.barHint}>No claims were extracted from this entry.</p>
        ) : (
          <>
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
          </>
        )}
      </div>
    )
  }
  const other: Side = side === 'britannica' ? 'wikipedia' : 'britannica'
  const otherAnchor = other === 'britannica' ? a.britannica : a.wikipedia
  return (
    <div className={`${styles.bar} ${styles.barActive}`} role="status" aria-live="polite">
      <div className={styles.barText}>
        <p className={styles.barHead}>
          <span className={styles.verdict} data-tone={a.verdict}>
            <VerdictIcon verdict={a.verdict} />
            {VERDICTS[a.verdict].label}
          </span>
          <span className={styles.barLabel}>{a.label ?? (a.claimType ? `A ${a.claimType} claim` : 'Claim')}</span>
          {a.kind && <span className={styles.kind}>{KINDS[a.kind].label}</span>}
          {a.downgraded && <span className={styles.kind}>Lowered: the model’s Wikipedia quote was not in the article</span>}
        </p>
        <p className={styles.barNote}>
          <span className="inference-tag">Inference</span> {a.explanation}
        </p>
        {a.quantity && (
          <p className={`${styles.barOther} num`}>
            {thenName(c.britannica)}: {a.quantity.britannica.value} {a.quantity.britannica.unit}
            {' · '}Today: {a.quantity.wikipedia ? `${a.quantity.wikipedia.value} ${a.quantity.wikipedia.unit}` : 'no figure'}
          </p>
        )}
        {narrow && otherAnchor && (
          <p className={styles.barOther}>
            <span className="num">{other === 'britannica' ? thenName(c.britannica) : 'Today'}:</span> “{otherAnchor.quote}”{' '}
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

/** The page scan, with every Parse block outlined and the selected text boxed. */
function Scan({ comparison: c, boxed, claimSelected }: { comparison: Comparison; boxed: ScanBlock | undefined; claimSelected: boolean }) {
  const b = c.britannica
  if (!b.imageUrl) {
    return (
      <div className={styles.scanEmpty}>
        <p>The page scan appears here once the backend sends an image for this page.</p>
        <p className={styles.scanMeta}>{b.meta}</p>
      </div>
    )
  }
  return (
    <figure className={styles.scan}>
      <p className={styles.noteTop}>
        {boxed
          ? claimSelected
            ? 'The selected claim’s block is boxed on the scan.'
            : 'The cited passage’s block is boxed on the scan.'
          : b.blocks.length
            ? `Nemotron Parse found ${b.blocks.length} blocks on this page. Select a claim or a citation to box its block.`
            : 'No block positions are available for this page.'}
      </p>
      <div className={styles.scanFrame}>
        <img src={b.imageUrl} alt={`Page scan: ${b.headword ?? 'fragment'}, ${editionLine(b)}`} />
        {b.blocks.map((block, i) => (
          <span
            key={i}
            className={`${styles.block} ${block === boxed ? styles.blockOn : ''}`}
            title={`${block.kind}: ${block.text.slice(0, 80)}${block.text.length > 80 ? '…' : ''}`}
            style={{
              left: `${block.bbox[0][0] * 100}%`,
              top: `${block.bbox[0][1] * 100}%`,
              width: `${(block.bbox[1][0] - block.bbox[0][0]) * 100}%`,
              height: `${(block.bbox[1][1] - block.bbox[0][1]) * 100}%`,
            }}
          />
        ))}
      </div>
      <figcaption>
        {b.meta}
        {b.scanSha256 && <span className={styles.sha}> · scan sha256 {b.scanSha256.slice(0, 12)}…</span>}
      </figcaption>
    </figure>
  )
}

function Pending({ what }: { what: string }) {
  return (
    <p className={styles.pending}>
      <Icon name="pending" size={14} /> {what} pending: this stage has not run for this entry yet.
    </p>
  )
}

function MatchPending({ comparison: c }: { comparison: Comparison }) {
  return (
    <div className={styles.none}>
      <h2 className={styles.title}>Matching pending</h2>
      <p>
        This {c.britannica.fragment ? 'fragment' : 'entry'} has not been matched to a Wikipedia article yet. The comparison appears here once the match stage
        has run.
      </p>
    </div>
  )
}

function NoCounterpart({ comparison: c }: { comparison: Comparison }) {
  return (
    <div className={styles.none}>
      <h2 className={styles.title}>No clear modern counterpart</h2>
      <p>
        No Wikipedia article passed the rerank threshold for this entry, so nothing is compared. The closest candidates and their reranker logits
        {c.match.threshold !== null && <> (threshold {c.match.threshold})</>}:
      </p>
      <ul className={styles.noneList}>
        {c.candidates.map((k) => (
          <li key={k.title}>
            <a href={k.url} target="_blank" rel="noreferrer">
              {k.title}
            </a>
            <span className="num">{k.rerankLogit !== null ? k.rerankLogit.toFixed(2) : '–'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
