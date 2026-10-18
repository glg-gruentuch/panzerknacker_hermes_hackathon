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
  plate: Plate
  /** Topic slugs to show first. The rest follow in index order. */
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
    plate: plate('helminthology'),
    featured: ['consumption', 'smallpox'],
  },
  {
    slug: 'anatomy',
    label: 'Anatomy and physiology',
    plate: plate('anatomy'),
    featured: ['blood'],
  },
  {
    slug: 'geology',
    label: 'Geology',
    plate: plate('geyser'),
    featured: ['basalt'],
  },
  {
    slug: 'natural-sciences',
    label: 'Natural sciences',
    plate: plate('electricity'),
    featured: ['electricity'],
  },
  {
    slug: 'astronomy',
    label: 'Astronomy',
    plate: plate('astronomy'),
    featured: ['sun'],
  },
]

/** The plate behind the landing page before a subject is chosen. */
export const HERO_PLATE = plate('anatomy')

export const areaOf = (slug: AreaSlug | null | undefined) => AREAS.find((a) => a.slug === slug)

