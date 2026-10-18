// The backend may not know an entry's edition or year yet. These helpers keep
// that visible ("edition not recorded") instead of guessing.

interface Dated {
  edition: string
  year: number | null
}

const known = (edition: string) => edition && edition.toLowerCase() !== 'not recorded'

/** "Third edition, 1797", "Third edition", or "Edition not recorded". */
export function editionLine(d: Dated): string {
  const parts = [known(d.edition) ? d.edition : null, d.year !== null ? String(d.year) : null].filter(Boolean)
  return parts.length ? parts.join(', ') : 'Edition not recorded'
}

/** A short name for the old text: "1797", or "Britannica" when the year is unknown. */
export const thenName = (d: Dated) => (d.year !== null ? String(d.year) : 'Britannica')

/** "the 1797 entry", or "the Britannica entry". */
export const theEntry = (d: Dated) => (d.year !== null ? `the ${d.year} entry` : 'the Britannica entry')
