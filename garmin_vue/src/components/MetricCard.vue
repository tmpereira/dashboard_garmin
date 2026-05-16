<template>
  <div class="metric-card" :style="{ borderLeftColor: color }">
    <div class="mc-icon">{{ icon }}</div>
    <div class="mc-body">
      <div class="mc-label">{{ label }}</div>
      <div class="mc-value" :style="{ color }">{{ value }}</div>
      <div class="mc-sub">{{ sub }}</div>
      <div v-if="progress != null" class="progress-bar">
        <div class="progress-fill" :style="{ width: progress + '%', background: color }"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: String,
  label: String,
  value: [String, Number],
  sub: String,
  color: { type: String, default: '#3b82f6' },
  progress: { type: Number, default: null },
})
</script>

<style scoped>
.metric-card {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-left: 4px solid;
  border-radius: 10px;
  padding: 1rem 1.25rem;
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  transition: transform 0.15s;
}
.metric-card:hover { transform: translateY(-2px); }
.mc-icon { font-size: 1.8rem; line-height: 1; }
.mc-body { flex: 1; min-width: 0; }
.mc-label { font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
.mc-value { font-size: 1.6rem; font-weight: 700; line-height: 1.1; }
.mc-sub { font-size: 0.78rem; color: #94a3b8; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.progress-bar { height: 4px; background: #2d3748; border-radius: 2px; margin-top: 8px; }
.progress-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
</style>
