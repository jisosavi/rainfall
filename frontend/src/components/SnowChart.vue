<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DailyValue } from '../api'
import { formatCm, formatShortDate, t } from '../strings'

// Snow depth through the winter: an area chart, gaps where a day has no reading.
const props = defineProps<{ values: DailyValue[]; start: string; end: string; selectedDate: string; title: string }>()
const emit = defineEmits<{ pick: [date: string] }>()

const WIDTH = 300
const HEIGHT = 96
const TOP = 4

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

const days = computed(() => {
  const byDate = new Map(props.values.map((v) => [v.date, v]))
  const out: Array<{ date: string; cm: number | null }> = []
  for (let d = props.start; d <= props.end; d = addDays(d, 1)) {
    const v = byDate.get(d)
    out.push({ date: d, cm: v && v.has_data ? v.value : null })
  }
  return out
})

const maxCm = computed(() => Math.max(20, ...days.value.map((d) => d.cm ?? 0)))
const step = computed(() => WIDTH / Math.max(days.value.length - 1, 1))
const x = (i: number) => i * step.value
const y = (cm: number) => HEIGHT - (cm / maxCm.value) * (HEIGHT - TOP)

// Consecutive days with data form one segment; a missing day breaks the line.
const segments = computed(() => {
  const out: Array<Array<[number, number]>> = []
  let current: Array<[number, number]> = []
  days.value.forEach((d, i) => {
    if (d.cm === null) {
      if (current.length) out.push(current)
      current = []
    } else current.push([x(i), y(d.cm)])
  })
  if (current.length) out.push(current)
  return out
})
const linePath = (seg: Array<[number, number]>) => seg.map(([px, py], i) => `${i ? 'L' : 'M'}${px},${py}`).join(' ')
const areaPath = (seg: Array<[number, number]>) =>
  `${linePath(seg)} L${seg[seg.length - 1][0]},${HEIGHT} L${seg[0][0]},${HEIGHT} Z`

const selectedIndex = computed(() => days.value.findIndex((d) => d.date === props.selectedDate))
const hovered = ref<number | null>(null)
const caption = computed(() => {
  const day = days.value[hovered.value ?? selectedIndex.value]
  return day ? `${formatShortDate(day.date)}: ${formatCm(day.cm)}` : ''
})

const deepest = computed(() =>
  days.value.reduce<{ date: string; cm: number } | null>(
    (best, d) => (d.cm !== null && (best === null || d.cm > best.cm) ? { date: d.date, cm: d.cm } : best),
    null,
  ),
)
const coverDays = computed(() => days.value.filter((d) => (d.cm ?? 0) >= 1).length)
const dataDays = computed(() => days.value.filter((d) => d.cm !== null).length)
</script>

<template>
  <figure class="snow">
    <figcaption>
      <span>{{ title }}</span>
      <span class="caption" aria-live="polite">{{ caption }}</span>
    </figcaption>
    <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT + 1}`" role="img" :aria-label="`${title}: ${t.seasonMax} ${formatCm(deepest?.cm ?? null)}`" @mouseleave="hovered = null">
      <line :x1="0" :x2="WIDTH" :y1="HEIGHT + 0.5" :y2="HEIGHT + 0.5" class="baseline" />
      <text x="2" :y="TOP + 8" class="ymax">{{ formatCm(maxCm) }}</text>
      <g v-for="(seg, i) in segments" :key="i">
        <path :d="areaPath(seg)" class="area" />
        <path :d="linePath(seg)" class="line" />
      </g>
      <g v-if="selectedIndex >= 0">
        <line :x1="x(selectedIndex)" :x2="x(selectedIndex)" :y1="TOP" :y2="HEIGHT" class="marker" />
        <circle v-if="days[selectedIndex].cm !== null" :cx="x(selectedIndex)" :cy="y(days[selectedIndex].cm!)" r="3" class="dot" />
      </g>
      <line v-if="hovered !== null" :x1="x(hovered)" :x2="x(hovered)" :y1="TOP" :y2="HEIGHT" class="hover" />
      <!-- One full-height hit target per day, wider than the line. -->
      <rect
        v-for="(d, i) in days"
        :key="d.date"
        :x="x(i) - step / 2"
        y="0"
        :width="step"
        :height="HEIGHT"
        class="hit"
        @mouseenter="hovered = i"
        @click="emit('pick', d.date)"
      >
        <title>{{ formatShortDate(d.date) }}: {{ formatCm(d.cm) }}</title>
      </rect>
    </svg>
    <div class="axis">
      <span>{{ formatShortDate(start) }}</span>
      <span>{{ formatShortDate(end) }}</span>
    </div>
    <dl class="stats">
      <div>
        <dt>{{ t.seasonMax }}</dt>
        <dd>{{ formatCm(deepest?.cm ?? null) }}<span v-if="deepest" class="sub"> · {{ formatShortDate(deepest.date) }}</span></dd>
      </div>
      <div><dt>{{ t.snowCoverDays }}</dt><dd>{{ coverDays }} / {{ dataDays }}</dd></div>
    </dl>
  </figure>
</template>

<style scoped>
.snow {
  margin: 0;
}
figcaption {
  display: flex;
  justify-content: space-between;
  gap: 8px;
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
.baseline {
  stroke: var(--border);
  stroke-width: 1;
}
.area {
  fill: rgb(127 211 224 / 0.22);
}
.line {
  fill: none;
  stroke: #7fd3e0;
  stroke-width: 2;
  stroke-linejoin: round;
}
.marker {
  stroke: #fff;
  stroke-width: 1;
  stroke-dasharray: 2 2;
}
.dot {
  fill: #fff;
}
.hover {
  stroke: rgb(255 255 255 / 0.35);
  stroke-width: 1;
}
.ymax {
  fill: var(--text-muted);
  font-size: 9px;
}
.hit {
  fill: transparent;
  cursor: pointer;
}
.axis {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}
.stats {
  display: flex;
  gap: 24px;
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
.sub {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
