<template>
  <section v-if="state.loading || state.hasPlan || state.error" class="plan-card" :class="'plan-card--' + variant" @click="open">
    <div class="plan-card__head">
      <span class="plan-card__title">备考方案</span>
      <span v-if="state.hasPlan" class="plan-card__left">{{ state.daysLeft }} 天</span>
    </div>

    <!-- 加载 -->
    <div v-if="state.loading" class="plan-card__skeleton"></div>

    <!-- 出错 -->
    <div v-else-if="state.error" class="plan-card__empty">
      方案加载失败，点此重试
    </div>

    <!-- 有方案 -->
    <template v-else>
      <p class="plan-card__summary">{{ state.summary || '按你的画像生成的备考路线' }}</p>
      <div class="plan-card__bar">
        <div class="plan-card__bar-fill" :style="{ width: state.percent + '%' }"></div>
      </div>
      <div class="plan-card__meta">
        <span>今日 {{ state.done }}/{{ state.total }}</span>
        <span class="plan-card__pct">{{ state.percent }}%</span>
      </div>
    </template>
  </section>

  <!-- 无方案：引导去画像 -->
  <section v-else-if="state.ready" class="plan-card plan-card--empty" @click="goQuiz">
    <div class="plan-card__head">
      <span class="plan-card__title">还没有备考方案</span>
    </div>
    <p class="plan-card__summary">答完 6 步画像，小智给你排一条路</p>
    <button class="plan-card__cta">开始画像</button>
  </section>
</template>

<script setup>
import { reactive, onMounted } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'home' },
})

const state = reactive({
  loading: true,
  ready: false,
  error: '',
  hasPlan: false,
  summary: '',
  daysLeft: 0,
  done: 0,
  total: 0,
  percent: 0,
})

function getToken() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) {
      const obj = JSON.parse(raw)
      if (obj && obj.token) return obj.token
    }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

async function load() {
  state.loading = true
  state.error = ''
  try {
    const token = getToken()
    const res = await fetch('/api/plan/current', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const data = await res.json()
    state.hasPlan = !!data.has_plan
    state.summary = data.summary || ''
    state.daysLeft = data.days_left || 0
    state.done = data.progress?.done || 0
    state.total = data.progress?.total || 0
    state.percent = data.progress?.percent || 0
  } catch (e) {
    state.error = e.message || '加载失败'
  } finally {
    state.loading = false
    state.ready = true
  }
}

function open() {
  if (state.error) { load(); return }
  if (!state.hasPlan) { goQuiz(); return }
  location.hash = '#/study-plan'
}

function goQuiz() {
  location.hash = '#/profile-quiz'
}

onMounted(load)
</script>

<style scoped>
.plan-card {
  margin: 12px 0;
  padding: 16px 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #ffffff 0%, #f6f8ff 100%);
  border: 1px solid #e6ebf7;
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.plan-card:active { transform: scale(0.99); }
.plan-card:hover { box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08); }

.plan-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.plan-card__title { font-size: 15px; font-weight: 700; color: #111827; }
.plan-card__left {
  font-size: 12px;
  font-weight: 600;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.08);
  padding: 3px 10px;
  border-radius: 999px;
}
.plan-card__summary {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #6b7280;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plan-card__bar {
  height: 6px;
  border-radius: 999px;
  background: #eef1f8;
  overflow: hidden;
}
.plan-card__bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb, #60a5fa);
  transition: width 400ms cubic-bezier(0.22, 1, 0.36, 1);
}
.plan-card__meta {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}
.plan-card__pct { color: #2563eb; font-weight: 600; }

.plan-card__skeleton {
  height: 46px;
  border-radius: 10px;
  background: linear-gradient(90deg, #eef1f7 25%, #f7f9fd 37%, #eef1f7 63%);
  background-size: 400% 100%;
  animation: shimmer 1.2s infinite linear;
}
@keyframes shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}

.plan-card__empty { color: #6b7280; }
.plan-card__cta {
  margin-top: 10px;
  padding: 9px 18px;
  border: none;
  border-radius: 12px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

@media (prefers-reduced-motion: reduce) {
  .plan-card__skeleton { animation: none; }
  .plan-card__bar-fill { transition: none; }
}
</style>
