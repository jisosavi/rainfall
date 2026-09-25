import type { Parameter } from '../api'
import { RAIN_CLASSES, rainClass, type RainClass } from './rainScale'
import { SNOW_CLASSES, snowClass } from './snowScale'

export interface Scale {
  classes: RainClass[]
  classOf: (value: number) => RainClass
}

export const SCALES: Record<Parameter, Scale> = {
  precipitation: { classes: RAIN_CLASSES, classOf: rainClass },
  snow_depth: { classes: SNOW_CLASSES, classOf: snowClass },
}
