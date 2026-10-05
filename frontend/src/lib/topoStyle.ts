// The "Topographic" map background: OpenTopoMap's vector style (https://opentopomap.org/vector/),
// with relief, contour lines and 3D terrain from Mapterhorn's open terrain tiles, which combine
// national elevation models (e.g. Finland 2 m, Greenland 2 m, Iceland 10 m) with Copernicus GLO-30.
//
// otm-layers.json is OpenTopoMap's layer list (otm_layers.json, converted from JavaScript to JSON,
// the hidden raster fallback layers left out). Map style © OpenTopoMap, licensed CC BY-SA.
// Labels use each place's own name ({name}: "Inari", "Kárášjohka", "Tórshavn").
// Adapted for our station circles: the elevation colouring (zooms 0–8) is paler and streams a
// softer blue (lake outlines too), so they don't compete with the colour scales (snow and cold classes are blue).
import type * as maplibregl from 'maplibre-gl'
import mlcontour from 'maplibre-contour'
import otmLayers from './otm-layers.json'

// OpenTopoMap's required credit (https://opentopomap.org/about), in English: "Kartendaten:
// © OpenStreetMap-Mitwirkende, SRTM | Kartendarstellung: © OpenTopoMap (CC-BY-SA)". Our
// elevation comes from Mapterhorn rather than SRTM, so Mapterhorn is credited instead.
export const TOPO_ATTRIBUTION =
  'Map data: © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors' +
  ' | Map display: © <a href="https://opentopomap.org/about" target="_blank" rel="noopener">OpenTopoMap</a> (CC-BY-SA)' +
  ' | Elevation: <a href="https://mapterhorn.com/attribution" target="_blank" rel="noopener">Mapterhorn</a> (national elevation models, Copernicus GLO-30)'

const SOFT_WATER = '#6fa9dc' // instead of pure blue

let demSource: InstanceType<typeof mlcontour.DemSource> | undefined

/** The elevation source shared by relief, contours and 3D terrain (set up once per page). */
function dem(maplib: typeof maplibregl) {
  if (!demSource) {
    demSource = new mlcontour.DemSource({
      url: 'https://tiles.mapterhorn.com/{z}/{x}/{y}.webp',
      encoding: 'terrarium',
      maxzoom: 15,
      worker: true, // contour lines are computed off the main thread
      cacheSize: 100,
      timeoutMs: 10_000,
    })
    demSource.setupMaplibre(maplib)
  }
  return demSource
}

export function topoStyle(maplib: typeof maplibregl): maplibregl.StyleSpecification {
  const source = dem(maplib)
  const layers = (otmLayers as maplibregl.LayerSpecification[]).map((original) => {
    let layer = original
    if (layer.id === 'color-relief') {
      layer = { ...layer, paint: { ...layer.paint, 'color-relief-opacity': 0.45 } } as maplibregl.LayerSpecification
    } else if (layer.id === 'water-line') {
      layer = { ...layer, paint: { ...layer.paint, 'line-color': SOFT_WATER } } as maplibregl.LayerSpecification
    } else if (layer.id === 'water-poly') {
      // Lapland's thousands of small lakes otherwise draw a dense pattern of dark-blue outlines.
      layer = { ...layer, paint: { ...layer.paint, 'fill-outline-color': SOFT_WATER } } as maplibregl.LayerSpecification
    } else if (layer.id === 'ocean') {
      // Sea polygons are cut at tile edges; an outline would draw a grid over the sea.
      const fill = (layer.paint as { 'fill-color'?: string } | undefined)?.['fill-color']
      layer = { ...layer, paint: { ...layer.paint, 'fill-outline-color': fill } } as maplibregl.LayerSpecification
    }
    const translated = (layer as { metadata?: { translate?: boolean } }).metadata?.translate
    if (translated && 'layout' in layer && layer.layout && 'text-field' in layer.layout) {
      return { ...layer, layout: { ...layer.layout, 'text-field': '{name}' } } as maplibregl.LayerSpecification
    }
    return layer
  })
  return {
    version: 8,
    sources: {
      'opentopomap-vector': {
        type: 'vector',
        tiles: ['https://opentopomap.org/otm/{z}/{x}/{y}.pbf'],
        maxzoom: 14,
        attribution: TOPO_ATTRIBUTION,
      },
      dem: {
        type: 'raster-dem',
        encoding: 'terrarium',
        tiles: [source.sharedDemProtocolUrl],
        maxzoom: 15,
        tileSize: 512,
      },
      'contour-source': {
        type: 'vector',
        tiles: [
          source.contourProtocolUrl({
            multiplier: 1,
            thresholds: { 10: [50, 1000], 11: [20, 500], 12: [10, 100], 13: [10, 100], 14: [10, 100], 15: [10, 50] },
            contourLayer: 'contours',
            elevationKey: 'ele',
            levelKey: 'level',
            extent: 4096,
            buffer: 1,
          }),
        ],
        maxzoom: 15,
      },
    },
    glyphs: 'https://fonts.undpgeohub.org/fonts/{fontstack}/{range}.pbf',
    sprite: 'https://opentopomap.org/vector/otm_sprite',
    layers,
  }
}

/** 3D terrain, as on opentopomap.org (heights exaggerated ×2 so northern fells read well). */
export const TERRAIN_EXAGGERATION = 2
