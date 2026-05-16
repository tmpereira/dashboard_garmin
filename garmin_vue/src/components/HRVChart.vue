<template>
  <div>
    <h3 class="chart-title">HRV Noturno — Média da Noite (ms)</h3>
    <Line :data="chartData" :options="chartOptions" style="max-height:260px" />
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

const props = defineProps({ hrv: { type: Array, default: () => [] } })

const chartData = computed(() => {
  const sorted = [...props.hrv]
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
        label: 'HRV Médio (noite)',
        data: sorted.map(h => h.last_night_avg),
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139,92,246,0.15)',
        tension: 0.4, pointRadius: 3, fill: true,
      },
      {
        label: 'HRV Semanal',
        data: sorted.map(h => h.weekly_avg),
        borderColor: '#64748b',
        backgroundColor: 'transparent',
        tension: 0.3, pointRadius: 0, borderDash: [5, 4],
      },
    ]
  }
})

const chartOptions = {
  responsive: true,
  plugins: {
    legend: { labels: { color: '#94a3b8' } },
    tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw} ms` } }
  },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
    y: { ticks: { color: '#64748b', callback: v => v + ' ms' }, grid: { color: '#1e2235' } },
  }
}
</script>

<style scoped>
.chart-title { font-size: 0.9rem; color: #94a3b8; margin-bottom: 1rem; }
</style>
