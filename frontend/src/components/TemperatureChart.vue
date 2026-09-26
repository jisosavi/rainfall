<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DailyValue } from '../api'
import { tempClass } from '../lib/tempScale'
import { formatCelsius, formatShortDate, t } from '../strings'

// 30 days of temperature: the min–max range as a band, the daily mean as a line.
const props = defineProps<{
  mean: DailyValue[]
  min: DailyValue[]
  max: DailyValue[]
  start: string
  end: string
  selectedDate: string
}>()
const emit = defineEmits<{ pick: [date: string] }>()

const WIDTH = 300
const HEIGHT = 110
const PAD_Y = 6
const GUTTER = 30 // left, for the range labels

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

interface Day {
  date: string
  mean: number | null
  min: number | null
  max: number | null
}

const valueMap = (values: DailyValue[]) => new Map(values.filter((v) => v.has_data).map((v) => [v.date, v.value]))

// One slot per calendar day, including days with no row.
const days = computed<Day[]>(() => {
  const mean = valueMap(props.mean)
  const min = valueMap(props.min)
  const max = valueMap(props.max)
  const out: Day[] = []
  for (let d = props.start; d <= props.end; d = addDays(d, 1)) {
    out.push({ date: d, mean: mean.get(d) ?? null, min: min.get(d) ?? null, max: max.get(d) ?? null })
  }
  return out
})

// A whole-degree range around the data, at least 10 °C tall so a steady spell isn't magnified.
const range = computed(() => {
  const all = days.value.flatMap((d) => [d.mean, d.min, d.max]).filter((v): v is number => v !== null)
  let lo = all.length ? Math.floor(Math.min(...all)) : 0
  let hi = all.length ? Math.ceil(Math.max(...all)) : 10
  if (hi - lo < 10) {
    const mid = (hi + lo) / 2
    lo = Math.floor(mid - 5)
    hi = lo + 10
  }
  return { lo, hi }
})
const slot = computed(() => (WIDTH - GUTTER) / Math.max(days.value.length, 1))
const x = (i: number) => GUTTER + i * slot.value + slot.value / 2
const y = (c: number) => PAD_Y + ((range.value.hi - c) / (range.value.hi - range.value.lo)) * (HEIGHT - 2 * PAD_Y)

// Runs of consecutive days with data; gaps break the band and the line.
function runs<T>(pick: (d: Day) => T | null): Array<Array<{ i: number; v: T }>> {
  const out: Array<Array<{ i: number; v: T }>> = []
  let current: Array<{ i: number; v: T }> = []
  days.value.forEach((d, i) => {
    const v = pick(d)
    if (v === null) {
      if (current.length) out.push(current)
      current = []
    } else current.push({ i, v })
  })
  if (current.length) out.push(current)
  return out
}

const bandPaths = computed(() =>
  runs((d) => (d.min !== null && d.max !== null ? { min: d.min, max: d.max } : null)).map((run) => {
    // A single day is drawn as a short bar so it stays visible.
    const pts = run.length === 1 ? [{ ...run[0], dx: -slot.value / 3 }, { ...run[0], dx: slot.value / 3 }] : run.map((p) => ({ ...p, dx: 0 }))
    const top = pts.map((p) => `${x(p.i) + p.dx},${y(p.v.max)}`)
    const bottom = pts.map((p) => `${x(p.i) + p.dx},${y(p.v.min)}`).reverse()
    return `M${top.join(' L')} L${bottom.join(' L')} Z`
  }),
)
const meanPaths = computed(() =>
  runs((d) => d.mean).map((run) => (run.length === 1 ? null : `M${run.map((p) => `${x(p.i)},${y(p.v)}`).join(' L')}`)).filter(Boolean) as string[],
)
// Lone mean values (no neighbour to join) still get a dot.
const loneMeans = computed(() => runs((d) => d.mean).filter((run) => run.length === 1).map((run) => run[0]))

const zeroInRange = computed(() => range.value.lo < 0 && range.value.hi > 0)
// Whole degrees with a true minus sign, e.g. "−42°".
const degrees = (c: number) => `${c < 0 ? '−' : ''}${Math.abs(c)}°`

const hovered = ref<number | null>(null)
const activeIndex = computed(() => hovered.value ?? days.value.findIndex((d) => d.date === props.selectedDate))
const active = computed(() => days.value[activeIndex.value])
const caption = computed(() => {
  const d = active.value
  if (!d) return ''
  if (d.mean === null && d.min === null && d.max === null) return `${formatShortDate(d.date)}: ${t.noData}`
  return `${formatShortDate(d.date)}: ${t.temperatureDay(formatCelsius(d.mean), formatCelsius(d.min), formatCelsius(d.max))}`
})

const highest = computed(() => {
  const v = days.value.map((d) => d.max).filter((m): m is number => m !== null)
  return v.length ? Math.max(...v) : null
})
const lowest = computed(() => {
  const v = days.value.map((d) => d.min).filter((m): m is number => m !== null)
  return v.length ? Math.min(...v) : null
})
const average = computed(() => {
  const v = days.value.map((d) => d.mean).filter((m): m is number => m !== null)
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
})
</script>

<template>
  <figure class="temperature">
    <figcaption>
      <span>{{ t.last30Days }}</span>
      <span class="caption" aria-live="polite">{{ caption }}</span>
    </figcaption>
    <svg
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      role="img"
      :aria-label="`${t.last30Days}: ${t.warmest} ${formatCelsius(highest)}, ${t.coldest} ${formatCelsius(lowest)}`"
      @mouseleave="hovered = null"
    >
      <!-- Recessive frame: top and bottom of the range, and 0 °C when it's inside. -->
      <line :x1="GUTTER" :x2="WIDTH" :y1="y(range.hi)" :y2="y(range.hi)" class="grid" />
      <line :x1="GUTTER" :x2="WIDTH" :y1="y(range.lo)" :y2="y(range.lo)" class="grid" />
      <line v-if="zeroInRange" :x1="GUTTER" :x2="WIDTH" :y1="y(0)" :y2="y(0)" class="zero" />
      <text :x="GUTTER - 4" :y="y(range.hi) + 3" class="tick" text-anchor="end">{{ degrees(range.hi) }}</text>
      <text :x="GUTTER - 4" :y="y(range.lo) + 3" class="tick" text-anchor="end">{{ degrees(range.lo) }}</text>
      <text v-if="zeroInRange && y(range.lo) - y(0) > 12 && y(0) - y(range.hi) > 12" :x="GUTTER - 4" :y="y(0) + 3" class="tick" text-anchor="end">0°</text>

      <path v-for="(p, i) in bandPaths" :key="`band${i}`" :d="p" class="band" />
      <path v-for="(p, i) in meanPaths" :key="`mean${i}`" :d="p" class="mean" />
      <circle v-for="p in loneMeans" :key="`lone${p.i}`" :cx="x(p.i)" :cy="y(p.v)" r="2.5" class="lone" />

      <!-- Crosshair and point for the hovered (or shown) day. -->
      <template v-if="active">
        <line :x1="x(activeIndex)" :x2="x(activeIndex)" :y1="0" :y2="HEIGHT" class="crosshair" />
        <circle
          v-if="active.mean !== null"
          :cx="x(activeIndex)"
          :cy="y(active.mean)"
          r="4.5"
          class="point"
          :fill="tempClass(active.mean).color"
        />
      </template>

      <rect
        v-for="(d, i) in days"
        :key="d.date"
        :x="GUTTER + i * slot"
        y="0"
        :width="slot"
        :height="HEIGHT"
        class="hit"
        @mouseenter="hovered = i"
        @click="emit('pick', d.date)"
      >
        <title>{{ formatShortDate(d.date) }}: {{ t.temperatureDay(formatCelsius(d.mean), formatCelsius(d.min), formatCelsius(d.max)) }}</title>
      </rect>
    </svg>
    <div class="axis">
      <span>{{ formatShortDate(start) }}</span>
      <span class="key"><span class="key-line" />{{ t.chartMean }}<span class="key-band" />{{ t.chartRange }}</span>
      <span>{{ formatShortDate(end) }}</span>
    </div>
    <dl class="stats">
      <div><dt>{{ t.warmest }}</dt><dd>{{ formatCelsius(highest) }}</dd></div>
      <div><dt>{{ t.coldest }}</dt><dd>{{ formatCelsius(lowest) }}</dd></div>
      <div><dt>{{ t.averageMean }}</dt><dd>{{ formatCelsius(average === null ? null : Math.round(average * 10) / 10) }}</dd></div>
    </dl>
  </figure>
</template>

<style scoped>
.temperature {
  margin: 0;
}
figcaption {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 2px 8px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.caption {
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
svg {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}
.grid {
  stroke: var(--border-subtle);
  stroke-width: 1;
}
.zero {
  stroke: var(--border);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}
.tick {
  font-size: 9px;
  fill: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.band {
  fill: rgb(255 255 255 / 0.16);
  stroke: rgb(255 255 255 / 0.28);
  stroke-width: 1;
  stroke-linejoin: round;
}
.mean {
  fill: none;
  stroke: var(--text-primary);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.lone {
  fill: var(--text-primary);
}
.crosshair {
  stroke: rgb(255 255 255 / 0.35);
  stroke-width: 1;
  pointer-events: none;
}
/* The point wears the map colour of the day's mean, with a surface ring. */
.point {
  stroke: var(--surface);
  stroke-width: 2;
  pointer-events: none;
}
.hit {
  fill: transparent;
  cursor: pointer;
}
.axis {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}
.key {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-secondary);
}
.key-line {
  width: 14px;
  height: 2px;
  border-radius: 1px;
  background: var(--text-primary);
}
.key-band {
  width: 14px;
  height: 8px;
  margin-left: 6px;
  border-radius: 2px;
  background: rgb(255 255 255 / 0.16);
  border: 1px solid rgb(255 255 255 / 0.28);
}
.stats {
  display: flex;
  gap: 20px;
  margin: 12px 0 0;
}
.stats dt {
  font-size: 11px;
  color: var(--text-secondary);
}
.stats dd {
  margin: 2px 0 0;
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}
</style>
