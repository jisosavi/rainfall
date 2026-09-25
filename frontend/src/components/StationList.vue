<script setup lang="ts">
import { computed } from 'vue'
import type { StationDay } from '../api'
import { rainClass } from '../lib/rainScale'
import { formatMm, t } from '../strings'

const props = defineProps<{ stations: StationDay[]; selectedId: string | null }>()
const emit = defineEmits<{ select: [id: string] }>()

// Table view of the map: wettest first, stations without data last.
const sorted = computed(() =>
  [...props.stations].sort(
    (a, b) => (b.precipitation_mm ?? -1) - (a.precipitation_mm ?? -1) || a.name.localeCompare(b.name, 'fi'),
  ),
)
</script>

<template>
  <section class="station-list panel" :aria-label="t.listHeading">
    <h2>{{ t.listHeading }}</h2>
    <div class="scroll">
      <table>
        <thead>
          <tr><th scope="col">{{ t.station }}</th><th scope="col" class="num">{{ t.rainfall }}</th></tr>
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
                :style="s.has_data && s.precipitation_mm !== null ? { background: rainClass(s.precipitation_mm).color } : {}"
              />{{ s.name }}
            </td>
            <td class="num">{{ s.has_data ? formatMm(s.precipitation_mm) : t.noData }}</td>
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
