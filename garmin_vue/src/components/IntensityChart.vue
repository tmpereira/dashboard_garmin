<template>
  <div>
    <h3 class="chart-title">Minutos de Intensidade Semanal (meta: 150 min)</h3>
    <Bar :data="chartData" :options="chartOptions" style="max-height:320px" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const props = defineProps({ weekly: { type: Array, default: () => [] } })

const chartData = computed(() => {
  const items = [...(props.weekly || [])]
    .filter(w => w.calendarDate)
    .sort((a, b) => a.calendarDate.localeCompare(b.calendarDate))

  const labels = items.map(w => {
    const d = new Date(w.calendarDate + 'T12:00:00')
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  })
  return {
    labels,
    datasets: [
      {
        label: 'Moderado',
        data: items.map(w => w.moderate_min ?? 0),
        backgroundColor: '#3b82f6', borderRadius: 4,
      },
      {
        label: 'Vigoroso',
        data: items.map(w => w.vigorous_min ?? 0),
        backgroundColor: '#ef4444', borderRadius: 4,
      },
    ]
  }
})

const chartOptions = {
  responsive: true,
  plugins: {
    legend: { labels: { color: '#94a3b8' } },
    tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.raw} min` } },
    annotation: {},
  },
  scales: {
    x: { stacked: true, ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
    y: {
      stacked: true,
      ticks: { color: '#64748b', callback: v => v + ' min' },
      grid: { color: '#1e2235' },
    },
  }
}
</script>

<style scoped>
.chart-title { font-size: 0.9rem; color: #94a3b8; margin-bottom: 1rem; }
</style>
