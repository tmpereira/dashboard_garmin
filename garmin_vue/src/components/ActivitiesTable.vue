<template>
  <div>
    <div v-if="!activities?.length" class="empty">Nenhuma atividade no período.</div>
    <div v-else>
      <p class="count">{{ activities.length }} atividade(s) encontrada(s)</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th>Nome</th>
              <th>Tipo</th>
              <th>Distância</th>
              <th>Duração</th>
              <th>FC Méd</th>
              <th>Calorias</th>
              <th>Elevação</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="act in sorted" :key="act.id">
              <td>{{ fmtDate(act.date) }}</td>
              <td class="name">{{ act.name || '—' }}</td>
              <td><span class="badge">{{ typeLabel(act.type) }}</span></td>
              <td>{{ fmtDist(act.distance_m) }}</td>
              <td>{{ fmtDur(act.duration_s) }}</td>
              <td>{{ act.avg_hr || '—' }}</td>
              <td>{{ act.calories ? fmt(act.calories) + ' kcal' : '—' }}</td>
              <td>{{ act.elevation_gain ? '+' + Math.round(act.elevation_gain) + ' m' : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ activities: { type: Array, default: () => [] } })

const sorted = computed(() =>
  [...(props.activities || [])].sort((a, b) => {
    const da = a.date || ''
    const db = b.date || ''
    return db.localeCompare(da)
  })
)

function fmtDate(val) {
  if (!val) return '—'
  return new Date(val + 'T12:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}
function fmtDist(m) {
  if (!m) return '—'
  return (m / 1000).toFixed(2) + ' km'
}
function fmtDur(secs) {
  if (!secs) return '—'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
    : `${m}:${String(s).padStart(2,'0')}`
}
function fmt(n) { return Number(n).toLocaleString('pt-BR') }
function typeLabel(t) {
  if (!t) return '—'
  const map = {
    running: '🏃 Corrida', cycling: '🚴 Ciclismo', walking: '🚶 Caminhada',
    swimming: '🏊 Natação', strength_training: '🏋️ Musculação',
    soccer: '⚽ Futebol', trail_running: '🏔️ Trail',
  }
  return map[t] || t
}
</script>

<style scoped>
.empty { color: #64748b; padding: 2rem; text-align: center; }
.count { font-size: 0.85rem; color: #64748b; margin-bottom: 1rem; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
thead tr { border-bottom: 2px solid #2d3748; }
th { text-align: left; padding: 0.6rem 0.75rem; color: #64748b; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
tbody tr { border-bottom: 1px solid #1e2235; transition: background 0.15s; }
tbody tr:hover { background: #1e2235; }
td { padding: 0.6rem 0.75rem; color: #e2e8f0; }
td.name { max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badge {
  background: #1e2235;
  border: 1px solid #3d4466;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 0.78rem;
  white-space: nowrap;
}
</style>
