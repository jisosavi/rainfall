<script setup lang="ts" generic="T extends string">
defineProps<{ modelValue: T; options: Array<{ value: T; label: string }>; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<template>
  <div class="segmented" role="radiogroup" :aria-label="label">
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
.segmented {
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
