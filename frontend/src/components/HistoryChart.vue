<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DailyValue } from '../api'
import { rainClass } from '../lib/rainScale'
import { formatMm, formatShortDate, t } from '../strings'

const props = defineProps<{ values: DailyValue[]; start: string; end: string; selectedDate: string }>()
const emit = defineEmits<{ pick: [date: string] }>()

const WIDTH = 300
const HEIGHT = 96
const GAP = 2

function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

// One slot per calendar day, including days with no row.
const days = computed(() => {
  const byDate = new Map(props.values.map((v) => [v.date, v]))
  const out: Array<{ date: string; mm: number | null }> = []
  for (let d = props.start; d <= props.end; d = addDays(d, 1)) {
    const v = byDate.get(d)
    out.push({ date: d, mm: v && v.has_data ? v.value : null })
  }
  return out
})

const maxMm = computed(() => Math.max(5, ...days.value.map((d) => d.mm ?? 0)))
const slot = computed(() => WIDTH / Math.max(days.value.length, 1))

// Bar with rounded top corners, anchored to the baseline.
function barPath(i: number, mm: number): string {
  const w = slot.value - GAP
  const x = i * slot.value + GAP / 2
  const h = Math.max((mm / maxMm.value) * (HEIGHT - 4), mm > 0 ? 2 : 0)
  const r = Math.min(4, w / 2, h)
  const y = HEIGHT - h
  return `M${x},${HEIGHT} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${HEIGHT} Z`
}

const hovered = ref<number | null>(null)
const caption = computed(() => {
  const i = hovered.value ?? days.value.findIndex((d) => d.date === props.selectedDate)
  const day = days.value[i]
  return day ? `${formatShortDate(day.date)}: ${formatMm(day.mm)}` : ''
})
const total = computed(() => days.value.reduce((sum, d) => sum + (d.mm ?? 0), 0))
const wetDays = computed(() => days.value.filter((d) => (d.mm ?? 0) >= 0.1).length)
</script>

<template>
  <figure class="history">
    <figcaption>
      <span>{{ t.last30Days }}</span>
      <span class="caption" aria-live="polite">{{ caption }}</span>
    </figcaption>
    <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT + 1}`" role="img" :aria-label="`${t.last30Days}: ${t.total} ${formatMm(total)}`" @mouseleave="hovered = null">
      <line :x1="0" :x2="WIDTH" :y1="HEIGHT + 0.5" :y2="HEIGHT + 0.5" class="baseline" />
      <g v-for="(d, i) in days" :key="d.date">
        <path
          v-if="d.mm !== null && d.mm > 0"
          :d="barPath(i, d.mm)"
          :class="['bar', { selected: d.date === selectedDate }]"
          :fill="rainClass(d.mm).color"
        />
        <circle v-else-if="d.mm === null" :cx="i * slot + slot / 2" :cy="HEIGHT - 3" r="2" class="missing" />
        <!-- Full-height hit target, larger than the bar itself. -->
        <rect
          :x="i * slot"
          y="0"
          :width="slot"
          :height="HEIGHT"
          class="hit"
          @mouseenter="hovered = i"
          @click="emit('pick', d.date)"
        >
          <title>{{ formatShortDate(d.date) }}: {{ formatMm(d.mm) }}</title>
        </rect>
      </g>
    </svg>
    <div class="axis">
      <span>{{ formatShortDate(start) }}</span>
      <span>{{ formatShortDate(end) }}</span>
    </div>
    <dl class="stats">
      <div><dt>{{ t.total }}</dt><dd>{{ formatMm(total) }}</dd></div>
      <div><dt>{{ t.wetDays }}</dt><dd>{{ wetDays }} / {{ days.length }}</dd></div>
    </dl>
  </figure>
</template>

<style scoped>
.history {
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
/* Bars use the map's rainfall colours; the selected date gets a white outline. */
.bar.selected {
  stroke: #fff;
  stroke-width: 1.5;
}
.missing {
  fill: none;
  stroke: var(--text-muted);
  stroke-width: 1;
}
.hit {
  fill: transparent;
  cursor: pointer;
}
.hit:hover {
  fill: rgb(255 255 255 / 0.06);
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
</style>
