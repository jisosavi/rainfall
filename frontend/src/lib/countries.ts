// Countries in the filter: the station country codes each covers, a short tag, and the map
// view to zoom to when it's chosen. Svalbard and Jan Mayen (SJ) count as Norway.
export type CountryFilter = 'all' | 'fi' | 'no' | 'se' | 'dk' | 'gl' | 'fo' | 'is' | 'ee'

type Bounds = [[number, number], [number, number]]

export interface Country {
  key: Exclude<CountryFilter, 'all'>
  label: string
  codes: string[]
  bounds: Bounds
}

// Finland, Sweden, mainland Norway and Denmark; Svalbard, Greenland, Iceland etc. are one zoom-out away.
export const START_BOUNDS: Bounds = [
  [4.5, 54.4],
  [31.6, 71.3],
]

export const COUNTRIES: Country[] = [
  { key: 'fi', label: 'Finland', codes: ['FI'], bounds: [[19.0, 59.6], [31.6, 70.1]] },
  { key: 'no', label: 'Norway', codes: ['NO', 'SJ'], bounds: [[4.5, 57.9], [31.2, 71.3]] },
  { key: 'se', label: 'Sweden', codes: ['SE'], bounds: [[10.9, 55.2], [24.2, 69.1]] },
  { key: 'dk', label: 'Denmark', codes: ['DK'], bounds: [[7.9, 54.5], [15.3, 57.8]] },
  { key: 'gl', label: 'Greenland', codes: ['GL'], bounds: [[-72.0, 59.5], [-17.0, 78.0]] }, // where its stations are
  { key: 'fo', label: 'Faroe Islands', codes: ['FO'], bounds: [[-7.8, 61.3], [-6.2, 62.45]] },
  { key: 'is', label: 'Iceland', codes: ['IS'], bounds: [[-24.6, 63.2], [-13.4, 66.6]] },
  { key: 'ee', label: 'Estonia', codes: ['EE'], bounds: [[21.6, 57.5], [28.3, 59.8]] },
]

export const COUNTRY_KEYS: CountryFilter[] = ['all', ...COUNTRIES.map((c) => c.key)]

const byCode = new Map(COUNTRIES.flatMap((c) => c.codes.map((code) => [code, c] as const)))

/** Tag shown next to a station name, e.g. "DK"; Svalbard stations show "NO". */
export const countryTag = (code: string): string => (byCode.get(code)?.codes[0] ?? code)

export const boundsFor = (filter: CountryFilter): Bounds =>
  COUNTRIES.find((c) => c.key === filter)?.bounds ?? START_BOUNDS

export const inCountry = (filter: CountryFilter, code: string): boolean =>
  filter === 'all' || (COUNTRIES.find((c) => c.key === filter)?.codes.includes(code) ?? false)
