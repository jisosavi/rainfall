<script setup lang="ts">
import { computed } from 'vue'
import { isTemperature, type Order, type Parameter, type Period, type RankedStation, type Rankings } from '../api'
import { countryTag } from '../lib/countries'
import { SCALES } from '../lib/scales'
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
const order = defineModel<Order>('order', { required: true })
const emit = defineEmits<{ select: [id: string] }>()

const temperature = computed(() => isTemperature(props.parameter))
const periodOptions = computed(() => {
  if (temperature.value) {
    return (['now', 'week', 'month', 'year', 'last30'] as const).map((value) => ({ value: value as Period, label: t.tempPeriods[value] }))
  }
  return (props.parameter === 'precipitation'
    ? (['week', 'month', 'year', 'last30'] as const)
    : (['now', 'winter_max', 'winter_days'] as const)
  ).map((value) => ({ value: value as Period, label: t.periods[value] }))
})
const orderOptions: Array<{ value: Order; label: string }> = [
  { value: 'warmest', label: t.orders.warmest },
  { value: 'coldest', label: t.orders.coldest },
]
const heading = computed(() => {
  const p = props.parameter
  return isTemperature(p) ? t.topTempHeading[p][order.value] : t.topHeading[p]
})
const isDayCount = computed(() => props.rankings?.period === 'winter_days')
// Rainfall and snow get a bar from zero; temperatures, which can be negative, a colour dot.
const max = computed(() => Math.max(1, ...(props.rankings?.stations.map((s) => s.value) ?? [1])))
const usesCoverage = computed(() => (props.rankings?.min_coverage ?? 0) > 0 || allStations.value)
// The coverage toggle matters wherever a period needs data on most days.
const coverageApplies = computed(() =>
  props.parameter === 'precipitation' ||
  period.value === 'winter_days' ||
  (props.parameter === 'temp_mean' && period.value !== 'now'),
)

function display(s: RankedStation): string {
  return isDayCount.value ? `${s.value} ${t.snowDaysUnit}` : formatValue(props.parameter, s.value)
}
</script>

<template>
  <section class="rankings panel" :aria-label="heading">
    <header>
      <h2>{{ heading }}</h2>
      <SegmentedControl v-if="temperature" v-model="order" :options="orderOptions" :label="t.orderLabel" class="periods" />
      <SegmentedControl v-model="period" :options="periodOptions" :label="t.periodLabel" class="periods" />
      <p v-if="rankings" class="range">{{ t.periodRange(formatShortDate(rankings.start), formatShortDate(rankings.end)) }}</p>
      <label v-if="coverageApplies" class="toggle" :title="t.allStationsHint">
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
            <span v-if="!temperature" class="bar" :style="{ width: `${(s.value / max) * 100}%` }" :class="parameter" />
          </span>
          <span class="value">
            <span v-if="temperature" class="dot" :style="{ background: SCALES[parameter].classOf(s.value).color }" />{{ display(s) }}
            <span v-if="s.on_date && rankings.period !== 'now'" class="coverage">{{ t.onDate(formatShortDate(s.on_date)) }}</span>
            <span v-else-if="usesCoverage" class="coverage">{{ t.coverage(s.days_with_data, s.days) }}</span>
          </span>
        </li>
      </ol>
      <p v-else-if="!loading" class="empty">{{ t.noRankings[parameter] }}</p>
      <p class="note">{{ temperature ? t.tempRankingNote : t.rankingNote }}</p>
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
.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: 0;
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
