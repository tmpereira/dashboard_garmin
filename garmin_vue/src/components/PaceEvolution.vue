<template>
  <div>
    <div v-if="!hasData" class="empty-state">
      <span>📈</span>
      <p>Sem corridas disponíveis para exibir a evolução de ritmo.</p>
    </div>

    <div v-else>
      <div class="header-row">
        <h3 class="chart-title">Evolução do Ritmo de Corrida</h3>
        <div class="controls">
          <label class="ctrl-label">MA:</label>
          <select v-model.number="maWindow" class="ctrl-select">
            <option :value="3">3 corridas</option>
            <option :value="5">5 corridas</option>
            <option :value="7">7 corridas</option>
          </select>
        </div>
      </div>

      <Line :data="chartData" :options="chartOptions" style="max-height:420px" />

      <div class="stats-row">
        <div class="stat-item">
          <span class="stat-label">Melhor ritmo</span>
          <span class="stat-value" style="color:#10b981">{{ fmtPace(bestPace) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Ritmo médio</span>
          <span class="stat-value" style="color:#3b82f6">{{ fmtPace(meanPace) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Corridas analisadas</span>
          <span class="stat-value">{{ runs.length }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Tendência</span>
          <span class="stat-value" :style="{ color: trendImproving ? '#10b981' : '#f97316' }">
            {{ trendImproving ? '↑ melhorando' : '↓ piorando' }}
          </span>
        </div>
      </div>

      <!-- Zone bands legend -->
      <div v-if="zoneBands.length" class="zone-note">
        <span class="zone-note-label">Faixas de zona:</span>
        <div v-for="z in zoneBands" :key="z.name" class="zone-chip" :style="{ background: z.color + '33', borderColor: z.color }">
          {{ z.name }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Tooltip, Legend, Filler
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler)

const props = defineProps({
  activities: { type: Array, default: () => [] },
  zones: { type: Array, default: () => [] },
})

const maWindow = ref(5)

const runs = computed(() => {
  return (props.activities || [])
    .filter(a => (a.type || '').toLowerCase().includes('run') && a.avg_speed_ms > 0)
    .map(a => ({
      date:   a.date,
      pace:   1000 / a.avg_speed_ms,
      distKm: (a.distance_m || 0) / 1000,
      hr:     a.avg_hr || null,
      name:   a.name || 'Corrida',
    }))
    .sort((a, b) => a.date.localeCompare(b.date))
})

const hasData = computed(() => runs.value.length >= 2)

// Moving average
function movingAvg(arr, window) {
  return arr.map((_, i) => {
    const start = Math.max(0, i - window + 1)
    const chunk = arr.slice(start, i + 1)
    return chunk.reduce((s, v) => s + v, 0) / chunk.length
  })
}

const paces = computed(() => runs.value.map(r => r.pace))
const maValues = computed(() => movingAvg(paces.value, maWindow.value))

const bestPace = computed(() => Math.min(...paces.value))
const meanPace = computed(() => paces.value.reduce((a, b) => a + b, 0) / paces.value.length)
const trendImproving = computed(() => {
  if (maValues.value.length < 4) return false
  const n = maValues.value.length
  return maValues.value[n - 1] < maValues.value[Math.max(0, n - 4)]
})

function fmtDate(str) {
  const d = new Date(str + 'T12:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

function fmtPace(sec) {
  if (!sec) return '—'
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}/km`
}

const chartData = computed(() => ({
  labels: runs.value.map(r => fmtDate(r.date)),
  datasets: [
    {
      label: 'Ritmo por corrida',
      data: paces.value.map(v => +v.toFixed(2)),
      borderColor: 'rgba(148,163,184,0.5)',
      backgroundColor: 'transparent',
      pointRadius: 4,
      pointBackgroundColor: '#94a3b8',
      borderWidth: 1.5,
      tension: 0.2,
      fill: false,
    },
    {
      label: `Média móvel (${maWindow.value})`,
      data: maValues.value.map(v => +v.toFixed(2)),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.08)',
      pointRadius: 0,
      borderWidth: 3,
      tension: 0.35,
      fill: false,
    },
  ]
}))

const chartOptions = computed(() => ({
  responsive: true,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { labels: { color: '#94a3b8' } },
    tooltip: {
      callbacks: {
        label: ctx => {
          const v = ctx.raw
          const m = Math.floor(v / 60)
          const s = Math.round(v % 60)
          return `${ctx.dataset.label}: ${m}:${String(s).padStart(2, '0')}/km`
        }
      }
    }
  },
  scales: {
    x: { ticks: { color: '#64748b', maxTicksLimit: 15 }, grid: { color: '#1e2235' } },
    y: {
      reverse: true,
      ticks: {
        color: '#64748b',
        callback: v => { const m = Math.floor(v/60); const s = Math.round(v%60); return `${m}:${String(s).padStart(2,'0')}` }
      },
      grid: { color: '#1e2235' },
      title: { display: true, text: 'Ritmo (min/km)', color: '#94a3b8' },
    }
  }
}))

// Zone bands for legend only (annotation plugin not used to avoid extra dep)
const zoneBands = computed(() => props.zones?.slice(0, 5) || [])
</script>

<style scoped>
.header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
.chart-title { font-size: 0.95rem; font-weight: 600; color: #e2e8f0; margin: 0; }
.controls { display: flex; align-items: center; gap: 0.5rem; }
.ctrl-label { font-size: 0.8rem; color: #94a3b8; }
.ctrl-select { background: #1e2235; border: 1px solid #2d3748; color: #e2e8f0; border-radius: 6px; padding: 0.3rem 0.5rem; font-size: 0.82rem; cursor: pointer; }

.stats-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1.25rem; }
.stat-item { background: #1e2235; border: 1px solid #2d3748; border-radius: 8px; padding: 0.6rem 1rem; }
.stat-label { display: block; font-size: 0.72rem; color: #64748b; text-transform: uppercase; }
.stat-value { display: block; font-size: 1.2rem; font-weight: 600; color: #e2e8f0; }

.zone-note { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-top: 1rem; }
.zone-note-label { font-size: 0.78rem; color: #64748b; }
.zone-chip { font-size: 0.72rem; padding: 2px 8px; border: 1px solid; border-radius: 12px; }

.empty-state { text-align: center; padding: 3rem; color: #64748b; }
.empty-state span { font-size: 3rem; }
.empty-state p { margin-top: 0.5rem; }
</style>
