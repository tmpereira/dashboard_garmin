<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <span class="logo">🏃</span>
        <div>
          <h1>Dashboard Garmin</h1>
          <p class="subtitle">{{ data?.profile }} &nbsp;·&nbsp; Forerunner 165 &nbsp;·&nbsp; Todos os dados 2026</p>
        </div>
      </div>
      <div class="header-right" v-if="data?.user_summary">
        <div class="today-badge">
          <span class="today-label">Hoje</span>
          <span class="today-date">{{ todayDate }}</span>
        </div>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>Carregando dados Garmin...</p>
    </div>

    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="app-body">
      <!-- ── Sidebar (desktop) ── -->
      <aside class="sidebar">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="['sidebar-item', { active: activeTab === tab.id }]"
          @click="selectTab(tab.id)"
        >
          <span class="sidebar-icon">{{ tab.icon }}</span>
          <span class="sidebar-label">{{ tab.label }}</span>
        </button>
      </aside>

      <!-- ── Área principal ── -->
      <div class="main-area">
        <!-- Navegação Hamburger (mobile only) -->
        <nav class="navbar">
          <div class="nav-current" @click="menuOpen = !menuOpen">
            <span class="nav-active-label">
              {{ tabs.find(t => t.id === activeTab)?.icon }}
              {{ tabs.find(t => t.id === activeTab)?.label }}
            </span>
            <span class="hamburger" :class="{ open: menuOpen }">
              <span></span><span></span><span></span>
            </span>
          </div>
          <div class="nav-dropdown" v-if="menuOpen">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              :class="['nav-item', { active: activeTab === tab.id }]"
              @click="selectTab(tab.id)"
            >
              <span class="nav-item-icon">{{ tab.icon }}</span>
              <span>{{ tab.label }}</span>
            </button>
          </div>
        </nav>

        <div class="content">

      <!-- ============ OVERVIEW ============ -->
      <section v-show="activeTab === 'overview'" class="section">
        <h2 class="section-title">Resumo do Dia</h2>
        <div class="cards-grid">
          <MetricCard icon="👟" label="Passos" :value="fmt(summary.totalSteps)" :sub="`Meta: ${fmt(summary.dailyStepGoal)}`" color="#3b82f6" :progress="stepsProgress" />
          <MetricCard icon="🔥" label="Calorias" :value="`${fmt(summary.totalKilocalories)} kcal`" :sub="`Ativas: ${fmt(summary.activeKilocalories)} kcal`" color="#f97316" />
          <MetricCard icon="❤️" label="FC Repouso" :value="`${summary.restingHeartRate} bpm`" :sub="`Mín: ${summary.minHeartRate} · Máx: ${summary.maxHeartRate}`" color="#ef4444" />
          <MetricCard icon="⚡" label="Body Battery" :value="summary.bodyBatteryMostRecentValue" :sub="`Carregou: +${summary.bodyBatteryChargedValue} · Drenou: -${summary.bodyBatteryDrainedValue}`" color="#eab308" />
          <MetricCard icon="😮‍💨" label="SpO2" :value="`${summary.latestSpo2}%`" :sub="`Média: ${summary.averageSpo2}% · Mín: ${summary.lowestSpo2}%`" color="#06b6d4" />
          <MetricCard icon="🧘" label="Estresse Médio" :value="summary.averageStressLevel" :sub="`Máx: ${summary.maxStressLevel}`" :color="stressColor(summary.averageStressLevel)" />
          <MetricCard icon="📍" label="Distância" :value="`${(summary.totalDistanceMeters/1000).toFixed(2)} km`" :sub="`${fmt(summary.totalDistanceMeters)} m`" color="#8b5cf6" />
          <MetricCard icon="🫁" label="Respiração" :value="`${summary.latestRespirationValue} rpm`" :sub="`Máx: ${summary.highestRespirationValue} · Mín: ${summary.lowestRespirationValue}`" color="#10b981" />
        </div>

        <!-- VO2 Max & Fitness Age -->
        <div class="cards-grid" style="margin-top:1.5rem">
          <div class="card wide" v-if="vo2max">
            <div class="card-icon">🫀</div>
            <div class="card-body">
              <div class="card-label">VO2 Máx</div>
              <div class="card-value" style="color:#3b82f6">{{ vo2max }}</div>
              <div class="card-sub">ml/kg/min</div>
            </div>
          </div>
          <div class="card wide" v-if="fitnessAge">
            <div class="card-icon">🧬</div>
            <div class="card-body">
              <div class="card-label">Idade de Fitness</div>
              <div class="card-value" style="color:#10b981">{{ Math.round(fitnessAge.fitness_age) }}</div>
              <div class="card-sub">Idade real: {{ fitnessAge.chronological_age }} · Alcançável: {{ Math.round(fitnessAge.achievable_fitness_age) }}</div>
            </div>
          </div>
          <div class="card wide" v-if="racePred">
            <div class="card-icon">🏅</div>
            <div class="card-body">
              <div class="card-label">Predições de Corrida</div>
              <div class="race-grid">
                <span>5K</span><strong>{{ fmtTime(racePred.time5K) }}</strong>
                <span>10K</span><strong>{{ fmtTime(racePred.time10K) }}</strong>
                <span>Meia</span><strong>{{ fmtTime(racePred.timeHalfMarathon) }}</strong>
                <span>Maratona</span><strong>{{ fmtTime(racePred.timeMarathon) }}</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ============ SONO ============ -->
      <section v-show="activeTab === 'sleep'" class="section">
        <h2 class="section-title">Sono</h2>
        <div class="chart-box">
          <SleepChart :sleep="data.sleep" />
        </div>
        <div class="sleep-stats" v-if="sleepStats">
          <div class="stat-item"><span>Média de sono</span><strong>{{ fmtHours(sleepStats.total_h) }}</strong></div>
          <div class="stat-item"><span>Média sono profundo</span><strong>{{ fmtHours(sleepStats.deep_h) }}</strong></div>
          <div class="stat-item"><span>Média sono leve</span><strong>{{ fmtHours(sleepStats.light_h) }}</strong></div>
          <div class="stat-item"><span>Média REM</span><strong>{{ fmtHours(sleepStats.rem_h) }}</strong></div>
        </div>
      </section>

      <!-- ============ FREQUÊNCIA CARDÍACA ============ -->
      <section v-show="activeTab === 'hr'" class="section">
        <h2 class="section-title">Frequência Cardíaca</h2>
        <div class="chart-box">
          <HeartRateChart :heart-rates="data.heart_rates" />
        </div>
        <div class="chart-box" style="margin-top:1.5rem">
          <h3 class="sub-title">HRV Noturno</h3>
          <HRVChart :hrv="data.hrv" />
        </div>
      </section>

      <!-- ============ PASSOS ============ -->
      <section v-show="activeTab === 'steps'" class="section">
        <h2 class="section-title">Passos & Distância</h2>
        <div class="chart-box">
          <StepsChart :daily-steps="data.steps_daily" :weekly-steps="data.steps_weekly" />
        </div>
      </section>

      <!-- ============ INTENSIDADE ============ -->
      <section v-show="activeTab === 'intensity'" class="section">
        <h2 class="section-title">Minutos de Intensidade Semanal</h2>
        <div class="chart-box">
          <IntensityChart :weekly="data.intensity_weekly" />
        </div>
      </section>

      <!-- ============ ATIVIDADES ============ -->
      <section v-show="activeTab === 'activities'" class="section">
        <h2 class="section-title">Atividades Recentes</h2>
        <ActivitiesTable :activities="data.activities" />
      </section>

      <!-- ============ ESTRESSE ============ -->
      <section v-show="activeTab === 'stress'" class="section">
        <h2 class="section-title">Estresse & Body Battery</h2>
        <div class="chart-box">
          <StressChart :stress-daily="data.stress_daily" />
        </div>
      </section>

      <!-- ============ PMC ============ -->
      <section v-show="activeTab === 'pmc'" class="section">
        <h2 class="section-title">PMC — Gestão de Performance</h2>
        <div class="chart-box">
          <PMCChart :pmc="data.pmc" />
        </div>
      </section>

      <!-- ============ CORRIDA ============ -->
      <section v-show="activeTab === 'corrida'" class="section">
        <h2 class="section-title">Análise de Corrida</h2>
        <div class="chart-box">
          <RunningZones :activities="data.activities" />
        </div>
        <div class="chart-box" style="margin-top:1.5rem">
          <PaceEvolution :activities="data.activities" />
        </div>
      </section>

      <!-- ============ EFICIÊNCIA ============ -->
      <section v-show="activeTab === 'eficiencia'" class="section">
        <h2 class="section-title">Eficiência & Sono × Performance</h2>
        <div class="chart-box">
          <RunningEconomy :ef-monthly="data.ef_monthly" />
        </div>
      </section>

    </div><!-- /content -->
      </div><!-- /main-area -->
    </div><!-- /app-body -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import MetricCard from './components/MetricCard.vue'
import SleepChart from './components/SleepChart.vue'
import HeartRateChart from './components/HeartRateChart.vue'
import HRVChart from './components/HRVChart.vue'
import StepsChart from './components/StepsChart.vue'
import IntensityChart from './components/IntensityChart.vue'
import ActivitiesTable from './components/ActivitiesTable.vue'
import StressChart from './components/StressChart.vue'
import PMCChart from './components/PMCChart.vue'
import RunningZones from './components/RunningZones.vue'
import RunningEconomy from './components/RunningEconomy.vue'
import PaceEvolution from './components/PaceEvolution.vue'

const data = ref(null)
const loading = ref(true)
const error = ref(null)
const activeTab = ref('overview')
const menuOpen = ref(false)

function selectTab(id) {
  activeTab.value = id
  menuOpen.value = false
}

const tabs = [
  { id: 'overview', icon: '📊', label: 'Visão Geral' },
  { id: 'sleep', icon: '😴', label: 'Sono' },
  { id: 'hr', icon: '❤️', label: 'FC & HRV' },
  { id: 'steps', icon: '👟', label: 'Passos' },
  { id: 'intensity', icon: '⚡', label: 'Intensidade' },
  { id: 'stress', icon: '🧘', label: 'Estresse' },
  { id: 'activities', icon: '🏃', label: 'Atividades' },
  { id: 'pmc', icon: '🏋️', label: 'PMC' },
  { id: 'corrida', icon: '🚀', label: 'Corrida' },
  { id: 'eficiencia', icon: '📈', label: 'Eficiência' },
]

onMounted(async () => {
  try {
    const dataUrl = import.meta.env.VITE_GARMIN_DATA_URL || '/garmin_data.json'
    const res = await fetch(dataUrl)
    data.value = await res.json()
  } catch (e) {
    error.value = 'Erro ao carregar garmin_data_30.json: ' + e.message
  } finally {
    loading.value = false
  }
})

const summary = computed(() => data.value?.user_summary ?? {})
const racePred = computed(() => data.value?.race_predictions ?? null)
const vo2max = computed(() => data.value?.vo2max ?? null)
const fitnessAge = computed(() => data.value?.fitness_age ?? null)
const todayDate = computed(() => {
  const d = data.value?._meta?.period_end
  return d ? new Date(d).toLocaleDateString('pt-BR', { weekday:'long', day:'2-digit', month:'long', year:'numeric' }) : ''
})
const stepsProgress = computed(() => {
  const s = summary.value
  if (!s.totalSteps || !s.dailyStepGoal) return null
  return Math.min(100, Math.round((s.totalSteps / s.dailyStepGoal) * 100))
})
const sleepStats = computed(() => data.value?.sleep_avg ?? null)

function fmt(n) { return n != null ? Number(n).toLocaleString('pt-BR') : '-' }
function fmtTime(secs) {
  if (!secs) return '-'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  return h > 0 ? `${h}h${String(m).padStart(2,'0')}m${String(s).padStart(2,'0')}s` : `${m}m${String(s).padStart(2,'0')}s`
}
function fmtHours(h) {
  if (h == null) return '-'
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  return `${hh}h ${mm}min`
}
function stressColor(val) {
  if (!val) return '#64748b'
  if (val < 26) return '#10b981'
  if (val < 51) return '#eab308'
  if (val < 76) return '#f97316'
  return '#ef4444'
}
</script>

<style scoped>
.dashboard { min-height: 100vh; display: flex; flex-direction: column; }

/* ── App body (sidebar + main) ─────────────────────────── */
.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Sidebar (desktop only) ─────────────────────────── */
.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: #13151f;
  border-right: 1px solid #2d3748;
  display: flex;
  flex-direction: column;
  padding: 0.75rem 0;
  gap: 2px;
  position: sticky;
  top: 0;
  height: calc(100vh - 72px); /* subtrair altura do header */
  overflow-y: auto;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: transparent;
  border: none;
  color: #94a3b8;
  padding: 0.65rem 1.1rem;
  cursor: pointer;
  font-size: 0.875rem;
  text-align: left;
  border-radius: 8px;
  margin: 0 0.4rem;
  transition: background 0.15s, color 0.15s;
  width: calc(100% - 0.8rem);
}
.sidebar-item:hover { background: #1e2235; color: #e2e8f0; }
.sidebar-item.active {
  background: #1e3a8a;
  color: #fff;
  font-weight: 600;
}
.sidebar-icon { font-size: 1.1rem; width: 1.4rem; text-align: center; flex-shrink: 0; }
.sidebar-label { flex: 1; }

/* ── Área principal ──────────────────────────────────── */
.main-area {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 2rem;
  background: linear-gradient(135deg, #1a1d2e 0%, #0f1117 100%);
  border-bottom: 1px solid #2d3748;
}
.header-left { display: flex; align-items: center; gap: 1rem; }
.logo { font-size: 2.5rem; }
h1 { font-size: 1.5rem; font-weight: 700; color: #fff; }
.subtitle { font-size: 0.85rem; color: #94a3b8; margin-top: 2px; }
.today-badge { text-align: right; }
.today-label { display: block; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
.today-date { font-size: 0.9rem; color: #94a3b8; }

.loading {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 60vh; gap: 1rem; color: #94a3b8;
}
.spinner {
  width: 48px; height: 48px;
  border: 4px solid #2d3748;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error { padding: 2rem; color: #ef4444; text-align: center; }

.content { padding: 0 1.5rem 2rem; }

/* ── Navbar hamburger (mobile only) ────────────────────── */
/* Oculto no desktop; só aparece em @media mobile abaixo */
.navbar { display: none; }

/* ── Navbar hamburger styles (usados quando .navbar está visível no mobile) */
.navbar-inner {
  position: relative;
  margin-bottom: 1.5rem;
  z-index: 100;
}

.nav-current {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 10px;
  padding: 0.75rem 1.1rem;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.nav-current:hover { background: #1e2235; }

.nav-active-label {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e2e8f0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Hamburguer icon */
.hamburger {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 22px;
  flex-shrink: 0;
}
.hamburger span {
  display: block;
  height: 2px;
  background: #94a3b8;
  border-radius: 2px;
  transition: all 0.25s;
  transform-origin: center;
}
.hamburger.open span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.hamburger.open span:nth-child(2) { opacity: 0; transform: scaleX(0); }
.hamburger.open span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

/* Dropdown */
.nav-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  animation: dropIn 0.15s ease;
}
@keyframes dropIn {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 1px solid #0f1117;
  color: #94a3b8;
  padding: 0.75rem 1.1rem;
  cursor: pointer;
  font-size: 0.9rem;
  text-align: left;
  transition: background 0.15s, color 0.15s;
}
.nav-item:last-child { border-bottom: none; }
.nav-item:hover { background: #1e2235; color: #e2e8f0; }
.nav-item.active {
  background: #1e3a8a;
  color: #fff;
  font-weight: 600;
}
.nav-item-icon { font-size: 1.1rem; width: 1.5rem; text-align: center; }

.section { animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.section-title { font-size: 1.25rem; font-weight: 600; color: #e2e8f0; margin-bottom: 1.25rem; }
.sub-title { font-size: 1rem; font-weight: 600; color: #94a3b8; margin-bottom: 0.75rem; }

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}

.card.wide {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 12px;
  padding: 1.25rem;
  display: flex; align-items: center; gap: 1rem;
}
.card-icon { font-size: 2rem; }
.card-label { font-size: 0.8rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.card-value { font-size: 2rem; font-weight: 700; line-height: 1.1; }
.card-sub { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }

.race-grid { display: grid; grid-template-columns: auto auto; gap: 0.25rem 1rem; font-size: 0.9rem; margin-top: 4px; }
.race-grid span { color: #94a3b8; }
.race-grid strong { color: #e2e8f0; }

.chart-box {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 12px;
  padding: 1.5rem;
}

.sleep-stats {
  display: flex; gap: 2rem; flex-wrap: wrap;
  margin-top: 1rem;
  padding: 1rem 1.5rem;
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 12px;
}
.stat-item { display: flex; flex-direction: column; gap: 2px; }
.stat-item span { font-size: 0.8rem; color: #64748b; }
.stat-item strong { font-size: 1.1rem; color: #e2e8f0; }

/* ── Responsivo Mobile ───────────────────────────────────────── */
@media (max-width: 640px) {
  .header {
    padding: 0.9rem 1rem;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  h1 { font-size: 1.1rem; }
  .logo { font-size: 1.8rem; }
  .subtitle { font-size: 0.75rem; }
  .today-badge { display: none; }

  /* Esconde sidebar, mostra hamburger */
  .sidebar { display: none; }
  .navbar {
    display: block;
    position: relative;
    margin-bottom: 1rem;
    z-index: 100;
  }

  .main-area { overflow-y: visible; }
  .content { padding: 0 0.75rem 2rem; }

  .cards-grid {
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
  }

  .card.wide {
    padding: 0.9rem;
    gap: 0.6rem;
  }
  .card-icon { font-size: 1.5rem; }
  .card-value { font-size: 1.4rem; }

  .chart-box { padding: 1rem 0.75rem; }

  .section-title { font-size: 1rem; }
  .sub-title { font-size: 0.9rem; }

  .sleep-stats {
    gap: 1rem;
    padding: 0.75rem 1rem;
  }
}
</style>
