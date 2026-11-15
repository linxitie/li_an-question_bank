<template>
  <div class="xz" :class="{ 'xz--dark': state.theme === 'dark' }" :style="{ fontSize: state.fontSize + 'px' }">
    <!-- 侧栏 -->
    <aside class="xz-side" :class="{ 'is-open': sideOpen }">
      <div class="xz-side__top">
        <span class="xz-side__brand">联考小智</span>
        <button class="xz-side__icon" title="设置" @click="settingsOpen = true">⚙</button>
      </div>
      <button class="xz-side__new" @click="newChat">＋ 开启新对话</button>
      <input class="xz-side__search" v-model="query" placeholder="搜索对话" />

      <div class="xz-side__scroll">
        <template v-for="group in groupedSessions" :key="group.label">
          <div v-if="group.items.length" class="xz-side__group">{{ group.label }}</div>
          <div v-for="s in group.items" :key="s.id" class="xz-side__item"
               :class="{ on: s.id === state.sessionId }" @click="switchChat(s.id)">
            <span class="xz-side__title" @dblclick.stop="renameChat(s)">{{ s.title || "新对话" }}</span>
            <button class="xz-side__mini" title="置顶" @click.stop="pinChat(s)">📌</button>
            <button class="xz-side__mini" title="删除" @click.stop="removeChat(s.id)">×</button>
          </div>
        </template>
        <p v-if="!sessions.length" class="xz-side__empty">还没有对话</p>
      </div>

      <div class="xz-side__foot">
        <button @click="exportChat">导出对话</button>
        <button @click="clearChat">清空当前</button>
      </div>
    </aside>

    <!-- 主区 -->
    <main class="xz-main">
      <header class="xz-top">
        <button class="xz-top__menu" @click="sideOpen = !sideOpen">☰</button>
        <div class="xz-top__modes">
          <button :class="{ on: state.model === 'fast' && state.mode === 'chat' }"
                  @click="state.model = 'fast'; state.mode = 'chat'">标准</button>
          <button :class="{ on: state.model === 'reason' }" @click="state.model = 'reason'">深度思考</button>
          <button :class="{ on: state.mode === 'agent' }" @click="state.mode = 'agent'">Agent</button>
        </div>
        <span class="xz-top__hint">{{ state.mode === "agent" ? "会调用工具多步执行" : (state.model === "reason" ? "先推理再作答" : "快问快答") }}</span>
      </header>

      <section class="xz-thread" ref="threadRef" @scroll="onScroll" @click="onThreadClick">
        <div v-if="!state.messages.length" class="xz-welcome">
          <h1>{{ greeting }}</h1>
          <p class="xz-welcome__sub">我可以帮你分析错题、拆解考点、排复习节奏。</p>
          <div class="xz-cards">
            <button v-for="c in suggestions" :key="c.q" class="xz-card" @click="send(c.q)">
              <span class="xz-card__t">{{ c.q }}</span>
              <span class="xz-card__d">{{ c.d }}</span>
            </button>
          </div>
        </div>

        <div v-for="(m, i) in state.messages" :key="i" class="xz-msg" :class="'xz-msg--' + m.role">
          <div class="xz-msg__who">{{ m.role === "user" ? "我" : "智" }}</div>
          <div class="xz-msg__main">
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

            <div class="xz-msg__text" v-html="render(m.content)"></div>
            <span v-if="m.streaming" class="cursor"></span>

            <div v-if="!m.streaming && m.content" class="xz-msg__ops">
              <button title="复制" @click="copyText(m.content)">⧉</button>
              <button v-if="m.role === 'assistant'" title="重新生成" @click="regenerate(i)">↻</button>
              <button v-if="m.role === 'user'" title="编辑重发" @click="editMessage(i)">✎</button>
              <button v-if="m.role === 'assistant'" title="有帮助" :class="{ on: m.rated === 'up' }" @click="feedback(m, true)">👍</button>
              <button v-if="m.role === 'assistant'" title="没帮助" :class="{ on: m.rated === 'down' }" @click="feedback(m, false)">👎</button>
              <button title="删除" @click="delMessage(i)">🗑</button>
            </div>
          </div>
        </div>
      </section>

      <button v-if="showJump" class="xz-jump" @click="scrollBottom">↓</button>

      <footer class="xz-composer">
        <div v-if="state.attachments.length" class="atts">
          <span v-for="(a, i) in state.attachments" :key="i" class="att">
            📄 {{ a.name }}
            <button class="att__x" @click="removeAttachment(i)">×</button>
          </span>
        </div>
        <div class="composer" :class="{ 'has-text': state.input.trim() }">
          <textarea ref="inputRef" v-model="state.input" class="composer__input" rows="1"
                    :placeholder="state.mode === 'agent' ? '交给小智去做…' : '给联考小智发送消息'"
                    @keydown.enter.exact.prevent="send()"></textarea>
          <div class="composer__bar">
            <button class="chip chip--icon" title="添加附件（图片 / PDF / 文档）" @click="pickFile">📎</button>
            <input id="xz-file" type="file" multiple class="xz-file" @change="onFileChange" />
            <button class="chip" :class="{ on: state.model === 'reason' }"
                    @click="state.model = state.model === 'reason' ? 'fast' : 'reason'">
              <span class="chip__icon">✦</span> 深度思考
            </button>
            <button class="chip" :class="{ on: state.mode === 'agent' }"
                    @click="state.mode = state.mode === 'agent' ? 'chat' : 'agent'">
              <span class="chip__icon">⚙</span> Agent
            </button>
            <span class="composer__count" v-if="state.input.length">{{ state.input.length }} 字</span>
            <button v-if="state.busy" class="send stop" @click="stop">■</button>
            <button v-else class="send" :disabled="!state.input.trim()" @click="send()">↑</button>
          </div>
        </div>
        <p class="xz-tip">内容由 AI 生成，请仔细甄别 · Enter 发送，Shift+Enter 换行</p>
      </footer>
    </main>

    <!-- 设置抽屉 -->
    <div v-if="settingsOpen" class="xz-drawer" @click.self="settingsOpen = false">
      <div class="xz-drawer__panel">
        <h3>设置</h3>
        <label class="xz-drawer__row">
          <span>外观</span>
          <button class="xz-drawer__btn" @click="toggleTheme">{{ state.theme === "dark" ? "深色（工作台）" : "浅色（默认）" }}</button>
        </label>
        <label class="xz-drawer__row">
          <span>正文字号</span>
          <input type="range" min="12" max="18" v-model.number="state.fontSize" />
          <em>{{ state.fontSize }} px</em>
        </label>
        <p class="xz-drawer__note">会话保存在本机浏览器，换设备不同步。</p>
        <button class="xz-drawer__close" @click="settingsOpen = false">关闭</button>
      </div>
    </div>

    <transition name="fade">
      <div v-if="toast" class="xz-toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue"

/* ===== 联考小智 · 工作台 ===== */
const STORE_KEY = "li_an_xiaozhi_v3"
const BT = String.fromCharCode(96)
const FENCE = BT + BT + BT

/* 后端模型档位（对外只暴露「标准 / 深度思考」两个名字） */
// 后端模型档位映射：只在请求体里出现，界面上统一叫「标准 / 深度思考」
const MODEL_IDS = { fast: "deepseek-chat", reason: "deepseek-reasoner" }

const threadRef = ref(null)
const inputRef = ref(null)
const sideOpen = ref(false)
const settingsOpen = ref(false)
const sessions = ref([])
const query = ref("")
const showJump = ref(false)
const toast = ref("")
const state = reactive({
  sessionId: "",
  mode: "chat",        // chat | agent
  model: "fast",       // fast | reason
  input: "",
  busy: false,
  messages: [],
  fontSize: 14,
  theme: "light",
  attachments: [],
})
let controller = null

const greeting = computed(function () {
  const h = new Date().getHours()
  if (h < 6) return "夜深了，还要再练一会儿吗？"
  if (h < 12) return "早上好，今天想先攻哪科？"
  if (h < 18) return "下午好，我来帮你拆题。"
  return "晚上好，今天辛苦了。"
})

const suggestions = [
  { q: "我的错题今天该复习哪些", d: "按遗忘曲线挑出今天该看的题" },
  { q: "资料分析有哪些考点", d: "查知识库里的知识点与关系" },
  { q: "三天内怎么排复习节奏", d: "结合剩余天数和每日时长排" },
  { q: "行测 65 申论 58，平均多少分", d: "直接算，不用自己按计算器" },
]

/* ---------- 小工具 ---------- */
function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6) }
function token() {
  try {
    const raw = localStorage.getItem("__VTJ_AUTH_STATE__")
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem("token") || ""
}
function flash(msg) {
  toast.value = msg
  setTimeout(function () { toast.value = "" }, 1600)
}

/* ---------- 会话持久化 ---------- */
function loadStore() {
  try { const raw = localStorage.getItem(STORE_KEY); return raw ? JSON.parse(raw) : [] } catch (e) { return [] }
}
function saveStore() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(sessions.value.slice(0, 60))) } catch (e) { /* ignore */ }
}
const filtered = computed(function () {
  const k = query.value.trim()
  if (!k) return sessions.value
  return sessions.value.filter(function (s) {
    if ((s.title || "").indexOf(k) >= 0) return true
    return (s.messages || []).some(function (m) { return String(m.content || "").indexOf(k) >= 0 })
  })
})
const groupedSessions = computed(function () {
  const now = new Date()
  const today = now.toDateString()
  const weekAgo = now.getTime() - 7 * 86400000
  const pinned = { label: "置顶", items: [] }
  const g = [
    { label: "今天", items: [] },
    { label: "最近 7 天", items: [] },
    { label: "更早", items: [] },
  ]
  filtered.value.forEach(function (s) {
    if (s.pinned) { pinned.items.push(s); return }
    const d = new Date(s.at || 0)
    if (d.toDateString() === today) g[0].items.push(s)
    else if ((s.at || 0) >= weekAgo) g[1].items.push(s)
    else g[2].items.push(s)
  })
  return [pinned].concat(g)
})

function persistCurrent() {
  const cur = sessions.value.find(function (x) { return x.id === state.sessionId })
  if (!cur) return
  cur.messages = state.messages.filter(function (m) { return !m.streaming })
  cur.at = Date.now()
  const firstUser = cur.messages.find(function (m) { return m.role === "user" })
  if (!cur.renamed) cur.title = firstUser ? String(firstUser.content).slice(0, 18) : "新对话"
  saveStore()
}
function newChat() {
  const id = uid()
  sessions.value.unshift({ id: id, title: "新对话", messages: [], at: Date.now() })
  state.sessionId = id
  state.messages = []
  saveStore()
  sideOpen.value = false
  nextTick(function () { if (inputRef.value) inputRef.value.focus() })
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
  flash("已删除对话")
}
function renameChat(s) {
  const name = window.prompt("重命名对话", s.title || "")
  if (name === null) return
  s.title = name.trim() || s.title
  s.renamed = true
  saveStore()
}
function pinChat(s) {
  s.pinned = !s.pinned
  saveStore()
  flash(s.pinned ? "已置顶" : "已取消置顶")
}

/* ---------- 渲染 ---------- */
function esc(v) {
  return String(v || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}
function renderTable(block) {
  const rows = block.split("\n").filter(function (r) { return r.trim() })
  if (rows.length < 2) return esc(block)
  const head = rows[0].split("|").filter(function (c) { return c.trim() !== "" })
  const body = rows.slice(2)
  let html = "<table class=\"md-table\"><thead><tr>"
  head.forEach(function (c) { html += "<th>" + esc(c.trim()) + "</th>" })
  html += "</tr></thead><tbody>"
  body.forEach(function (r) {
    const cells = r.split("|").filter(function (c, i, a) { return i > 0 && i < a.length - 1 })
    html += "<tr>"
    cells.forEach(function (c) { html += "<td>" + esc(c.trim()) + "</td>" })
    html += "</tr>"
  })
  return html + "</tbody></table>"
}
function renderInline(p) {
  return esc(p)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\u0060([^\u0060]+)\u0060/g, "<code class=\"inline\">$1</code>")
}
function render(text) {
  const src = String(text || "")
  const parts = src.split(FENCE)
  let html = ""
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      const body = parts[i].replace(/^[a-zA-Z0-9]*\n/, "")
      html += "<div class=\"codeblock\"><div class=\"codeblock__bar\"><span>代码</span><button class=\"copy\" type=\"button\">复制</button></div><pre class=\"code\"><code>" + esc(body) + "</code></pre></div>"
      continue
    }
    const lines = parts[i].split("\n")
    let buf = []
    let list = null
    const flush = function () {
      if (list) { html += "<" + list + ">" + buf.join("") + "</" + list + ">"; buf = []; list = null }
    }
    for (let j = 0; j < lines.length; j++) {
      const line = lines[j]
      if (/^\s*\|/.test(line)) {
        flush()
        let tbl = [line]
        while (j + 1 < lines.length && /^\s*\|/.test(lines[j + 1])) { j += 1; tbl.push(lines[j]) }
        html += renderTable(tbl.join("\n"))
        continue
      }
      if (/^###\s+/.test(line)) { flush(); html += "<h4>" + renderInline(line.replace(/^###\s+/, "")) + "</h4>"; continue }
      if (/^##\s+/.test(line)) { flush(); html += "<h3>" + renderInline(line.replace(/^##\s+/, "")) + "</h3>"; continue }
      if (/^#\s+/.test(line)) { flush(); html += "<h3>" + renderInline(line.replace(/^#\s+/, "")) + "</h3>"; continue }
      if (/^>\s?/.test(line)) { flush(); html += "<blockquote>" + renderInline(line.replace(/^>\s?/, "")) + "</blockquote>"; continue }
      const ol = line.match(/^\s*(\d+)\.\s+(.*)$/)
      if (ol) {
        if (list !== "ol") { flush(); list = "ol" }
        buf.push("<li>" + renderInline(ol[2]) + "</li>")
        continue
      }
      const ul = line.match(/^\s*[-*]\s+(.*)$/)
      if (ul) {
        if (list !== "ul") { flush(); list = "ul" }
        buf.push("<li>" + renderInline(ul[1]) + "</li>")
        continue
      }
      flush()
      if (line.trim() === "") continue
      html += "<p>" + renderInline(line) + "</p>"
    }
    flush()
  }
  return html
}

function shortArgs(args) {
  if (!args) return ""
  const s = JSON.stringify(args)
  return s.length > 46 ? s.slice(0, 46) + "…" : s
}
function pretty(v) {
  try { return JSON.stringify(v, null, 2).slice(0, 900) } catch (e) { return String(v) }
}
function thinkLabel(m) { return "已深度思考（用时 " + (m.thinkSeconds || 1) + " 秒）" }
function scrollBottom() {
  nextTick(function () { const el = threadRef.value; if (el) el.scrollTop = el.scrollHeight })
}
function onScroll() {
  const el = threadRef.value
  if (!el) return
  showJump.value = el.scrollHeight - el.scrollTop - el.clientHeight > 240
}

/* ---------- 消息操作 ---------- */
function copyText(t) {
  try {
    if (navigator.clipboard) navigator.clipboard.writeText(String(t || ""))
    else {
      const ta = document.createElement("textarea")
      ta.value = String(t || "")
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove()
    }
    flash("已复制")
  } catch (e) { flash("复制失败") }
}
function onThreadClick(e) {
  const btn = e.target.closest && e.target.closest("button.copy")
  if (!btn) return
  const box = btn.closest(".codeblock")
  const code = box ? box.querySelector("code") : null
  if (code) copyText(code.textContent)
}
function delMessage(i) {
  state.messages.splice(i, 1)
  persistCurrent()
}
function editMessage(i) {
  const m = state.messages[i]
  if (!m) return
  state.input = m.content
  state.messages.splice(i, state.messages.length - i)
  nextTick(function () { if (inputRef.value) inputRef.value.focus() })
}
async function regenerate(i) {
  const m = state.messages[i]
  if (!m) return
  let q = ""
  for (let k = i; k >= 0; k--) {
    if (state.messages[k].role === "user") { q = state.messages[k].content; break }
  }
  if (!q) return
  state.messages.splice(i, state.messages.length - i)
  await send(q, true)
}
async function feedback(m, good) {
  m.rated = good ? "up" : "down"
  try {
    const r = await fetch("/api/agent/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token() },
      body: JSON.stringify({ message_id: m.messageId || null, rating: good ? "up" : "down" }),
    })
    flash(good ? "感谢反馈" : "已记录，会改进")
  } catch (e) { flash(good ? "感谢反馈" : "已记录") }
}
function exportChat() {
  const lines = []
  state.messages.forEach(function (m) {
    lines.push("## " + (m.role === "user" ? "我" : "联考小智"))
    if (m.reasoning) lines.push("> 思考：" + m.reasoning.replace(/\n/g, " "))
    lines.push(m.content || "")
    lines.push("")
  })
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" })
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  a.download = "联考小智-" + new Date().toISOString().slice(0, 10) + ".md"
  a.click()
  URL.revokeObjectURL(a.href)
  flash("已导出")
}
function toggleTheme() {
  state.theme = state.theme === 'dark' ? 'light' : 'dark'
  try { localStorage.setItem('li_an_xiaozhi_theme', state.theme) } catch (e) { /* ignore */ }
}

function pickFile() {
  const el = document.getElementById("xz-file")
  if (el) el.click()
}

async function onFileChange(e) {
  const files = Array.from(e.target.files || [])
  e.target.value = ""
  for (const file of files) {
    if (file.size > 10 * 1024 * 1024) { flash("单个文件不能超过 10MB"); continue }
    const fd = new FormData()
    fd.append("file", file)
    try {
      const res = await fetch("/api/agent/upload", {
        method: "POST",
        headers: { Authorization: "Bearer " + token() },
        body: fd,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "上传失败")
      state.attachments.push({ name: data.filename || file.name, url: data.file_url })
      flash("已添加附件")
    } catch (err) { flash(err.message || "上传失败") }
  }
}

function removeAttachment(i) {
  state.attachments.splice(i, 1)
}

function clearChat() {
  if (!window.confirm("清空当前对话？")) return
  state.messages = []
  persistCurrent()
}

/* ---------- 发送 ---------- */
async function send(preset, isRetry) {
  const text = (typeof preset === "string" ? preset : state.input).trim()
  if (!text || state.busy) return
  if (!isRetry) state.input = ""
  state.busy = true
  sideOpen.value = false

  const history = state.messages
    .filter(function (m) { return !m.streaming && m.content && m.role })
    .slice(-20)
    .map(function (m) { return { role: m.role, content: m.content } })

  let outgoing = text
  if (!isRetry && state.attachments.length) {
    outgoing += "\n\n附件：" + state.attachments.map(function (a) { return a.name + " (" + a.url + ")" }).join("、")
  }
  if (!isRetry && state.attachments.length) state.attachments = []
  if (!isRetry) state.messages.push({ role: "user", content: outgoing, at: Date.now() })
  const reply = reactive({
    role: "assistant", content: "", reasoning: "", tools: [], streaming: true,
    thinking: state.model === "reason", thinkOpen: true, thinkSeconds: 0, rated: "", at: Date.now(),
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
      body: JSON.stringify({ message: text, history: history, model: MODEL_IDS[state.model] || MODEL_IDS.fast }),
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
      for (let ci = 0; ci < chunks.length; ci++) {
        const line = chunks[ci].trim()
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
  try {
    const t = localStorage.getItem("li_an_xiaozhi_theme")
    if (t === "dark" || t === "light") state.theme = t
  } catch (e) { /* ignore */ }
  sessions.value = loadStore()
  if (sessions.value.length) switchChat(sessions.value[0].id)
  else newChat()
})
</script>

<style scoped>
.xz { display: flex; height: 100vh; background: #fff; color: #1f2329; font-family: "PingFang SC", "Noto Sans SC", system-ui, sans-serif; position: relative; }

/* 侧栏 */
.xz-side { width: 252px; flex: 0 0 252px; background: #f9fafb; border-right: 1px solid #eef0f3; display: flex; flex-direction: column; padding: 12px 10px; }
.xz-side__top { display: flex; align-items: center; justify-content: space-between; padding: 2px 8px 10px; }
.xz-side__brand { font-size: 14px; font-weight: 700; color: #4d6bfe; }
.xz-side__icon { border: none; background: none; font-size: 14px; color: #9aa0aa; cursor: pointer; }
.xz-side__new { padding: 9px 0; border-radius: 10px; border: 1px solid #dfe3ea; background: #fff; font-size: 13px; cursor: pointer; margin-bottom: 8px; }
.xz-side__new:hover { border-color: #4d6bfe; color: #4d6bfe; }
.xz-side__search { width: 100%; box-sizing: border-box; margin-bottom: 8px; padding: 7px 10px; border: 1px solid #e6e9ef; border-radius: 8px; font-size: 12.5px; outline: none; background: #fff; }
.xz-side__search:focus { border-color: #c9d4ff; }
.xz-side__scroll { flex: 1; overflow-y: auto; }
.xz-side__group { margin: 10px 8px 4px; font-size: 11px; color: #9aa0aa; }
.xz-side__item { display: flex; align-items: center; gap: 2px; padding: 7px 8px; border-radius: 8px; font-size: 13px; color: #3d434d; cursor: pointer; }
.xz-side__item:hover { background: #eef1f6; }
.xz-side__item.on { background: #e8eeff; color: #4d6bfe; font-weight: 600; }
.xz-side__title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.xz-side__mini { border: none; background: none; color: #c2c7cf; cursor: pointer; font-size: 11px; opacity: 0; }
.xz-side__item:hover .xz-side__mini { opacity: 1; }
.xz-side__empty { color: #c2c7cf; font-size: 12px; padding: 12px; }
.xz-side__foot { display: flex; gap: 6px; padding-top: 8px; border-top: 1px solid #eef0f3; }
.xz-side__foot button { flex: 1; border: 1px solid #e6e9ef; background: #fff; border-radius: 8px; padding: 6px 0; font-size: 11.5px; color: #5c6270; cursor: pointer; }
.xz-side__foot button:hover { border-color: #c9d4ff; color: #4d6bfe; }

/* 主区 */
.xz-main { flex: 1; display: flex; flex-direction: column; min-width: 0; position: relative; }
.xz-top { display: flex; align-items: center; gap: 10px; padding: 11px 20px; border-bottom: 1px solid #f0f2f5; }
.xz-top__menu { display: none; border: none; background: none; font-size: 16px; cursor: pointer; }
.xz-top__modes { display: flex; gap: 4px; background: #f4f5f7; padding: 3px; border-radius: 10px; }
.xz-top__modes button { border: none; background: none; padding: 6px 13px; border-radius: 8px; font-size: 12.5px; color: #5c6270; cursor: pointer; }
.xz-top__modes button.on { background: #fff; color: #4d6bfe; font-weight: 600; box-shadow: 0 1px 3px rgba(77,107,254,.14); }
.xz-top__hint { margin-left: auto; font-size: 11.5px; color: #a8aeb8; }

.xz-thread { flex: 1; overflow-y: auto; padding: 26px 20px 10px; }
.xz-welcome { max-width: 640px; margin: 9vh auto 0; }
.xz-welcome h1 { margin: 0 0 6px; font-size: 23px; font-weight: 700; }
.xz-welcome__sub { margin: 0 0 20px; font-size: 13px; color: #8a909c; }
.xz-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.xz-card { text-align: left; border: 1px solid #eef0f3; background: #fbfcfd; border-radius: 12px; padding: 12px 14px; cursor: pointer; transition: all 160ms ease; }
.xz-card:hover { border-color: #c9d4ff; background: #f6f9ff; transform: translateY(-1px); }
.xz-card__t { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.xz-card__d { display: block; font-size: 11.5px; color: #9aa0aa; }

.xz-msg { max-width: 780px; margin: 0 auto 20px; display: flex; gap: 12px; }
.xz-msg__who { width: 26px; height: 26px; flex: 0 0 26px; border-radius: 7px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: #fff; background: #c9ced8; }
.xz-msg--assistant .xz-msg__who { background: linear-gradient(135deg, #4d6bfe, #7a90ff); }
.xz-msg__main { flex: 1; min-width: 0; }
.xz-msg--user .xz-msg__main { background: #f4f6fa; border-radius: 12px; padding: 10px 14px; }
.xz-msg__text { line-height: 1.85; color: #1f2329; word-break: break-word; }
.xz-msg__text :deep(p) { margin: 0 0 8px; }
.xz-msg__text :deep(h3), .xz-msg__text :deep(h4) { margin: 14px 0 8px; font-size: 1.02em; }
.xz-msg__text :deep(blockquote) { margin: 8px 0; padding: 6px 12px; border-left: 3px solid #dbe2ff; color: #5c6270; background: #f7f9ff; }
.xz-msg__text :deep(ul), .xz-msg__text :deep(ol) { margin: 6px 0 10px; padding-left: 22px; }
.xz-msg__text :deep(.md-table) { border-collapse: collapse; margin: 10px 0; font-size: 0.92em; }
.xz-msg__text :deep(.md-table th), .xz-msg__text :deep(.md-table td) { border: 1px solid #e6e9ef; padding: 6px 10px; text-align: left; }
.xz-msg__text :deep(.md-table th) { background: #f7f9ff; font-weight: 600; }
.xz-msg__text :deep(.codeblock) { margin: 10px 0; border-radius: 10px; overflow: hidden; border: 1px solid #e6e9ef; }
.xz-msg__text :deep(.codeblock__bar) { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; background: #f4f6fa; font-size: 11.5px; color: #8a909c; }
.xz-msg__text :deep(.codeblock__bar button) { border: none; background: none; color: #4d6bfe; font-size: 11.5px; cursor: pointer; }
.xz-msg__text :deep(pre.code) { margin: 0; background: #0f172a; color: #e6edf3; padding: 13px 15px; overflow-x: auto; font-size: 0.86em; line-height: 1.6; }
.xz-msg__text :deep(code.inline) { background: #eef1f6; padding: 1px 5px; border-radius: 5px; font-size: 0.92em; }
.cursor { display: inline-block; width: 7px; height: 15px; background: #4d6bfe; vertical-align: -2px; animation: blink 1s steps(2) infinite; }
@keyframes blink { 50% { opacity: 0; } }

.xz-msg__ops { display: flex; gap: 4px; margin-top: 6px; opacity: 0; transition: opacity 160ms ease; }
.xz-msg:hover .xz-msg__ops { opacity: 1; }
.xz-msg__ops button { border: none; background: none; padding: 3px 7px; border-radius: 6px; font-size: 11.5px; color: #9aa0aa; cursor: pointer; }
.xz-msg__ops button:hover { background: #f1f3f7; color: #4d6bfe; }
.xz-msg__ops button.on { color: #4d6bfe; }

.think { margin-bottom: 10px; border-left: 2px solid #dbe2ff; padding-left: 12px; }
.think__head { display: flex; align-items: center; gap: 6px; border: none; background: none; padding: 2px 0; font-size: 12.5px; color: #7a828f; cursor: pointer; }
.think__spark { color: #4d6bfe; }
.think__arrow { transition: transform 200ms ease; }
.think__arrow.up { transform: rotate(180deg); }
.think__body { margin-top: 6px; font-size: 12.5px; line-height: 1.75; color: #8a909c; font-style: italic; white-space: pre-wrap; }

.tools { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.tool { border: 1px solid #eef0f3; border-radius: 10px; background: #fbfcfd; font-size: 11.5px; }
.tool summary { display: flex; align-items: center; gap: 8px; padding: 7px 10px; cursor: pointer; list-style: none; }
.tool summary::-webkit-details-marker { display: none; }
.tool__dot { width: 7px; height: 7px; border-radius: 50%; background: #f59e0b; }
.tool__dot.ok { background: #10b981; }
.tool__name { font-weight: 700; color: #4d6bfe; }
.tool__arg { color: #a8aeb8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool__result { margin: 0; padding: 8px 10px; background: #fff; border-top: 1px solid #f0f2f5; font-size: 11px; color: #5c6270; max-height: 200px; overflow: auto; }

.xz-jump { position: absolute; right: 26px; bottom: 120px; width: 32px; height: 32px; border-radius: 50%; border: 1px solid #e6e9ef; background: #fff; color: #5c6270; cursor: pointer; box-shadow: 0 4px 12px rgba(17,24,39,.08); }

.xz-composer { padding: 8px 20px 14px; }
.composer { max-width: 780px; margin: 0 auto; border: 1px solid #e3e6ec; border-radius: 18px; background: #fff; padding: 10px 12px 8px; transition: border-color 160ms ease, box-shadow 160ms ease; }
.composer.has-text { border-color: #c9d4ff; box-shadow: 0 4px 18px rgba(77,107,254,.08); }
.composer__input { width: 100%; border: none; outline: none; resize: none; font-size: inherit; line-height: 1.7; max-height: 150px; background: none; color: #1f2329; padding: 0; }
.composer__bar { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.chip { display: inline-flex; align-items: center; gap: 4px; border: 1px solid #e3e6ec; background: #fff; border-radius: 999px; padding: 5px 12px; font-size: 12px; color: #5c6270; cursor: pointer; }
.chip.on { border-color: #4d6bfe; background: #f2f5ff; color: #4d6bfe; font-weight: 600; }
.chip__icon { font-size: 11px; }
.composer__count { margin-left: 4px; font-size: 11px; color: #c2c7cf; }
.send { margin-left: auto; width: 34px; height: 34px; border-radius: 50%; border: none; background: #4d6bfe; color: #fff; font-size: 15px; cursor: pointer; }
.send:disabled { background: #d7dbe4; cursor: not-allowed; }
.send.stop { background: #ef4444; }
.xz-tip { max-width: 780px; margin: 8px auto 0; text-align: center; font-size: 10.5px; color: #b6bcc8; }

.xz-drawer { position: absolute; inset: 0; background: rgba(17,24,39,.22); display: flex; justify-content: flex-end; z-index: 30; }
.xz-drawer__panel { width: 280px; background: #fff; padding: 18px; display: flex; flex-direction: column; gap: 14px; }
.xz-drawer__panel h3 { margin: 0; font-size: 14px; }
.xz-drawer__row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: #5c6270; }
.xz-drawer__row input { flex: 1; }
.xz-drawer__note { font-size: 11.5px; color: #a8aeb8; margin: 0; }
.xz-drawer__close { margin-top: auto; padding: 9px 0; border-radius: 10px; border: 1px solid #e3e6ec; background: #fff; cursor: pointer; }

.xz-toast { position: absolute; left: 50%; bottom: 90px; transform: translateX(-50%); background: rgba(31,35,41,.88); color: #fff; padding: 8px 16px; border-radius: 10px; font-size: 12.5px; z-index: 40; }
.fade-enter-active, .fade-leave-active { transition: opacity 200ms ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 860px) {
  .xz-side { position: absolute; z-index: 20; height: 100%; transform: translateX(-100%); transition: transform 220ms ease; }
  .xz-side.is-open { transform: none; }
  .xz-top__menu { display: block; }
  .xz-cards { grid-template-columns: 1fr; }
  .xz-msg { max-width: none; }
}
@media (prefers-reduced-motion: reduce) {
  .cursor { animation: none; }
  .xz-side { transition: none; }
  .xz-card { transition: none; }
}

/* ===== 深色工作台：设计令牌取自 DeepSeek Harness（MIT）theme/design-platform.css ===== */
.xz--dark {
  --xz-bg-base: rgb(21, 21, 23);
  --xz-bg-layer-1: rgb(35, 35, 36);
  --xz-bg-layer-2: rgb(44, 44, 46);
  --xz-bg-layer-3: rgb(53, 54, 56);
  --xz-border-l1: rgba(255, 255, 255, 0.06);
  --xz-border-l2: rgba(255, 255, 255, 0.12);
  --xz-border-l3: rgba(255, 255, 255, 0.16);
  --xz-text-primary: rgb(249, 250, 251);
  --xz-text-secondary: rgb(173, 178, 184);
  --xz-text-tertiary: rgb(129, 133, 140);
  --xz-brand: rgb(86, 134, 254);
  --xz-brand-bright: rgb(122, 170, 255);
  --xz-radius-sm: 8px;
  --xz-radius-md: 12px;
  --xz-radius-lg: 16px;
  --xz-radius-panel: 20px;
  --xz-ease: cubic-bezier(0.4, 0, 0.2, 1);
  background: var(--xz-bg-base);
  color: var(--xz-text-primary);
}
.xz--dark .xz-side { background: var(--xz-bg-layer-1); border-right-color: var(--xz-border-l1); }
.xz--dark .xz-side__brand { color: var(--xz-brand-bright); }
.xz--dark .xz-side__new { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l2); color: var(--xz-text-primary); border-radius: var(--xz-radius-md); }
.xz--dark .xz-side__new:hover { border-color: var(--xz-brand); color: var(--xz-brand-bright); }
.xz--dark .xz-side__search { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l1); color: var(--xz-text-primary); }
.xz--dark .xz-side__group { color: var(--xz-text-tertiary); }
.xz--dark .xz-side__item { color: var(--xz-text-secondary); border-radius: var(--xz-radius-sm); }
.xz--dark .xz-side__item:hover { background: var(--xz-bg-layer-2); }
.xz--dark .xz-side__item.on { background: var(--xz-bg-layer-3); color: var(--xz-text-primary); }
.xz--dark .xz-side__foot { border-top-color: var(--xz-border-l1); }
.xz--dark .xz-side__foot button { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l1); color: var(--xz-text-secondary); }
.xz--dark .xz-top { border-bottom-color: var(--xz-border-l1); }
.xz--dark .xz-top__modes { background: var(--xz-bg-layer-2); border-radius: var(--xz-radius-md); }
.xz--dark .xz-top__modes button { color: var(--xz-text-secondary); }
.xz--dark .xz-top__modes button.on { background: var(--xz-bg-layer-3); color: var(--xz-text-primary); box-shadow: none; }
.xz--dark .xz-top__hint { color: var(--xz-text-tertiary); }
.xz--dark .xz-welcome h1 { color: var(--xz-text-primary); }
.xz--dark .xz-welcome__sub { color: var(--xz-text-secondary); }
.xz--dark .xz-card { background: var(--xz-bg-layer-1); border-color: var(--xz-border-l1); border-radius: var(--xz-radius-lg); transition: border-color var(--xz-ease) 0.2s, background var(--xz-ease) 0.2s; }
.xz--dark .xz-card:hover { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l3); transform: none; }
.xz--dark .xz-card__t { color: var(--xz-text-primary); }
.xz--dark .xz-card__d { color: var(--xz-text-tertiary); }
.xz--dark .xz-msg--user .xz-msg__main { background: var(--xz-bg-layer-2); border-radius: var(--xz-radius-md); }
.xz--dark .xz-msg__text { color: var(--xz-text-primary); }
.xz--dark .xz-msg__who { background: var(--xz-bg-layer-3); color: var(--xz-text-secondary); }
.xz--dark .xz-msg--assistant .xz-msg__who { background: var(--xz-brand); color: #fff; }
.xz--dark .xz-msg__text :deep(blockquote) { background: var(--xz-bg-layer-1); border-left-color: var(--xz-border-l3); color: var(--xz-text-secondary); }
.xz--dark .xz-msg__text :deep(.md-table th) { background: var(--xz-bg-layer-1); }
.xz--dark .xz-msg__text :deep(.md-table th), .xz--dark .xz-msg__text :deep(.md-table td) { border-color: var(--xz-border-l1); }
.xz--dark .xz-msg__text :deep(.codeblock) { border-color: var(--xz-border-l1); border-radius: var(--xz-radius-md); }
.xz--dark .xz-msg__text :deep(.codeblock__bar) { background: var(--xz-bg-layer-2); color: var(--xz-text-tertiary); }
.xz--dark .xz-msg__text :deep(code.inline) { background: var(--xz-bg-layer-3); color: var(--xz-text-primary); }
.xz--dark .think { border-left-color: var(--xz-border-l2); }
.xz--dark .think__head { color: var(--xz-text-secondary); }
.xz--dark .think__body { color: var(--xz-text-tertiary); }
.xz--dark .tool { background: var(--xz-bg-layer-1); border-color: var(--xz-border-l1); border-radius: var(--xz-radius-md); }
.xz--dark .tool__result { background: var(--xz-bg-base); border-top-color: var(--xz-border-l1); color: var(--xz-text-secondary); }
.xz--dark .xz-msg__ops button { color: var(--xz-text-tertiary); border-radius: 6px; }
.xz--dark .xz-msg__ops button:hover { background: var(--xz-bg-layer-2); color: var(--xz-text-primary); }
.xz--dark .composer { background: var(--xz-bg-layer-1); border-color: var(--xz-border-l2); border-radius: var(--xz-radius-panel); }
.xz--dark .composer.has-text { border-color: var(--xz-brand); box-shadow: 0 0 0 3px rgba(86, 134, 254, 0.16); }
.xz--dark .composer__input { color: var(--xz-text-primary); }
.xz--dark .chip { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l1); color: var(--xz-text-secondary); border-radius: var(--xz-radius-lg); }
.xz--dark .chip:hover { border-color: var(--xz-border-l3); color: var(--xz-text-primary); }
.xz--dark .chip.on { background: rgba(86, 134, 254, 0.16); border-color: var(--xz-brand); color: var(--xz-brand-bright); }
.xz--dark .att { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l1); color: var(--xz-text-secondary); }
.xz--dark .xz-tip { color: var(--xz-text-tertiary); }
.xz--dark .xz-jump { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l1); color: var(--xz-text-secondary); border-radius: 50%; }
.xz--dark .xz-drawer__panel { background: var(--xz-bg-layer-1); color: var(--xz-text-primary); }
.xz--dark .xz-drawer__row { color: var(--xz-text-secondary); }
.xz--dark .xz-drawer__btn, .xz--dark .xz-drawer__close { background: var(--xz-bg-layer-2); border-color: var(--xz-border-l1); color: var(--xz-text-primary); }
</style>