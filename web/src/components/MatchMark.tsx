import type { MatchStrength } from '../api/types'
import styles from './MatchMark.module.css'

export const MATCH_LABEL: Record<MatchStrength, string> = {
  strong: 'Clear match',
  partial: 'Partial match',
  none: 'No clear match',
}

/** A filled, half or empty circle: how confident the pairing is. */
export function MatchMark({ strength, withLabel = false }: { strength: MatchStrength; withLabel?: boolean }) {
  return (
    <span className={styles.wrap} title={MATCH_LABEL[strength]}>
      <svg className={styles.mark} viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="4.75" fill="none" stroke="currentColor" strokeWidth="1.5" />
        {strength === 'strong' && <circle cx="6" cy="6" r="4.75" fill="currentColor" />}
        {strength === 'partial' && <path d="M6 1.25a4.75 4.75 0 0 1 0 9.5z" fill="currentColor" />}
      </svg>
      {withLabel ? <span>{MATCH_LABEL[strength]}</span> : <span className="visually-hidden">{MATCH_LABEL[strength]}</span>}
    </span>
  )
}
