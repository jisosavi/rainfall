<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useStationHistory, type DailyValue, type Parameter, type StationDay } from '../api'
import { SCALES } from '../lib/scales'
import { formatDate, formatValue, t } from '../strings'
import HistoryChart from './HistoryChart.vue'
import SnowChart from './SnowChart.vue'

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

function valueOn(values: DailyValue[] | undefined, date: string): DailyValue | undefined {
  return values?.find((v) => v.date === date)
}

interface Section {
  parameter: Parameter
  value: number | null
  flag: string | null
}
const sections = computed<Section[]>(() => {
  const rainValue = valueOn(rain.data.value?.values, day.value)
  const snowValue = valueOn(snow.data.value?.values, day.value)
  const all: Section[] = [
    { parameter: 'precipitation', value: rainValue?.has_data ? rainValue.value : null, flag: rainValue?.flag ?? null },
    { parameter: 'snow_depth', value: snowValue?.has_data ? snowValue.value : null, flag: snowValue?.flag ?? null },
  ]
  // The map's own value is authoritative for the shown measurement.
  const shown = all.find((s) => s.parameter === props.parameter)!
  shown.value = props.station.has_data ? props.station.value : null
  shown.flag = props.station.flag
  // Show a measurement only if the station reports it (some are snow-only or rain-only).
  const has: Record<Parameter, boolean> = {
    precipitation: (rain.data.value?.values.length ?? 0) > 0 || props.parameter === 'precipitation',
    snow_depth: (snow.data.value?.values.length ?? 0) > 0 || props.parameter === 'snow_depth',
  }
  return all
    .filter((s) => has[s.parameter])
    .sort((a, b) => Number(b.parameter === props.parameter) - Number(a.parameter === props.parameter))
})

const swatch = (s: Section) => (s.value !== null ? SCALES[s.parameter].classOf(s.value).color : null)
</script>

<template>
  <aside class="station-panel panel" :aria-label="station.name">
    <header>
      <div>
        <h2>{{ station.name }} <span class="tag">{{ t.countryTag[station.source] }}</span></h2>
        <p class="date">{{ formatDate(station.date) }}</p>
      </div>
      <button type="button" class="icon" :aria-label="t.close" :title="t.close" @click="emit('close')">×</button>
    </header>

    <section v-for="s in sections" :key="s.parameter" class="measure">
      <h3>{{ t.parameterLabel[s.parameter] }}</h3>
      <p class="value" :class="{ secondary: s.parameter !== parameter }">
        <span v-if="swatch(s)" class="swatch" :style="{ background: swatch(s)! }" />
        <span v-else class="swatch hollow" />
        {{ formatValue(s.parameter, s.value) }}
      </p>
      <p v-if="s.flag" class="suspect" role="note">⚠ {{ t.suspectLong }}</p>

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
.note,
.muted {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
