<template>
  <div class="essay">
    <button v-if="!open" class="essay__fab" title="申论作文 AI 批改" @click="open = true">✍️</button>

    <transition name="fade">
      <div v-if="open" class="essay__mask" @click.self="open = false">
        <section class="essay__panel">
          <header class="essay__head">
            <div>
              <p class="essay__title">申论作文 AI 批改</p>
              <p class="essay__sub">粘贴题目与正文，小智按采分点给点评</p>
            </div>
            <button class="essay__close" @click="open = false">×</button>
          </header>

          <label class="essay__field">
            <span>作文题目</span>
            <input v-model="state.title" class="essay__input" placeholder="例如：请以「新时代公安使命」为主题写一篇议论文" />
          </label>

          <label class="essay__field">
            <span>作文正文</span>
            <textarea v-model="state.body" class="essay__textarea" rows="10" placeholder="把你的作文正文粘贴进来…"></textarea>
          </label>

          <div class="essay__actions">
            <span class="essay__count">{{ state.body.length }} 字</span>
            <button class="essay__btn" :disabled="state.loading || !canSubmit" @click="grade">
              {{ state.loading ? '批改中…' : '开始 AI 批改' }}
            </button>
          </div>

          <div v-if="state.error" class="essay__err">{{ state.error }}</div>
          <div v-if="state.result" class="essay__result">
            <p class="essay__result-title">批改意见</p>
            <pre class="essay__result-body">{{ state.result }}</pre>
          </div>
        </section>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

const open = ref(false)
const state = reactive({ title: '', body: '', loading: false, error: '', result: '' })

const canSubmit = computed(() => state.title.trim() && state.body.trim().length >= 50)

function token() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

async function grade() {
  state.loading = true
  state.error = ''
  state.result = ''
  try {
    const prompt = [
      '【任务】申论作文批改',
      '请以联考申论阅卷标准打分并点评，输出格式：',
      '1) 总分（满分 40，按 立意/结构/内容/语言 四维各 10 分）',
      '2) 各维度得分与一句理由',
      '3) 三个最该改的具体问题（逐条，可直接照着改）',
      '4) 一段可替换的示范开头',
      '',
      '【作文题目】' + state.title,
      '【作文正文】' + state.body,
    ].join('\n')

    const res = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token() },
      body: JSON.stringify({ message: prompt, scene: 'essay', persist: false }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data?.detail || data?.error?.message || 'HTTP ' + res.status)
    state.result = data.reply || data.message?.content || ''
  } catch (e) {
    state.error = e.message || '批改失败，请稍后重试'
  } finally {
    state.loading = false
  }
}
</script>

<style scoped>
.essay__fab {
  position: fixed; right: 24px; bottom: 96px; z-index: 890;
  width: 44px; height: 44px; border-radius: 50%; border: none;
  background: #fff; box-shadow: 0 8px 24px rgba(17,24,39,.16);
  font-size: 19px; cursor: pointer; transition: transform 160ms ease;
}
.essay__fab:hover { transform: translateY(-2px); }

.essay__mask { position: fixed; inset: 0; background: rgba(17,24,39,.35); z-index: 2000; display: flex; justify-content: flex-end; }
.essay__panel {
  width: min(560px, 96vw); height: 100%; overflow-y: auto; background: #fff; padding: 20px 22px;
  display: flex; flex-direction: column; gap: 14px;
}
.essay__head { display: flex; align-items: flex-start; justify-content: space-between; }
.essay__title { margin: 0; font-size: 15px; font-weight: 700; color: #1a2b5f; }
.essay__sub { margin: 3px 0 0; font-size: 11.5px; color: #8a8faa; }
.essay__close { border: none; background: none; font-size: 20px; color: #9aa0aa; cursor: pointer; line-height: 1; }

.essay__field { display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; color: #4b5563; }
.essay__input, .essay__textarea {
  width: 100%; box-sizing: border-box; border: 1px solid #e3e6ec; border-radius: 10px;
  padding: 10px 12px; font-size: 13px; outline: none; background: #fff; color: #111827;
}
.essay__textarea { resize: vertical; line-height: 1.7; }
.essay__input:focus, .essay__textarea:focus { border-color: #4d6bfe; box-shadow: 0 0 0 3px rgba(77,107,254,.1); }

.essay__actions { display: flex; align-items: center; gap: 12px; }
.essay__count { font-size: 11.5px; color: #9aa0aa; }
.essay__btn { margin-left: auto; padding: 10px 18px; border: none; border-radius: 10px; background: #c41e3a; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; }
.essay__btn:disabled { background: #e5b6bf; cursor: not-allowed; }

.essay__err { font-size: 12px; color: #b91c1c; }
.essay__result { border-top: 1px solid #eef1f7; padding-top: 12px; }
.essay__result-title { margin: 0 0 8px; font-size: 13px; font-weight: 700; color: #1a2b5f; }
.essay__result-body { margin: 0; white-space: pre-wrap; font-family: inherit; font-size: 13px; line-height: 1.75; color: #374151; }

.fade-enter-active, .fade-leave-active { transition: opacity 200ms ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
