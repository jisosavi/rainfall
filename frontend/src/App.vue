<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NotFoundError, useDates, useStations } from './api'
import { useSelectionStore } from './stores/selection'
import { formatDate, t } from './strings'
import AboutDialog from './components/AboutDialog.vue'
import CountryFilter from './components/CountryFilter.vue'
import DateControl from './components/DateControl.vue'
import MapLegend from './components/MapLegend.vue'
import RainMap from './components/RainMap.vue'
import StationList from './components/StationList.vue'
import StationPanel from './components/StationPanel.vue'

const { date, stationId, country } = storeToRefs(useSelectionStore())
const stations = useStations(date)
const dates = useDates()

const about = ref<InstanceType<typeof AboutDialog>>()
const showList = ref(false)

const shownDate = computed(() => stations.data.value?.date ?? date.value)
const COUNTRY_SOURCE = { fi: 'fmi', no: 'met', se: 'smhi' } as const
const stationRows = computed(() => {
  const all = stations.data.value?.stations ?? []
  const selected = country.value
  if (selected === 'all') return all
  return all.filter((s) => s.source === COUNTRY_SOURCE[selected])
})
const selectedStation = computed(() => stationRows.value.find((s) => s.id === stationId.value) ?? null)
const reporting = computed(() => stationRows.value.filter((s) => s.has_data).length)

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
    <RainMap :stations="stationRows" :selected-id="stationId" @select="selectStation" />

    <div class="left-column">
      <header class="top panel">
        <div class="title-row">
          <div>
            <h1>{{ t.title }}</h1>
            <p class="subtitle">{{ t.subtitle }}</p>
          </div>
          <button type="button" @click="about?.open()">{{ t.aboutButton }}</button>
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
        <div class="controls-row">
          <CountryFilter v-model="country" />
          <button type="button" class="small" :aria-pressed="showList" @click="showList = !showList">
            {{ showList ? t.hideList : t.showList }}
          </button>
        </div>
      </header>

      <StationList v-if="showList" :stations="stationRows" :selected-id="stationId" @select="selectStation" />
      <MapLegend class="legend-position" />
    </div>

    <StationPanel
      v-if="selectedStation"
      :key="selectedStation.id"
      :station="selectedStation"
      @close="selectStation(null)"
      @pick-date="date = $event"
    />

    <AboutDialog ref="about" />
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
