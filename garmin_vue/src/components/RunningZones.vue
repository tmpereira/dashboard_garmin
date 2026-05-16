<template>
  <div>
    <!-- 1km test input -->
    <div class="zones-config">
      <h3 class="section-title">Calculadora de Zonas de Ritmo</h3>
      <p class="section-desc">
        Insira o tempo do seu melhor teste de 1km (ou será detectado automaticamente da atividade <code>[teste]</code>).
      </p>
      <div class="test-row">
        <div class="input-group">
          <label>Tempo 1km (mm:ss)</label>
          <input v-model="testTimeStr" placeholder="ex: 4:30" class="pace-input" @input="onInput" />
        </div>
        <div class="input-group" v-if="autoTestActivity">
          <label>Detectado automaticamente</label>
          <div class="auto-badge">
            🎯 {{ autoTestActivity.name }} —
            {{ formatPaceFromSpeed(autoTestActivity.avgSpeed) }}
          </div>
        </div>
        <button class="calc-btn" @click="useAutoTest" v-if="autoTestActivity">Usar Detectado</button>
      </div>

      <div v-if="zonas.length" class="zones-table">
        <h4>Zonas de Corrida (baseadas em vVO2max)</h4>
        <div class="zones-grid">
          <div v-for="z in zonas" :key="z.name" class="zone-card" :style="{ borderLeftColor: z.color }">
            <div class="zone-name" :style="{ color: z.color }">{{ z.name }}</div>
            <div class="zone-desc">{{ z.desc }}</div>
            <div class="zone-pace">{{ z.paceRange }}</div>
            <div class="zone-speed">{{ z.speedRange }}</div>
            <div class="zone-count" v-if="z.count !== undefined">
              <span class="count-dot" :style="{ background: z.color }"></span>
              {{ z.count }} atividade(s)
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Zone distribution pie (only if activities) -->
    <div v-if="zoneDist.total > 0" style="margin-top:2rem">
      <h3 class="section-title">Distribuição por Zona ({{ zoneDist.total }} corridas)</h3>
      <div class="dist-row">
        <div style="max-width:380px; flex:0 0 auto">
          <Doughnut :data="donutData" :options="donutOptions" />
        </div>
        <div class="dist-bars">
          <div v-for="z in zonas" :key="z.name" class="dist-bar-row">
            <span class="dist-label" :style="{ color: z.color }">{{ z.name }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barPct(z) + '%', background: z.color }"></div>
            </div>
            <span class="dist-pct">{{ barPct(z).toFixed(0) }}%</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="zonas.length" class="empty-note">
      ℹ️ Nenhuma corrida disponível para calcular distribuição de zonas.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS, ArcElement, Tooltip, Legend
} from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend)

const props = defineProps({ activities: { type: Array, default: () => [] } })

const testTimeStr = ref('')

// Auto-detect [teste] activity with ~1km distance
const autoTestActivity = computed(() => {
  for (const act of (props.activities || [])) {
    const name = act.name || ''
    if (name.toLowerCase().includes('[teste]')) {
          const dist = act.distance_m || 0
          // if approx 1km
          if (dist > 900 && dist < 1200) {
            return {
              name,
              avgSpeed: act.avg_speed_ms,
            }
      }
    }
  }
  return null
})

function useAutoTest() {
  if (autoTestActivity.value?.avgSpeed) {
    const paceSecPerKm = 1000 / autoTestActivity.value.avgSpeed
    const m = Math.floor(paceSecPerKm / 60)
    const s = Math.round(paceSecPerKm % 60)
    testTimeStr.value = `${m}:${s.toString().padStart(2, '0')}`
  }
}

function onInput() { /* reactive */ }

// Parse mm:ss to seconds
function parseTime(str) {
  if (!str) return null
  const parts = str.split(':')
  if (parts.length !== 2) return null
  const m = parseInt(parts[0], 10)
  const s = parseInt(parts[1], 10)
  if (isNaN(m) || isNaN(s)) return null
  return m * 60 + s
}

// Base speed from 1km test time (m/s)
const baseSpeed = computed(() => {
  const secs = parseTime(testTimeStr.value)
  if (!secs) return null
  return 1000 / secs // m/s
})

// vVO2max = base speed of 1km test (simplification)
// Zones based on % of vVO2max (Daniels formula)
const ZONE_DEFS = [
  { name: 'Z1 — Recuperação', desc: 'Regenerativo, muito fácil', pctLow: 0.55, pctHigh: 0.65, color: '#3b82f6' },
  { name: 'Z2 — Base Aeróbica', desc: 'Aeróbico fácil, conversa normal', pctLow: 0.65, pctHigh: 0.75, color: '#10b981' },
  { name: 'Z3 — Limiar', desc: 'Tempo, difícil mas sustentável', pctLow: 0.83, pctHigh: 0.88, color: '#f59e0b' },
  { name: 'Z4 — Intervalo', desc: 'VO2max, esforço forte', pctLow: 0.95, pctHigh: 1.00, color: '#f97316' },
  { name: 'Z5 — Repetição', desc: 'Velocidade pura, anaeróbico', pctLow: 1.05, pctHigh: 1.15, color: '#ef4444' },
]

function msToPaceStr(speedMs) {
  if (!speedMs || speedMs <= 0) return '—'
  const secPerKm = 1000 / speedMs
  const m = Math.floor(secPerKm / 60)
  const s = Math.round(secPerKm % 60)
  return `${m}:${s.toString().padStart(2, '0')}/km`
}

function msToKmhStr(speedMs) {
  return speedMs ? (speedMs * 3.6).toFixed(1) + ' km/h' : '—'
}

function formatPaceFromSpeed(spd) {
  return msToPaceStr(spd)
}

const zonas = computed(() => {
  if (!baseSpeed.value) return []

  const runActs = (props.activities || []).filter(act => {
    return (act.type || '').toLowerCase().includes('run')
  })

  return ZONE_DEFS.map(z => {
    const lo = baseSpeed.value * z.pctLow
    const hi = baseSpeed.value * z.pctHigh
    // count runs in zone
    const count = runActs.filter(act => {
      const spd = act.avg_speed_ms || 0
      return spd >= lo && spd <= hi
    }).length

    return {
      ...z,
      speedLow: lo,
      speedHigh: hi,
      paceRange: `${msToPaceStr(hi)} – ${msToPaceStr(lo)}`,
      speedRange: `${msToKmhStr(lo)} – ${msToKmhStr(hi)}`,
      count,
    }
  })
})

const zoneDist = computed(() => {
  const total = zonas.value.reduce((s, z) => s + (z.count || 0), 0)
  return { total }
})

function barPct(z) {
  if (!zoneDist.value.total) return 0
  return (z.count / zoneDist.value.total) * 100
}

const donutData = computed(() => ({
  labels: zonas.value.map(z => z.name),
  datasets: [{
    data: zonas.value.map(z => z.count || 0),
    backgroundColor: zonas.value.map(z => z.color),
    borderWidth: 2,
    borderColor: '#0f1117',
  }]
}))

const donutOptions = {
  responsive: true,
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw} corridas` } }
  }
}
</script>

<style scoped>
.zones-config { background: #1e2235; border-radius: 12px; padding: 1.5rem; }
.section-title { font-size: 1rem; font-weight: 600; color: #e2e8f0; margin: 0 0 0.5rem; }
.section-desc { font-size: 0.85rem; color: #64748b; margin-bottom: 1rem; }
.section-desc code { background: #0f1117; padding: 1px 5px; border-radius: 4px; }

.test-row { display: flex; gap: 1rem; align-items: flex-end; flex-wrap: wrap; margin-bottom: 1.5rem; }
.input-group { display: flex; flex-direction: column; gap: 0.35rem; }
.input-group label { font-size: 0.78rem; color: #94a3b8; }
.pace-input {
  background: #0f1117; border: 1px solid #2d3748; color: #e2e8f0;
  border-radius: 8px; padding: 0.5rem 0.75rem; width: 130px;
  font-size: 1rem;
}
.pace-input:focus { outline: none; border-color: #3b82f6; }
.auto-badge { background: #0f1117; padding: 0.5rem 0.75rem; border-radius: 8px; font-size: 0.85rem; color: #10b981; }
.calc-btn {
  background: #3b82f6; color: white; border: none; border-radius: 8px;
  padding: 0.5rem 1rem; cursor: pointer; font-size: 0.85rem; height: 38px;
}
.calc-btn:hover { background: #2563eb; }

h4 { font-size: 0.88rem; color: #94a3b8; margin-bottom: 1rem; }
.zones-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.75rem; }
.zone-card {
  background: #0f1117; border: 1px solid #2d3748; border-left: 3px solid;
  border-radius: 8px; padding: 0.85rem 1rem;
}
.zone-name { font-size: 0.88rem; font-weight: 600; margin-bottom: 3px; }
.zone-desc { font-size: 0.75rem; color: #64748b; margin-bottom: 6px; }
.zone-pace { font-size: 0.95rem; color: #e2e8f0; font-weight: 600; }
.zone-speed { font-size: 0.78rem; color: #94a3b8; }
.zone-count { display: flex; align-items: center; gap: 0.4rem; margin-top: 6px; font-size: 0.78rem; color: #94a3b8; }
.count-dot { width: 8px; height: 8px; border-radius: 50%; }

.dist-row { display: flex; gap: 2rem; align-items: flex-start; flex-wrap: wrap; }
.dist-bars { flex: 1; min-width: 240px; display: flex; flex-direction: column; gap: 0.75rem; padding-top: 1rem; }
.dist-bar-row { display: flex; align-items: center; gap: 0.75rem; }
.dist-label { font-size: 0.78rem; width: 120px; flex-shrink: 0; }
.bar-track { flex: 1; height: 12px; background: #1e2235; border-radius: 6px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 6px; transition: width 0.5s; }
.dist-pct { font-size: 0.78rem; color: #94a3b8; width: 36px; text-align: right; }

.empty-note { color: #64748b; font-size: 0.85rem; margin-top: 1rem; padding: 1rem; background: #1e2235; border-radius: 8px; }
</style>
