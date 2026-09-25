<script setup lang="ts">
import { ref } from 'vue'
import type { Source } from '../api'
import { t } from '../strings'

// Ingestion runs (Railway cron `15 7,13 * * *`), shown in UTC and the viewer's local time.
const RUNS_UTC: Array<[number, number]> = [
  [7, 15],
  [13, 15],
]
const pad = (n: number) => String(n).padStart(2, '0')
const localTime = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })
function runTimes() {
  const today = new Date()
  const utc = RUNS_UTC.map(([h, m]) => `${pad(h)}:${pad(m)}`)
  const local = RUNS_UTC.map(([h, m]) =>
    localTime.format(new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate(), h, m))),
  )
  return { utc: utc.join(' and '), local: local.join(' and ') }
}
const runs = runTimes()

// Stations per source on the date shown on the map.
defineProps<{ stationCounts: Partial<Record<Source, number>> }>()

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

      <section aria-labelledby="about-data">
        <h3 id="about-data">{{ t.aboutDataHeading }}</h3>
        <p>{{ t.aboutDataIntro }}</p>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th scope="col">{{ t.aboutDataColumns.country }}</th>
                <th scope="col">{{ t.aboutDataColumns.provider }}</th>
                <th scope="col" class="num">{{ t.aboutDataColumns.stations }}</th>
                <th scope="col">{{ t.aboutDataColumns.licence }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in t.dataSources" :key="d.source">
                <td>{{ d.country }}</td>
                <td><a :href="d.url" target="_blank" rel="noopener">{{ d.provider }}</a></td>
                <td class="num">{{ stationCounts[d.source] ?? '–' }}</td>
                <td><a :href="d.licenceUrl" target="_blank" rel="noopener">{{ d.licence }}</a></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="note">{{ t.aboutStationsNote }} {{ t.aboutProcessingNote }}</p>
      </section>

      <section aria-labelledby="about-updates">
        <h3 id="about-updates">{{ t.aboutUpdatesHeading }}</h3>
        <p>{{ t.aboutUpdatesIntro(runs.utc, runs.local) }}</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">{{ t.aboutUpdatesColumns.country }}</th>
                <th scope="col">{{ t.aboutUpdatesColumns.newValues }}</th>
                <th scope="col">{{ t.aboutUpdatesColumns.corrections }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in t.dataSources" :key="d.source">
                <td>{{ d.country }}</td>
                <td>{{ d.newValues }}</td>
                <td>{{ d.corrections }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="about-project">
        <h3 id="about-project">{{ t.aboutProjectHeading }}</h3>
        <p>
          {{ t.aboutDeveloperPrefix }}
          <a :href="t.developerUrl" target="_blank" rel="noopener">{{ t.developerName }}</a>.
          <a :href="t.sourceUrl" target="_blank" rel="noopener">{{ t.aboutSourceLink }}</a>
        </p>
        <p>
          {{ t.aboutCodeLicencePrefix }}
          <a :href="t.codeLicenceUrl" target="_blank" rel="noopener">{{ t.aboutCodeLicenceLink }}</a
          >{{ t.aboutCodeLicenceSuffix }}
        </p>
        <p>
          {{ t.aboutFeedbackPrefix }}
          <a :href="t.feedbackUrl" target="_blank" rel="noopener">{{ t.aboutFeedbackLink }}</a>
        </p>
      </section>
    </div>
  </dialog>
</template>

<style scoped>
.about {
  width: min(600px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  padding: 0;
  color: var(--text-primary);
  overflow-y: auto;
}
.about::backdrop {
  background: rgb(0 0 0 / 0.55);
}
.content {
  padding: 20px 24px 8px;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
h2 {
  margin: 0;
  font-size: 19px;
}
h3 {
  margin: 20px 0 4px;
  padding-top: 14px;
  border-top: 1px solid var(--border-subtle);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-secondary);
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
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th {
  text-align: left;
  font-weight: 500;
  color: var(--text-muted);
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
td {
  padding: 8px;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: top;
  line-height: 1.4;
}
th:first-child,
td:first-child {
  padding-left: 0;
}
.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.data-table td:last-child {
  white-space: nowrap;
}
@media (max-width: 520px) {
  .content {
    padding: 16px 16px 4px;
  }
  td,
  th {
    padding: 6px 5px;
  }
  .data-table td:last-child {
    white-space: normal;
  }
}
.note {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 10px;
}
a {
  color: var(--link);
}
</style>
