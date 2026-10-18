import type { Verdict } from '../api/types'

// One stroke icon set, drawn on a 16px grid at 1.5px. Decorative by default:
// the control that holds an icon carries the accessible name.

const PATHS = {
  close: 'M4 4l8 8M12 4l-8 8',
  prev: 'M10 3.5L5.5 8l4.5 4.5',
  next: 'M6 3.5l4.5 4.5L6 12.5',
  arrow: 'M3 8h10M9 4l4 4-4 4',
  external: 'M6 3.5h6.5V10M12.5 3.5L4 12',
  /* Panel docked on the right: hide pushes it right, show pulls it left. */
  panelHide: 'M5.5 3.5L10 8l-4.5 4.5M13 2.5v11',
  panelShow: 'M10.5 3.5L6 8l4.5 4.5M13 2.5v11',
  chat: 'M2.75 3.25h10.5v7.5H8l-3.25 2.5v-2.5h-2z',
  check: 'M3.5 8.5l3 3 6-7',
  partly: 'M3.5 8h9',
  wrong: 'M4.5 4.5l7 7M11.5 4.5l-7 7',
  absent: 'M2.75 8h1.5M7.25 8h1.5M11.75 8h1.5',
  pending: 'M8 4v4l2.5 1.5M8 2.75a5.25 5.25 0 1 1 0 10.5a5.25 5.25 0 1 1 0-10.5',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}

const VERDICT_ICON: Record<Verdict, IconName> = { agrees: 'check', differs: 'partly', contradicts: 'wrong', not_in_wikipedia: 'absent' }

/** A verdict's icon, in its colour. Always shown next to a label, never alone. */
export function VerdictIcon({ verdict, size = 14 }: { verdict: Verdict; size?: number }) {
  return (
    <span data-tone={verdict} style={{ display: 'inline-flex', color: 'var(--tone-line)' }}>
      <Icon name={VERDICT_ICON[verdict]} size={size} />
    </span>
  )
}

/** A short sample of the underline a verdict draws in the text, for legends. */
export function UnderlineSample({ verdict }: { verdict: Verdict }) {
  const stroke = 'var(--tone-line)'
  const dash = verdict === 'differs' ? '3.5 2.5' : verdict === 'not_in_wikipedia' ? '1.2 2.4' : undefined
  return (
    <svg data-tone={verdict} width="22" height="8" viewBox="0 0 22 8" fill="none" aria-hidden="true" focusable="false">
      {verdict === 'contradicts' ? (
        <path d="M1 5c1.5-3 3-3 4.5 0s3 3 4.5 0 3-3 4.5 0 3 3 4.5 0" stroke={stroke} strokeWidth="1.4" strokeLinecap="round" />
      ) : (
        <path d="M1 5h20" stroke={stroke} strokeWidth="1.6" strokeDasharray={dash} strokeLinecap={verdict === 'not_in_wikipedia' ? 'round' : undefined} />
      )}
    </svg>
  )
}
