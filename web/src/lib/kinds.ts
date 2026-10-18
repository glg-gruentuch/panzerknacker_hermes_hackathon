import type { ChangeKind, Grounding, Verdict } from '../api/types'

/**
 * How a Britannica claim compares with the matched Wikipedia article. The only use of colour in the app.
 * Wikipedia is a comparison source, not ground truth: these say whether the texts agree, not who is right.
 */
export const VERDICTS: Record<Verdict, { label: string; hint: string }> = {
  agrees: { label: 'Agrees', hint: 'Wikipedia says the same thing' },
  differs: { label: 'Differs', hint: 'Wikipedia says something related, but not the same' },
  contradicts: { label: 'Contradicts', hint: 'Wikipedia says the opposite' },
  not_in_wikipedia: { label: 'Not in Wikipedia', hint: 'The matched article does not cover this claim' },
}

export const VERDICT_ORDER: Verdict[] = ['contradicts', 'differs', 'agrees', 'not_in_wikipedia']

/** Optional tag: language change or knowledge change, when the backend provides it. */
export const KINDS: Record<ChangeKind, { label: string; family: 'same' | 'language' | 'knowledge' }> = {
  retained: { label: 'Same wording', family: 'same' },
  reworded: { label: 'New words', family: 'language' },
  revised: { label: 'New knowledge', family: 'knowledge' },
  dropped: { label: 'Dropped since', family: 'knowledge' },
}

/** Agent answers use the same scale: well supported reads like agreement, unsupported like contradiction. */
export const GROUNDING_TONE: Record<Grounding, Verdict> = { supported: 'agrees', partial: 'differs', unsupported: 'contradicts' }
