<template>
  <div class="ds">
    <!-- 侧栏 -->
    <aside class="ds__side" :class="{ 'is-open': sideOpen }">
      <div class="side__brand">联考小智</div>
      <button class="side__new" @click="newChat">＋ 开启新对话</button>

      <div class="side__scroll">
        <template v-for="group in groupedSessions" :key="group.label">
          <p class="side__group" v-if="group.items.length">{{ group.label }}</p>
          <div v-for="s in group.items" :key="s.id" class="side__item"
               :class="{ on: s.id === state.sessionId }" @click="switchChat(s.id)">
            <span class="side__title">{{ s.title || "未命名对话" }}</span>
            <button class="side__del" @click.stop="removeChat(s.id)">×</button>
          </div>
        </template>
      </div>
    </aside>

    <!-- 主区 -->
    <main class="ds__main">
      <header class="ds__top">
        <button class="ds__menu" @click="sideOpen = !sideOpen">☰</button>
        <div class="ds__model">
          <button :class="{ on: state.model === 'deepseek-chat' }" @click="state.model = 'deepseek-chat'">对话</button>
          <button :class="{ on: state.model === 'deepseek-reasoner' }" @click="state.model = 'deepseek-reasoner'">深度思考</button>
          <button :class="{ on: state.mode === 'agent' }" @click="state.mode = 'agent'">Agent</button>
        </div>
      </header>

      <section class="ds__thread" ref="threadRef">
        <div v-if="!state.messages.length" class="ds__welcome">
          <h1>{{ greeting }}</h1>
          <p class="ds__welcome-sub">我可以帮你分析错题、拆解考点、排复习节奏。</p>
          <div class="ds__cards">
            <button v-for="c in suggestions" :key="c" class="ds__card" @click="send(c)">
              <span class="ds__card-title">{{ c }}</span>
              <span class="ds__card-desc">{{ cardDesc(c) }}</span>
            </button>
          </div>
        </div>

        <div v-for="(m, i) in state.messages" :key="i" class="ds-msg" :class="'ds-msg--' + m.role">
          <div class="ds-msg__who">{{ m.role === "user" ? "你" : "小智" }}</div>
          <div class="ds-msg__main">
            <!-- 深度思考折叠区 -->
            <div v-if="m.reasoning || m.thinking" class="think" :class="{ 'is-open': m.thinkOpen }">
              <button class="think__head" @click="m.thinkOpen = !m.thinkOpen">
                <span class="think__spark">✦</span>
                <span>{{ m.thinking ? "深度思考中…" : thinkLabel(m) }}</span>
                <span class="think__arrow" :class="{ up: m.thinkOpen }">⌄</span>
              </button>
              <div v-if="m.thinkOpen && m.reasoning" class="think__body">{{ m.reasoning }}</div>
            </div>

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

            <div class="ds-msg__text" v-html="render(m.content)"></div>
            <span v-if="m.streaming" class="cursor"></span>
          </div>
        </div>
      </section>

      <footer class="ds__composer">
        <div class="composer" :class="{ 'has-text': state.input.trim() }">
          <textarea v-model="state.input" class="composer__input" rows="1"
                    :placeholder="state.mode === 'agent' ? '交给小智去做…' : '给联考小智发送消息'"
                    @keydown.enter.exact.prevent="send()"></textarea>
          <div class="composer__bar">
            <button class="chip" :class="{ on: state.model === 'deepseek-reasoner' }"
                    @click="state.model = state.model === 'deepseek-reasoner' ? 'deepseek-chat' : 'deepseek-reasoner'">
              <span class="chip__icon">✦</span> 深度思考
            </button>
            <button class="chip" :class="{ on: state.mode === 'agent' }"
                    @click="state.mode = state.mode === 'agent' ? 'chat' : 'agent'">
              <span class="chip__icon">⚙</span> Agent
            </button>
            <button v-if="state.busy" class="send stop" @click="stop">■</button>
            <button v-else class="send" :disabled="!state.input.trim()" @click="send()">↑</button>
          </div>
        </div>
        <p class="ds__tip">内容由 AI 生成，请仔细甄别 · Enter 发送，Shift+Enter 换行</p>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue"

const KEY = "li_an_ai_studio_v2"
const BT = String.fromCharCode(96)
const FENCE = BT + BT + BT
const INLINE = new RegExp(BT + "([^" + BT + "]+)" + BT, "g")

const threadRef = ref(null)
const sideOpen = ref(false)
const sessions = ref([])
const state = reactive({ sessionId: "", mode: "chat", model: "deepseek-chat", input: "", busy: false, messages: [] })
let controller = null

const greeting = computed(function () {
  const h = new Date().getHours()
  if (h < 6) return "夜深了，还要再练一会儿吗？"
  if (h < 12) return "早上好，今天想先攻哪科？"
  if (h < 18) return "下午好，我来帮你拆题。"
  return "晚上好，今天辛苦了。"
})

const suggestions = [
  "我的错题今天该复习哪些?",
  "资料分析有哪些考点",
  "三天内怎么排复习节奏",
  "行测 65 申论 58，平均多少分",
]

function cardDesc(q) {
  if (q.indexOf("错题") >= 0) return "按遗忘曲线挑出今天该看的题"
  if (q.indexOf("考点") >= 0) return "查知识库里的知识点与关系"
  if (q.indexOf("节奏") >= 0) return "结合剩余天数和每日时长排"
  return "直接算，不用自己按计算器"
}

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
  try { localStorage.setItem(KEY, JSON.stringify(sessions.value.slice(0, 40))) } catch (e) { /* ignore */ }
}

const groupedSessions = computed(function () {
  const now = new Date()
  const today = now.toDateString()
  const weekAgo = now.getTime() - 7 * 86400000
  const g = [
    { label: "今天", items: [] },
    { label: "最近 7 天", items: [] },
    { label: "更早", items: [] },
  ]
  sessions.value.forEach(function (s) {
    const t = s.at || 0
    const d = new Date(t)
    if (d.toDateString() === today) g[0].items.push(s)
    else if (t >= weekAgo) g[1].items.push(s)
    else g[2].items.push(s)
  })
  return g
})

function persistCurrent() {
  const cur = sessions.value.find(function (x) { return x.id === state.sessionId })
  if (!cur) return
  cur.messages = state.messages.filter(function (m) { return !m.streaming })
  cur.at = Date.now()
  const firstUser = cur.messages.find(function (m) { return m.role === "user" })
  cur.title = firstUser ? String(firstUser.content).slice(0, 18) : "未命名对话"
  saveStore()
}
function newChat() {
  const id = uid()
  sessions.value.unshift({ id: id, title: "未命名对话", messages: [], at: Date.now() })
  state.sessionId = id
  state.messages = []
  saveStore()
  sideOpen.value = false
}
function switchChat(id) {
  persistCurrent()
  const s = sessions.value.find(function (x) { return x.id === id })
  if (!s) return
  state.sessionId = id
  state.messages = (s.messages || []).map(function (m) { return Object.assign({}, m, { streaming: false }) })
  sideOpen.value = false
  scrollBottom()
}
function removeChat(id) {
  sessions.value = sessions.value.filter(function (x) { return x.id !== id })
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
function thinkLabel(m) {
  const sec = m.thinkSeconds || 1
  return "已深度思考（用时 " + sec + " 秒）"
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
    .filter(function (m) { return !m.streaming && m.content })
    .slice(-20)
    .map(function (m) { return { role: m.role, content: m.content } })

  state.messages.push({ role: "user", content: text })
  const reply = reactive({
    role: "assistant", content: "", reasoning: "", tools: [], streaming: true,
    thinking: state.model === "deepseek-reasoner", thinkOpen: true, thinkSeconds: 0,
  })
  state.messages.push(reply)
  scrollBottom()

  const startedAt = Date.now()
  controller = new AbortController()
  try {
    const url = state.mode === "agent" ? "/api/llm/agent/stream" : "/api/llm/chat/stream"
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token() },
      body: JSON.stringify({ message: text, history: history, model: state.model }),
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
        if (evt.type === "reasoning") {
          reply.reasoning += evt.text || ""
          reply.thinkSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000))
          scrollBottom()
        } else if (evt.type === "token") {
          if (reply.thinking) {
            reply.thinking = false
            reply.thinkOpen = false
            reply.thinkSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000))
          }
          reply.content += evt.text || ""
          scrollBottom()
        } else if (evt.type === "tool_call") {
          if (!reply.tools) reply.tools = []
          reply.tools.push({ name: evt.name, args: evt.args, status: "running" })
          scrollBottom()
        } else if (evt.type === "tool_result") {
          const list = (reply.tools || []).slice().reverse()
          const hit = list.find(function (t) { return t.name === evt.name && t.status === "running" })
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
    reply.thinking = false
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
.ds { display: flex; height: 100vh; background: #fff; color: #1f2329; font-family: "PingFang SC", "Noto Sans SC", system-ui, sans-serif; }

/* 侧栏 */
.ds__side { width: 250px; flex: 0 0 250px; background: #f9fafb; border-right: 1px solid #eef0f3; display: flex; flex-direction: column; padding: 14px 10px; }
.side__brand { font-size: 14px; font-weight: 700; color: #4d6bfe; padding: 4px 8px 12px; letter-spacing: 0.02em; }
.side__new { display: flex; align-items: center; justify-content: center; gap: 6px; margin: 0 4px 12px; padding: 9px 0; border-radius: 10px; border: 1px solid #dfe3ea; background: #fff; font-size: 13px; color: #1f2329; cursor: pointer; }
.side__new:hover { border-color: #4d6bfe; color: #4d6bfe; }
.side__scroll { flex: 1; overflow-y: auto; }
.side__group { margin: 12px 8px 6px; font-size: 11px; color: #9aa0aa; }
.side__item { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-radius: 8px; font-size: 13px; color: #3d434d; cursor: pointer; }
.side__item:hover { background: #eef1f6; }
.side__item.on { background: #e8eeff; color: #4d6bfe; font-weight: 600; }
.side__title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.side__del { border: none; background: none; color: #c2c7cf; cursor: pointer; opacity: 0; }
.side__item:hover .side__del { opacity: 1; }

/* 主区 */
.ds__main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.ds__top { display: flex; align-items: center; gap: 12px; padding: 12px 22px; border-bottom: 1px solid #f0f2f5; }
.ds__menu { display: none; border: none; background: none; font-size: 16px; cursor: pointer; }
.ds__model { display: flex; gap: 4px; background: #f4f5f7; padding: 3px; border-radius: 10px; }
.ds__model button { border: none; background: none; padding: 6px 14px; border-radius: 8px; font-size: 12.5px; color: #5c6270; cursor: pointer; }
.ds__model button.on { background: #fff; color: #4d6bfe; font-weight: 600; box-shadow: 0 1px 3px rgba(77,107,254,.14); }

.ds__thread { flex: 1; overflow-y: auto; padding: 28px 22px 10px; }
.ds__welcome { max-width: 640px; margin: 10vh auto 0; }
.ds__welcome h1 { margin: 0 0 6px; font-size: 24px; font-weight: 700; color: #1f2329; }
.ds__welcome-sub { margin: 0 0 22px; font-size: 13px; color: #8a909c; }
.ds__cards { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.ds__card { text-align: left; border: 1px solid #eef0f3; background: #fbfcfd; border-radius: 12px; padding: 12px 14px; cursor: pointer; transition: all 160ms ease; }
.ds__card:hover { border-color: #c9d4ff; background: #f6f9ff; transform: translateY(-1px); }
.ds__card-title { display: block; font-size: 13px; font-weight: 600; color: #2b3140; margin-bottom: 4px; }
.ds__card-desc { display: block; font-size: 11.5px; color: #9aa0aa; }

.ds-msg { max-width: 760px; margin: 0 auto 22px; display: flex; gap: 12px; }
.ds-msg__who { width: 26px; flex: 0 0 26px; font-size: 11px; font-weight: 700; color: #fff; background: #c9ced8; border-radius: 7px; display: flex; align-items: center; justify-content: center; height: 26px; }
.ds-msg--assistant .ds-msg__who { background: linear-gradient(135deg, #4d6bfe, #7a90ff); }
.ds-msg__main { flex: 1; min-width: 0; }
.ds-msg--user .ds-msg__main { background: #f4f6fa; border-radius: 12px; padding: 10px 14px; }
.ds-msg__text { font-size: 14px; line-height: 1.8; color: #1f2329; word-break: break-word; }
.ds-msg__text :deep(pre.code) { background: #0f172a; color: #e6edf3; padding: 13px 15px; border-radius: 10px; overflow-x: auto; font-size: 12.5px; margin: 10px 0; }
.ds-msg__text :deep(code.inline) { background: #eef1f6; padding: 1px 5px; border-radius: 5px; font-size: 12.5px; }
.cursor { display: inline-block; width: 7px; height: 15px; background: #4d6bfe; vertical-align: -2px; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* 深度思考 */
.think { margin-bottom: 10px; border-left: 2px solid #dbe2ff; padding-left: 12px; }
.think__head { display: flex; align-items: center; gap: 6px; border: none; background: none; padding: 2px 0; font-size: 12.5px; color: #7a828f; cursor: pointer; }
.think__spark { color: #4d6bfe; }
.think__arrow { transition: transform 200ms ease; }
.think__arrow.up { transform: rotate(180deg); }
.think__body { margin-top: 6px; font-size: 12.5px; line-height: 1.75; color: #8a909c; font-style: italic; white-space: pre-wrap; }

/* 工具卡 */
.tools { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.tool { border: 1px solid #eef0f3; border-radius: 10px; background: #fbfcfd; font-size: 11.5px; }
.tool summary { display: flex; align-items: center; gap: 8px; padding: 7px 10px; cursor: pointer; list-style: none; }
.tool summary::-webkit-details-marker { display: none; }
.tool__dot { width: 7px; height: 7px; border-radius: 50%; background: #f59e0b; }
.tool__dot.ok { background: #10b981; }
.tool__name { font-weight: 700; color: #4d6bfe; }
.tool__arg { color: #a8aeb8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool__result { margin: 0; padding: 8px 10px; background: #fff; border-top: 1px solid #f0f2f5; font-size: 11px; color: #5c6270; max-height: 200px; overflow: auto; }

/* 输入区 */
.ds__composer { padding: 8px 22px 14px; }
.composer { max-width: 760px; margin: 0 auto; border: 1px solid #e3e6ec; border-radius: 18px; background: #fff; padding: 10px 12px 8px; transition: border-color 160ms ease, box-shadow 160ms ease; }
.composer.has-text { border-color: #c9d4ff; box-shadow: 0 4px 18px rgba(77,107,254,.08); }
.composer__input { width: 100%; border: none; outline: none; resize: none; font-size: 14px; line-height: 1.7; max-height: 150px; background: none; color: #1f2329; padding: 0; }
.composer__bar { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.chip { display: inline-flex; align-items: center; gap: 4px; border: 1px solid #e3e6ec; background: #fff; border-radius: 999px; padding: 5px 12px; font-size: 12px; color: #5c6270; cursor: pointer; }
.chip.on { border-color: #4d6bfe; background: #f2f5ff; color: #4d6bfe; font-weight: 600; }
.chip__icon { font-size: 11px; }
.send { margin-left: auto; width: 34px; height: 34px; border-radius: 50%; border: none; background: #4d6bfe; color: #fff; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.send:disabled { background: #d7dbe4; cursor: not-allowed; }
.send.stop { background: #ef4444; }
.ds__tip { max-width: 760px; margin: 8px auto 0; text-align: center; font-size: 10.5px; color: #b6bcc8; }

@media (max-width: 860px) {
  .ds__side { position: absolute; z-index: 20; height: 100%; transform: translateX(-100%); transition: transform 220ms ease; }
  .ds__side.is-open { transform: none; }
  .ds__menu { display: block; }
  .ds__cards { grid-template-columns: 1fr; }
  .ds-msg { max-width: none; }
}
@media (prefers-reduced-motion: reduce) {
  .cursor { animation: none; }
  .ds__side { transition: none; }
  .ds__card { transition: none; }
}
</style>

