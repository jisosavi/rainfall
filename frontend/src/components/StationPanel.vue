<script setup lang="ts">
import { computed, toRef } from 'vue'
import {
  TEMPERATURES,
  isTemperature,
  measurementOf,
  useLastData,
  useStationHistory,
  type DailyValue,
  type Measurement,
  type Parameter,
  type StationDay,
  type TemperatureParameter,
} from '../api'
import { SCALES } from '../lib/scales'
import { countryTag } from '../lib/countries'
import { formatCelsius, formatDate, formatValue, suspectLong, t } from '../strings'
import HistoryChart from './HistoryChart.vue'
import SnowChart from './SnowChart.vue'
import TemperatureChart from './TemperatureChart.vue'

// `station` is the station on the shown date for the measurement shown on the map.
const props = defineProps<{ station: StationDay; parameter: Parameter }>()
const emit = defineEmits<{ close: []; pickDate: [date: string] }>()

const stationId = computed(() => props.station.id)
const day = toRef(() => props.station.date)

// The winter containing the shown date runs from 1 October; in spring and summer
// that is the previous October, so the whole last winter is shown.
const seasonStartYear = computed(() => {
  const [y, m] = day.value.split('-').map(Number)
  return m >= 10 ? y : y - 1
})
const seasonStart = computed(() => `${seasonStartYear.value}-10-01`)

const rain = useStationHistory(stationId, day, 'precipitation')
const snow = useStationHistory(stationId, day, 'snow_depth', seasonStart)
const temperature = {
  temp_mean: useStationHistory(stationId, day, 'temp_mean'),
  temp_min: useStationHistory(stationId, day, 'temp_min'),
  temp_max: useStationHistory(stationId, day, 'temp_max'),
}
const temperatureLoaded = computed(() => TEMPERATURES.every((p) => temperature[p].data.value))
const hasTemperature = computed(() => TEMPERATURES.some((p) => temperature[p].data.value?.values.some((v) => v.has_data)))

function valueOn(values: DailyValue[] | undefined, date: string): DailyValue | undefined {
  return values?.find((v) => v.date === date)
}

interface Section {
  measurement: Measurement
  parameter: Parameter // the value shown large (for temperature: the one on the map, else the mean)
  value: number | null
  flag: string | null
}
const historyOf = (p: Parameter) => (p === 'precipitation' ? rain : p === 'snow_depth' ? snow : temperature[p])

const sections = computed<Section[]>(() => {
  const temperatureParameter: TemperatureParameter = isTemperature(props.parameter) ? props.parameter : 'temp_mean'
  const all: Section[] = (['precipitation', 'snow_depth', temperatureParameter] as Parameter[]).map((p) => {
    const v = valueOn(historyOf(p).data.value?.values, day.value)
    return { measurement: measurementOf(p), parameter: p, value: v?.has_data ? v.value : null, flag: v?.flag ?? null }
  })
  // The map's own value is authoritative for the shown measurement.
  const shown = all.find((s) => s.parameter === props.parameter)!
  shown.value = props.station.has_data ? props.station.value : null
  shown.flag = props.station.flag
  // Show other measurements only if the station has values for them in the charts' period
  // (some stations are snow-only, rain-only or temperature-only, and FMI lists missing rows
  // for measurements a station doesn't make).
  const shownMeasurement = measurementOf(props.parameter)
  const reports = (values: DailyValue[] | undefined) => values?.some((v) => v.has_data) ?? false
  const has: Record<Measurement, boolean> = {
    precipitation: reports(rain.data.value?.values) || shownMeasurement === 'precipitation',
    snow_depth: reports(snow.data.value?.values) || shownMeasurement === 'snow_depth',
    temperature: hasTemperature.value || shownMeasurement === 'temperature',
  }
  return all
    .filter((s) => has[s.measurement])
    .sort((a, b) => Number(b.measurement === shownMeasurement) - Number(a.measurement === shownMeasurement))
})

const swatch = (s: Section) => (s.value !== null ? SCALES[s.parameter].classOf(s.value).color : null)

// The day's mean, minimum and maximum, under the large temperature value.
const temperatureRow = computed(() =>
  TEMPERATURES.map((p) => {
    const v = p === props.parameter ? props.station : valueOn(temperature[p].data.value?.values, day.value)
    return { parameter: p, label: t.temperatureShort[p], value: v?.has_data ? (v.value ?? null) : null }
  }),
)

// For a measurement without a value on the shown date: when the station last had one.
const missing = (p: Parameter) => computed(() => sections.value.some((s) => s.parameter === p && s.value === null))
const lastData: Record<Parameter, ReturnType<typeof useLastData>> = {
  precipitation: useLastData(stationId, day, 'precipitation', missing('precipitation')),
  snow_depth: useLastData(stationId, day, 'snow_depth', missing('snow_depth')),
  temp_mean: useLastData(stationId, day, 'temp_mean', missing('temp_mean')),
  temp_min: useLastData(stationId, day, 'temp_min', missing('temp_min')),
  temp_max: useLastData(stationId, day, 'temp_max', missing('temp_max')),
}
const sectionTitle = (s: Section) => (s.measurement === 'temperature' ? t.parameterLabel[s.parameter] : t.measurementLabel[s.measurement])
</script>

<template>
  <aside class="station-panel panel" :aria-label="station.name">
    <header>
      <div>
        <h2>{{ station.name }} <span class="tag">{{ countryTag(station.country) }}</span></h2>
        <p class="date">{{ formatDate(station.date) }}</p>
      </div>
      <button type="button" class="icon" :aria-label="t.close" :title="t.close" @click="emit('close')">×</button>
    </header>

    <section v-for="s in sections" :key="s.measurement" class="measure">
      <h3>{{ sectionTitle(s) }}</h3>
      <p class="value" :class="{ secondary: s.measurement !== measurementOf(parameter) }">
        <span v-if="swatch(s)" class="swatch" :style="{ background: swatch(s)! }" />
        <span v-else class="swatch hollow" />
        {{ formatValue(s.parameter, s.value) }}
      </p>
      <div v-if="s.value === null" class="no-data" role="note">
        <span>{{ t.noDataOnDate }}</span>
        <template v-if="lastData[s.parameter].data.value">
          <template v-if="lastData[s.parameter].data.value!.date">
            <span>
              {{ t.lastData(formatDate(lastData[s.parameter].data.value!.date!), formatValue(s.parameter, lastData[s.parameter].data.value!.value)) }}
            </span>
            <button type="button" class="small" @click="emit('pickDate', lastData[s.parameter].data.value!.date!)">
              {{ t.showThatDay }}
            </button>
          </template>
          <span v-else>{{ t.neverData }}</span>
        </template>
      </div>
      <dl v-if="s.measurement === 'temperature'" class="kinds">
        <div v-for="k in temperatureRow" :key="k.parameter" :class="{ current: k.parameter === s.parameter }">
          <dt>{{ k.label }}</dt>
          <dd>{{ formatCelsius(k.value) }}</dd>
        </div>
      </dl>
      <p v-if="s.flag === 'suspect_spatial'" class="suspect" role="note">⚠ {{ suspectLong(s.parameter) }}</p>
      <p v-else-if="s.flag === 'confirmed_hourly'" class="confirmed" role="note">✓ {{ t.confirmedLong }}</p>

      <template v-if="s.parameter === 'precipitation'">
        <HistoryChart
          v-if="rain.data.value"
          :values="rain.data.value.values"
          :start="rain.data.value.start"
          :end="rain.data.value.end"
          :selected-date="station.date"
          @pick="emit('pickDate', $event)"
        />
        <p v-else-if="rain.isError.value" class="muted">{{ t.loadError }}</p>
        <p v-else class="muted">{{ t.loading }}</p>
      </template>

      <template v-else-if="s.measurement === 'temperature'">
        <TemperatureChart
          v-if="temperatureLoaded && hasTemperature"
          :mean="temperature.temp_mean.data.value!.values"
          :min="temperature.temp_min.data.value!.values"
          :max="temperature.temp_max.data.value!.values"
          :start="temperature.temp_mean.data.value!.start"
          :end="temperature.temp_mean.data.value!.end"
          :selected-date="station.date"
          @pick="emit('pickDate', $event)"
        />
        <p v-else-if="temperatureLoaded" class="muted">{{ t.noTemperatureData }}</p>
        <p v-else-if="TEMPERATURES.some((p) => temperature[p].isError.value)" class="muted">{{ t.loadError }}</p>
        <p v-else class="muted">{{ t.loading }}</p>
      </template>

      <template v-else>
        <SnowChart
          v-if="snow.data.value && snow.data.value.values.length"
          :values="snow.data.value.values"
          :start="snow.data.value.start"
          :end="snow.data.value.end"
          :selected-date="station.date"
          :title="t.winterSeason(seasonStartYear)"
          @pick="emit('pickDate', $event)"
        />
        <p v-else-if="snow.data.value" class="muted">{{ t.noSnowData }}</p>
        <p v-else-if="snow.isError.value" class="muted">{{ t.loadError }}</p>
        <p v-else class="muted">{{ t.loading }}</p>
      </template>
    </section>

    <dl class="meta">
      <div v-if="station.region"><dt>{{ t.region }}</dt><dd>{{ station.region }}</dd></div>
      <div v-if="station.owner"><dt>{{ t.owner }}</dt><dd>{{ station.owner }}</dd></div>
      <div><dt>{{ t.stationId }}</dt><dd>{{ station.source_station_id }} · {{ t.sourceName[station.source] }}</dd></div>
      <div><dt>{{ t.coordinates }}</dt><dd>{{ station.lat.toFixed(3) }}° N, {{ station.lon.toFixed(3) }}° E</dd></div>
    </dl>
    <p class="note">{{ t.measurementNote }}</p>
  </aside>
</template>

<style scoped>
.station-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
h2 {
  margin: 0;
  font-size: 18px;
  line-height: 1.25;
}
.tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 4px;
  vertical-align: 2px;
}
.date {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.icon {
  width: 32px;
  font-size: 20px;
  line-height: 1;
  flex: none;
}
.measure {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
}
h3 {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
}
.value {
  margin: 0;
  font-size: 30px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  font-variant-numeric: tabular-nums;
}
.value.secondary {
  font-size: 22px;
}
.swatch {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex: none;
}
.swatch.hollow {
  border: 2px solid #fff;
}
.kinds {
  margin: -4px 0 0;
  display: flex;
  gap: 18px;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.kinds dt {
  font-size: 11px;
  color: var(--text-muted);
}
.kinds dd {
  margin: 1px 0 0;
  color: var(--text-secondary);
}
.kinds .current dt,
.kinds .current dd {
  color: var(--text-primary);
}
.meta {
  margin: 0;
  display: grid;
  gap: 6px;
  font-size: 13px;
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
}
.meta div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.meta dt {
  color: var(--text-secondary);
}
.meta dd {
  margin: 0;
  text-align: right;
}
.suspect {
  margin: -4px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: #fab219;
}
.no-data {
  margin: -4px 0 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-secondary);
}
.no-data span:first-child {
  flex-basis: 100%;
}
.confirmed {
  margin: -4px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-secondary);
}
.note,
.muted {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
