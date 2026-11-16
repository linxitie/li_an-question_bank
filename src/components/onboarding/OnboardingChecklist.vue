<template>
  <section v-if="state.ready && !allDone" class="onb">
    <header class="onb__head">
      <div>
        <p class="onb__title">开始用起来</p>
        <p class="onb__sub">完成这三步，小智才有东西可帮你排</p>
      </div>
      <span class="onb__count">{{ doneCount }}/3</span>
    </header>

    <ol class="onb__steps">
      <li v-for="s in steps" :key="s.key" class="onb__step" :class="{ done: s.done }">
        <span class="onb__dot">{{ s.done ? '✓' : s.index }}</span>
        <div class="onb__body">
          <p class="onb__label">{{ s.label }}</p>
          <p class="onb__desc">{{ s.desc }}</p>
        </div>
        <button v-if="!s.done" class="onb__go" @click="go(s.path)">{{ s.cta }}</button>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'

const state = reactive({
  ready: false,
  hasProfile: false,
  hasPlan: false,
  focusSessions: 0,
})

const steps = computed(() => [
  {
    key: 'profile',
    index: 1,
    label: '完成备考画像',
    desc: '6 个问题，决定方案怎么排',
    done: state.hasProfile,
    cta: '去填写',
    path: '/profile-quiz',
  },
  {
    key: 'plan',
    index: 2,
    label: '生成备考方案',
    desc: '按画像排出阶段与每日任务',
    done: state.hasPlan,
    cta: '去生成',
    path: '/study-plan',
  },
  {
    key: 'focus',
    index: 3,
    label: '开始第一次专注',
    desc: '右下角番茄钟，25 分钟就够',
    done: state.focusSessions > 0,
    cta: '去专注',
    path: '/home',
  },
])

const doneCount = computed(() => steps.value.filter((s) => s.done).length)
const allDone = computed(() => doneCount.value === 3)

function token() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

function go(path) {
  location.hash = '#' + path
}

onMounted(async () => {
  const t = token()
  if (!t) { state.ready = true; return }
  const H = { Authorization: 'Bearer ' + t }
  try {
    const [p, pl, f] = await Promise.all([
      fetch('/api/profile', { headers: H }),
      fetch('/api/plan/current', { headers: H }),
      fetch('/api/v1/growth/focus/heatmap?weeks=8', { headers: H }),
    ])
    const pd = await p.json()
    state.hasProfile = !!(pd && pd.has_profile !== false)
    const pld = await pl.json()
    state.hasPlan = !!(pld && pld.has_plan)
    const fd = await f.json()
    state.focusSessions = fd.session_count || 0
  } catch (e) { /* 静默：拿不到就按未完成展示 */ }
  finally { state.ready = true }
})
</script>

<style scoped>
.onb {
  grid-column: 1 / -1;
  padding: 16px 18px; border-radius: 12px;
  background: linear-gradient(135deg, #f7f9ff, #ffffff);
  border: 1px solid #e3e9fb;
}
.onb__head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 12px; }
.onb__title { margin: 0; font-size: 14px; font-weight: 700; color: #1a2b5f; }
.onb__sub { margin: 3px 0 0; font-size: 11.5px; color: #8a8faa; }
.onb__count { font-size: 12px; font-weight: 700; color: #c41e3a; }
.onb__steps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.onb__step { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 10px; background: #fff; border: 1px solid #eef1f7; }
.onb__step.done { opacity: .62; }
.onb__dot { width: 22px; height: 22px; flex: 0 0 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: #fff; background: #c9d4ff; }
.onb__step.done .onb__dot { background: #10b981; }
.onb__body { flex: 1; }
.onb__label { margin: 0; font-size: 13px; font-weight: 600; color: #1a2b5f; }
.onb__desc { margin: 2px 0 0; font-size: 11.5px; color: #8a8faa; }
.onb__go { border: 1px solid #dbe2ff; background: #f4f7ff; color: #3b5bdb; border-radius: 8px; padding: 6px 14px; font-size: 12px; cursor: pointer; }
.onb__go:hover { background: #e8eeff; }
@media (max-width: 900px) { .onb__step { align-items: flex-start; } }
</style>
