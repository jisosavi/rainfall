import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

/** Selected date and station, mirrored to the URL (?date=…&station=…) so views can be shared. */
export const useSelectionStore = defineStore('selection', () => {
  const params = new URLSearchParams(window.location.search)
  const initialDate = params.get('date')

  // null = follow the latest date with data.
  const date = ref<string | null>(initialDate && ISO_DATE.test(initialDate) ? initialDate : null)
  const stationId = ref<string | null>(params.get('station'))

  watch([date, stationId], ([d, s]) => {
    const url = new URL(window.location.href)
    d ? url.searchParams.set('date', d) : url.searchParams.delete('date')
    s ? url.searchParams.set('station', s) : url.searchParams.delete('station')
    window.history.replaceState(null, '', url)
  })

  return { date, stationId }
})
