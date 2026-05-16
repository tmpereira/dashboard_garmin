<template>
  <div>
    <h3 class="chart-title">Duração e Qualidade do Sono (horas)</h3>
    <Bar :data="chartData" :options="chartOptions" style="max-height:320px" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const props = defineProps({ sleep: { type: Array, default: () => [] } })

const chartData = computed(() => {
  const sorted = [...props.sleep]
    .filter(s => s.date)
    .sort((a, b) => a.date.localeCompare(b.date))

  const labels = sorted.map(s => {
    const d = new Date(s.date + 'T12:00:00')
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  })
  return {
    labels,
    datasets: [
      { label: 'Profundo', data: sorted.map(s => s.deep_h  || 0), backgroundColor: '#1e40af', borderRadius: 4 },
      { label: 'Leve',     data: sorted.map(s => s.light_h || 0), backgroundColor: '#3b82f6', borderRadius: 4 },
      { label: 'REM',      data: sorted.map(s => s.rem_h   || 0), backgroundColor: '#8b5cf6', borderRadius: 4 },
      { label: 'Acordado', data: sorted.map(s => s.awake_h || 0), backgroundColor: '#f97316', borderRadius: 4 },
    ]
  }
})

const chartOptions = {
  responsive: true,
  plugins: {
    legend: { labels: { color: '#94a3b8' } },
    tooltip: { callbacks: {
      label: ctx => `${ctx.dataset.label}: ${ctx.raw}h`
    }}
  },
  scales: {
    x: { stacked: true, ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
    y: { stacked: true, ticks: { color: '#64748b', callback: v => v + 'h' }, grid: { color: '#1e2235' } },
  }
}
</script>

<style scoped>
.chart-title { font-size: 0.9rem; color: #94a3b8; margin-bottom: 1rem; }
</style>
