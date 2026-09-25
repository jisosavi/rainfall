<script setup lang="ts">
import { RAIN_CLASSES } from '../lib/rainScale'
import { t } from '../strings'
</script>

<template>
  <section class="legend panel" :aria-label="t.legendTitle">
    <h2>{{ t.legendTitle }}</h2>
    <ul>
      <li v-for="c in [...RAIN_CLASSES].reverse()" :key="c.label">
        <span class="swatch" :style="{ background: c.color }" />{{ c.label }}
      </li>
      <li><span class="swatch hollow" />{{ t.noData }}</li>
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
