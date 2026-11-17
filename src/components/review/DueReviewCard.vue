<template>
  <!-- 没有错题时也要给引导，否则用户根本不知道有复习功能 -->
  <section v-if="state.ready && state.total === 0" class="due-review due-review--empty">
    <div class="due-review__main">
      <div class="due-review__icon">🔁</div>
      <div class="due-review__text">
        <p class="due-review__title">遗忘曲线复习</p>
        <p class="due-review__sub">答题后错题会自动排进复习计划，这里会提醒你哪天该看哪道</p>
      </div>
    </div>
    <button class="due-review__cta ghost" @click="goPractice">去刷题</button>
  </section>

  <section v-else-if="state.ready && state.total > 0" class="due-review">
    <div class="due-review__main">
      <div class="due-review__icon">🔁</div>
      <div class="due-review__text">
        <p class="due-review__title">
          今日待复习 <strong>{{ state.dueToday }}</strong> 题
        </p>
        <p class="due-review__sub">
          7 天内到期 {{ state.due7d }} 题 · 未排程 {{ state.unscheduled }} 题
        </p>
      </div>
    </div>
    <button class="due-review__cta" :disabled="state.dueToday === 0" @click="goReview">
      {{ state.dueToday > 0 ? "开始复习" : "今天清空啦" }}
    </button>
  </section>
</template>

<script setup>
import { onMounted, reactive } from "vue"

const state = reactive({
  ready: false,
  total: 0,
  dueToday: 0,
  due7d: 0,
  unscheduled: 0,
})

function getToken() {
  try {
    const raw = localStorage.getItem("__VTJ_AUTH_STATE__")
    if (raw) {
      const o = JSON.parse(raw)
      if (o && o.token) return o.token
    }
  } catch (e) { /* ignore */ }
  return localStorage.getItem("token") || ""
}

async function load() {
  const token = getToken()
  if (!token) { state.ready = true; return }
  try {
    const res = await fetch("/api/v1/growth/review/summary", {
      headers: { Authorization: "Bearer " + token },
    })
    const d = await res.json()
    state.total = d.total || 0
    state.dueToday = d.due_today || 0
    state.due7d = d.due_7d || 0
    state.unscheduled = d.unscheduled || 0
  } catch (e) { /* 静默 */ }
  finally { state.ready = true }
}

function goPractice() {
  location.hash = "#/question-bank"
}

function goReview() {
  location.hash = "#/wrong-questions"
}

onMounted(load)
</script>

<style scoped>
.due-review {
  display: flex; align-items: center; justify-content: space-between; gap: 14px;
  margin: 0 0 14px; padding: 14px 18px; border-radius: 16px;
  background: linear-gradient(135deg, #fff7f8, #fef2f3);
  border: 1px solid #fbd5db;
}
.due-review__main { display: flex; align-items: center; gap: 12px; }
.due-review__icon { font-size: 22px; }
.due-review__title { margin: 0; font-size: 14px; font-weight: 700; color: #9f1239; }
.due-review__title strong { color: #c41e3a; font-size: 16px; }
.due-review__sub { margin: 4px 0 0; font-size: 12px; color: #b06a76; }
.due-review__cta {
  padding: 9px 18px; border: none; border-radius: 12px;
  background: #c41e3a; color: #fff; font-size: 13px; font-weight: 700; cursor: pointer;
  transition: transform 140ms ease, opacity 140ms ease;
}
.due-review__cta:disabled { background: #f3c7cf; cursor: default; }
.due-review--empty { background: #fbfcfe; border-color: #eef1f7; }
.due-review--empty .due-review__title { color: #4b5563; }
.due-review__cta.ghost { background: #fff; color: #4d6bfe; border: 1px solid #dbe2ff; }
.due-review__cta:not(:disabled):hover { transform: translateY(-1px); }
</style>
