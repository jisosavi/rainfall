<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  NotFoundError,
  isTemperature,
  measurementOf,
  useDates,
  useRankings,
  useStations,
  useStatus,
  type Measurement,
  type Order,
  type Parameter,
  type Period,
  type Source,
  type StationDay,
  type TemperatureParameter,
} from './api'
import { useSelectionStore } from './stores/selection'
import { inCountry } from './lib/countries'
import { formatDate, formatTimestamp, t } from './strings'
import AboutDialog from './components/AboutDialog.vue'
import CountryFilter from './components/CountryFilter.vue'
import DateControl from './components/DateControl.vue'
import MapLegend from './components/MapLegend.vue'
import RainMap from './components/RainMap.vue'
import SegmentedControl from './components/SegmentedControl.vue'
import RankingsPanel from './components/RankingsPanel.vue'
import StationList from './components/StationList.vue'
import StationPanel from './components/StationPanel.vue'

const { date, stationId, country, parameter } = storeToRefs(useSelectionStore())
const stations = useStations(date, parameter)
const dates = useDates(parameter)
const status = useStatus()

const measurementOptions: Array<{ value: Measurement; label: string }> = [
  { value: 'precipitation', label: t.measurementLabel.precipitation },
  { value: 'snow_depth', label: t.measurementLabel.snow_depth },
  { value: 'temperature', label: t.measurementLabel.temperature },
]
const temperatureOptions: Array<{ value: TemperatureParameter; label: string }> = [
  { value: 'temp_mean', label: t.temperatureShort.temp_mean },
  { value: 'temp_min', label: t.temperatureShort.temp_min },
  { value: 'temp_max', label: t.temperatureShort.temp_max },
]
// Switching back to Temperature returns to the last chosen of mean, min and max.
const lastTemperature = ref<TemperatureParameter>(isTemperature(parameter.value) ? parameter.value : 'temp_mean')
const measurement = computed<Measurement>({
  get: () => measurementOf(parameter.value),
  set: (m) => (parameter.value = m === 'temperature' ? lastTemperature.value : m),
})
const temperatureKind = computed<TemperatureParameter>({
  get: () => (isTemperature(parameter.value) ? parameter.value : lastTemperature.value),
  set: (p) => {
    lastTemperature.value = p
    parameter.value = p
  },
})

const about = ref<InstanceType<typeof AboutDialog>>()
// Left column: map only, the station list, or the Top 15 rankings.
type View = 'map' | 'list' | 'top'
const view = ref<View>('map')
// For temperature the rankings button names the shown kind ("Top mean"), not "Top 15".
const viewOptions = computed<Array<{ value: View; label: string }>>(() => [
  { value: 'map', label: t.viewMap },
  { value: 'list', label: t.viewList },
  { value: 'top', label: isTemperature(parameter.value) ? t.viewTopTemperature[parameter.value] : t.viewTop },
])
// Rainfall: this month's totals. Snow depth and temperature: the shown day.
const defaultPeriod = (p: Parameter): Period => (p === 'precipitation' ? 'month' : 'now')
const period = ref<Period>(defaultPeriod(parameter.value))
// Warmest first in summer (April–September), coldest first in winter.
const order = ref<Order>([3, 4, 5, 6, 7, 8].includes(new Date().getMonth()) ? 'warmest' : 'coldest')
watch(
  () => measurementOf(parameter.value),
  () => (period.value = defaultPeriod(parameter.value)),
)
const allStations = ref(false)

const shownDate = computed(() => stations.data.value?.date ?? date.value)
const rankings = useRankings(
  parameter,
  period,
  shownDate,
  country,
  allStations,
  order,
  computed(() => view.value === 'top'),
)
const stationRows = computed(() => {
  const all = stations.data.value?.stations ?? []
  return all.filter((s) => inCountry(country.value, s.country))
})
// A ranked station without a value on the shown date isn't in stationRows; build its panel
// entry from the ranking so it still opens (showing "No data on this date · Last data").
const selectedStation = computed<StationDay | null>(() => {
  const onMap = stationRows.value.find((s) => s.id === stationId.value)
  if (onMap) return onMap
  const ranked = view.value === 'top' ? rankings.data.value?.stations.find((s) => s.id === stationId.value) : undefined
  if (!ranked || !shownDate.value) return null
  return {
    id: ranked.id,
    source: ranked.source,
    source_station_id: ranked.source_station_id,
    name: ranked.name,
    lat: ranked.lat,
    lon: ranked.lon,
    country: ranked.country,
    region: ranked.region,
    owner: ranked.owner,
    elevation_m: null,
    date: shownDate.value,
    parameter: parameter.value,
    value: null,
    unit: '',
    has_data: false,
    flag: null,
  }
})

// Choosing a station in the list or the Top 15 flies the map to it (map clicks don't move it).
const flyTarget = ref<{ lon: number; lat: number; seq: number } | null>(null)
function selectFromList(id: string) {
  stationId.value = id
  const s = stationRows.value.find((x) => x.id === id) ?? rankings.data.value?.stations.find((x) => x.id === id)
  if (s) flyTarget.value = { lon: s.lon, lat: s.lat, seq: (flyTarget.value?.seq ?? 0) + 1 }
}
const reporting = computed(() => stationRows.value.filter((s) => s.has_data).length)
// Per source, on the shown date and ignoring the country filter (for the About dialog).
const stationCounts = computed(() => {
  const counts: Partial<Record<Source, number>> = {}
  for (const s of stations.data.value?.stations ?? []) counts[s.source] = (counts[s.source] ?? 0) + 1
  return counts
})

const errorMessage = computed(() => {
  const error = stations.error.value
  if (!error) return null
  return error instanceof NotFoundError ? t.noDataYet : t.loadError
})

function selectStation(id: string | null) {
  stationId.value = id
}
</script>

<template>
  <main class="app" :class="{ 'has-panel': selectedStation }">
    <RainMap
      :stations="stationRows"
      :selected-id="stationId"
      :parameter="parameter"
      :focus="country"
      :ranks="view === 'top' ? (rankings.data.value?.stations ?? []) : []"
      :fly-to="flyTarget"
      @select="selectStation"
    />

    <div class="left-column">
      <header class="top panel">
        <div class="title-row">
          <div>
            <h1>{{ t.title }}</h1>
            <p class="subtitle">{{ t.subtitle }}</p>
          </div>
          <button type="button" @click="about?.open()">{{ t.aboutButton }}</button>
        </div>

        <div class="switches">
          <SegmentedControl v-model="measurement" :options="measurementOptions" :label="t.measurement" class="parameter-switch" />
          <SegmentedControl
            v-if="measurement === 'temperature'"
            v-model="temperatureKind"
            :options="temperatureOptions"
            :label="t.temperatureKind"
            class="kind-switch"
          />
        </div>

        <DateControl :dates="dates.data.value ?? []" :current="shownDate" @change="date = $event" />

        <div class="status-row">
          <p v-if="errorMessage" class="status error" role="status">{{ errorMessage }}</p>
          <p v-else-if="stations.isPending.value" class="status">{{ t.loading }}</p>
          <p v-else-if="shownDate" class="status">
            {{ formatDate(shownDate) }} ·
            {{ stationRows.length ? t.stationsWithData(reporting, stationRows.length) : t.noStationsForDate }}
          </p>
        </div>
        <button
          v-if="status.data.value?.updated_at"
          type="button"
          class="updated link"
          :title="t.dataUpdatedHint"
          @click="about?.open()"
        >
          {{ t.dataUpdated(formatTimestamp(status.data.value.updated_at)) }}
        </button>
        <div class="controls-row">
          <CountryFilter v-model="country" />
          <SegmentedControl v-model="view" :options="viewOptions" :label="t.viewLabel" class="view-switch" />
        </div>
      </header>

      <StationList v-if="view === 'list'" :stations="stationRows" :selected-id="stationId" :parameter="parameter" @select="selectFromList" />
      <RankingsPanel
        v-else-if="view === 'top'"
        v-model:period="period"
        v-model:all-stations="allStations"
        v-model:order="order"
        :parameter="parameter"
        :rankings="rankings.data.value"
        :loading="rankings.isFetching.value"
        :selected-id="stationId"
        @select="selectFromList"
      />
      <MapLegend class="legend-position" :parameter="parameter" />
    </div>

    <StationPanel
      v-if="selectedStation"
      :key="selectedStation.id"
      :station="selectedStation"
      :parameter="parameter"
      @close="selectStation(null)"
      @pick-date="date = $event"
    />

    <AboutDialog ref="about" :station-counts="stationCounts" :last-fetched="status.data.value?.sources ?? {}" />
  </main>
</template>

<style scoped>
.app {
  position: fixed;
  inset: 0;
  overflow: hidden;
}
.left-column {
  position: absolute;
  z-index: 2;
  top: 16px;
  left: 16px;
  bottom: 16px;
  width: 360px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}
.left-column > * {
  pointer-events: auto;
}
.top {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
h1 {
  margin: 0;
  font-size: 18px;
}
.subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}
.switches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.kind-switch :deep(button) {
  font-size: 12px;
}
.parameter-switch :deep(button) {
  font-size: 13px;
  padding: 5px 14px;
}
.updated {
  align-self: flex-start;
  margin-top: -6px;
  font-size: 11px;
}
.view-switch :deep(button) {
  font-size: 12px;
}
.left-column :deep(.rankings) {
  flex: 1 1 auto;
  max-height: 100%;
}
.controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.status {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}
.status.error {
  color: var(--text-primary);
}
.left-column :deep(.station-list) {
  flex: 1 1 auto;
  max-height: 100%;
}
.legend-position {
  margin-top: auto;
  align-self: flex-start;
}
/* Keep the zoom buttons clear of the station panel. */
.has-panel :deep(.maplibregl-ctrl-bottom-right) {
  right: 356px;
}
.station-panel {
  position: absolute;
  z-index: 2;
  top: 16px;
  right: 16px;
  bottom: 16px;
  width: 340px;
}

@media (max-width: 760px) {
  .left-column {
    top: 8px;
    left: 8px;
    right: 8px;
    bottom: auto;
    width: auto;
    max-height: 55vh;
  }
  .legend-position {
    position: fixed;
    left: 8px;
    bottom: 44px;
  }
  .has-panel .legend-position {
    display: none;
  }
  /* The panel covers the bottom of the screen; pinch-zoom replaces the buttons. */
  .has-panel :deep(.maplibregl-ctrl-bottom-right) {
    display: none;
  }
  .station-panel {
    top: auto;
    left: 8px;
    right: 8px;
    bottom: 8px;
    width: auto;
    max-height: 60vh;
  }
}
</style>
