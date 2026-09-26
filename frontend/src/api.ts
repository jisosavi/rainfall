import { computed, ref, type Ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'

export type Source = 'fmi' | 'met' | 'smhi' | 'dmi'
export type Parameter = 'precipitation' | 'snow_depth'

export interface StationDay {
  id: string
  source: Source
  source_station_id: string
  name: string
  lat: number
  lon: number
  country: string
  region: string | null
  owner: string | null
  date: string
  parameter: Parameter
  value: number | null
  unit: string
  has_data: boolean
  flag: string | null
}

export interface StationsForDate {
  date: string
  parameter: Parameter
  stations: StationDay[]
}

export interface DailyValue {
  date: string
  value: number | null
  has_data: boolean
  flag: string | null
}

export interface StationHistory {
  station_id: string
  parameter: Parameter
  unit: string
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

export interface Status {
  updated_at: string | null
  sources: Partial<Record<Source, string>>
}

/** When the data was last fetched from the sources (refreshed every few minutes). */
export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: () => getJson<Status>('/api/status'),
    staleTime: 5 * 60_000,
    refetchInterval: 15 * 60_000,
    retry,
  })
}

export function useDates(parameter: Ref<Parameter>) {
  return useQuery({
    queryKey: computed(() => ['dates', parameter.value]),
    queryFn: () => getJson<{ dates: string[] }>('/api/dates', { parameter: parameter.value }).then((r) => r.dates),
    staleTime: 10 * 60_000,
    retry,
  })
}

/** Stations for a date; `null` asks the API for the latest date with data. */
export function useStations(date: Ref<string | null>, parameter: Ref<Parameter>) {
  return useQuery({
    queryKey: computed(() => ['stations', parameter.value, date.value ?? 'latest']),
    queryFn: () =>
      getJson<StationsForDate>('/api/stations', { date: date.value ?? undefined, parameter: parameter.value }),
    staleTime: 10 * 60_000,
    placeholderData: (previous) => previous,
    retry,
  })
}

export function useStationHistory(
  stationId: Ref<string | null>,
  end: Ref<string | null>,
  parameter: Parameter,
  start: Ref<string | null> = ref(null),
) {
  return useQuery({
    queryKey: computed(() => ['history', parameter, stationId.value, start.value, end.value]),
    queryFn: () =>
      getJson<StationHistory>(`/api/stations/${stationId.value}/history`, {
        end: end.value ?? undefined,
        start: start.value ?? undefined,
        parameter,
      }),
    enabled: computed(() => stationId.value !== null && end.value !== null),
    staleTime: 10 * 60_000,
    placeholderData: (previous) => previous,
    retry,
  })
}
