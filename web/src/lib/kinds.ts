import type { ChangeKind, Verdict } from '../api/types'

/** Whether the Britannica claim holds up today. The only use of colour in the app. */
export const VERDICTS: Record<Verdict, { label: string; hint: string }> = {
  correct: { label: 'Correct', hint: 'Still true today' },
  partly: { label: 'Partly correct', hint: 'Half right, or true then but not now' },
  wrong: { label: 'Wrong', hint: 'Contradicted by current knowledge' },
}

export const VERDICT_ORDER: Verdict[] = ['wrong', 'partly', 'correct']

/** What kind of change it is. The challenge asks to tell language change from knowledge change. */
export const KINDS: Record<ChangeKind, { label: string; family: 'same' | 'language' | 'knowledge' }> = {
  retained: { label: 'Same wording', family: 'same' },
  reworded: { label: 'New words', family: 'language' },
  revised: { label: 'New knowledge', family: 'knowledge' },
  dropped: { label: 'Dropped since', family: 'knowledge' },
  added: { label: 'New since', family: 'knowledge' },
}
