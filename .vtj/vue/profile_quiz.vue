<!-- 模块4 v2 - 备考画像问卷向导（引导式/多样式/交互式） -->
<template>
  <div class="quiz-page">
    <!-- 顶部 -->
    <div class="quiz-hero">
      <div class="quiz-hero-bg"></div>
      <button class="quiz-skip-btn" @click="goHome">跳过，先逛逛</button>
      <div class="quiz-hero-inner">
        <div class="quiz-title-row">
          <span class="quiz-title">备考画像</span>
          <span class="quiz-badge">AI</span>
        </div>
        <div class="quiz-sub">回答几个问题，小智为你定制最优备考方案</div>
      </div>
    </div>

    <div class="quiz-body">
      <!-- 模板选择（多样式） -->
      <div v-if="!state.template" class="tpl-panel">
        <div class="tpl-title">选择你喜欢的问卷风格</div>
        <div class="tpl-grid">
          <div v-for="t in state.templates" :key="t.template_id" class="tpl-card"
               :class="{ active: state.template && state.template.template_id === t.template_id }"
               @click="selectTemplate(t.template_id)">
            <div class="tpl-name">{{ t.name }}</div>
            <div class="tpl-style">{{ styleName(t.style) }}</div>
          </div>
        </div>
        <div class="tpl-tip">风格不影响结果，选择顺手的方式即可</div>
      </div>

      <!-- 问卷向导 -->
      <div v-else class="form-card" :class="state.dir > 0 ? 'slide-next' : 'slide-prev'" :key="state.step">
        <div class="step-progress">
          <div v-for="(s, i) in state.template.steps" :key="i" class="step-dot"
               :class="{ active: i === state.step, done: i < state.step }">
            <span>{{ i < state.step ? '✓' : i + 1 }}</span>
          </div>
        </div>
        <div class="step-title">{{ state.template.steps[state.step].title }}</div>

        <div v-for="f in state.template.steps[state.step].fields" :key="f.key" class="form-item">
          <label class="form-label">{{ f.label }}</label>

          <!-- 单选 -->
          <div v-if="f.type === 'single'" class="chip-row">
            <div v-for="opt in f.options" :key="opt" class="chip"
                 :class="{ active: state.answers[f.key] === opt }"
                 @click="state.answers[f.key] = opt">{{ opt }}</div>
          </div>

          <!-- 多选 -->
          <div v-else-if="f.type === 'multi'" class="chip-row">
            <div v-for="opt in f.options" :key="opt" class="chip"
                 :class="{ active: state.answers[f.key].includes(opt) }"
                 @click="toggleMulti(f.key, opt)">{{ opt }}</div>
          </div>

          <!-- 文本 -->
          <input v-else-if="f.type === 'text'" type="text" v-model="state.answers[f.key]"
                 class="form-input" :placeholder="f.label"/>

          <!-- 长文本（自述学习情况） -->
          <textarea v-else-if="f.type === 'textarea'" v-model="state.answers[f.key]"
                    class="form-textarea" rows="5"
                    :placeholder="f.placeholder || f.label"></textarea>

          <!-- 日期 -->
          <input v-else-if="f.type === 'date'" type="date" v-model="state.answers[f.key]"
                 class="form-input"/>

          <!-- 滑杆 -->
          <div v-else-if="f.type === 'slider'" class="slider-wrap">
            <input type="range" :min="f.min" :max="f.max" step="1"
                   v-model.number="state.answers[f.key]" class="slider"/>
            <div class="slider-val">{{ state.answers[f.key] }} 小时/天</div>
          </div>
        </div>

        <!-- 操作提示 -->
        <div v-if="state.notice" class="notice-bar">{{ state.notice }}</div>

        <div class="step-actions">
          <button v-if="state.step > 0" class="btn ghost" @click="prevStep">上一步</button>
          <button v-else class="btn ghost" @click="state.template = null">换风格</button>
          <button class="btn ghost" @click="reshuffle">换一批问题</button>
          <button v-if="!isLastStep" class="btn primary" :disabled="!canNext" @click="nextStep">下一步</button>
          <button v-else class="btn primary" :disabled="state.saving" @click="submit">
            {{ state.saving ? '保存中…' : '生成我的备考方案' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, onMounted } from 'vue'
import { buildSteps, initialAnswers } from '@/modules/profile-quiz/pool'

const state = reactive({
  templates: [],
  template: null,
  step: 0,
  dir: 1,
  seed: '',
  answers: {},
  loading: false,
  saving: false,
  notice: '',
})

const styleName = (s) => ({ card: '极简卡片 · 快速完成', chat: '沉浸问答 · 像聊天一样', diagnose: '专业诊断 · 数据更全' }[s] || s)

const isLastStep = computed(() => state.step === state.template.steps.length - 1)

const canNext = computed(() => {
  const fields = state.template.steps[state.step].fields
  return fields.every((f) => {
    const v = state.answers[f.key]
    if (f.type === 'multi') return v.length > 0
    if (f.type === 'slider') return v > 0
    return !!v
  })
})

function toggleMulti(key, opt) {
  const arr = state.answers[key]
  const idx = arr.indexOf(opt)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(opt)
}

function selectTemplate(id) {
  const t = state.templates.find((x) => x.template_id === id)
  if (!t) return
  state.template = t
  state.step = 0
  state.dir = 1
  state.seed = String(Date.now()) + ':' + Math.random().toString(36).slice(2)
  // 动态问题池：每次进入换一批问法，避免“问题单一”
  const dynamic = buildSteps({ seed: state.seed })
  if (dynamic.length) t.steps = dynamic
  state.answers = {}
  t.steps.forEach((s) => {
    s.fields.forEach((f) => {
      state.answers[f.key] = f.type === 'multi' ? [] : (f.type === 'slider' ? (f.min ?? 1) : '')
    })
  })
}

function prevStep() {
  if (state.step > 0) { state.dir = -1; state.step -= 1 }
}

function nextStep() {
  if (!isLastStep.value) { state.dir = 1; state.step += 1 }
}

/** 换一批问题：问法轮换，已答内容保留 */
function reshuffle() {
  if (!state.template) return
  state.seed = String(Date.now()) + ':' + Math.random().toString(36).slice(2)
  const dynamic = buildSteps({ seed: state.seed })
  if (dynamic.length) state.template.steps = dynamic
  state.step = 0
  state.dir = 1
}

function goHome() {
  // /question_bank 路由不存在（根路径 '/' 才是题库页），此前点「跳过」会跳空白
  location.hash = '#/home'
}

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

async function loadTemplates() {
  state.loading = true
  try {
    const token = getToken()
    const res = await fetch('/api/profile/questions', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    const data = await res.json()
    state.templates = data.templates || []
    if (state.templates.length) selectTemplate(state.templates[0].template_id)
  } catch (e) {
    state.notice = '问卷加载失败，请稍后重试'
  } finally {
    state.loading = false
  }
}

async function submit() {
  state.saving = true
  state.notice = ''
  try {
    const token = getToken()
    const res = await fetch('/api/profile/upsert', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ ...state.answers, profile_status: 1 }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '保存失败')
    }
    location.hash = '#/study-plan'
  } catch (e) {
    state.notice = e.message || '保存失败，请重试'
  } finally {
    state.saving = false
  }
}

onMounted(loadTemplates)
</script>

<style scoped>
.quiz-page { min-height: 100vh; background: #f5f7fa; padding-bottom: 40px; }
.quiz-hero { position: relative; overflow: hidden; padding: 40px 20px 60px; background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 60%, #3b82f6 100%); border-radius: 0 0 28px 28px; }
.quiz-hero-bg { position: absolute; right: -40px; top: -60px; width: 220px; height: 220px; border-radius: 50%; background: rgba(255,255,255,0.08); }
.quiz-skip-btn { position: absolute; top: 16px; right: 16px; padding: 6px 14px; border-radius: 16px; background: rgba(255,255,255,0.15); color: #fff; border: 1px solid rgba(255,255,255,0.3); font-size: 12px; cursor: pointer; z-index: 10; }
.quiz-skip-btn:hover { background: rgba(255,255,255,0.25); }
.quiz-hero-inner { position: relative; }
.quiz-title-row { display: flex; align-items: center; gap: 10px; }
.quiz-title { font-size: 24px; font-weight: 700; color: #fff; }
.quiz-badge { font-size: 12px; padding: 2px 8px; border-radius: 8px; background: rgba(255,255,255,0.2); color: #fff; }
.quiz-sub { margin-top: 8px; font-size: 14px; color: rgba(255,255,255,0.85); }

.quiz-body { max-width: 560px; margin: -30px auto 0; padding: 0 16px; position: relative; }

.tpl-panel { background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 4px 16px rgba(30,58,138,0.08); }
.tpl-title { font-size: 16px; font-weight: 600; margin-bottom: 14px; }
.tpl-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.tpl-card { padding: 14px 10px; border: 2px solid #e5e7eb; border-radius: 12px; text-align: center; cursor: pointer; transition: all .2s; }
.tpl-card.active, .tpl-card:hover { border-color: #2563eb; background: #eff6ff; }
.tpl-name { font-size: 13px; font-weight: 600; color: #1f2937; }
.tpl-style { margin-top: 4px; font-size: 11px; color: #6b7280; }
.tpl-tip { margin-top: 12px; font-size: 12px; color: #9ca3af; text-align: center; }

.form-card { background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 4px 16px rgba(30,58,138,0.08); }
.step-progress { display: flex; gap: 8px; margin-bottom: 16px; }
.step-dot { width: 26px; height: 26px; border-radius: 50%; background: #e5e7eb; color: #9ca3af; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; }
.step-dot.active { background: #2563eb; color: #fff; }
.step-dot.done { background: #16a34a; color: #fff; }
.step-title { font-size: 17px; font-weight: 700; margin-bottom: 16px; color: #1f2937; }

.form-item { margin-bottom: 18px; }
.form-label { display: block; font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; }
.form-input { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 14px; box-sizing: border-box; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { padding: 8px 14px; border-radius: 20px; border: 1.5px solid #d1d5db; font-size: 13px; color: #374151; cursor: pointer; transition: all .15s; }
.chip.active { border-color: #2563eb; background: #eff6ff; color: #2563eb; font-weight: 600; }
.slider-wrap { display: flex; align-items: center; gap: 12px; }
.slider { flex: 1; }
.slider-val { min-width: 70px; font-size: 14px; color: #2563eb; font-weight: 600; }

.notice-bar { margin-bottom: 12px; padding: 8px 12px; background: #fff3f3; color: #c8161e; border-radius: 8px; font-size: 12px; }
.step-actions { display: flex; gap: 12px; margin-top: 8px; }
.btn { flex: 1; padding: 12px; border-radius: 12px; font-size: 15px; font-weight: 600; border: none; cursor: pointer; transition: all .2s; }
.btn.primary { background: #2563eb; color: #fff; }
.btn.primary:disabled { background: #93c5fd; cursor: not-allowed; }
.btn.ghost { background: #f3f4f6; color: #374151; }
</style>

<style scoped>
/* ---- 动态过渡：卡片滑动进场（参考多邻国/百词斩的节奏） ---- */
.form-card { will-change: transform, opacity; }
.form-card.slide-next { animation: slideNext 260ms cubic-bezier(0.22, 1, 0.36, 1) both; }
.form-card.slide-prev { animation: slidePrev 260ms cubic-bezier(0.22, 1, 0.36, 1) both; }

@keyframes slideNext {
  from { opacity: 0; transform: translateX(28px) scale(0.985); }
  to   { opacity: 1; transform: translateX(0) scale(1); }
}
@keyframes slidePrev {
  from { opacity: 0; transform: translateX(-28px) scale(0.985); }
  to   { opacity: 1; transform: translateX(0) scale(1); }
}

.step-dot.done { animation: pop 220ms ease-out both; }
@keyframes pop {
  0% { transform: scale(1); }
  50% { transform: scale(1.16); }
  100% { transform: scale(1); }
}

/* 长文本（自述学习情况） */
.form-textarea {
  width: 100%;
  min-height: 120px;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  color: #111827;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}
.form-textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

@media (prefers-reduced-motion: reduce) {
  .form-card.slide-next,
  .form-card.slide-prev,
  .step-dot.done { animation: none; }
}
</style>

