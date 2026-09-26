import type { Parameter } from '../api'
import { RAIN_CLASSES, rainClass, type RainClass } from './rainScale'
import { SNOW_CLASSES, snowClass } from './snowScale'
import { TEMP_CLASSES, tempClass } from './tempScale'

export interface Scale {
  classes: RainClass[]
  classOf: (value: number) => RainClass
}

const temperature: Scale = { classes: TEMP_CLASSES, classOf: tempClass }

export const SCALES: Record<Parameter, Scale> = {
  precipitation: { classes: RAIN_CLASSES, classOf: rainClass },
  snow_depth: { classes: SNOW_CLASSES, classOf: snowClass },
  temp_mean: temperature,
  temp_min: temperature,
  temp_max: temperature,
}
