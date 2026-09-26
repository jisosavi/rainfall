<script setup lang="ts">
import { computed } from 'vue'
import type { Parameter, Period, RankedStation, Rankings } from '../api'
import { countryTag } from '../lib/countries'
import { formatShortDate, formatValue, t } from '../strings'
import SegmentedControl from './SegmentedControl.vue'

const props = defineProps<{
  parameter: Parameter
  rankings: Rankings | undefined
  loading: boolean
  selectedId: string | null
}>()
const period = defineModel<Period>('period', { required: true })
const allStations = defineModel<boolean>('allStations', { required: true })
const emit = defineEmits<{ select: [id: string] }>()

const periodOptions = computed(() =>
  (props.parameter === 'precipitation'
    ? (['week', 'month', 'year', 'last30'] as const)
    : (['now', 'winter_max', 'winter_days'] as const)
  ).map((value) => ({ value: value as Period, label: t.periods[value] })),
)
const isDayCount = computed(() => props.rankings?.period === 'winter_days')
const max = computed(() => Math.max(1, ...(props.rankings?.stations.map((s) => s.value) ?? [1])))
const usesCoverage = computed(() => (props.rankings?.min_coverage ?? 0) > 0 || allStations.value)

function display(s: RankedStation): string {
  return isDayCount.value ? `${s.value} ${t.snowDaysUnit}` : formatValue(props.parameter, s.value)
}
</script>

<template>
  <section class="rankings panel" :aria-label="t.topHeading[parameter]">
    <header>
      <h2>{{ t.topHeading[parameter] }}</h2>
      <SegmentedControl v-model="period" :options="periodOptions" :label="t.periodLabel" class="periods" />
      <p v-if="rankings" class="range">{{ t.periodRange(formatShortDate(rankings.start), formatShortDate(rankings.end)) }}</p>
      <label v-if="parameter === 'precipitation' || period === 'winter_days'" class="toggle" :title="t.allStationsHint">
        <input v-model="allStations" type="checkbox" /> {{ t.allStations }}
      </label>
    </header>
    <div class="scroll">
      <ol v-if="rankings && rankings.stations.length">
        <li
          v-for="s in rankings.stations"
          :key="s.id"
          :class="{ selected: s.id === selectedId }"
          tabindex="0"
          @click="emit('select', s.id)"
          @keydown.enter="emit('select', s.id)"
        >
          <span class="rank">{{ s.rank }}</span>
          <span class="who">
            <span class="name">{{ s.name }}</span>
            <span class="tag">{{ countryTag(s.country) }}</span>
            <span class="bar" :style="{ width: `${(s.value / max) * 100}%` }" :class="parameter" />
          </span>
          <span class="value">
            {{ display(s) }}
            <span v-if="usesCoverage" class="coverage">{{ t.coverage(s.days_with_data, s.days) }}</span>
          </span>
        </li>
      </ol>
      <p v-else-if="!loading" class="empty">{{ t.noRankings }}</p>
      <p class="note">{{ t.rankingNote }}</p>
    </div>
  </section>
</template>

<style scoped>
.rankings {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
header {
  padding: 12px 14px 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
h2 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.periods :deep(button) {
  font-size: 11px;
  padding: 3px 7px;
}
.range {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
}
.toggle {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.scroll {
  overflow-y: auto;
  min-height: 0;
}
ol {
  list-style: none;
  margin: 0;
  padding: 0;
}
li {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-top: 1px solid var(--border-subtle);
  font-size: 13px;
  cursor: pointer;
}
li:hover,
li:focus-visible,
li.selected {
  background: var(--surface-raised);
  outline: none;
}
.rank {
  font-weight: 600;
  color: var(--text-secondary);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.who {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 6px;
  min-width: 0;
}
.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag {
  font-size: 10px;
  color: var(--text-muted);
}
.bar {
  flex-basis: 100%;
  height: 3px;
  border-radius: 2px;
  background: #3f97e0;
  max-width: 100%;
}
.bar.snow_depth {
  background: #7fd3e0;
}
.value {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.coverage {
  display: block;
  font-size: 10px;
  color: var(--text-muted);
}
.empty,
.note {
  margin: 0;
  padding: 8px 14px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
