<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useStationHistory, type StationDay } from '../api'
import { rainClass } from '../lib/rainScale'
import { formatDate, formatMm, t } from '../strings'
import HistoryChart from './HistoryChart.vue'

const props = defineProps<{ station: StationDay }>()
const emit = defineEmits<{ close: []; pickDate: [date: string] }>()

const history = useStationHistory(
  computed(() => props.station.id),
  toRef(() => props.station.date),
)
const swatch = computed(() =>
  props.station.has_data && props.station.precipitation_mm !== null ? rainClass(props.station.precipitation_mm).color : null,
)
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

    <p class="value">
      <span v-if="swatch" class="swatch" :style="{ background: swatch }" />
      <span v-else class="swatch hollow" />
      {{ station.has_data ? formatMm(station.precipitation_mm) : t.noData }}
    </p>

    <HistoryChart
      v-if="history.data.value"
      :values="history.data.value.values"
      :start="history.data.value.start"
      :end="history.data.value.end"
      :selected-date="station.date"
      @pick="emit('pickDate', $event)"
    />
    <p v-else-if="history.isError.value" class="muted">{{ t.loadError }}</p>
    <p v-else class="muted">{{ t.loading }}</p>

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
.value {
  margin: 0;
  font-size: 32px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
  font-variant-numeric: tabular-nums;
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
.note,
.muted {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
