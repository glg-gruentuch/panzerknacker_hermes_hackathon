import type { AreaSlug } from '../api/types'
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
  plate: Plate
  /** Topic slugs to show first, with today's title and a Compare link. The rest follow in index order. */
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
    plate: plate('helminthology'),
    featured: ['consumption', 'smallpox'],
  },
  {
    slug: 'anatomy',
    label: 'Anatomy and physiology',
    blurb: 'The parts of the body, and what people thought made them work.',
    plate: plate('anatomy'),
    featured: ['blood'],
  },
  {
    slug: 'geology',
    label: 'Geology',
    blurb: 'Rocks, earthquakes and the forces that shape the earth.',
    plate: plate('geyser'),
    featured: ['basalt'],
  },
  {
    slug: 'natural-sciences',
    label: 'Natural sciences',
    blurb: 'Electricity, magnetism and the experiments of natural philosophy.',
    plate: plate('electricity'),
    featured: ['electricity'],
  },
  {
    slug: 'astronomy',
    label: 'Astronomy',
    blurb: 'The sun, the moon and the planets, and how people explained what they saw in the sky.',
    plate: plate('astronomy'),
    featured: ['sun'],
  },
]

/** The plate behind the landing page before a subject is chosen. */
export const HERO_PLATE = plate('anatomy')

export const areaOf = (slug: AreaSlug | null | undefined) => AREAS.find((a) => a.slug === slug)

