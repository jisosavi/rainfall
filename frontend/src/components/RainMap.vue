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
import { TERRAIN_EXAGGERATION, topoStyle } from '../lib/topoStyle'
import { formatValue, suspectShort, t } from '../strings'

const props = defineProps<{
  stations: StationDay[]
  selectedId: string | null
  parameter: Parameter
  focus: CountryFilter
  ranks: RankedStation[] // Top 15: rank numbers next to these stations
  flyTo: { lon: number; lat: number; seq: number } | null // a station chosen in a list
  background: 'dark' | 'topo' // map background: the dark map or OpenTopoMap
  terrain: boolean // 3D terrain (topographic background only)
}>()
const emit = defineEmits<{
  select: [id: string | null]
  'update:background': [background: 'dark' | 'topo']
  'update:terrain': [terrain: boolean]
}>()

// Map buttons above the zoom control: Topo (background) and 3D (topographic only).
class BackgroundControl implements maplibregl.IControl {
  container = document.createElement('div')
  topo = document.createElement('button')
  terrain = document.createElement('button')
  onAdd() {
    this.container.className = 'maplibregl-ctrl maplibregl-ctrl-group map-buttons'
    for (const [button, label] of [[this.topo, t.topoButton], [this.terrain, t.terrainButton]] as const) {
      button.type = 'button'
      button.textContent = label
      this.container.appendChild(button)
    }
    this.topo.addEventListener('click', () => emit('update:background', props.background === 'topo' ? 'dark' : 'topo'))
    this.terrain.addEventListener('click', () => emit('update:terrain', !props.terrain))
    this.update()
    return this.container
  }
  onRemove() {
    this.container.remove()
  }
  update() {
    const topo = props.background === 'topo'
    this.topo.setAttribute('aria-pressed', String(topo))
    this.topo.title = topo ? t.topoOn : t.topoOff
    this.topo.setAttribute('aria-label', this.topo.title)
    this.terrain.hidden = !topo
    this.terrain.setAttribute('aria-pressed', String(props.terrain))
    this.terrain.title = props.terrain ? t.terrainOn : t.terrainOff
    this.terrain.setAttribute('aria-label', this.terrain.title)
  }
}
const backgroundControl = new BackgroundControl()

const container = ref<HTMLDivElement>()
let map: maplibregl.Map | undefined
let overlay: MapboxOverlay | undefined


// Keep the start view clear of the overlay panels (see App.vue layout).
function startPadding() {
  if (window.matchMedia('(max-width: 760px)').matches) {
    return { top: 16, bottom: 16, left: 8, right: 8 } // the map starts below the top box
  }
  return { top: 16, bottom: 16, left: 392, right: 16 } // 360 px left column + gutters
}
const DARK_STYLE = 'https://tiles.openfreemap.org/styles/dark'
const MAP_SURFACE: [number, number, number, number] = [12, 12, 12, 255]
const WHITE: [number, number, number, number] = [255, 255, 255, 235]
// "No data" rings: white on the dark map, dark grey on the light topographic map.
const HOLLOW_ON_TOPO: [number, number, number, number] = [60, 60, 64, 235]
const hollow = () => (props.background === 'topo' ? HOLLOW_ON_TOPO : WHITE)

// With 3D terrain, circles sit at the terrain's height (as MapLibre draws it, exaggerated);
// recomputed when terrain tiles load, so they follow the hills instead of floating or sinking.
const terrainOn = () => props.background === 'topo' && props.terrain
let heightVersion = 0
function position(lon: number, lat: number, elevation?: number | null): [number, number] | [number, number, number] {
  if (!terrainOn() || !map) return [lon, lat]
  const height = map.queryTerrainElevation([lon, lat])
  return [lon, lat, height ?? (elevation ?? 0) * TERRAIN_EXAGGERATION]
}
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
    getPosition: (d) => position(d.lon, d.lat),
    updateTriggers: { getPosition: heightVersion },
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
    billboard: true,
    data: props.ranks.filter((r) => !shown.has(r.id)),
    getPosition: (d) => position(d.lon, d.lat),
    updateTriggers: { getPosition: heightVersion, getLineColor: props.background },
    radiusUnits: 'pixels',
    getRadius: 5,
    stroked: true,
    filled: false,
    lineWidthUnits: 'pixels',
    getLineWidth: 2,
    getLineColor: hollow(),
  })
}

// Fixed-size white ring on top of the selected station, independent of zoom.
function selectionRing(station: StationDay) {
  return new ScatterplotLayer<StationDay>({
    id: 'selection',
    billboard: true,
    data: [station],
    getPosition: (d) => position(d.lon, d.lat, d.elevation_m),
    updateTriggers: { getPosition: heightVersion },
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
    billboard: true,
    data: drawOrder(props.stations),
    getPosition: (d) => position(d.lon, d.lat, d.elevation_m),
    // Radius in metres, so circles shrink when zoomed out (dense southern Norway) and grow
    // to full size when zoomed in; clamped to stay visible and clickable.
    radiusUnits: 'meters',
    getRadius: 6000,
    radiusMinPixels: 4.5,
    radiusMaxPixels: 7,
    stroked: true,
    filled: true,
    lineWidthUnits: 'pixels',
    // A little thicker on the light topographic map, where the dark ring carries the contrast.
    getLineWidth: (d) => (d.flag === 'suspect_spatial' ? 2.5 : d.has_data ? (props.background === 'topo' ? 2 : 1.5) : 2),
    getFillColor: (d) => (d.has_data && d.value !== null ? [...scale.classOf(d.value).rgb, 255] : [0, 0, 0, 0]),
    updateTriggers: {
      getFillColor: props.parameter,
      getPosition: heightVersion,
      getLineColor: props.background,
      getLineWidth: props.background,
    },
    // Filled circles get a thin dark ring so overlapping stations stay separate (and pale
    // classes stay visible on the light topographic map).
    getLineColor: (d) => (d.flag === 'suspect_spatial' ? SUSPECT : d.has_data ? MAP_SURFACE : hollow()),
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
    style: props.background === 'topo' ? topoStyle(maplibregl) : DARK_STYLE,
    bounds: props.focus === 'all' ? START_BOUNDS : boundsFor(props.focus),
    fitBoundsOptions: { padding: startPadding() },
    attributionControl: { compact: true, customAttribution: t.attribution },
  })
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
  map.addControl(backgroundControl, 'bottom-right') // added last, so it sits above the zoom buttons
  // Development only: lets automated screenshots move the camera.
  if (import.meta.env.DEV) (window as unknown as { __map?: maplibregl.Map }).__map = map
  // On small screens the credits would cover the legend; start collapsed behind the ⓘ button.
  map.once('load', () => {
    if (window.matchMedia('(max-width: 760px)').matches) {
      container.value?.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show')
    }
  })

  // deck.gl 9.4 reads the terrain height under the map centre from map.transform (MapLibre 4);
  // MapLibre 6 no longer exposes it, so provide the values it needs from the public API.
  // Without this, circles drift away from the terrain when 3D is on.
  Object.defineProperty(map, 'transform', {
    configurable: true,
    get: () => ({ elevation: map!.getCenterElevation(), height: map!.getCanvas().clientHeight }),
  })

  overlay = new MapboxOverlay({
    layers: buildLayers(),
    getTooltip: tooltip,
    onClick: (info) => emit('select', (info.object as StationDay | undefined)?.id ?? null),
    getCursor: ({ isHovering }) => (isHovering ? 'pointer' : 'grab'),
  })
  map.addControl(overlay)

  // Style changes drop the terrain; re-apply it. When terrain tiles arrive, move the circles.
  map.on('style.load', applyTerrain)
  map.on('sourcedata', (e) => {
    if (e.sourceId === 'dem' && e.tile) refreshHeights()
  })
  map.on('moveend', refreshHeights)
})

// Terrain tiles arrive in bursts; move the circles once things settle (not on every repaint).
let heightsTimer: ReturnType<typeof setTimeout> | undefined
function refreshHeights() {
  if (!terrainOn()) return
  clearTimeout(heightsTimer)
  heightsTimer = setTimeout(() => {
    heightVersion += 1
    overlay?.setProps({ layers: buildLayers() })
  }, 250)
}

function applyTerrain() {
  if (!map) return
  // The style is ready enough once its elevation source exists (isStyleLoaded() stays false
  // while tiles keep loading).
  if (terrainOn() && map.getSource('dem')) {
    map.setTerrain({ source: 'dem', exaggeration: TERRAIN_EXAGGERATION })
    if (map.getPitch() < 10) map.easeTo({ pitch: 55, duration: 800 })
  } else {
    if (map.getTerrain()) map.setTerrain(null)
    if (map.getPitch() > 0) map.easeTo({ pitch: 0, duration: 600 })
  }
  heightVersion += 1
  overlay?.setProps({ layers: buildLayers() })
}

watch(
  () => props.background,
  (background) => {
    backgroundControl.update()
    map?.setStyle(background === 'topo' ? topoStyle(maplibregl) : DARK_STYLE)
  },
)
watch(
  () => props.terrain,
  () => {
    backgroundControl.update()
    applyTerrain()
  },
)

// A station chosen in the list or the Top 15: centre it in the area left free by the
// panels, zoomed in to regional level (or keep a closer zoom).
const STATION_ZOOM = 7
function panelPadding() {
  if (window.matchMedia('(max-width: 760px)').matches) {
    return { top: 24, bottom: Math.round(window.innerHeight * 0.6), left: 16, right: 16 } // panel over the bottom
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
  () => [props.stations, props.selectedId, props.parameter, props.ranks, props.background],
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
