import { useSyncExternalStore } from 'react'

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia(query)
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}

/** Layout breakpoints. Keep in step with the media queries in the CSS modules. */
export const WIDE = '(min-width: 1200px)'
export const NARROW = '(max-width: 759px)'
