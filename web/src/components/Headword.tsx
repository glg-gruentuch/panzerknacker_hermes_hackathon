import { useEffect, useId, useMemo, useState, type CSSProperties, type KeyboardEvent } from 'react'
import type { TopicSummary } from '../api/types'
import { useMediaQuery } from '../lib/useMediaQuery'
import { Icon } from './Icon'
import { MatchMark } from './MatchMark'
import styles from './Headword.module.css'

interface Props {
  topics: TopicSummary[]
  value: string
  onChange: (value: string) => void
  onSubmit: (query: string) => void
  size: 'hero' | 'compact'
  autoFocus?: boolean
}

const TYPE_MS = 90
const DELETE_MS = 40
const HOLD_MS = 1600
const GAP_MS = 400

/**
 * Types out each name in turn, holds it, deletes it, and moves on.
 * Returns the visible text and the full name it is typing.
 */
function useTypewriter(names: string[], running: boolean) {
  const [index, setIndex] = useState(0)
  const [length, setLength] = useState(0)
  const [deleting, setDeleting] = useState(false)

  const name = names.length ? names[index % names.length] : ''

  useEffect(() => {
    if (!running || !name) return
    let delay: number
    let step: () => void
    if (!deleting && length < name.length) {
      delay = TYPE_MS
      step = () => setLength((n) => n + 1)
    } else if (!deleting) {
      delay = HOLD_MS
      step = () => setDeleting(true)
    } else if (length > 0) {
      delay = DELETE_MS
      step = () => setLength((n) => n - 1)
    } else {
      delay = GAP_MS
      step = () => {
        setDeleting(false)
        setIndex((i) => (i + 1) % names.length)
      }
    }
    const timer = window.setTimeout(step, delay)
    return () => window.clearTimeout(timer)
  }, [running, name, length, deleting, names.length])

  return { text: name.slice(0, length), name }
}

/** The search field, set like an encyclopaedia headword. It only suggests articles the site has. */
export function Headword({ topics, value, onChange, onSubmit, size, autoFocus }: Props) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const reduceMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

  const names = useMemo(() => topics.map((t) => t.label), [topics])
  const longest = useMemo(() => names.reduce((a, b) => (b.length > a.length ? b : a), ''), [names])
  const typewriter = useTypewriter(names, !value && !reduceMotion)
  const placeholder = reduceMotion ? (names[0] ?? '') : typewriter.text

  // Suggestions appear once the reader types. Names that start with the text come first.
  const options = useMemo(() => {
    const q = value.trim().toLowerCase()
    if (!q) return []
    const starts = (t: TopicSummary) => t.label.toLowerCase().startsWith(q) || t.headword.toLowerCase().startsWith(q)
    return topics
      .filter((t) => t.label.toLowerCase().includes(q) || t.headword.toLowerCase().includes(q) || t.wikipediaTitle?.toLowerCase().includes(q))
      .sort((a, b) => Number(starts(b)) - Number(starts(a)))
  }, [topics, value])

  // The inline completion: the rest of the first article name that starts with the typed text.
  const completion = value ? names.find((n) => n.toLowerCase().startsWith(value.toLowerCase()) && n.length > value.length) : undefined
  const ghost = completion ? completion.slice(value.length) : ''

  // In the hero an empty field searches for the name it is typing out, so the first click works.
  const fallback = size === 'hero' ? typewriter.name || names[0] || '' : ''
  const query = completion ?? (value.trim() || fallback)

  // The ::after mirror sizes the field. In the masthead it holds the longest name, so the button does not move.
  const mirror = value ? (completion ?? value) : size === 'hero' ? placeholder : longest

  // In the hero the button sits on its own line under the headword; in the masthead it follows it.
  const go = (
    <button type="submit" className={styles.go} disabled={!query}>
      Compare
      <Icon name="arrow" size={14} />
    </button>
  )

  const choose = (query: string) => {
    setOpen(false)
    setActive(-1)
    onChange(query)
    onSubmit(query)
  }

  const accept = () => {
    if (!completion) return
    onChange(completion)
    setActive(-1)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    const atEnd = e.currentTarget.selectionStart === value.length && e.currentTarget.selectionEnd === value.length
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(options.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(-1, i - 1))
    } else if (e.key === 'Escape') {
      setOpen(false)
      setActive(-1)
    } else if (e.key === 'Enter' && open && active >= 0 && options[active]) {
      e.preventDefault()
      choose(options[active].label)
    } else if (ghost && ((e.key === 'Tab' && !e.shiftKey) || (e.key === 'ArrowRight' && atEnd))) {
      e.preventDefault()
      accept()
    }
  }

  return (
    <form
      role="search"
      className={`${styles.form} ${styles[size]}`}
      style={{ '--chars': longest.length + 1 } as CSSProperties}
      onSubmit={(e) => {
        e.preventDefault()
        if (query) choose(query)
      }}
    >
      <label htmlFor={`${id}-input`} className="visually-hidden">
        Article
      </label>
      <div className={styles.line}>
        <span className={styles.field} data-value={mirror}>
          {ghost && (
            <span className={styles.ghost} aria-hidden="true">
              <span className={styles.ghostTyped}>{value}</span>
              {ghost}
            </span>
          )}
          <input
            id={`${id}-input`}
            className={styles.input}
            size={1}
            value={value}
            placeholder={placeholder}
            autoComplete="off"
            spellCheck={false}
            autoFocus={autoFocus}
            role="combobox"
            aria-expanded={open && options.length > 0}
            aria-controls={`${id}-list`}
            aria-autocomplete="both"
            aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
            onChange={(e) => {
              onChange(e.target.value)
              setOpen(true)
              setActive(-1)
            }}
            onClick={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            onKeyDown={onKeyDown}
          />
        </span>
        {size === 'compact' && go}
      </div>
      {size === 'hero' && go}

      {open && options.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className={styles.list} aria-label="Articles">
          {options.map((t, i) => (
            <li
              key={t.slug}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={styles.option}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(t.label)}
            >
              <span className={styles.optHead}>{t.headword}</span>
              <span className={`${styles.optMeta} num`}>
                {t.edition}, {t.year}
              </span>
              <span className={styles.optMatch}>
                <MatchMark strength={t.match} />
                {t.wikipediaTitle ?? 'No clear match'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </form>
  )
}
