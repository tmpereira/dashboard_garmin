<template>
  <div>

    <!-- ═══ BLOCO: Prontidão / Status / Carga Aguda ═══ -->
    <div class="garmin-block">
      <!-- Prontidão para Treino -->
      <div class="gb-card" :style="{ borderTopColor: readiness.color }">
        <div class="gb-top">
          <span class="gb-icon">{{ readiness.icon }}</span>
          <div class="gb-label">Prontidão para Treino</div>
        </div>
        <div class="gb-score" :style="{ color: readiness.color }">{{ readiness.score }}</div>
        <div class="gb-status" :style="{ color: readiness.color }">{{ readiness.label }}</div>
        <div class="gb-desc">{{ readiness.desc }}</div>
        <!-- Mini gauge -->
        <div class="gb-gauge-track">
          <div class="gb-gauge-fill" :style="{ width: readiness.score + '%', background: readiness.color }"></div>
          <div class="gb-gauge-markers">
            <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
          </div>
        </div>
        <div class="gb-factors" v-if="readiness.factors.length">
          <div v-for="f in readiness.factors" :key="f.label" class="gbf-row">
            <span class="gbf-label">{{ f.label }}</span>
            <div class="gbf-bar-track">
              <div class="gbf-bar" :style="{ width: f.pct + '%', background: f.color }"></div>
            </div>
            <span class="gbf-val" :style="{ color: f.color }">{{ f.val }}</span>
          </div>
        </div>
      </div>

      <!-- Status de Treino -->
      <div class="gb-card" :style="{ borderTopColor: trainingStatusInfo.color }">
        <div class="gb-top">
          <span class="gb-icon">{{ trainingStatusInfo.icon }}</span>
          <div class="gb-label">Status de Treino</div>
        </div>
        <div class="gb-status-big" :style="{ color: trainingStatusInfo.color }">
          {{ trainingStatusInfo.label }}
        </div>
        <div class="gb-desc">{{ trainingStatusInfo.desc }}</div>
        <div class="gb-stat-rows">
          <div class="gs-row" v-if="currentCTL !== null">
            <span class="gs-k">CTL (Condicionamento)</span>
            <span class="gs-v" style="color:#3b82f6">{{ currentCTL.toFixed(1) }}</span>
          </div>
          <div class="gs-row" v-if="currentATL !== null">
            <span class="gs-k">ATL (Fadiga)</span>
            <span class="gs-v" style="color:#f97316">{{ currentATL.toFixed(1) }}</span>
          </div>
          <div class="gs-row" v-if="currentTSB !== null">
            <span class="gs-k">TSB (Balanço)</span>
            <span class="gs-v" :style="{ color: tsbColor(currentTSB) }">{{ currentTSB.toFixed(1) }}</span>
          </div>
          <div class="gs-row" v-if="latestHRV">
            <span class="gs-k">HRV Status</span>
            <span class="gs-v" :style="{ color: hrvStatusColor }">{{ hrvStatusLabel }}</span>
          </div>
        </div>
      </div>

      <!-- Carga Aguda -->
      <div class="gb-card" :style="{ borderTopColor: acuteLoadInfo.color }">
        <div class="gb-top">
          <span class="gb-icon">⚡</span>
          <div class="gb-label">Carga Aguda (ATL)</div>
        </div>
        <div class="gb-score" :style="{ color: acuteLoadInfo.color }">
          {{ currentATL !== null ? currentATL.toFixed(1) : '—' }}
        </div>
        <div class="gb-status" :style="{ color: acuteLoadInfo.color }">{{ acuteLoadInfo.label }}</div>
        <div class="gb-desc">Média ponderada de 7 dias de TRIMP</div>
        <div class="gb-stat-rows" style="margin-top:0.75rem">
          <div class="gs-row">
            <span class="gs-k">Última semana</span>
            <span class="gs-v">{{ weekTRIMP.toFixed(1) }} TRIMP</span>
          </div>
          <div class="gs-row" v-if="lastActivityDate">
            <span class="gs-k">Último treino</span>
            <span class="gs-v">{{ lastActivityDate }}</span>
          </div>
          <div class="gs-row">
            <span class="gs-k">Atividades (7d)</span>
            <span class="gs-v">{{ recentActivities }} treino(s)</span>
          </div>
        </div>
        <!-- Tendência ATL nos últimos 14 dias -->
        <div v-if="atlHistory.length > 1" style="margin-top:0.75rem">
          <Line :data="atlMiniChart" :options="atlMiniOptions" style="max-height:80px" />
        </div>
      </div>
    </div>
    <!-- ═══ fim bloco ═══ -->

    <!-- ═══ GRÁFICO 60 DIAS ═══ -->
    <div v-if="history60.length > 1" class="chart-block" style="margin-top:1.5rem">
      <div class="chart-block-header">
        <span class="chart-block-title">CTL · ATL · TSB — últimos 60 dias</span>
        <span class="chart-block-sub">Condicionamento, Fadiga e Balanço ao longo do tempo</span>
      </div>
      <Line :data="metrics60Data" :options="metrics60Options" style="max-height:260px" />
    </div>
    <!-- ═══ fim gráfico 60 dias ═══ -->

    <div class="pmc-header" style="margin-top:1.5rem">
      <div class="pmc-info">
        <div class="pmc-badge" v-if="currentTSB !== null">
          <span class="badge-label">Estado Atual (TSB)</span>
          <span class="badge-value" :style="{ color: tsbColor(currentTSB) }">
            {{ currentTSB.toFixed(1) }}
          </span>
          <span class="badge-sub">{{ tsbLabel(currentTSB) }}</span>
        </div>
        <div class="pmc-badge" v-if="currentCTL !== null">
          <span class="badge-label">Condicionamento (CTL)</span>
          <span class="badge-value" style="color:#3b82f6">{{ currentCTL.toFixed(1) }}</span>
          <span class="badge-sub">carga crônica (42 dias)</span>
        </div>
        <div class="pmc-badge" v-if="currentATL !== null">
          <span class="badge-label">Fadiga (ATL)</span>
          <span class="badge-value" style="color:#f97316">{{ currentATL.toFixed(1) }}</span>
          <span class="badge-sub">carga aguda (7 dias)</span>
        </div>
      </div>
    </div>

    <!-- ═══ GUIA DE INTERPRETAÇÃO ═══ -->
    <div class="guide-section">
      <h3 class="guide-title">📖 Guia de Interpretação</h3>
      <div class="guide-grid">

        <!-- Prontidão -->
        <div class="guide-card">
          <div class="guide-card-header" style="border-left-color:#10b981">
            <span class="guide-card-icon">🟢</span>
            <span>Prontidão para Treino (0–100)</span>
          </div>
          <p class="guide-card-desc">Estimativa de quão recuperado você está para treinar hoje. Calculado com HRV (40%), Body Battery (30%), Sono (20%) e TSB (10%).</p>
          <table class="guide-table">
            <thead><tr><th>Score</th><th>Nível</th><th>O que fazer</th></tr></thead>
            <tbody>
              <tr><td style="color:#10b981">75–100</td><td>Excelente</td><td>Treino intenso, tiros ou competição</td></tr>
              <tr><td style="color:#84cc16">60–74</td><td>Boa</td><td>Pode treinar forte; monitore sensações</td></tr>
              <tr><td style="color:#eab308">45–59</td><td>Moderada</td><td>Ritmo moderado; evite séries duras</td></tr>
              <tr><td style="color:#f97316">30–44</td><td>Baixa</td><td>Treino leve ou recuperação ativa</td></tr>
              <tr><td style="color:#ef4444">0–29</td><td>Muito Baixa</td><td>Descanse — forçar aumenta risco de lesão</td></tr>
            </tbody>
          </table>
        </div>

        <!-- Status de Treino -->
        <div class="guide-card">
          <div class="guide-card-header" style="border-left-color:#3b82f6">
            <span class="guide-card-icon">📊</span>
            <span>Status de Treino (TSB)</span>
          </div>
          <p class="guide-card-desc">Onde você está no ciclo de treinamento. TSB = CTL − ATL. Negativo = fadigado, positivo = descansado.</p>
          <table class="guide-table">
            <thead><tr><th>Status</th><th>TSB</th><th>Significado</th></tr></thead>
            <tbody>
              <tr><td>🔵 Descansado</td><td style="color:#3b82f6">&gt; +10</td><td>Volume baixo. Hora de intensificar</td></tr>
              <tr><td>🟢 Produtivo</td><td style="color:#10b981">-5 a +10</td><td>Zona ideal de estresse/recuperação</td></tr>
              <tr><td>🟡 Acumulando</td><td style="color:#eab308">-15 a -5</td><td>Carga crescendo. Normal em blocos</td></tr>
              <tr><td>🟠 Evoluindo</td><td style="color:#f97316">-30 a -15</td><td>Alta fadiga. Sono e nutrição críticos</td></tr>
              <tr><td>🔴 Sobretreinando</td><td style="color:#ef4444">&lt; -30</td><td>Risco real. Reduza carga urgente</td></tr>
            </tbody>
          </table>
        </div>

        <!-- Carga Aguda -->
        <div class="guide-card">
          <div class="guide-card-header" style="border-left-color:#f97316">
            <span class="guide-card-icon">⚡</span>
            <span>Carga Aguda — ATL (7 dias)</span>
          </div>
          <p class="guide-card-desc">Estresse médio dos últimos 7 dias. Mede sua fadiga recente. Subindo = volume crescendo; descendo = você está descansando.</p>
          <table class="guide-table">
            <thead><tr><th>ATL</th><th>Nível</th><th>Contexto</th></tr></thead>
            <tbody>
              <tr><td style="color:#94a3b8">&lt; 10</td><td>Muito Baixa</td><td>Destreino ou semana de descanso</td></tr>
              <tr><td style="color:#10b981">10–25</td><td>Baixa</td><td>Volume leve — bom para recuperação</td></tr>
              <tr><td style="color:#eab308">25–50</td><td>Moderada</td><td>Treino consistente e regular</td></tr>
              <tr><td style="color:#f97316">50–80</td><td>Alta</td><td>Bloco intenso — normal pré-prova</td></tr>
              <tr><td style="color:#ef4444">&gt; 80</td><td>Muito Alta</td><td>Carga extrema — monitore sinais de fadiga</td></tr>
            </tbody>
          </table>
        </div>

        <!-- Como ler junto -->
        <div class="guide-card guide-card-wide">
          <div class="guide-card-header" style="border-left-color:#a855f7">
            <span class="guide-card-icon">💡</span>
            <span>Como ler tudo junto</span>
          </div>
          <div class="guide-examples">
            <div class="ge-row">
              <div class="ge-badge" style="background:rgba(16,185,129,0.15); border-color:#10b981">
                <span>Prontidão <strong style="color:#10b981">72</strong> · Produtivo · ATL Moderada</span>
              </div>
              <span class="ge-arrow">→</span>
              <span class="ge-text">Boa semana de treino. Pode treinar normal ou um pouco acima do habitual.</span>
            </div>
            <div class="ge-row">
              <div class="ge-badge" style="background:rgba(239,68,68,0.15); border-color:#ef4444">
                <span>Prontidão <strong style="color:#ef4444">38</strong> · Sobretreinando · ATL Alta</span>
              </div>
              <span class="ge-arrow">→</span>
              <span class="ge-text">Semana pesada demais. Insira 2–3 dias leves antes do próximo bloco intenso.</span>
            </div>
            <div class="ge-row">
              <div class="ge-badge" style="background:rgba(59,130,246,0.15); border-color:#3b82f6">
                <span>Prontidão <strong style="color:#10b981">85</strong> · Descansado · ATL Muito Baixa</span>
              </div>
              <span class="ge-arrow">→</span>
              <span class="ge-text">Fresco mas destreinando. Momento certo para retomar volume ou intensidade.</span>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Line, Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, BarElement, Tooltip, Legend, Filler
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend, Filler)

const props = defineProps({
  pmc: { type: Object, default: () => ({}) },
})

const hasData = computed(() => !!(props.pmc?.history?.length))

const currentCTL = computed(() => props.pmc?.ctl ?? null)
const currentATL = computed(() => props.pmc?.atl ?? null)
const currentTSB = computed(() => props.pmc?.tsb ?? null)

const weekTRIMP      = computed(() => props.pmc?.trimp_7d ?? 0)
const recentActivities = computed(() => props.pmc?.activities_7d ?? 0)
const lastActivityDate = computed(() => null) // removido — não pré-calculado

// ── HRV ──────────────────────────────────────────────────────────────────
const latestHRV = computed(() => props.pmc?.hrv_score != null ? { lastNightAvg: props.pmc.hrv_score } : null)

const hrvStatusLabel = computed(() => {
  const s = props.pmc?.hrv_score
  if (s == null) return '—'
  if (s >= 70) return 'Equilibrado'
  if (s >= 40) return 'Abaixo do baseline'
  return 'Baixo'
})

const hrvStatusColor = computed(() => {
  const s = props.pmc?.hrv_score
  if (s == null) return '#64748b'
  if (s >= 70) return '#10b981'
  if (s >= 40) return '#f97316'
  return '#ef4444'
})

// ── ATL mini-chart (últimos 14 dias do histórico) ─────────────────────────
const atlHistory = computed(() => (props.pmc?.history || []).slice(-14))

const atlMiniChart = computed(() => ({
  labels: atlHistory.value.map(r => fmtDate(r.date)),
  datasets: [{
    data: atlHistory.value.map(r => +r.atl.toFixed(2)),
    borderColor: '#f97316',
    backgroundColor: 'rgba(249,115,22,0.15)',
    borderWidth: 2,
    pointRadius: 0,
    fill: true,
    tension: 0.3,
  }]
}))

const atlMiniOptions = {
  responsive: true,
  plugins: { legend: { display: false }, tooltip: { enabled: false } },
  scales: { x: { display: false }, y: { display: false } }
}

// ── Prontidão para Treino ─────────────────────────────────────────────────
const readiness = computed(() => {
  const pmc = props.pmc
  if (!pmc || pmc.readiness == null) {
    return { score: '—', color: '#64748b', label: '—', icon: '❓', desc: 'Dados insuficientes.', factors: [] }
  }
  const s = pmc.readiness
  const color = s >= 70 ? '#10b981' : s >= 50 ? '#eab308' : s >= 30 ? '#f97316' : '#ef4444'
  const label = s >= 75 ? 'Excelente' : s >= 60 ? 'Boa' : s >= 45 ? 'Moderada' : s >= 30 ? 'Baixa' : 'Muito Baixa'
  const icon  = s >= 75 ? '🟢' : s >= 60 ? '🟡' : s >= 45 ? '🟠' : '🔴'
  const desc  = s >= 75 ? 'Excelente momento para treinos intensos ou competição.'
    : s >= 60 ? 'Bom para treino moderado a intenso.'
    : s >= 45 ? 'Prefira treinos leves ou recuperação ativa.'
    : 'Recomendado descanso ou atividade muito leve.'

  const factors = []
  if (pmc.hrv_score != null)          factors.push({ label: 'HRV noturno',      pct: pmc.hrv_score,          val: `${pmc.hrv_score}`,          color: pmc.hrv_score >= 70 ? '#10b981' : pmc.hrv_score >= 40 ? '#eab308' : '#ef4444' })
  if (pmc.body_battery_score != null) factors.push({ label: 'Body Battery',     pct: pmc.body_battery_score, val: `${pmc.body_battery_score}`, color: pmc.body_battery_score >= 70 ? '#10b981' : pmc.body_battery_score >= 40 ? '#eab308' : '#ef4444' })
  if (pmc.sleep_score != null)        factors.push({ label: 'Qualidade do sono', pct: pmc.sleep_score,       val: `${pmc.sleep_score}%`,       color: pmc.sleep_score >= 70 ? '#10b981' : pmc.sleep_score >= 40 ? '#eab308' : '#ef4444' })
  if (pmc.tsb_score != null)          factors.push({ label: 'Balanço (TSB)',     pct: pmc.tsb_score,         val: currentTSB.value?.toFixed(1),color: pmc.tsb_score >= 70 ? '#10b981' : pmc.tsb_score >= 40 ? '#eab308' : '#ef4444' })

  return { score: s, color, label, icon, desc, factors }
})

// ── Status de Treino ──────────────────────────────────────────────────────
const trainingStatusInfo = computed(() => {
  const tsb = currentTSB.value
  if (tsb === null) return { label: 'Sem dados', desc: 'Nenhuma atividade registrada.', color: '#64748b', icon: '⚪' }
  if (tsb > 10)  return { label: 'Descansado',    desc: 'Carga abaixo do normal. Bom para intensificar.', color: '#3b82f6', icon: '🔵' }
  if (tsb > -5)  return { label: 'Produtivo',      desc: 'Equilíbrio ótimo entre treino e recuperação.',  color: '#10b981', icon: '🟢' }
  if (tsb > -15) return { label: 'Acumulando',     desc: 'Carga crescente. Monitore a recuperação.',      color: '#eab308', icon: '🟡' }
  if (tsb > -30) return { label: 'Evoluindo',      desc: 'Alta carga. Sono e nutrição são fundamentais.', color: '#f97316', icon: '🟠' }
  return               { label: 'Sobretreinando', desc: 'Risco de overtraining. Reduza a carga urgente.', color: '#ef4444', icon: '🔴' }
})

// ── Carga Aguda info ──────────────────────────────────────────────────────
const acuteLoadInfo = computed(() => {
  const atl = currentATL.value
  if (atl === null) return { label: 'Sem dados', color: '#64748b' }
  if (atl > 80) return { label: 'Muito Alta', color: '#ef4444' }
  if (atl > 50) return { label: 'Alta', color: '#f97316' }
  if (atl > 25) return { label: 'Moderada', color: '#eab308' }
  if (atl > 10) return { label: 'Baixa', color: '#10b981' }
  return { label: 'Muito Baixa', color: '#94a3b8' }
})

// ── Formatters ────────────────────────────────────────────────────────────
function fmtDate(str) {
  const d = new Date(str + 'T12:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

// ── Gráfico 60 dias (CTL / ATL / TSB) ───────────────────────────────────
const history60 = computed(() => (props.pmc?.history || []).slice(-60))

const metrics60Data = computed(() => ({
  labels: history60.value.map(r => fmtDate(r.date)),
  datasets: [
    {
      label: 'CTL — Condicionamento',
      data: history60.value.map(r => +r.ctl.toFixed(2)),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.08)',
      tension: 0.3, pointRadius: 0, borderWidth: 3, fill: false,
    },
    {
      label: 'ATL — Fadiga',
      data: history60.value.map(r => +r.atl.toFixed(2)),
      borderColor: '#f97316',
      backgroundColor: 'transparent',
      tension: 0.3, pointRadius: 0, borderWidth: 2, borderDash: [5, 4], fill: false,
    },
    {
      label: 'TSB — Balanço',
      data: history60.value.map(r => +r.tsb.toFixed(2)),
      borderColor: '#94a3b8',
      backgroundColor: 'rgba(148,163,184,0.07)',
      tension: 0.2, pointRadius: 0, borderWidth: 1.5, fill: true,
    },
  ]
}))

const metrics60Options = {
  responsive: true,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { labels: { color: '#94a3b8', boxWidth: 14, font: { size: 12 } } },
    tooltip: {
      backgroundColor: '#1a1d2e',
      titleColor: '#e2e8f0',
      bodyColor: '#94a3b8',
      borderColor: '#2d3748',
      borderWidth: 1,
    }
  },
  scales: {
    x: { ticks: { color: '#64748b', maxTicksLimit: 10 }, grid: { color: '#1e2235' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
  }
}

// ── PMC Chart ─────────────────────────────────────────────────────────────
const pmcChartData = computed(() => {
  const rows = props.pmc?.history || []
  return {
    labels: rows.map(r => fmtDate(r.date)),
    datasets: [
      {
        label: 'CTL (Condicionamento)',
        data: rows.map(r => +r.ctl.toFixed(2)),
        borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)',
        tension: 0.3, pointRadius: 0, borderWidth: 3, fill: false,
      },
      {
        label: 'ATL (Fadiga)',
        data: rows.map(r => +r.atl.toFixed(2)),
        borderColor: '#f97316', backgroundColor: 'transparent',
        tension: 0.3, pointRadius: 0, borderWidth: 2, borderDash: [4, 3], fill: false,
      },
      {
        label: 'TSB (Estado Físico)',
        data: rows.map(r => +r.tsb.toFixed(2)),
        borderColor: '#94a3b8', backgroundColor: 'rgba(148,163,184,0.08)',
        tension: 0.2, pointRadius: 0, borderWidth: 1.5, fill: true,
      },
    ]
  }
})

const pmcOptions = {
  responsive: true,
  interaction: { mode: 'index', intersect: false },
  plugins: { legend: { labels: { color: '#94a3b8' } } },
  scales: {
    x: { ticks: { color: '#64748b', maxTicksLimit: 12 }, grid: { color: '#1e2235' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
  }
}

// TSB bar (last 60 days)
const tsbBarData = computed(() => {
  const rows = (props.pmc?.history || []).slice(-60)
  return {
    labels: rows.map(r => fmtDate(r.date)),
    datasets: [{
      label: 'TSB',
      data: rows.map(r => +r.tsb.toFixed(2)),
      backgroundColor: rows.map(r => tsbColor(r.tsb)),
      borderRadius: 2,
    }]
  }
})

const tsbBarOptions = {
  responsive: true,
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: ctx => `TSB: ${ctx.raw} · ${tsbLabel(ctx.raw)}` } }
  },
  scales: {
    x: { ticks: { color: '#64748b', maxTicksLimit: 15 }, grid: { color: '#1e2235' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#1e2235' } },
  }
}

function tsbColor(v) {
  if (v > 5)   return '#3b82f6'
  if (v > -10) return '#94a3b8'
  if (v > -30) return '#10b981'
  return '#ef4444'
}

function tsbLabel(v) {
  if (v > 5)   return '🔵 Descansado'
  if (v > -10) return '⚪ Manutenção'
  if (v > -30) return '🟢 Evoluindo'
  return '🔴 Alto Risco'
}

const tsbZones = [
  { color: '#3b82f6', label: 'TSB > 5 — Descansado / Adaptando' },
  { color: '#94a3b8', label: 'TSB −10 a 5 — Manutenção' },
  { color: '#10b981', label: 'TSB −30 a −10 — Evoluindo' },
  { color: '#ef4444', label: 'TSB < −30 — Alto Risco de Overtraining' },
]
</script>

<style scoped>
/* ── Chart block 60d ─────────────────────────────────────────── */
.chart-block {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 12px;
  padding: 1rem 1.25rem 1.25rem;
}
.chart-block-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.chart-block-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e2e8f0;
}
.chart-block-sub {
  font-size: 0.78rem;
  color: #64748b;
}

/* ── Garmin Metrics Block ─────────────────────────────────────── */
.garmin-block {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.gb-card {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-top: 3px solid #3b82f6;
  border-radius: 12px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.gb-top {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.25rem;
}
.gb-icon { font-size: 1.4rem; }
.gb-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: #64748b;
}

.gb-score {
  font-size: 3rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -1px;
}
.gb-status {
  font-size: 1rem;
  font-weight: 600;
}
.gb-status-big {
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1.1;
}
.gb-desc {
  font-size: 0.8rem;
  color: #64748b;
  line-height: 1.4;
  margin-bottom: 0.25rem;
}

/* Gauge bar */
.gb-gauge-track {
  height: 10px;
  background: #0f1117;
  border-radius: 5px;
  overflow: visible;
  position: relative;
  margin-top: 0.25rem;
}
.gb-gauge-fill {
  height: 100%;
  border-radius: 5px;
  transition: width 0.6s ease;
}
.gb-gauge-markers {
  display: flex;
  justify-content: space-between;
  font-size: 0.65rem;
  color: #475569;
  margin-top: 3px;
}

/* Factor rows */
.gb-factors { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.45rem; }
.gbf-row { display: flex; align-items: center; gap: 0.5rem; }
.gbf-label { font-size: 0.72rem; color: #94a3b8; width: 130px; flex-shrink: 0; }
.gbf-bar-track { flex: 1; height: 6px; background: #0f1117; border-radius: 3px; overflow: hidden; }
.gbf-bar { height: 100%; border-radius: 3px; transition: width 0.5s; }
.gbf-val { font-size: 0.72rem; font-weight: 600; width: 52px; text-align: right; }

/* Stat rows */
.gb-stat-rows { display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.5rem; }
.gs-row { display: flex; justify-content: space-between; align-items: center; }
.gs-k { font-size: 0.78rem; color: #64748b; }
.gs-v { font-size: 0.88rem; font-weight: 600; color: #e2e8f0; }

/* ── PMC Section ─────────────────────────────────────────────── */
.pmc-header { margin-bottom: 1.5rem; }
.pmc-info { display: flex; gap: 1rem; flex-wrap: wrap; }
.pmc-badge {
  background: #1e2235; border: 1px solid #2d3748; border-radius: 10px;
  padding: 0.75rem 1.25rem; min-width: 160px;
}
.badge-label { display: block; font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.badge-value { display: block; font-size: 2rem; font-weight: 700; line-height: 1.1; }
.badge-sub { display: block; font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }

.empty-state { text-align: center; padding: 3rem; color: #64748b; }
.empty-state span { font-size: 3rem; }
.empty-state p { margin-top: 0.5rem; font-size: 1rem; }
.empty-state .hint { font-size: 0.85rem; color: #475569; margin-top: 0.25rem; }

.chart-title { font-size: 0.9rem; color: #94a3b8; margin-bottom: 1rem; }

.zone-legend { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1.25rem; }
.zl-item {
  display: flex; align-items: center; gap: 0.5rem;
  background: #1e2235; border: 1px solid #2d3748;
  border-left: 3px solid; border-radius: 6px;
  padding: 0.35rem 0.75rem; font-size: 0.8rem; color: #94a3b8;
}
.zl-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

/* ── Guia de Interpretação ───────────────────────────────────── */
.guide-section {
  margin-top: 2.5rem;
  border-top: 1px solid #1e2235;
  padding-top: 2rem;
}
.guide-title {
  font-size: 1rem; font-weight: 700; color: #94a3b8;
  margin-bottom: 1.25rem; letter-spacing: 0.3px;
}
.guide-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}
.guide-card {
  background: #111827; border: 1px solid #1e2235; border-radius: 10px;
  padding: 1.1rem 1.25rem; display: flex; flex-direction: column; gap: 0.65rem;
}
.guide-card-wide { grid-column: 1 / -1; }
.guide-card-header {
  display: flex; align-items: center; gap: 0.6rem;
  font-size: 0.82rem; font-weight: 700; color: #cbd5e1;
  text-transform: uppercase; letter-spacing: 0.5px;
  border-left: 3px solid #64748b; padding-left: 0.6rem;
}
.guide-card-icon { font-size: 1.1rem; }
.guide-card-desc { font-size: 0.78rem; color: #64748b; line-height: 1.5; margin: 0; }
.guide-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
.guide-table thead tr { border-bottom: 1px solid #1e2235; }
.guide-table th {
  color: #475569; font-weight: 600; text-align: left;
  padding: 0.3rem 0.4rem; font-size: 0.7rem;
  text-transform: uppercase; letter-spacing: 0.4px;
}
.guide-table td {
  color: #94a3b8; padding: 0.35rem 0.4rem;
  border-bottom: 1px solid #0f1117; vertical-align: middle;
}
.guide-table tr:last-child td { border-bottom: none; }
.guide-examples { display: flex; flex-direction: column; gap: 0.75rem; }
.ge-row { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.ge-badge {
  border: 1px solid; border-radius: 8px; padding: 0.4rem 0.75rem;
  font-size: 0.8rem; color: #cbd5e1; white-space: nowrap;
}
.ge-arrow { color: #475569; font-size: 1.1rem; flex-shrink: 0; }
.ge-text { font-size: 0.8rem; color: #64748b; line-height: 1.4; }

/* ── Mobile ─────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .garmin-block { grid-template-columns: 1fr; }
  .guide-grid   { grid-template-columns: 1fr; }
  .guide-card   { padding: 0.9rem; }
  .gb-score     { font-size: 2.2rem; }
  .gb-status-big{ font-size: 1.3rem; }
  .guide-card   { overflow-x: auto; }
  .ge-row       { flex-direction: column; align-items: flex-start; }
  .pmc-info     { gap: 0.5rem; }
  .pmc-badge    { min-width: 120px; padding: 0.6rem 0.9rem; }
  .badge-value  { font-size: 1.5rem; }
}
</style>
