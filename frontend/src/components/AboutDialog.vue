<script setup lang="ts">
import { ref } from 'vue'
import { t } from '../strings'

const dialog = ref<HTMLDialogElement>()
defineExpose({ open: () => dialog.value?.showModal() })

// Close when clicking the backdrop (outside the dialog box).
function onClick(event: MouseEvent) {
  if (event.target === dialog.value) dialog.value?.close()
}
</script>

<template>
  <dialog ref="dialog" class="about panel" aria-labelledby="about-title" @click="onClick">
    <div class="content">
      <header>
        <h2 id="about-title">{{ t.aboutTitle }}</h2>
        <button type="button" class="icon" :aria-label="t.close" :title="t.close" @click="dialog?.close()">×</button>
      </header>
      <p>{{ t.aboutBody }}</p>
      <p>
        {{ t.aboutDataPrefix }}
        <a :href="t.fmiOpenDataUrl" target="_blank" rel="noopener">{{ t.aboutDataLink }}</a>{{ t.aboutDataAnd }}
        <a :href="t.metOpenDataUrl" target="_blank" rel="noopener">{{ t.aboutMetLink }}</a>
        {{ t.aboutDataAnd2 }}
        <a :href="t.smhiOpenDataUrl" target="_blank" rel="noopener">{{ t.aboutSmhiLink }}</a>
        {{ t.aboutDataSuffix }}
      </p>
      <p>
        {{ t.aboutDeveloperPrefix }}
        <a :href="t.developerUrl" target="_blank" rel="noopener">{{ t.developerName }}</a>.
        <a :href="t.sourceUrl" target="_blank" rel="noopener">{{ t.aboutSourceLink }}</a>
      </p>
      <p>
        {{ t.aboutFeedbackPrefix }}
        <a :href="t.feedbackUrl" target="_blank" rel="noopener">{{ t.aboutFeedbackLink }}</a>
      </p>
    </div>
  </dialog>
</template>

<style scoped>
.about {
  max-width: min(440px, calc(100vw - 32px));
  padding: 0;
  color: var(--text-primary);
}
.about::backdrop {
  background: rgb(0 0 0 / 0.55);
}
.content {
  padding: 18px 20px 6px;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
h2 {
  margin: 0;
  font-size: 18px;
}
.icon {
  width: 32px;
  font-size: 20px;
  line-height: 1;
}
p {
  line-height: 1.5;
  font-size: 14px;
}
a {
  color: var(--link);
}
</style>
