<script setup lang="ts">
import type { Parameter } from '../api'
import { SCALES } from '../lib/scales'
import { suspectLegend, t } from '../strings'

defineProps<{ parameter: Parameter }>()
</script>

<template>
  <section class="legend panel" :aria-label="t.legendTitle[parameter]">
    <h2>{{ t.legendTitle[parameter] }}</h2>
    <ul :class="{ long: SCALES[parameter].classes.length > 6 }">
      <li v-for="c in [...SCALES[parameter].classes].reverse()" :key="c.label">
        <span class="swatch" :style="{ background: c.color }" />{{ c.label }}
      </li>
      <li><span class="swatch hollow" />{{ t.noData }}</li>
      <li><span class="swatch suspect" />⚠ {{ suspectLegend(parameter) }}</li>
    </ul>
  </section>
</template>

<style scoped>
.legend {
  padding: 10px 12px;
}
h2 {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
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
  /* Ten temperature classes: two columns, read top to bottom, so the legend stays short. */
  ul.long {
    grid-auto-flow: column;
    grid-template-rows: repeat(6, auto);
    column-gap: 12px;
  }
}
</style>
