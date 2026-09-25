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

const FINLAND_BOUNDS: [[number, number], [number, number]] = [
  [19.0, 59.6],
  [31.6, 70.1],
]
const MAP_SURFACE: [number, number, number, number] = [12, 12, 12, 255]
const WHITE: [number, number, number, number] = [255, 255, 255, 235]

// Hollow (no data) first, then dry to wet, so the heaviest rainfall is drawn on top.
function drawOrder(stations: StationDay[]): StationDay[] {
  return [...stations].sort((a, b) => (a.precipitation_mm ?? -1) - (b.precipitation_mm ?? -1))
}

function buildLayer() {
  const selected = props.selectedId
  return new ScatterplotLayer<StationDay>({
    id: 'stations',
    data: drawOrder(props.stations),
    getPosition: (d) => [d.lon, d.lat],
    radiusUnits: 'pixels',
    getRadius: (d) => (d.id === selected ? 9 : 6),
    stroked: true,
    filled: true,
    lineWidthUnits: 'pixels',
    getLineWidth: (d) => (d.id === selected ? 3 : d.has_data ? 1.5 : 2),
    getFillColor: (d) =>
      d.has_data && d.precipitation_mm !== null ? [...rainClass(d.precipitation_mm).rgb, 255] : [0, 0, 0, 0],
    // Filled circles get a thin ring in the map colour so overlapping stations stay separate.
    getLineColor: (d) => (d.id === selected || !d.has_data ? WHITE : MAP_SURFACE),
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 60],
    updateTriggers: { getRadius: selected, getLineWidth: selected, getLineColor: selected },
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
    bounds: FINLAND_BOUNDS,
    fitBoundsOptions: { padding: 24 },
    attributionControl: { compact: true, customAttribution: t.attribution },
  })
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')

  overlay = new MapboxOverlay({
    layers: [buildLayer()],
    getTooltip: tooltip,
    onClick: (info) => emit('select', (info.object as StationDay | undefined)?.id ?? null),
    getCursor: ({ isHovering }) => (isHovering ? 'pointer' : 'grab'),
  })
  map.addControl(overlay)
})

watch(
  () => [props.stations, props.selectedId],
  () => overlay?.setProps({ layers: [buildLayer()] }),
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
