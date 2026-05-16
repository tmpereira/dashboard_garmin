<template>
  <div>
    <h3 class="chart-title">FC Mínima, Média em Repouso e Máxima (bpm)</h3>
    <Line :data="chartData" :options="chartOptions" style="max-height:300px" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Tooltip, Legend, Filler
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler)

const props = defineProps({ heartRates: { type: Array, default: () => [] } })

const chartData = computed(() => {
  const sorted = [...props.heartRates]
    .filter(h => h.date)
    .sort((a, b) => a.date.localeCompare(b.date))

  const labels = sorted.map(h => {
    const d = new Date(h.date + 'T12:00:00')
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  })
  return {
    labels,
    datasets: [
      {
        label: 'FC Máxima',
        data: sorted.map(h => h.max),
        borderColor: '#ef4444', backgroundColor: 'transparent',
        tension: 0.3, pointRadius: 3,
      },
      {
        label: 'FC Repouso',
        data: sorted.map(h => h.resting),
        borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)',
        tension: 0.3, pointRadius: 3, fill: true,
      },
      {
        label: 'FC Mínima',
        data: sorted.map(h => h.min),
        borderColor: '#10b981', backgroundColor: 'transparent',
        tension: 0.3, pointRadius: 3,
      },
    ]
  }
})

const chartOptions = {
  responsive: true,
  plugins: {
    legend: { labels: { color: '#94a3b8' } },
    tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw} bpm` } }
  },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
    y: { ticks: { color: '#64748b', callback: v => v + ' bpm' }, grid: { color: '#1e2235' } },
  }
}
</script>

<style scoped>
.chart-title { font-size: 0.9rem; color: #94a3b8; margin-bottom: 1rem; }
</style>
