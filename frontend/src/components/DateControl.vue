<script setup lang="ts">
import { computed } from 'vue'
import { t } from '../strings'

// `dates` are the available dates, newest first. `current` is the date shown.
const props = defineProps<{ dates: string[]; current: string | null }>()
const emit = defineEmits<{ change: [date: string | null] }>()

const index = computed(() => (props.current ? props.dates.indexOf(props.current) : -1))
const older = computed(() => {
  if (!props.current) return null
  if (index.value >= 0) return props.dates[index.value + 1] ?? null
  return props.dates.find((d) => d < props.current!) ?? null
})
const newer = computed(() => {
  if (!props.current) return null
  if (index.value >= 0) return index.value > 0 ? props.dates[index.value - 1] : null
  return [...props.dates].reverse().find((d) => d > props.current!) ?? null
})
const isLatest = computed(() => props.current !== null && props.current === props.dates[0])

// The picker allows up to today so its built-in "Today" button works; a date newer than the
// latest data (usually today, before its values exist) shows the latest date instead.
const today = new Date().toISOString().slice(0, 10)

function onInput(event: Event) {
  const value = (event.target as HTMLInputElement).value
  if (!value) return
  emit('change', props.dates[0] && value > props.dates[0] ? null : value)
}
</script>

<template>
  <div class="date-control">
    <button type="button" class="icon" :disabled="!older" :aria-label="t.previousDay" :title="t.previousDay" @click="emit('change', older)">‹</button>
    <label>
      <span class="visually-hidden">{{ t.chooseDate }}</span>
      <input
        type="date"
        :value="current ?? ''"
        :min="dates[dates.length - 1]"
        :max="today"
        @change="onInput"
      />
    </label>
    <button type="button" class="icon" :disabled="!newer" :aria-label="t.nextDay" :title="t.nextDay" @click="emit('change', newer)">›</button>
    <button type="button" :disabled="isLatest" @click="emit('change', null)">{{ t.latest }}</button>
  </div>
</template>

<style scoped>
.date-control {
  display: flex;
  align-items: center;
  gap: 6px;
}
input[type='date'] {
  font: inherit;
  color: var(--text-primary);
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 8px;
  color-scheme: dark;
}
.icon {
  width: 32px;
  font-size: 18px;
  line-height: 1;
}
</style>
