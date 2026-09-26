<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as maplibregl from 'maplibre-gl'
// MapLibre 6 loads its worker relative to its own module, which Vite relocates; bundle it explicitly.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import type { PickingInfo } from '@deck.gl/core'
import type { Parameter, RankedStation, StationDay } from '../api'
import { boundsFor, START_BOUNDS, type CountryFilter } from '../lib/countries'
import { SCALES } from '../lib/scales'
import { formatValue, suspectShort, t } from '../strings'

const props = defineProps<{
  stations: StationDay[]
  selectedId: string | null
  parameter: Parameter
  focus: CountryFilter
  ranks: RankedStation[] // Top 15: rank numbers next to these stations
  flyTo: { lon: number; lat: number; seq: number } | null // a station chosen in a list
}>()
const emit = defineEmits<{ select: [id: string | null] }>()

const container = ref<HTMLDivElement>()
let map: maplibregl.Map | undefined
let overlay: MapboxOverlay | undefined


// Keep the start view clear of the overlay panels (see App.vue layout).
function startPadding() {
  if (window.matchMedia('(max-width: 760px)').matches) {
    return { top: 210, bottom: 16, left: 8, right: 8 } // header card on top
  }
  return { top: 16, bottom: 16, left: 392, right: 16 } // 360 px left column + gutters
}
const MAP_SURFACE: [number, number, number, number] = [12, 12, 12, 255]
const WHITE: [number, number, number, number] = [255, 255, 255, 235]
// Status "warning" amber: a value far above all nearby stations (always paired with a text label).
const SUSPECT: [number, number, number, number] = [250, 178, 25, 255]

// Hollow (no data) first, then low to high, so the heaviest rainfall (or the warmest
// temperature) is drawn on top.
function drawOrder(stations: StationDay[]): StationDay[] {
  const key = (s: StationDay) => (s.has_data && s.value !== null ? s.value : -Infinity)
  return [...stations].sort((a, b) => (key(a) === key(b) ? 0 : key(a) < key(b) ? -1 : 1))
}

function buildLayers() {
  const selected = props.selectedId
  const selectedStation = props.stations.find((s) => s.id === selected)
  return [
    stationsLayer(),
    ...(props.ranks.length ? [unreportedRanked()] : []),
    ...(selectedStation ? [selectionRing(selectedStation)] : []),
    ...(props.ranks.length ? [rankLabels()] : []),
  ]
}

// Rank numbers for the Top 15: dark digits on a white badge with a dark edge, so they read
// against the dark map and can't be mistaken for a (white) station circle.
function rankLabels() {
  return new TextLayer<RankedStation>({
    id: 'ranks',
    data: props.ranks,
    getPosition: (d) => [d.lon, d.lat],
    getText: (d) => String(d.rank),
    getSize: 12,
    getColor: [12, 12, 12, 255],
    getPixelOffset: [0, -16],
    fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
    fontWeight: 700,
    background: true,
    getBackgroundColor: [245, 245, 246, 255],
    getBorderColor: [12, 12, 12, 255],
    getBorderWidth: 1,
    backgroundPadding: [4, 1],
    characterSet: '0123456789',
  })
}

// A ranked station without a value on the shown date (e.g. snow days this winter, but no
// reading today) still gets a hollow ring, so its rank number marks a visible station.
function unreportedRanked() {
  const shown = new Set(props.stations.map((s) => s.id))
  return new ScatterplotLayer<RankedStation>({
    id: 'ranked-unreported',
    data: props.ranks.filter((r) => !shown.has(r.id)),
    getPosition: (d) => [d.lon, d.lat],
    radiusUnits: 'pixels',
    getRadius: 5,
    stroked: true,
    filled: false,
    lineWidthUnits: 'pixels',
    getLineWidth: 2,
    getLineColor: WHITE,
  })
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
  const scale = SCALES[props.parameter]
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
    getLineWidth: (d) => (d.flag === 'suspect_spatial' ? 2.5 : d.has_data ? 1.5 : 2),
    getFillColor: (d) => (d.has_data && d.value !== null ? [...scale.classOf(d.value).rgb, 255] : [0, 0, 0, 0]),
    updateTriggers: { getFillColor: props.parameter },
    // Filled circles get a thin ring in the map colour so overlapping stations stay separate.
    getLineColor: (d) => (d.flag === 'suspect_spatial' ? SUSPECT : d.has_data ? MAP_SURFACE : WHITE),
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 60],
  })
}

function tooltip({ object }: PickingInfo<StationDay>) {
  if (!object) return null
  const value = formatValue(props.parameter, object.has_data ? object.value : null)
  return {
    html: `<strong>${escapeHtml(object.name)}</strong><br>${value}${object.flag === 'suspect_spatial' ? `<br>⚠ ${suspectShort(props.parameter)}` : ''}`,
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
    bounds: props.focus === 'all' ? START_BOUNDS : boundsFor(props.focus),
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

// A station chosen in the list or the Top 15: centre it in the area left free by the
// panels, zoomed in to regional level (or keep a closer zoom).
const STATION_ZOOM = 7
function panelPadding() {
  if (window.matchMedia('(max-width: 760px)').matches) {
    return { top: 60, bottom: Math.round(window.innerHeight * 0.6), left: 16, right: 16 }
  }
  return { top: 40, bottom: 40, left: 392, right: 372 }
}
watch(
  () => props.flyTo?.seq,
  () => {
    if (!map || !props.flyTo) return
    map.flyTo({
      center: [props.flyTo.lon, props.flyTo.lat],
      zoom: Math.max(map.getZoom(), STATION_ZOOM),
      padding: panelPadding(),
      duration: 1200,
    })
  },
)

// Choosing a country zooms the map to it; "All" returns to the start view.
watch(
  () => props.focus,
  (focus) => map?.fitBounds(boundsFor(focus), { padding: startPadding(), duration: 800 }),
)

watch(
  () => [props.stations, props.selectedId, props.parameter, props.ranks],
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
