// Ordinal blue ramp, pale (dry) → deep (heavy): more rain, deeper colour. Validated with
// the dataviz palette validator (--ordinal --mode dark, surface #1b1b1d): all checks pass.
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
  ['Dry (0 mm)', '#cde2fb'],
  ['0.1–0.9 mm', '#9ec5f4'],
  ['1–4.9 mm', '#6da7ec'],
  ['5–9.9 mm', '#3987e5'],
  ['10–19.9 mm', '#256abf'],
  ['20 mm or more', '#184f95'],
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
