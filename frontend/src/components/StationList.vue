<script setup lang="ts">
import { computed } from 'vue'
import type { Parameter, StationDay } from '../api'
import { SCALES } from '../lib/scales'
import { formatValue, t } from '../strings'

const props = defineProps<{ stations: StationDay[]; selectedId: string | null; parameter: Parameter }>()
const emit = defineEmits<{ select: [id: string] }>()

// Table view of the map: wettest first, stations without data last.
const sorted = computed(() =>
  [...props.stations].sort(
    (a, b) => (b.value ?? -1) - (a.value ?? -1) || a.name.localeCompare(b.name, 'fi'),
  ),
)
</script>

<template>
  <section class="station-list panel" :aria-label="t.listHeading[parameter]">
    <h2>{{ t.listHeading[parameter] }}</h2>
    <div class="scroll">
      <table>
        <thead>
          <tr><th scope="col">{{ t.station }}</th><th scope="col" class="num">{{ t.parameterLabel[parameter] }}</th></tr>
        </thead>
        <tbody>
          <tr
            v-for="s in sorted"
            :key="s.id"
            :class="{ selected: s.id === selectedId }"
            tabindex="0"
            @click="emit('select', s.id)"
            @keydown.enter="emit('select', s.id)"
          >
            <td>
              <span
                class="swatch"
                :class="{ hollow: !s.has_data }"
                :style="s.has_data && s.value !== null ? { background: SCALES[parameter].classOf(s.value).color } : {}"
              /><span class="name">{{ s.name }}</span><span class="tag">{{ t.countryTag[s.source] }}</span>
            </td>
            <td class="num">
              <span v-if="s.flag" class="suspect" :title="t.suspectLong" :aria-label="t.suspectShort">⚠ </span>{{ formatValue(parameter, s.has_data ? s.value : null) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.station-list {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
h2 {
  margin: 0;
  padding: 12px 14px 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.scroll {
  overflow-y: auto;
  min-height: 0;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th {
  position: sticky;
  top: 0;
  background: var(--surface);
  text-align: left;
  font-weight: 500;
  color: var(--text-muted);
  padding: 4px 14px;
}
td {
  padding: 5px 14px;
  border-top: 1px solid var(--border-subtle);
}
td:first-child {
  display: flex;
  align-items: center;
  gap: 8px;
}
.num {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
tbody tr {
  cursor: pointer;
}
tbody tr:hover,
tbody tr:focus-visible {
  background: var(--surface-raised);
  outline: none;
}
tr.selected {
  background: var(--surface-raised);
}
.name {
  flex: 1;
}
.tag {
  font-size: 10px;
  color: var(--text-muted);
}
.suspect {
  color: #fab219;
}
.swatch {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex: none;
}
.swatch.hollow {
  border: 1.5px solid #fff;
}
</style>
