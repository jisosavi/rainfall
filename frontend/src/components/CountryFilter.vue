<script setup lang="ts">
import type { CountryFilter } from '../stores/selection'
import { t } from '../strings'
import SegmentedControl from './SegmentedControl.vue'

const model = defineModel<CountryFilter>({ required: true })

const options: Array<{ value: CountryFilter; label: string }> = [
  { value: 'all', label: t.countryAll },
  { value: 'fi', label: t.countryFinland },
  { value: 'no', label: t.countryNorway },
  { value: 'se', label: t.countrySweden },
]
</script>

<template>
  <SegmentedControl v-model="model" :options="options" :label="t.countryFilter" />
</template>
