import { useId, useMemo, useState, type KeyboardEvent } from 'react'
import type { TopicSummary } from '../api/types'
import { fieldFor } from '../config/areas'
import { editionLine } from '../lib/when'
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
  /** The word the empty field shows and searches for, e.g. "Blood". */
  example?: string
}

/** The search field, set like an encyclopaedia headword: "BLOOD, in anatomy." The field follows the topic's subject area. */
export function Headword({ topics, value, onChange, onSubmit, size, autoFocus, example = 'Blood' }: Props) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)

  const options = useMemo(() => {
    const q = value.trim().toLowerCase()
    if (!q) return topics.slice(0, 12)
    return topics
      .filter((t) => t.label.toLowerCase().includes(q) || (t.headword ?? '').toLowerCase().includes(q) || t.wikipediaTitle?.toLowerCase().includes(q))
      .slice(0, 12)
  }, [topics, value])

  const field = fieldFor(value || example, topics)

  // In the hero an empty field searches for the word it shows ("Blood"), so the first click works.
  const fallback = size === 'hero' ? example : ''
  const query = value.trim() || fallback

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

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
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
      choose(options[active].slug)
    }
  }

  return (
    <form
      role="search"
      className={`${styles.form} ${styles[size]}`}
      onSubmit={(e) => {
        e.preventDefault()
        if (query) choose(query)
      }}
    >
      <label htmlFor={`${id}-input`} className="visually-hidden">
        Medical topic
      </label>
      <div className={styles.line}>
        <span className={styles.field} data-value={value || example}>
          <input
            id={`${id}-input`}
            className={styles.input}
            size={1}
            value={value}
            placeholder={example}
            autoComplete="off"
            spellCheck={false}
            autoFocus={autoFocus}
            role="combobox"
            aria-expanded={open && options.length > 0}
            aria-controls={`${id}-list`}
            aria-autocomplete="list"
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
        <span className={styles.suffix} aria-hidden="true" hidden={!field}>
          , <em>{field}.</em>
        </span>
        {size === 'compact' && go}
      </div>
      {size === 'hero' && go}

      {open && options.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className={styles.list} aria-label="Indexed topics">
          {options.map((t, i) => (
            <li
              key={t.slug}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={styles.option}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(t.slug)}
            >
              <span className={styles.optHead}>{t.headword ?? t.label}</span>
              <span className={`${styles.optMeta} num`}>{editionLine(t)}</span>
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
