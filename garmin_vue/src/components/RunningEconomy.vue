<template>
  <div>
    <!-- Running Economy (EF) -->
    <div class="section-block">
      <h3 class="chart-title">Economia de Corrida — Fator de Eficiência (EF)</h3>
      <p class="chart-desc">EF = Velocidade (m/min) ÷ FC média. Valores maiores indicam melhor economia aeróbica.</p>

      <div v-if="efData.length">
        <Bar :data="efChartData" :options="efOptions" style="max-height:320px" />
        <div class="ef-summary">
          <div class="ef-stat">
            <span class="ef-label">Melhor EF</span>
            <span class="ef-value" style="color:#10b981">{{ bestEF.toFixed(3) }}</span>
          </div>
          <div class="ef-stat">
            <span class="ef-label">EF Médio</span>
            <span class="ef-value" style="color:#3b82f6">{{ avgEF.toFixed(3) }}</span>
          </div>
          <div class="ef-stat">
            <span class="ef-label">Tendência</span>
            <span class="ef-value" :style="{ color: efTrend >= 0 ? '#10b981' : '#ef4444' }">
              {{ efTrend >= 0 ? '↑' : '↓' }} {{ Math.abs(efTrend).toFixed(3) }}
            </span>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <span>🏃</span><p>Sem corridas com FC para calcular o EF.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  Tooltip, Legend
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const props = defineProps({
  efMonthly: { type: Array, default: () => [] },
})

// ─── Efficiency Factor ──────────────────────────────────────────────────────

const efData = computed(() => props.efMonthly || [])

const bestEF = computed(() => Math.max(...efData.value.map(d => d.ef), 0))
const avgEF = computed(() => {
  if (!efData.value.length) return 0
  return efData.value.reduce((s, d) => s + d.ef, 0) / efData.value.length
})
const efTrend = computed(() => {
  if (efData.value.length < 2) return 0
  return efData.value.at(-1).ef - efData.value[0].ef
})

function fmtMonth(str) {
  const [y, m] = str.split('-')
  const months = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
  return `${months[+m - 1]} ${y}`
}

const efChartData = computed(() => ({
  labels: efData.value.map(d => fmtMonth(d.month)),
  datasets: [{
    label: 'EF Médio',
    data: efData.value.map(d => +d.ef.toFixed(4)),
    backgroundColor: efData.value.map(d => d.ef >= bestEF.value * 0.97 ? '#10b981' : '#3b82f6'),
    borderRadius: 4,
  }]
}))

const efOptions = {
  responsive: true,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: ctx => [`EF: ${ctx.raw}`, `N: ${efData.value[ctx.dataIndex]?.count} corridas`]
      }
    }
  },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' }, title: { display: true, text: 'EF', color: '#94a3b8' } }
  }
}

</script>

<style scoped>
.section-block { }
.chart-title { font-size: 0.95rem; font-weight: 600; color: #e2e8f0; margin: 0 0 0.3rem; }
.chart-desc { font-size: 0.82rem; color: #64748b; margin-bottom: 1.25rem; }

.ef-summary { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-top: 1rem; }
.ef-stat { background: #1e2235; border: 1px solid #2d3748; border-radius: 8px; padding: 0.65rem 1rem; }
.ef-label { display: block; font-size: 0.72rem; color: #64748b; text-transform: uppercase; }
.ef-value { display: block; font-size: 1.5rem; font-weight: 700; }

.empty-state { text-align: center; padding: 2.5rem; color: #64748b; }
.empty-state span { font-size: 2.5rem; }
.empty-state p { margin-top: 0.5rem; }
.empty-state .hint { font-size: 0.8rem; color: #475569; }

.corr-note { margin-top: 0.75rem; font-size: 0.85rem; color: #94a3b8; }
</style>
