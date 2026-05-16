<template>
  <div>
    <h3 class="chart-title">Passos Diários</h3>
    <Bar :data="dailyChartData" :options="barOptions" style="max-height:280px" />
    <h3 class="chart-title" style="margin-top:2rem">Passos Semanais (total)</h3>
    <Bar :data="weeklyChartData" :options="weeklyOptions" style="max-height:240px" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const props = defineProps({
  dailySteps: { type: Array, default: () => [] },
  weeklySteps: { type: Array, default: () => [] },
})

const dailyChartData = computed(() => {
  const items = [...(props.dailySteps || [])]
    .filter(s => s.date)
    .sort((a, b) => a.date.localeCompare(b.date))

  return {
    labels: items.map(s => {
      const d = new Date(s.date + 'T12:00:00')
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
    }),
    datasets: [{
      label: 'Passos',
      data: items.map(s => s.steps ?? 0),
      backgroundColor: items.map(s => (s.steps ?? 0) >= 8000 ? '#10b981' : '#3b82f6'),
      borderRadius: 4,
    }]
  }
})

const weeklyChartData = computed(() => {
  const items = [...(props.weeklySteps || [])]
    .filter(s => s.date)
    .sort((a, b) => a.date.localeCompare(b.date))

  return {
    labels: items.map(s => {
      const d = new Date(s.date + 'T12:00:00')
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
    }),
    datasets: [{
      label: 'Total semanal',
      data: items.map(s => s.total_steps ?? 0),
      backgroundColor: '#6366f1',
      borderRadius: 4,
    }]
  }
})

const barOptions = {
  responsive: true,
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: ctx => `Passos: ${ctx.raw.toLocaleString('pt-BR')}` } }
  },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
    y: { ticks: { color: '#64748b', callback: v => v.toLocaleString('pt-BR') }, grid: { color: '#1e2235' } },
  }
}

const weeklyOptions = {
  ...barOptions,
  plugins: {
    ...barOptions.plugins,
    legend: { labels: { color: '#94a3b8' } },
    tooltip: { callbacks: { label: ctx => `Total: ${ctx.raw.toLocaleString('pt-BR')} passos` } }
  }
}
</script>

<style scoped>
.chart-title { font-size: 0.9rem; color: #94a3b8; margin-bottom: 1rem; }
</style>
