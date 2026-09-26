<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Parameter } from '../api'
import { SCALES } from '../lib/scales'
import { store, stored, useMobile } from '../lib/useMobile'
import { suspectLegend, t } from '../strings'

const props = defineProps<{ parameter: Parameter }>()

// Always open on desktop. On phones a button, closed by default; the choice is remembered.
const KEY = 'legendOpen.mobile'
const mobile = useMobile()
const openOnMobile = ref(stored(KEY, false))
const open = computed(() => !mobile.value || openOnMobile.value)
function toggle(value: boolean) {
  openOnMobile.value = value
  store(KEY, value)
}
const classes = computed(() => SCALES[props.parameter].classes)
</script>

<template>
  <section v-if="open" class="legend panel" :aria-label="t.legendTitle[parameter]">
    <header>
      <h2>{{ t.legendTitle[parameter] }}</h2>
      <button v-if="mobile" type="button" class="icon close" :aria-label="t.legendClose" :title="t.legendClose" @click="toggle(false)">×</button>
    </header>
    <ul :class="{ long: classes.length > 6 }">
      <li v-for="c in [...classes].reverse()" :key="c.label">
        <span class="swatch" :style="{ background: c.color }" />{{ c.label }}
      </li>
      <li><span class="swatch hollow" />{{ t.noData }}</li>
      <li><span class="swatch suspect" />⚠ {{ suspectLegend(parameter) }}</li>
    </ul>
  </section>
  <button v-else type="button" class="legend-button panel" :aria-expanded="false" @click="toggle(true)">
    {{ t.legendButton }}
    <span class="strip" aria-hidden="true"><span v-for="c in classes" :key="c.label" :style="{ background: c.color }" /></span>
  </button>
</template>

<style scoped>
.legend {
  padding: 10px 12px;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin: 0 0 6px;
}
h2 {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.close {
  margin: -4px -6px 0 0;
  width: 24px;
  height: 24px;
  padding: 0;
  font-size: 16px;
  line-height: 1;
  border: none;
  background: transparent;
  color: var(--text-secondary);
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
  font-size: 12px;
}
/* Ten temperature classes: two columns, read top to bottom, so the legend stays short. */
ul.long {
  grid-auto-flow: column;
  grid-template-rows: repeat(6, auto);
  column-gap: 14px;
}
li {
  display: flex;
  align-items: center;
  gap: 8px;
}
.swatch {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: none;
}
.swatch.hollow {
  border: 2px solid #fff;
}
.swatch.suspect {
  border: 2px solid #fab219;
}
.legend-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
}
.strip {
  display: inline-flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
}
.strip span {
  width: 7px;
}
@media (max-width: 760px) {
  .legend {
    padding: 8px 10px;
  }
  ul {
    gap: 2px;
    font-size: 11px;
  }
  .swatch {
    width: 10px;
    height: 10px;
  }
}
</style>
