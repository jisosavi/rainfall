import { onScopeDispose, ref } from 'vue'

// The phone layout (same breakpoint as the CSS media queries): shorter labels, bottom sheets.
export const MOBILE_QUERY = '(max-width: 760px)'

export function useMobile() {
  const query = window.matchMedia(MOBILE_QUERY)
  const mobile = ref(query.matches)
  const update = (e: MediaQueryListEvent) => (mobile.value = e.matches)
  query.addEventListener('change', update)
  onScopeDispose(() => query.removeEventListener('change', update))
  return mobile
}

/** A per-device preference in localStorage; storage can be unavailable, so never throw. */
export function stored(key: string, fallback: boolean): boolean {
  try {
    const value = localStorage.getItem(key)
    return value === null ? fallback : value === '1'
  } catch {
    return fallback
  }
}

export function store(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // Private mode or blocked storage: the choice just isn't remembered.
  }
}
