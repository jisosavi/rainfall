<script setup lang="ts">
import type { CountryFilter } from '../stores/selection'
import { t } from '../strings'

defineProps<{ modelValue: CountryFilter }>()
const emit = defineEmits<{ 'update:modelValue': [value: CountryFilter] }>()

const options: Array<{ value: CountryFilter; label: string }> = [
  { value: 'all', label: t.countryAll },
  { value: 'fi', label: t.countryFinland },
  { value: 'no', label: t.countryNorway },
  { value: 'se', label: t.countrySweden },
]
</script>

<template>
  <div class="country-filter" role="radiogroup" :aria-label="t.countryFilter">
    <button
      v-for="o in options"
      :key="o.value"
      type="button"
      role="radio"
      class="small"
      :aria-checked="modelValue === o.value"
      :class="{ active: modelValue === o.value }"
      @click="emit('update:modelValue', o.value)"
    >
      {{ o.label }}
    </button>
  </div>
</template>

<style scoped>
.country-filter {
  display: inline-flex;
}
button {
  border-radius: 0;
  margin-left: -1px;
}
button:first-child {
  border-radius: 6px 0 0 6px;
  margin-left: 0;
}
button:last-child {
  border-radius: 0 6px 6px 0;
}
button.active {
  background: #3a3a40;
  border-color: #6a6a72;
  position: relative;
}
</style>
