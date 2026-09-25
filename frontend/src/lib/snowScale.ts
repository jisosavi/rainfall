// Snow depth scale for the dark map: muted grey-brown for bare ground (real data, recessive),
// then icy white → cyan → blue → indigo → lilac. Checked with the dataviz palette validator
// (--mode dark, surface #1b1b1d): adjacent classes pass normal-vision (ΔE >= 15.4) and
// colour-blind (ΔE >= 11.5) separation. Indigo is 2.98:1 against the map, just under 3:1,
// so exact values are always available as text (tooltip, list, panel).
import type { RainClass } from './rainScale'

const hexToRgb = (hex: string): [number, number, number] => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]

const classes: Array<[string, string]> = [
  ['No snow', '#7a7064'],
  ['1–9 cm', '#e3f4ff'],
  ['10–29 cm', '#7fd3e0'],
  ['30–59 cm', '#3f8fe4'],
  ['60–99 cm', '#6a4fd0'],
  ['100 cm or more', '#e39be9'],
]

export const SNOW_CLASSES: RainClass[] = classes.map(([label, color]) => ({ label, color, rgb: hexToRgb(color) }))

export function snowClassIndex(cm: number): number {
  if (cm < 1) return 0
  if (cm < 10) return 1
  if (cm < 30) return 2
  if (cm < 60) return 3
  if (cm < 100) return 4
  return 5
}

export const snowClass = (cm: number): RainClass => SNOW_CLASSES[snowClassIndex(cm)]
