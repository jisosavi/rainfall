<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as maplibregl from 'maplibre-gl'
// MapLibre 6 loads its worker relative to its own module, which Vite relocates; bundle it explicitly.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { ScatterplotLayer } from '@deck.gl/layers'
import type { PickingInfo } from '@deck.gl/core'
import type { StationDay } from '../api'
import { rainClass } from '../lib/rainScale'
import { formatMm, t } from '../strings'

const props = defineProps<{ stations: StationDay[]; selectedId: string | null }>()
const emit = defineEmits<{ select: [id: string | null] }>()

const container = ref<HTMLDivElement>()
let map: maplibregl.Map | undefined
let overlay: MapboxOverlay | undefined

// Finland, Sweden and mainland Norway; Svalbard and Jan Mayen are one zoom-out away.
const START_BOUNDS: [[number, number], [number, number]] = [
  [4.5, 55.2],
  [31.6, 71.3],
]

// Keep the start view clear of the overlay panels (see App.vue layout).
function startPadding() {
  if (window.matchMedia('(max-width: 760px)').matches) {
    return { top: 210, bottom: 16, left: 8, right: 8 } // header card on top
  }
  return { top: 16, bottom: 16, left: 392, right: 16 } // 360 px left column + gutters
}
const MAP_SURFACE: [number, number, number, number] = [12, 12, 12, 255]
const WHITE: [number, number, number, number] = [255, 255, 255, 235]

// Hollow (no data) first, then dry to wet, so the heaviest rainfall is drawn on top.
function drawOrder(stations: StationDay[]): StationDay[] {
  return [...stations].sort((a, b) => (a.precipitation_mm ?? -1) - (b.precipitation_mm ?? -1))
}

function buildLayers() {
  const selected = props.selectedId
  const selectedStation = props.stations.find((s) => s.id === selected)
  return [stationsLayer(), ...(selectedStation ? [selectionRing(selectedStation)] : [])]
}

// Fixed-size white ring on top of the selected station, independent of zoom.
function selectionRing(station: StationDay) {
  return new ScatterplotLayer<StationDay>({
    id: 'selection',
    data: [station],
    getPosition: (d) => [d.lon, d.lat],
    radiusUnits: 'pixels',
    getRadius: 10,
    stroked: true,
    filled: false,
    lineWidthUnits: 'pixels',
    getLineWidth: 2.5,
    getLineColor: WHITE,
  })
}

function stationsLayer() {
  return new ScatterplotLayer<StationDay>({
    id: 'stations',
    data: drawOrder(props.stations),
    getPosition: (d) => [d.lon, d.lat],
    // Radius in metres, so circles shrink when zoomed out (dense southern Norway) and grow
    // to full size when zoomed in; clamped to stay visible and clickable.
    radiusUnits: 'meters',
    getRadius: 6000,
    radiusMinPixels: 4.5,
    radiusMaxPixels: 7,
    stroked: true,
    filled: true,
    lineWidthUnits: 'pixels',
    getLineWidth: (d) => (d.has_data ? 1.5 : 2),
    getFillColor: (d) =>
      d.has_data && d.precipitation_mm !== null ? [...rainClass(d.precipitation_mm).rgb, 255] : [0, 0, 0, 0],
    // Filled circles get a thin ring in the map colour so overlapping stations stay separate.
    getLineColor: (d) => (d.has_data ? MAP_SURFACE : WHITE),
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 60],
  })
}

function tooltip({ object }: PickingInfo<StationDay>) {
  if (!object) return null
  const value = object.has_data ? formatMm(object.precipitation_mm) : formatMm(null)
  return {
    html: `<strong>${escapeHtml(object.name)}</strong><br>${value}`,
    className: 'map-tooltip',
    style: { backgroundColor: '', color: '', padding: '', fontSize: '' },
  }
}

const escapeHtml = (text: string) =>
  text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)

maplibregl.setWorkerUrl(maplibreWorkerUrl)

onMounted(() => {
  map = new maplibregl.Map({
    container: container.value!,
    style: 'https://tiles.openfreemap.org/styles/dark',
    bounds: START_BOUNDS,
    fitBoundsOptions: { padding: startPadding() },
    attributionControl: { compact: true, customAttribution: t.attribution },
  })
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
  // On small screens the credits would cover the legend; start collapsed behind the ⓘ button.
  map.once('load', () => {
    if (window.matchMedia('(max-width: 760px)').matches) {
      container.value?.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show')
    }
  })

  overlay = new MapboxOverlay({
    layers: buildLayers(),
    getTooltip: tooltip,
    onClick: (info) => emit('select', (info.object as StationDay | undefined)?.id ?? null),
    getCursor: ({ isHovering }) => (isHovering ? 'pointer' : 'grab'),
  })
  map.addControl(overlay)
})

watch(
  () => [props.stations, props.selectedId],
  () => overlay?.setProps({ layers: buildLayers() }),
)

onBeforeUnmount(() => {
  overlay?.finalize()
  map?.remove()
})
</script>

<template>
  <div ref="container" class="rain-map" role="application" aria-label="Map of rainfall at weather stations" />
</template>

<style scoped>
.rain-map {
  position: absolute;
  inset: 0;
}
</style>
