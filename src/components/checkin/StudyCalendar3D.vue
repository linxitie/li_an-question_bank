<template>
  <div class="cal3d">
    <div class="cal3d__head">
      <span class="cal3d__month">{{ year }} 年 {{ month + 1 }} 月</span>
      <span class="cal3d__streak">连续 {{ state.streak }} 天</span>
    </div>

    <div class="cal3d__weekdays">
      <span v-for="w in ['一','二','三','四','五','六','日']" :key="w">{{ w }}</span>
    </div>

    <div class="cal3d__grid">
      <div v-for="n in leading" :key="'e' + n" class="cal3d__cell cal3d__cell--empty"></div>

      <div
        v-for="d in daysInMonth"
        :key="d"
        class="cal3d__cell"
        :class="{
          'is-signed': isSigned(d),
          'is-today': isToday(d),
          'is-future': isFuture(d),
        }"
      >
        <div class="cal3d__flip">
          <div class="cal3d__front">{{ d }}</div>
          <div class="cal3d__back">{{ isSigned(d) ? '✓' : '' }}</div>
        </div>
      </div>
    </div>

    <div class="cal3d__foot">
      <span v-if="state.checkedIn">今日已签到</span>
      <span v-else>今天还没签，点上面那块去签</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'

const today = new Date()
const year = today.getFullYear()
const month = today.getMonth()

const state = reactive({
  streak: 0,
  checkedIn: false,
  ready: false,
})

const daysInMonth = computed(() => new Date(year, month + 1, 0).getDate())
const leading = computed(() => {
  // 周一为一周第一天
  const firstDay = new Date(year, month, 1).getDay()
  return (firstDay + 6) % 7
})

function isToday(d) {
  return d === today.getDate()
}
function isFuture(d) {
  return d > today.getDate()
}
function isSigned(d) {
  if (!state.streak) return false
  // 连续天数从「今天或昨天」往前推
  const anchor = state.checkedIn ? today.getDate() : today.getDate() - 1
  return d <= anchor && d > anchor - state.streak
}

function getToken() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) {
      const o = JSON.parse(raw)
      if (o && o.token) return o.token
    }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

async function load() {
  const token = getToken()
  if (!token) { state.ready = true; return }
  try {
    const res = await fetch('/api/v1/growth/checkin/status', {
      headers: { Authorization: 'Bearer ' + token },
    })
    const data = await res.json()
    state.streak = data.continuous_days || 0
    state.checkedIn = !!data.checked_in
  } catch (e) { /* 静默降级为空日历 */ }
  finally { state.ready = true }
}

onMounted(load)
</script>

<style scoped>
.cal3d {
  padding: 16px;
  border-radius: 18px;
  background: linear-gradient(160deg, #ffffff, #f5f7ff);
  border: 1px solid #e8ecf6;
  transform-style: preserve-3d;
  perspective: 900px;
}

.cal3d__head {
  display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 10px;
}
.cal3d__month { font-size: 14px; font-weight: 700; color: #111827; }
.cal3d__streak {
  font-size: 11px; font-weight: 700; color: #c41e3a;
  background: rgba(196, 30, 58, 0.08); padding: 3px 9px; border-radius: 999px;
}

.cal3d__weekdays,
.cal3d__grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
.cal3d__weekdays { margin-bottom: 6px; }
.cal3d__weekdays span { text-align: center; font-size: 10px; color: #9ca3af; }

.cal3d__cell { aspect-ratio: 1 / 1; perspective: 400px; }
.cal3d__cell--empty { visibility: hidden; }

.cal3d__flip {
  position: relative; width: 100%; height: 100%;
  transform-style: preserve-3d;
  transition: transform 420ms cubic-bezier(0.22, 1, 0.36, 1);
  border-radius: 9px;
}
.cal3d__front, .cal3d__back {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: 9px; backface-visibility: hidden;
  font-size: 12px; font-weight: 600;
}
.cal3d__front { background: #fff; color: #9ca3af; border: 1px solid #eef1f7; }
.cal3d__back {
  transform: rotateY(180deg);
  background: linear-gradient(135deg, #c41e3a, #e2556c);
  color: #fff; font-size: 13px;
}

/* 已签到：翻到背面 */
.is-signed .cal3d__flip { transform: rotateY(180deg); }

/* 今天：立体抬起 */
.is-today .cal3d__flip {
  transform: translateZ(6px) scale(1.04);
  box-shadow: 0 6px 16px rgba(196, 30, 58, 0.18);
}
.is-today.is-signed .cal3d__flip {
  transform: rotateY(180deg) translateZ(6px) scale(1.04);
}
.is-today .cal3d__front { border-color: #c41e3a; color: #c41e3a; }

.is-future .cal3d__front { color: #d1d5db; border-style: dashed; }

.cal3d__foot { margin-top: 10px; font-size: 11px; color: #9ca3af; text-align: center; }

@media (prefers-reduced-motion: reduce) {
  .cal3d__flip { transition: none; }
}
</style>
