import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

import type { Parameter } from '../api'
import { COUNTRY_KEYS, type CountryFilter } from '../lib/countries'

export type { CountryFilter }

// Snow depth is the default view from November to February, rainfall otherwise.
const seasonalDefault = (): Parameter => ([10, 11, 0, 1].includes(new Date().getMonth()) ? 'snow_depth' : 'precipitation')
const SHOW: Record<string, Parameter> = {
  rain: 'precipitation',
  snow: 'snow_depth',
  tmean: 'temp_mean',
  tmin: 'temp_min',
  tmax: 'temp_max',
}
const SHOW_KEY = Object.fromEntries(Object.entries(SHOW).map(([key, p]) => [p, key])) as Record<Parameter, string>

/** Selected date, station, country and measurement, mirrored to the URL
 * (?date=…&station=…&country=…&show=rain|snow|tmean|tmin|tmax) so views can be shared. */
export const useSelectionStore = defineStore('selection', () => {
  const params = new URLSearchParams(window.location.search)
  const initialDate = params.get('date')

  // null = follow the latest date with data.
  const date = ref<string | null>(initialDate && ISO_DATE.test(initialDate) ? initialDate : null)
  const stationId = ref<string | null>(params.get('station'))
  const initialCountry = params.get('country') as CountryFilter | null
  const country = ref<CountryFilter>(initialCountry && COUNTRY_KEYS.includes(initialCountry) ? initialCountry : 'all')
  const parameter = ref<Parameter>(SHOW[params.get('show') ?? ''] ?? seasonalDefault())

  watch([date, stationId, country, parameter], ([d, s, c, p]) => {
    const url = new URL(window.location.href)
    d ? url.searchParams.set('date', d) : url.searchParams.delete('date')
    s ? url.searchParams.set('station', s) : url.searchParams.delete('station')
    c !== 'all' ? url.searchParams.set('country', c) : url.searchParams.delete('country')
    p !== seasonalDefault() ? url.searchParams.set('show', SHOW_KEY[p]) : url.searchParams.delete('show')
    window.history.replaceState(null, '', url)
  })

  return { date, stationId, country, parameter }
})
