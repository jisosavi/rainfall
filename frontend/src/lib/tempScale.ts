// Diverging temperature scale for the dark map, split at 0 °C: blues below freezing, a
// near-white class for 0–4.9 °C, then yellow → orange → red, with lilac and pink for the
// extremes (below −20 °C, 25 °C or above). Checked with the dataviz palette validator
// (--mode dark, surface #1b1b1d): adjacent classes pass normal-vision (ΔE >= 15.1) and
// colour-blind (ΔE >= 9.5) separation, and every colour clears 3:1 contrast on the map.
import type { RainClass } from './rainScale'

const hexToRgb = (hex: string): [number, number, number] => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]

const classes: Array<[string, string]> = [
  ['Below −20 °C', '#d38cf0'],
  ['−20 to −10.1 °C', '#5d68ec'],
  ['−10 to −5.1 °C', '#1aa9e8'],
  ['−5 to −0.1 °C', '#84d6f5'],
  ['0 to 4.9 °C', '#f2f1ec'],
  ['5 to 9.9 °C', '#f7da38'],
  ['10 to 14.9 °C', '#fc9e47'],
  ['15 to 19.9 °C', '#cd6b17'],
  ['20 to 24.9 °C', '#cf1748'],
  ['25 °C or above', '#ff9ad8'],
]

export const TEMP_CLASSES: RainClass[] = classes.map(([label, color]) => ({ label, color, rgb: hexToRgb(color) }))

const UPPER_BOUNDS = [-20, -10, -5, 0, 5, 10, 15, 20, 25]

export function tempClassIndex(celsius: number): number {
  const i = UPPER_BOUNDS.findIndex((bound) => celsius < bound)
  return i === -1 ? UPPER_BOUNDS.length : i
}

export const tempClass = (celsius: number): RainClass => TEMP_CLASSES[tempClassIndex(celsius)]
