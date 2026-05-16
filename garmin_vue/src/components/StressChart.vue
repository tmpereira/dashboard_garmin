<template>
  <div>
    <h3 class="chart-title">Nível de Estresse Diário & Body Battery</h3>
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

const props = defineProps({
  stressDaily: { type: Array, default: () => [] },
})

const chartData = computed(() => {
  const sorted = [...(props.stressDaily || [])]
    .filter(s => s.date)
    .sort((a, b) => a.date.localeCompare(b.date))

  const labels = sorted.map(s => {
    const dt = new Date(s.date + 'T12:00:00')
    return dt.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  })

  return {
    labels,
    datasets: [
      {
        label: 'Estresse',
        data: sorted.map(s => s.avg_stress ?? null),
        borderColor: '#f97316',
        backgroundColor: 'rgba(249,115,22,0.1)',
        tension: 0.3, pointRadius: 3, fill: true, yAxisID: 'y',
      },
      {
        label: 'Body Battery (máx)',
        data: sorted.map(s => s.body_battery_max ?? null),
        borderColor: '#eab308',
        backgroundColor: 'transparent',
        tension: 0.3, pointRadius: 3, yAxisID: 'y2',
      },
    ]
  }
})

const chartOptions = {
  responsive: true,
  interaction: { mode: 'index', intersect: false },
  plugins: { legend: { labels: { color: '#94a3b8' } } },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
    y: {
      position: 'left', title: { display: true, text: 'Estresse', color: '#f97316' },
      ticks: { color: '#64748b' }, grid: { color: '#1e2235' }, min: 0, max: 100,
    },
    y2: {
      position: 'right', title: { display: true, text: 'Body Battery', color: '#eab308' },
      ticks: { color: '#64748b' }, grid: { drawOnChartArea: false }, min: 0, max: 100,
    },
  }
}
</script>

<style scoped>
.chart-title { font-size: 0.9rem; color: #94a3b8; margin-bottom: 1rem; }
</style>
