<template>
  <div class="act-tab">

    <!-- ── Lista lateral ─────────────────────────────────── -->
    <div class="act-list" :class="{ collapsed: selected }">
      <div class="list-header">
        <input v-model="search" class="search-input" placeholder="🔍 Buscar atividade..." />
        <div class="filter-row">
          <button
            v-for="t in typeFilters" :key="t.key"
            :class="['type-btn', { active: typeFilter === t.key }]"
            @click="typeFilter = t.key"
          >{{ t.label }}</button>
        </div>
        <div class="list-count">{{ filtered.length }} atividade(s)</div>
      </div>

      <div class="list-items">
        <div
          v-for="act in filtered" :key="act.id"
          :class="['act-item', { active: selected?.id === act.id }]"
          @click="selectActivity(act)"
        >
          <span class="act-icon">{{ typeIcon(act) }}</span>
          <div class="act-item-body">
            <div class="act-item-name">{{ act.name }}</div>
            <div class="act-item-meta">
              {{ fmtDate(act.date) }} &nbsp;·&nbsp;
              {{ fmtDist(act.distance_m) }} &nbsp;·&nbsp;
              {{ fmtPace(act.avg_speed_ms) }}
            </div>
          </div>
          <div class="act-item-right">
            <span class="act-hr" v-if="act.avg_hr">{{ Math.round(act.avg_hr) }} bpm</span>
            <span class="act-dur">{{ fmtDuration(act.duration_s) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Painel de detalhes ─────────────────────────────── -->
    <div class="act-detail" v-if="selected">
      <button class="back-btn" @click="selected = null">← Voltar à lista</button>

      <!-- Cabeçalho -->
      <div class="detail-header">
        <div class="dh-left">
          <span class="dh-icon">{{ typeIcon(selected) }}</span>
          <div>
            <h2 class="dh-name">{{ selected.name }}</h2>
            <div class="dh-meta">
              {{ fmtDateFull(selected.date) }}
              <span v-if="selected.location"> &nbsp;·&nbsp; 📍 {{ selected.location }}</span>
            </div>
          </div>
        </div>
        <div class="dh-badges">
          <span v-if="selected.pr" class="badge badge-pr">🏅 PR</span>
          <span v-if="selected.favorite" class="badge badge-fav">⭐ Favorita</span>
        </div>
      </div>

      <!-- Cards de métricas principais -->
      <div class="metrics-row">
        <div class="mcard" v-if="selected.distance_m">
          <div class="mc-label">Distância</div>
          <div class="mc-val" style="color:#3b82f6">{{ fmtDist(selected.distance_m) }}</div>
        </div>
        <div class="mcard" v-if="selected.avg_speed_ms">
          <div class="mc-label">Ritmo médio</div>
          <div class="mc-val" style="color:#10b981">{{ fmtPace(selected.avg_speed_ms) }}</div>
        </div>
        <div class="mcard" v-if="selected.duration_s">
          <div class="mc-label">Tempo</div>
          <div class="mc-val">{{ fmtDuration(selected.duration_s) }}</div>
        </div>
        <div class="mcard" v-if="selected.avg_hr">
          <div class="mc-label">FC Média</div>
          <div class="mc-val" style="color:#ef4444">{{ Math.round(selected.avg_hr) }} <small>bpm</small></div>
          <div class="mc-sub" v-if="selected.max_hr">Máx: {{ selected.max_hr }} bpm</div>
        </div>
        <div class="mcard" v-if="selected.calories">
          <div class="mc-label">Calorias</div>
          <div class="mc-val" style="color:#f97316">{{ Math.round(selected.calories) }} <small>kcal</small></div>
        </div>
        <div class="mcard" v-if="selected.elevation_gain">
          <div class="mc-label">Desnível +</div>
          <div class="mc-val" style="color:#8b5cf6">{{ Math.round(selected.elevation_gain) }} <small>m</small></div>
        </div>
        <div class="mcard" v-if="selected.training_effect">
          <div class="mc-label">Ef. Treino</div>
          <div class="mc-val" style="color:#06b6d4">{{ selected.training_effect }}</div>
        </div>
      </div>

      <div class="detail-grid">

        <!-- Seções de dados disponíveis no formato compacto -->
        <div class="detail-sections">

          <!-- Ritmo / Velocidade -->
          <div class="dsection" v-if="selected.avg_speed_ms">
            <div class="ds-title">⏱ Ritmo & Velocidade</div>
            <table class="ds-table">
              <tr><td>Ritmo médio</td><td>{{ fmtPace(selected.avg_speed_ms) }}</td></tr>
              <tr><td>Velocidade média</td><td>{{ fmtSpeed(selected.avg_speed_ms) }}</td></tr>
            </table>
          </div>

          <!-- Cronometragem -->
          <div class="dsection" v-if="selected.duration_s">
            <div class="ds-title">🕐 Cronometragem</div>
            <table class="ds-table">
              <tr><td>Tempo total</td><td>{{ fmtDuration(selected.duration_s) }}</td></tr>
            </table>
          </div>

          <!-- FC -->
          <div class="dsection" v-if="selected.avg_hr">
            <div class="ds-title">❤️ Frequência Cardíaca</div>
            <table class="ds-table">
              <tr><td>FC Média</td><td>{{ Math.round(selected.avg_hr) }} bpm</td></tr>
              <tr v-if="selected.max_hr"><td>FC Máxima</td><td>{{ selected.max_hr }} bpm</td></tr>
            </table>
          </div>

          <!-- Elevação -->
          <div class="dsection" v-if="selected.elevation_gain">
            <div class="ds-title">⛰ Elevação</div>
            <table class="ds-table">
              <tr><td>Subida total</td><td>{{ Math.round(selected.elevation_gain) }} m</td></tr>
            </table>
          </div>

          <!-- Cadência -->
          <div class="dsection" v-if="selected.cadence">
            <div class="ds-title">🦵 Cadência</div>
            <table class="ds-table">
              <tr><td>Cadência média</td><td>{{ Math.round(selected.cadence) }} epm</td></tr>
            </table>
          </div>

          <!-- Efeito de Treino -->
          <div class="dsection" v-if="selected.training_effect">
            <div class="ds-title">🎯 Efeito de Treino</div>
            <table class="ds-table">
              <tr><td>Aeróbico</td><td>{{ selected.training_effect }}</td></tr>
            </table>
          </div>

        </div>
      </div>
    </div>

    <!-- Estado inicial -->
    <div v-if="!selected && !filtered.length" class="empty-state">
      <span>🏃</span><p>Nenhuma atividade encontrada.</p>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  activities: { type: Array, default: () => [] },
})

const search = ref('')
const typeFilter = ref('all')
const selected = ref(null)

const typeFilters = [
  { key: 'all', label: '🔘 Todas' },
  { key: 'running', label: '🏃 Corrida' },
  { key: 'cycling', label: '🚴 Ciclismo' },
  { key: 'strength', label: '🏋️ Força' },
  { key: 'other', label: '⚡ Outras' },
]

function actTypeKey(act) {
  return act.type || ''
}

function matchesType(act) {
  if (typeFilter.value === 'all') return true
  const key = actTypeKey(act).toLowerCase()
  if (typeFilter.value === 'running') return key.includes('run')
  if (typeFilter.value === 'cycling') return key.includes('cycl') || key.includes('ride') || key.includes('bike')
  if (typeFilter.value === 'strength') return key.includes('strength') || key.includes('gym') || key.includes('weight')
  return !key.includes('run') && !key.includes('cycl') && !key.includes('strength')
}

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return (props.activities || [])
    .filter(a => matchesType(a) && (!q || (a.name || '').toLowerCase().includes(q)))
    .sort((a, b) => (b.date || '').localeCompare(a.date || ''))
})

function selectActivity(act) {
  selected.value = act
  setTimeout(() => {
    document.querySelector('.act-detail')?.scrollTo(0, 0)
  }, 50)
}

// ── Formatters ──────────────────────────────────────────────────────────────

function fmtDate(str) {
  if (!str) return '—'
  const d = new Date(str + 'T12:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function fmtDateFull(str) {
  if (!str) return '—'
  const d = new Date(str + 'T12:00:00')
  return d.toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' })
}

function fmtDist(m) {
  if (!m) return '—'
  return m >= 1000 ? (m / 1000).toFixed(2) + ' km' : Math.round(m) + ' m'
}

function fmtPace(spd) {
  if (!spd) return '—'
  const secPerKm = 1000 / spd
  const m = Math.floor(secPerKm / 60)
  const s = Math.round(secPerKm % 60)
  return `${m}:${String(s).padStart(2, '0')}/km`
}

function fmtSpeed(spd) {
  return spd ? (spd * 3.6).toFixed(1) + ' km/h' : '—'
}

function fmtDuration(secs) {
  if (!secs) return '—'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.round(secs % 60)
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
  return `${m}:${String(s).padStart(2,'0')}`
}

function typeIcon(act) {
  const key = actTypeKey(act).toLowerCase()
  if (key.includes('run')) return '🏃'
  if (key.includes('cycl') || key.includes('ride')) return '🚴'
  if (key.includes('strength') || key.includes('gym')) return '🏋️'
  if (key.includes('swim')) return '🏊'
  if (key.includes('walk')) return '🚶'
  if (key.includes('yoga')) return '🧘'
  return '⚡'
}
</script>

<style scoped>
.act-tab {
  display: flex;
  gap: 1.5rem;
  min-height: 70vh;
}

/* ── Lista ── */
.act-list {
  width: 360px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}
.act-list.collapsed { width: 320px; }

.list-header {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 12px 12px 0 0;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.search-input {
  width: 100%;
  background: #0f1117;
  border: 1px solid #2d3748;
  border-radius: 8px;
  color: #e2e8f0;
  padding: 0.5rem 0.75rem;
  font-size: 0.88rem;
  box-sizing: border-box;
}
.search-input:focus { outline: none; border-color: #3b82f6; }

.filter-row { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.type-btn {
  font-size: 0.72rem;
  padding: 3px 8px;
  border-radius: 12px;
  border: 1px solid #2d3748;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
}
.type-btn.active { background: #1e40af; color: #fff; border-color: #3b82f6; }
.type-btn:hover:not(.active) { background: #1e2235; }

.list-count { font-size: 0.72rem; color: #475569; }

.list-items {
  flex: 1;
  overflow-y: auto;
  max-height: calc(100vh - 300px);
  border: 1px solid #2d3748;
  border-top: none;
  border-radius: 0 0 12px 12px;
}

.act-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #1e2235;
  cursor: pointer;
  transition: background 0.15s;
}
.act-item:hover { background: #1e2235; }
.act-item.active { background: #1e3a5f; border-left: 3px solid #3b82f6; }
.act-item:last-child { border-bottom: none; }

.act-icon { font-size: 1.4rem; flex-shrink: 0; }
.act-item-body { flex: 1; min-width: 0; }
.act-item-name { font-size: 0.82rem; color: #e2e8f0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.act-item-meta { font-size: 0.72rem; color: #64748b; margin-top: 2px; }
.act-item-right { text-align: right; flex-shrink: 0; }
.act-hr { display: block; font-size: 0.78rem; color: #ef4444; }
.act-dur { display: block; font-size: 0.78rem; color: #94a3b8; }

/* ── Detalhe ── */
.act-detail {
  flex: 1;
  overflow-y: auto;
  max-height: calc(100vh - 220px);
}

.back-btn {
  background: transparent;
  border: 1px solid #2d3748;
  color: #94a3b8;
  padding: 0.4rem 0.9rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.82rem;
  margin-bottom: 1.25rem;
  display: none; /* hidden on desktop, shown on mobile via media query */
}
@media (max-width: 900px) { .back-btn { display: inline-block; } }

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: linear-gradient(135deg, #1e2235 0%, #1a1d2e 100%);
  border: 1px solid #2d3748;
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.dh-left { display: flex; gap: 1rem; align-items: flex-start; }
.dh-icon { font-size: 2.5rem; }
.dh-name { font-size: 1.2rem; font-weight: 700; color: #e2e8f0; margin: 0 0 4px; }
.dh-meta { font-size: 0.82rem; color: #64748b; }
.dh-badges { display: flex; gap: 0.5rem; align-items: center; }
.badge { padding: 4px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
.badge-pr { background: rgba(234,179,8,0.2); color: #eab308; border: 1px solid #eab308; }
.badge-fav { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid #f59e0b; }

.metrics-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}
.mcard {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 10px;
  padding: 0.75rem 1rem;
  min-width: 110px;
}
.mc-label { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.mc-val { font-size: 1.5rem; font-weight: 700; line-height: 1.1; color: #e2e8f0; }
.mc-val small { font-size: 0.75rem; font-weight: 400; color: #94a3b8; }
.mc-sub { font-size: 0.72rem; color: #94a3b8; margin-top: 2px; }

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
@media (max-width: 1200px) { .detail-grid { grid-template-columns: 1fr; } }

.detail-sections { display: flex; flex-direction: column; gap: 0.75rem; }
.detail-charts { display: flex; flex-direction: column; gap: 1rem; }

.dsection {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 10px;
  padding: 1rem;
}
.ds-title {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #64748b;
  margin-bottom: 0.6rem;
}
.ds-table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
.ds-table td { padding: 4px 0; color: #94a3b8; }
.ds-table td:last-child { color: #e2e8f0; text-align: right; font-weight: 500; }
.te-badge { padding: 2px 8px; border-radius: 8px; color: #fff; font-size: 0.85rem; font-weight: 600; }
.te-msg { color: #64748b !important; font-style: italic; font-size: 0.78rem; padding-top: 6px !important; }

.chart-card {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 10px;
  padding: 1rem;
}
.cc-title {
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #64748b;
  margin-bottom: 0.75rem;
}

.zone-time-list { margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.4rem; }
.ztl-row { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; }
.ztl-name { width: 24px; font-weight: 700; flex-shrink: 0; }
.ztl-bar-track { flex: 1; height: 8px; background: #0f1117; border-radius: 4px; overflow: hidden; }
.ztl-bar { height: 100%; border-radius: 4px; transition: width 0.4s; }
.ztl-time { width: 48px; text-align: right; color: #94a3b8; }
.ztl-pct { width: 36px; text-align: right; color: #64748b; }

.laps-scroll { overflow-x: auto; }
.laps-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.laps-table th {
  text-align: left;
  padding: 6px 8px;
  color: #64748b;
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  border-bottom: 1px solid #2d3748;
}
.laps-table td {
  padding: 6px 8px;
  color: #94a3b8;
  border-bottom: 1px solid #1e2235;
}
.laps-table .td-pace { color: #e2e8f0; font-weight: 600; }
.laps-table tr:last-child td { border-bottom: none; }

.empty-state { text-align: center; padding: 4rem; color: #64748b; flex: 1; }
.empty-state span { font-size: 3rem; }
.empty-state p { margin-top: 1rem; }

@media (max-width: 900px) {
  .act-tab { flex-direction: column; }
  .act-list { width: 100%; }
  .act-list.collapsed { width: 100%; }
  .act-detail { max-height: none; }
}
</style>
