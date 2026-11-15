<template>
  <div class="studio">
    <aside class="studio__side" :class="{ 'is-open': sideOpen }">
      <div class="side__head">
        <span>会话</span>
        <button class="side__new" @click="newChat">＋ 新对话</button>
      </div>
      <ul class="side__list">
        <li v-for="s in sessions" :key="s.id" :class="{ on: s.id === state.sessionId }" @click="switchChat(s.id)">
          <span class="side__title">{{ s.title || "未命名对话" }}</span>
          <button class="side__del" @click.stop="removeChat(s.id)">×</button>
        </li>
        <li v-if="!sessions.length" class="side__empty">还没有对话</li>
      </ul>
    </aside>

    <main class="studio__main">
      <header class="studio__top">
        <button class="studio__menu" @click="sideOpen = !sideOpen">☰</button>
        <div class="studio__brand">
          <span class="studio__name">联考小智</span>
          <span class="studio__tag" :class="{ 'is-agent': state.mode === 'agent' }">{{ state.mode === 'agent' ? "Codex" : "Chat" }}</span>
        </div>
        <div class="studio__modes">
          <button :class="{ on: state.mode === 'chat' }" @click="state.mode = 'chat'">对话</button>
          <button :class="{ on: state.mode === 'agent' }" @click="state.mode = 'agent'">Agent</button>
        </div>
      </header>

      <section class="studio__thread" ref="threadRef">
        <div v-if="!state.messages.length" class="studio__hello">
          <h2>有什么要搞定的？</h2>
          <p>对话模式像 ChatGPT；Agent 模式会自己查库、算数、多步执行。</p>
          <div class="studio__chips">
            <button v-for="q in suggestions" :key="q" @click="send(q)">{{ q }}</button>
          </div>
        </div>

        <div v-for="(m, i) in state.messages" :key="i" class="msg" :class="'msg--' + m.role">
          <div class="msg__avatar">{{ m.role === "user" ? "我" : "智" }}</div>
          <div class="msg__body">
            <div v-if="m.tools && m.tools.length" class="tools">
              <details v-for="(t, ti) in m.tools" :key="ti" class="tool">
                <summary>
                  <span class="tool__dot" :class="t.status"></span>
                  <span class="tool__name">{{ t.name }}</span>
                  <span class="tool__arg">{{ shortArgs(t.args) }}</span>
                </summary>
                <pre class="tool__result">{{ pretty(t.result) }}</pre>
              </details>
            </div>
            <div class="msg__text" v-html="render(m.content)"></div>
            <span v-if="m.streaming" class="cursor"></span>
          </div>
        </div>
      </section>

      <footer class="studio__composer">
        <div class="composer">
          <textarea v-model="state.input" class="composer__input" rows="1"
                    :placeholder="state.mode === 'agent' ? '让我做什么？（可多步执行）' : '问点什么…'"
                    @keydown.enter.exact.prevent="send()"></textarea>
          <button v-if="state.busy" class="composer__btn stop" @click="stop">停止</button>
          <button v-else class="composer__btn" :disabled="!state.input.trim()" @click="send()">发送</button>
        </div>
        <p class="composer__hint">Enter 发送 · Shift+Enter 换行 · 当前模型 DeepSeek</p>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref, watch } from "vue"

const KEY = "li_an_ai_studio_v1"
const BT = String.fromCharCode(96)
const FENCE = BT + BT + BT
const INLINE = new RegExp(BT + "([^" + BT + "]+)" + BT, "g")

const threadRef = ref(null)
const sideOpen = ref(false)
const sessions = ref([])
const state = reactive({ sessionId: "", mode: "chat", input: "", busy: false, messages: [] })
let controller = null

const suggestions = [
  "我的错题今天该复习哪些？",
  "帮我查资料分析有哪些考点",
  "行测 65 分、申论 58 分，平均多少？",
  "三天内怎么排复习？",
]

function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6) }

function token() {
  try {
    const raw = localStorage.getItem("__VTJ_AUTH_STATE__")
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem("token") || ""
}

function loadStore() {
  try { const raw = localStorage.getItem(KEY); return raw ? JSON.parse(raw) : [] } catch (e) { return [] }
}
function saveStore() {
  try { localStorage.setItem(KEY, JSON.stringify(sessions.value.slice(0, 30))) } catch (e) { /* ignore */ }
}
function persistCurrent() {
  const cur = sessions.value.find((x) => x.id === state.sessionId)
  if (!cur) return
  cur.messages = state.messages.filter((m) => !m.streaming)
  const firstUser = cur.messages.find((m) => m.role === "user")
  cur.title = firstUser ? String(firstUser.content).slice(0, 18) : "未命名对话"
  saveStore()
}
function newChat() {
  const id = uid()
  sessions.value.unshift({ id, title: "未命名对话", messages: [] })
  state.sessionId = id
  state.messages = []
  saveStore()
  sideOpen.value = false
}
function switchChat(id) {
  persistCurrent()
  const s = sessions.value.find((x) => x.id === id)
  if (!s) return
  state.sessionId = id
  state.messages = (s.messages || []).map((m) => Object.assign({}, m, { streaming: false }))
  sideOpen.value = false
  scrollBottom()
}
function removeChat(id) {
  sessions.value = sessions.value.filter((x) => x.id !== id)
  if (state.sessionId === id) {
    if (sessions.value.length) switchChat(sessions.value[0].id)
    else newChat()
  }
  saveStore()
}

function esc(v) {
  return String(v || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}
function render(text) {
  const raw = esc(text)
  const parts = raw.split(FENCE)
  return parts.map(function (p, i) {
    if (i % 2 === 1) {
      const body = p.replace(/^[a-zA-Z0-9]*\n/, "")
      return "<pre class=\"code\"><code>" + body + "</code></pre>"
    }
    return p
      .replace(INLINE, "<code class=\"inline\">$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br/>")
  }).join("")
}

function shortArgs(args) {
  if (!args) return ""
  const s = JSON.stringify(args)
  return s.length > 46 ? s.slice(0, 46) + "…" : s
}
function pretty(v) {
  try { return JSON.stringify(v, null, 2).slice(0, 800) } catch (e) { return String(v) }
}
function scrollBottom() {
  nextTick(function () { const el = threadRef.value; if (el) el.scrollTop = el.scrollHeight })
}

async function send(preset) {
  const text = (typeof preset === "string" ? preset : state.input).trim()
  if (!text || state.busy) return
  state.input = ""
  state.busy = true
  sideOpen.value = false

  const history = state.messages
    .filter((m) => !m.streaming && m.content)
    .slice(-20)
    .map((m) => ({ role: m.role, content: m.content }))

  state.messages.push({ role: "user", content: text })
  const reply = reactive({ role: "assistant", content: "", tools: [], streaming: true })
  state.messages.push(reply)
  scrollBottom()

  controller = new AbortController()
  try {
    const url = state.mode === "agent" ? "/api/llm/agent/stream" : "/api/llm/chat/stream"
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token() },
      body: JSON.stringify({ message: text, history: history }),
      signal: controller.signal,
    })
    if (!res.ok || !res.body) throw new Error("HTTP " + res.status)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ""
    while (true) {
      const r = await reader.read()
      if (r.done) break
      buf += decoder.decode(r.value, { stream: true })
      const chunks = buf.split("\n\n")
      buf = chunks.pop() || ""
      for (const chunk of chunks) {
        const line = chunk.trim()
        if (line.indexOf("data:") !== 0) continue
        let evt = null
        try { evt = JSON.parse(line.slice(5).trim()) } catch (e) { continue }
        if (evt.type === "token") { reply.content += evt.text || ""; scrollBottom() }
        else if (evt.type === "tool_call") {
          if (!reply.tools) reply.tools = []
          reply.tools.push({ name: evt.name, args: evt.args, status: "running" })
          scrollBottom()
        } else if (evt.type === "tool_result") {
          const list = (reply.tools || []).slice().reverse()
          const hit = list.find((t) => t.name === evt.name && t.status === "running")
          if (hit) { hit.result = evt.result; hit.status = "ok" }
          scrollBottom()
        } else if (evt.type === "error") {
          reply.content += (reply.content ? "\n\n" : "") + "⚠️ " + (evt.message || "出错了")
        }
      }
    }
  } catch (e) {
    if (e.name !== "AbortError") reply.content += (reply.content ? "\n\n" : "") + "⚠️ " + e.message
  } finally {
    reply.streaming = false
    state.busy = false
    controller = null
    persistCurrent()
  }
}

function stop() { if (controller) controller.abort() }

watch(function () { return state.sessionId }, function () { scrollBottom() })

onMounted(function () {
  sessions.value = loadStore()
  if (sessions.value.length) switchChat(sessions.value[0].id)
  else newChat()
})
</script>

<style scoped>
.studio { display: flex; height: 100vh; background: #f7f8fb; color: #111827; }
.studio__side { width: 244px; flex: 0 0 244px; background: #fff; border-right: 1px solid #eef1f7; display: flex; flex-direction: column; }
.side__head { display: flex; align-items: center; justify-content: space-between; padding: 14px 14px 10px; font-size: 12px; color: #6b7280; }
.side__new { border: 1px solid #e5e7eb; background: #fff; border-radius: 8px; padding: 5px 10px; font-size: 12px; cursor: pointer; }
.side__new:hover { background: #f9fafb; }
.side__list { list-style: none; margin: 0; padding: 0 8px; overflow-y: auto; flex: 1; }
.side__list li { display: flex; align-items: center; gap: 6px; padding: 9px 10px; border-radius: 8px; font-size: 12.5px; color: #4b5563; cursor: pointer; }
.side__list li:hover { background: #f3f4f6; }
.side__list li.on { background: #eef2ff; color: #1d4ed8; font-weight: 600; }
.side__title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.side__del { border: none; background: none; color: #c7cbd4; cursor: pointer; }
.side__empty { color: #c7cbd4; font-size: 12px; padding: 12px; }
.studio__main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.studio__top { display: flex; align-items: center; gap: 12px; padding: 12px 18px; background: #fff; border-bottom: 1px solid #eef1f7; }
.studio__menu { display: none; border: none; background: none; font-size: 16px; cursor: pointer; }
.studio__brand { display: flex; align-items: center; gap: 8px; }
.studio__name { font-size: 14px; font-weight: 700; }
.studio__tag { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 6px; background: #eef2ff; color: #2563eb; }
.studio__tag.is-agent { background: #ecfdf5; color: #059669; }
.studio__modes { margin-left: auto; display: flex; gap: 4px; background: #f3f4f6; padding: 3px; border-radius: 9px; }
.studio__modes button { border: none; background: none; padding: 5px 12px; border-radius: 7px; font-size: 12px; color: #6b7280; cursor: pointer; }
.studio__modes button.on { background: #fff; color: #111827; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.studio__thread { flex: 1; overflow-y: auto; padding: 24px 20px 12px; }
.studio__hello { max-width: 620px; margin: 8vh auto 0; text-align: center; }
.studio__hello h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; }
.studio__hello p { margin: 0 0 20px; font-size: 13px; color: #6b7280; }
.studio__chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.studio__chips button { border: 1px solid #e5e7eb; background: #fff; border-radius: 999px; padding: 8px 14px; font-size: 12px; color: #4b5563; cursor: pointer; }
.studio__chips button:hover { border-color: #c7d2fe; color: #1d4ed8; }
.msg { display: flex; gap: 10px; max-width: 760px; margin: 0 auto 18px; }
.msg__avatar { width: 26px; height: 26px; flex: 0 0 26px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: #fff; background: #9ca3af; }
.msg--assistant .msg__avatar { background: #2563eb; }
.msg__body { flex: 1; min-width: 0; }
.msg--user .msg__body { background: #f3f4f6; border-radius: 12px; padding: 10px 14px; }
.msg__text { font-size: 13.5px; line-height: 1.75; color: #1f2937; word-break: break-word; }
.msg__text :deep(pre.code) { background: #0f172a; color: #e2e8f0; padding: 12px 14px; border-radius: 10px; overflow-x: auto; font-size: 12px; }
.msg__text :deep(code.inline) { background: #eef1f7; padding: 1px 5px; border-radius: 5px; font-size: 12px; }
.cursor { display: inline-block; width: 7px; height: 15px; background: #2563eb; vertical-align: -2px; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.tools { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.tool { border: 1px solid #e8ecfa; border-radius: 10px; background: #fafbff; font-size: 11.5px; }
.tool summary { display: flex; align-items: center; gap: 8px; padding: 7px 10px; cursor: pointer; list-style: none; }
.tool summary::-webkit-details-marker { display: none; }
.tool__dot { width: 7px; height: 7px; border-radius: 50%; background: #f59e0b; }
.tool__dot.ok { background: #10b981; }
.tool__name { font-weight: 700; color: #1d4ed8; }
.tool__arg { color: #9ca3af; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool__result { margin: 0; padding: 8px 10px; background: #fff; border-top: 1px solid #eef1f7; font-size: 11px; color: #4b5563; max-height: 200px; overflow: auto; }
.studio__composer { padding: 10px 20px 16px; }
.composer { max-width: 760px; margin: 0 auto; display: flex; gap: 8px; align-items: flex-end; background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 8px 8px 8px 14px; box-shadow: 0 2px 10px rgba(17,24,39,.04); }
.composer__input { flex: 1; border: none; outline: none; resize: none; font-size: 13.5px; line-height: 1.6; max-height: 140px; padding: 6px 0; background: none; }
.composer__btn { border: none; background: #2563eb; color: #fff; padding: 8px 16px; border-radius: 10px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.composer__btn:disabled { background: #c7d2fe; cursor: not-allowed; }
.composer__btn.stop { background: #ef4444; }
.composer__hint { max-width: 760px; margin: 6px auto 0; font-size: 10.5px; color: #b6bcc8; text-align: center; }
@media (max-width: 820px) {
  .studio__side { position: absolute; z-index: 20; height: 100%; transform: translateX(-100%); transition: transform 220ms ease; }
  .studio__side.is-open { transform: none; }
  .studio__menu { display: block; }
  .msg { max-width: none; }
}
@media (prefers-reduced-motion: reduce) {
  .cursor { animation: none; }
  .studio__side { transition: none; }
}
</style>

