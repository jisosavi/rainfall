<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { NotFoundError, useDates, useRankings, useStations, useStatus, type Parameter, type Period, type Source } from './api'
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

const parameterOptions: Array<{ value: Parameter; label: string }> = [
  { value: 'precipitation', label: t.parameterLabel.precipitation },
  { value: 'snow_depth', label: t.parameterLabel.snow_depth },
]

const about = ref<InstanceType<typeof AboutDialog>>()
// Left column: map only, the station list, or the Top 15 rankings.
type View = 'map' | 'list' | 'top'
const view = ref<View>('map')
const viewOptions: Array<{ value: View; label: string }> = [
  { value: 'map', label: t.viewMap },
  { value: 'list', label: t.viewList },
  { value: 'top', label: t.viewTop },
]
const DEFAULT_PERIOD: Record<Parameter, Period> = { precipitation: 'month', snow_depth: 'now' }
const period = ref<Period>(DEFAULT_PERIOD[parameter.value])
watch(parameter, (p) => (period.value = DEFAULT_PERIOD[p]))
const allStations = ref(false)

const shownDate = computed(() => stations.data.value?.date ?? date.value)
const rankings = useRankings(parameter, period, shownDate, country, allStations, computed(() => view.value === 'top'))
const stationRows = computed(() => {
  const all = stations.data.value?.stations ?? []
  return all.filter((s) => inCountry(country.value, s.country))
})
const selectedStation = computed(() => stationRows.value.find((s) => s.id === stationId.value) ?? null)
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

        <SegmentedControl v-model="parameter" :options="parameterOptions" :label="t.measurement" class="parameter-switch" />

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

      <StationList v-if="view === 'list'" :stations="stationRows" :selected-id="stationId" :parameter="parameter" @select="selectStation" />
      <RankingsPanel
        v-else-if="view === 'top'"
        v-model:period="period"
        v-model:all-stations="allStations"
        :parameter="parameter"
        :rankings="rankings.data.value"
        :loading="rankings.isFetching.value"
        :selected-id="stationId"
        @select="selectStation"
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
.parameter-switch {
  align-self: flex-start;
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
