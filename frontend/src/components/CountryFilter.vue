<script setup lang="ts">
import { COUNTRIES, type CountryFilter } from '../lib/countries'
import { t } from '../strings'

// A drop-down: with Denmark, Greenland and the Faroe Islands there are too many for buttons.
const model = defineModel<CountryFilter>({ required: true })
</script>

<template>
  <label class="country-filter">
    <span class="visually-hidden">{{ t.countryFilter }}</span>
    <select v-model="model">
      <option value="all">{{ t.countryAll }}</option>
      <option v-for="c in COUNTRIES" :key="c.key" :value="c.key">{{ c.label }}</option>
    </select>
  </label>
</template>

<style scoped>
select {
  font: inherit;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px;
  color-scheme: dark;
  cursor: pointer;
}
</style>
