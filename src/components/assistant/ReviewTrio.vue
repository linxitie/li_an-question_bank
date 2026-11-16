<template>
  <div class="trio">
    <button v-if="!state.open" class="trio__trigger" @click="start">
      🎩 三顶帽子点评
    </button>

    <div v-else class="trio__board">
      <div class="trio__head">
        <span>三顶帽子 · 同题三视角</span>
        <button class="trio__close" @click="state.open = false">收起</button>
      </div>

      <div class="trio__cols">
        <section v-for="r in roles" :key="r.key" class="trio__col" :class="'is-' + r.key">
          <header class="trio__col-head">
            <span class="trio__avatar">{{ r.emoji }}</span>
            <span class="trio__role">{{ r.name }}</span>
          </header>
          <div class="trio__bubble">
            <span v-if="state.loading[r.key]" class="trio__typing">
              <i></i><i></i><i></i>
            </span>
            <p v-else-if="state.text[r.key]" class="trio__text">{{ state.text[r.key] }}</p>
            <p v-else class="trio__err">{{ state.error[r.key] || '暂无回复' }}</p>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

const props = defineProps({
  question: { type: String, default: '' },
  answer: { type: String, default: '' },
  analysis: { type: String, default: '' },
})

const roles = [
  {
    key: 'setter',
    emoji: '🧑‍🏫',
    name: '出题人',
    prompt: '你现在是出题人。只做一件事：判断考生这道题有没有答偏、考点是否抓准。2 句话以内，直接说结论，不要客套。',
  },
  {
    key: 'marker',
    emoji: '🖊️',
    name: '阅卷人',
    prompt: '你现在是阅卷人。只做一件事：指出这个答案漏掉的采分点，逐条列，最多 3 条，每条一行，不要客套。',
  },
  {
    key: 'senior',
    emoji: '🎓',
    name: '上岸学长',
    prompt: '你现在是刚上岸的学长。只做一件事：用过来人的口气说这类题当年怎么错、考场上怎么快速处理。2 句话，口语化。',
  },
]

const state = reactive({
  open: false,
  loading: { setter: false, marker: false, senior: false },
  text: { setter: '', marker: '', senior: '' },
  error: { setter: '', marker: '', senior: '' },
})

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

function buildPayload(role) {
  const ctx = [
    role.prompt,
    '',
    '【题目】',
    props.question || '（未提供题干）',
    '',
    '【考生作答】',
    props.answer || '（未提供作答）',
    '',
    '【标准解析】',
    props.analysis || '（无）',
  ].join('\n')
  return ctx
}

async function ask(role, token) {
  state.loading[role.key] = true
  state.error[role.key] = ''
  try {
    const res = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
      },
      body: JSON.stringify({
        message: buildPayload(role),
        scene: 'qa',
        persist: false,   // 一次性任务，不落会话
      }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data?.detail || data?.error?.message || 'HTTP ' + res.status)
    state.text[role.key] = data.reply || data.message?.content || data.content || ''
  } catch (e) {
    state.error[role.key] = e.message || '请求失败'
  } finally {
    state.loading[role.key] = false
  }
}

function start() {
  state.open = true
  const token = getToken()
  // 三个角色并发，各自独立返回，先到先显示
  roles.forEach((r) => ask(r, token))
}
</script>

<style scoped>
.trio { margin-top: 12px; }

.trio__trigger {
  padding: 8px 16px; border-radius: 10px; border: 1px dashed #c7d2fe;
  background: #f5f7ff; color: #4c51bf; font-size: 12px; font-weight: 600; cursor: pointer;
}
.trio__trigger:hover { background: #eef2ff; }

.trio__board {
  margin-top: 10px; padding: 14px; border-radius: 14px;
  background: #fafbff; border: 1px solid #e8ecfa;
}
.trio__head {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 12px; font-weight: 700; color: #4c51bf; margin-bottom: 10px;
}
.trio__close { border: none; background: none; color: #9ca3af; font-size: 12px; cursor: pointer; }

.trio__cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (max-width: 900px) { .trio__cols { grid-template-columns: 1fr; } }

.trio__col { display: flex; flex-direction: column; gap: 6px; }
.trio__col-head { display: flex; align-items: center; gap: 6px; }
.trio__avatar { font-size: 15px; }
.trio__role { font-size: 12px; font-weight: 700; color: #374151; }

.trio__bubble {
  flex: 1; padding: 10px 12px; border-radius: 12px; font-size: 12.5px; line-height: 1.65;
  background: #fff; border: 1px solid #eef1f8; min-height: 64px;
}
.is-setter .trio__bubble { border-color: #dbeafe; background: #f8fbff; }
.is-marker .trio__bubble { border-color: #fde68a; background: #fffdf5; }
.is-senior .trio__bubble { border-color: #d1fae5; background: #f7fffb; }

.trio__text { margin: 0; color: #374151; white-space: pre-wrap; }
.trio__err { margin: 0; color: #b91c1c; }

.trio__typing { display: inline-flex; gap: 4px; align-items: center; height: 18px; }
.trio__typing i {
  width: 5px; height: 5px; border-radius: 50%; background: #c7d2fe;
  animation: blink 1.1s infinite ease-in-out;
}
.trio__typing i:nth-child(2) { animation-delay: 0.16s; }
.trio__typing i:nth-child(3) { animation-delay: 0.32s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-2px); }
}

@media (prefers-reduced-motion: reduce) {
  .trio__typing i { animation: none; }
}
</style>
