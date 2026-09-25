import { computed, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'

export type Source = 'fmi' | 'met'

export interface StationDay {
  id: string
  source: Source
  source_station_id: string
  name: string
  lat: number
  lon: number
  country: string
  region: string | null
  date: string
  precipitation_mm: number | null
  has_data: boolean
}

export interface StationsForDate {
  date: string
  stations: StationDay[]
}

export interface DailyValue {
  date: string
  precipitation_mm: number | null
  has_data: boolean
}

export interface StationHistory {
  station_id: string
  start: string
  end: string
  values: DailyValue[]
}

const API_URL = (import.meta.env.DEV ? '' : import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export class NotFoundError extends Error {}

async function getJson<T>(path: string, params: Record<string, string | undefined> = {}): Promise<T> {
  const query = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => e[1] !== undefined))
  const response = await fetch(`${API_URL}${path}${query.size ? `?${query}` : ''}`)
  if (response.status === 404) throw new NotFoundError(path)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

const retry = (count: number, error: Error) => !(error instanceof NotFoundError) && count < 2

export function useDates() {
  return useQuery({
    queryKey: ['dates'],
    queryFn: () => getJson<{ dates: string[] }>('/api/dates').then((r) => r.dates),
    staleTime: 10 * 60_000,
    retry,
  })
}

/** Stations for a date; `null` asks the API for the latest date with data. */
export function useStations(date: Ref<string | null>) {
  return useQuery({
    queryKey: computed(() => ['stations', date.value ?? 'latest']),
    queryFn: () => getJson<StationsForDate>('/api/stations', { date: date.value ?? undefined }),
    staleTime: 10 * 60_000,
    placeholderData: (previous) => previous,
    retry,
  })
}

export function useStationHistory(stationId: Ref<string | null>, end: Ref<string | null>) {
  return useQuery({
    queryKey: computed(() => ['history', stationId.value, end.value]),
    queryFn: () => getJson<StationHistory>(`/api/stations/${stationId.value}/history`, { end: end.value ?? undefined }),
    enabled: computed(() => stationId.value !== null && end.value !== null),
    staleTime: 10 * 60_000,
    placeholderData: (previous) => previous,
    retry,
  })
}
