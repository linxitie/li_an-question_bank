<template>
  <section class="inline-quiz">
    <header class="inline-quiz__head">
      <div>
        <p class="inline-quiz__eyebrow">第 1 步 · 了解你</p>
        <h3 class="inline-quiz__title">先答 6 个问题，方案才准</h3>
      </div>
      <div class="inline-quiz__dots">
        <span v-for="(s, i) in state.steps" :key="i" class="dot"
              :class="{ done: i < state.step, active: i === state.step }"></span>
      </div>
    </header>

    <div v-if="state.loading" class="inline-quiz__skeleton"></div>

    <div v-else-if="!finished && currentField" class="inline-quiz__body">
      <p class="inline-quiz__step-title">{{ currentStep.title }}</p>

      <div class="field">
        <label class="field__label">{{ currentField.label }}</label>

        <div v-if="isChoice" class="chips">
          <button v-for="opt in currentField.options" :key="opt" type="button"
                  class="chip" :class="{ on: isOn(opt) }" @click="pick(opt)">{{ opt }}</button>
        </div>

        <input v-if="currentField.type === 'text'" class="input"
               :value="value" :placeholder="currentField.placeholder || '选填'"
               @input="setValue($event)" />

        <input v-if="currentField.type === 'date'" class="input" type="date"
               :value="value" @input="setValue($event)" />

        <textarea v-if="currentField.type === 'textarea'" class="textarea" rows="4"
                  :value="value" :placeholder="currentField.placeholder || '随便说说你的情况'"
                  @input="setValue($event)"></textarea>

        <div v-if="currentField.type === 'slider'" class="slider">
          <input type="range" :min="currentField.min || 1" :max="currentField.max || 12"
                 :value="value" @input="setValue($event)" />
          <span class="slider__val">{{ value }} 小时/天</span>
        </div>
      </div>

      <div class="inline-quiz__actions">
        <button v-if="state.step > 0" class="btn ghost" @click="prev">上一步</button>
        <button class="btn primary" :disabled="!canNext" @click="next">{{ isLast ? "保存并继续" : "下一步" }}</button>
        <button class="btn text" @click="skip">先跳过</button>
      </div>
      <p v-if="state.error" class="inline-quiz__err">{{ state.error }}</p>
    </div>

    <div v-else class="inline-quiz__done">
      <p>✅ 画像已保存，下面直接生成你的复习计划</p>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { buildSteps, initialAnswers } from '@/modules/profile-quiz/pool'

const emit = defineEmits(['done', 'skip'])

const state = reactive({
  loading: true,
  saving: false,
  step: 0,
  steps: [],
  answers: {},
  error: '',
})

const isLast = computed(() => state.step === state.steps.length - 1)
const finished = computed(() => state.step >= state.steps.length)
const currentStep = computed(() => state.steps[state.step] || { title: "", fields: [] })
const currentField = computed(() => (currentStep.value.fields || [])[0] || null)
const isChoice = computed(() => {
  const t = currentField.value && currentField.value.type
  return t === "single" || t === "multi"
})
const value = computed(() => {
  const f = currentField.value
  if (!f) return ""
  return state.answers[f.key]
})
function setValue(e) {
  const f = currentField.value
  if (!f) return
  const raw = e && e.target ? e.target.value : e
  state.answers[f.key] = f.type === "slider" ? Number(raw) : raw
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

function isOn(opt) {
  const f = currentField.value
  if (!f) return false
  const v = state.answers[f.key]
  return f.type === 'multi' ? Array.isArray(v) && v.includes(opt) : v === opt
}

function pick(opt) {
  const f = currentField.value
  if (!f) return
  if (f.type === 'multi') {
    const arr = Array.isArray(state.answers[f.key]) ? state.answers[f.key] : []
    const i = arr.indexOf(opt)
    if (i >= 0) arr.splice(i, 1)
    else arr.push(opt)
    state.answers[f.key] = arr
  } else {
    state.answers[f.key] = opt
  }
}

const canNext = computed(() => {
  const step = state.steps[state.step]
  if (!step) return false
  return step.fields.every((f) => {
    const v = state.answers[f.key]
    if (f.type === 'multi') return Array.isArray(v) && v.length > 0
    if (f.type === 'slider') return Number(v) > 0
    return !!String(v || '').trim()
  })
})

function next() {
  if (!isLast.value) { state.step += 1; return }
  submit()
}

function prev() {
  if (state.step > 0) state.step -= 1
}

function skip() {
  emit('skip')
}

async function submit() {
  state.saving = true
  state.error = ''
  try {
    const token = getToken()
    const res = await fetch('/api/profile/upsert', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
      },
      body: JSON.stringify({ ...state.answers, profile_status: 1 }),
    })
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.detail || '保存失败')
    }
    state.step = state.steps.length
    emit('done', { ...state.answers })
  } catch (e) {
    state.error = e.message || '保存失败，请重试'
  } finally {
    state.saving = false
  }
}

onMounted(() => {
  state.steps = buildSteps({ seed: String(Date.now()) + Math.random() })
  state.answers = initialAnswers(state.steps)
  state.loading = false
})
</script>

<style scoped>
.inline-quiz {
  margin: 0 0 18px;
  padding: 18px 20px;
  border-radius: 18px;
  background: linear-gradient(140deg, #ffffff, #f6f8ff);
  border: 1px solid #e6ecfa;
}
.inline-quiz__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.inline-quiz__eyebrow { margin: 0; font-size: 11px; font-weight: 700; letter-spacing: 0.08em; color: #2563eb; }
.inline-quiz__title { margin: 4px 0 0; font-size: 16px; font-weight: 700; color: #111827; }
.inline-quiz__dots { display: flex; gap: 6px; padding-top: 6px; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #e5e7eb; transition: all 200ms ease; }
.dot.done { background: #93c5fd; }
.dot.active { background: #2563eb; transform: scale(1.35); }

.inline-quiz__body { margin-top: 14px; animation: slideIn 260ms cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes slideIn { from { opacity: 0; transform: translateX(18px); } to { opacity: 1; transform: none; } }

.inline-quiz__step-title { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #374151; }
.field { margin-bottom: 14px; }
.field__label { display: block; margin-bottom: 8px; font-size: 13px; color: #4b5563; }

.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  padding: 7px 14px; border-radius: 999px; border: 1px solid #e5e7eb;
  background: #fff; font-size: 12.5px; color: #4b5563; cursor: pointer; transition: all 150ms ease;
}
.chip.on { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; font-weight: 600; }

.input, .textarea {
  width: 100%; padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 10px;
  font-size: 13px; outline: none; background: #fff; color: #111827;
}
.input:focus, .textarea:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }
.textarea { resize: vertical; line-height: 1.6; }

.slider { display: flex; align-items: center; gap: 12px; }
.slider input { flex: 1; }
.slider__val { font-size: 12px; color: #2563eb; font-weight: 600; white-space: nowrap; }

.inline-quiz__actions { display: flex; gap: 10px; margin-top: 6px; }
.btn { padding: 9px 18px; border-radius: 10px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; }
.btn.primary:disabled { background: #c7d2fe; cursor: not-allowed; }
.btn.ghost { background: #f3f4f6; color: #374151; }
.btn.text { background: none; color: #9ca3af; }

.inline-quiz__err { margin: 8px 0 0; font-size: 12px; color: #b91c1c; }
.inline-quiz__done { margin-top: 12px; font-size: 13px; color: #059669; }

.inline-quiz__skeleton { height: 120px; border-radius: 12px; background: #eef1f7; }

@media (prefers-reduced-motion: reduce) {
  .inline-quiz__body { animation: none; }
  .dot { transition: none; }
}
</style>