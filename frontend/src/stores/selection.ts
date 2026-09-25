import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export type CountryFilter = 'all' | 'fi' | 'no'
const COUNTRIES: CountryFilter[] = ['all', 'fi', 'no']

/** Selected date, station and country, mirrored to the URL (?date=…&station=…&country=…). */
export const useSelectionStore = defineStore('selection', () => {
  const params = new URLSearchParams(window.location.search)
  const initialDate = params.get('date')

  // null = follow the latest date with data.
  const date = ref<string | null>(initialDate && ISO_DATE.test(initialDate) ? initialDate : null)
  const stationId = ref<string | null>(params.get('station'))
  const initialCountry = params.get('country') as CountryFilter | null
  const country = ref<CountryFilter>(initialCountry && COUNTRIES.includes(initialCountry) ? initialCountry : 'all')

  watch([date, stationId, country], ([d, s, c]) => {
    const url = new URL(window.location.href)
    d ? url.searchParams.set('date', d) : url.searchParams.delete('date')
    s ? url.searchParams.set('station', s) : url.searchParams.delete('station')
    c !== 'all' ? url.searchParams.set('country', c) : url.searchParams.delete('country')
    window.history.replaceState(null, '', url)
  })

  return { date, stationId, country }
})
