// Weather-map style scale: white (dry) → blues → yellow → orange → red (heavy).
// Checked with the dataviz palette validator (--mode dark, surface #1b1b1d): adjacent
// classes pass normal-vision (ΔE >= 16) and colour-blind (ΔE >= 13.7) separation, and
// every colour clears 3:1 contrast on the map. Dry is white filled; no data is a hollow ring.
export interface RainClass {
  label: string
  color: string
  rgb: [number, number, number]
}

const hexToRgb = (hex: string): [number, number, number] => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]

const classes: Array<[string, string]> = [
  ['Dry (0 mm)', '#eef2f6'],
  ['0.1–0.9 mm', '#8ec8f0'],
  ['1–4.9 mm', '#3f97e0'],
  ['5–9.9 mm', '#f6dc4c'],
  ['10–19.9 mm', '#f3922b'],
  ['20 mm or more', '#e3342f'],
]

export const RAIN_CLASSES: RainClass[] = classes.map(([label, color]) => ({ label, color, rgb: hexToRgb(color) }))

export function rainClassIndex(mm: number): number {
  if (mm <= 0) return 0
  if (mm < 1) return 1
  if (mm < 5) return 2
  if (mm < 10) return 3
  if (mm < 20) return 4
  return 5
}

export const rainClass = (mm: number): RainClass => RAIN_CLASSES[rainClassIndex(mm)]
