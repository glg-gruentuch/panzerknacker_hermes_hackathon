import type { AreaSlug, TopicSummary } from '../api/types'
import plates from './plates.json'

// The subject areas on the landing page. The backend tags each topic with one
// of these slugs (`area`); this file decides how each area looks and which of
// its articles to feature. Edit it freely.

export interface Plate {
  slug: string
  title: string
  src: string
  width: number
  height: number
  pageId: string
  row: number
  volumeId: string
  meta: string
  sourceSha256: string
}

export interface Area {
  slug: AreaSlug
  label: string
  /** One plain sentence on what the area covers. */
  blurb: string
  /** How a Britannica headword names its field: "BLOOD, in anatomy." */
  field: string
  plate: Plate
  /** Topic slugs to show first, with their teaser and verdicts. The rest follow in index order. */
  featured: string[]
}

const plate = (slug: string): Plate => {
  const p = (plates as Plate[]).find((x) => x.slug === slug)
  if (!p) throw new Error(`Plate "${slug}" is missing from plates.json. Run web/scripts/prepare-plates.py.`)
  return p
}

export const AREAS: Area[] = [
  {
    slug: 'infectious-disease',
    label: 'Infectious disease and fevers',
    blurb: 'How contagion, fevers and parasites were explained before germs were known.',
    field: 'in medicine',
    plate: plate('helminthology'),
    featured: ['consumption', 'smallpox'],
  },
  {
    slug: 'anatomy',
    label: 'Anatomy and physiology',
    blurb: 'The parts of the body, and what people thought made them work.',
    field: 'in anatomy',
    plate: plate('anatomy'),
    featured: ['blood'],
  },
  {
    slug: 'geology',
    label: 'Geology',
    blurb: 'Rocks, earthquakes and the forces that shape the earth.',
    field: 'in natural history',
    plate: plate('geyser'),
    featured: ['basalt'],
  },
  {
    slug: 'natural-sciences',
    label: 'Natural sciences',
    blurb: 'Electricity, magnetism and the experiments of natural philosophy.',
    field: 'in natural philosophy',
    plate: plate('electricity'),
    featured: ['electricity'],
  },
]

/** The plate behind the landing page before a subject is chosen. */
export const HERO_PLATE = plate('anatomy')

export const areaOf = (slug: AreaSlug | null | undefined) => AREAS.find((a) => a.slug === slug)

/**
 * The field a headword is set in, from the topic it names or starts to name:
 * "Basalt" gives "in natural history". Null when nothing matches yet.
 */
export function fieldFor(value: string, topics: TopicSummary[]): string | null {
  const q = value.trim().toLowerCase()
  if (!q) return null
  const exact = topics.find((t) => t.label.toLowerCase() === q || t.headword.toLowerCase() === q)
  const partial = exact ?? topics.find((t) => t.label.toLowerCase().startsWith(q) || t.headword.toLowerCase().startsWith(q))
  return areaOf(partial?.area)?.field ?? null
}
