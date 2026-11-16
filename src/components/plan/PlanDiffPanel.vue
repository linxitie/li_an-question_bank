<template>
  <section class="pd">
    <header class="pd__head">
      <div>
        <p class="pd__title">方案版本对比</p>
        <p class="pd__sub">{{ state.versions.length ? '共 ' + state.versions.length + ' 个版本' : '还没有快照' }}</p>
      </div>
      <button class="pd__btn" :disabled="state.busy" @click="capture">
        {{ state.busy ? '保存中…' : '存为新版本' }}
      </button>
    </header>

    <div v-if="state.loading" class="pd__skeleton"></div>

    <div v-else-if="state.versions.length < 2" class="pd__empty">
      <p>{{ state.versions.length ? '至少要有两个版本才能对比' : '当前方案还没存过快照' }}</p>
      <p class="pd__empty-tip">点「存为新版本」，改完方案再存一次，就能看出改了什么</p>
    </div>

    <div v-else>
      <div class="pd__pickers">
        <label class="pd__pick">
          <span>从</span>
          <select v-model.number="state.fromVersion" @change="loadDiff">
            <option v-for="v in state.versions" :key="'f' + v.version" :value="v.version">v{{ v.version }}</option>
          </select>
        </label>
        <label class="pd__pick">
          <span>到</span>
          <select v-model.number="state.toVersion" @change="loadDiff">
            <option v-for="v in state.versions" :key="'t' + v.version" :value="v.version">v{{ v.version }}</option>
          </select>
        </label>
        <span class="pd__counts" v-if="state.diff">
          +{{ state.diff.counts.added }} / −{{ state.diff.counts.removed }} / ~{{ state.diff.counts.changed }}
        </span>
      </div>

      <div class="pd__cols" v-if="state.diff">
        <div class="pd__col">
          <p class="pd__col-head">v{{ state.diff.from.version }}</p>
          <div v-for="(t, i) in leftTasks" :key="'l' + i" class="pd__task" :class="t.state">
            <span class="pd__mark">{{ t.mark }}</span>
            <span class="pd__text">{{ t.title }}</span>
          </div>
          <p v-if="!leftTasks.length" class="pd__none">（空）</p>
        </div>
        <div class="pd__col">
          <p class="pd__col-head">v{{ state.diff.to.version }}</p>
          <div v-for="(t, i) in rightTasks" :key="'r' + i" class="pd__task" :class="t.state">
            <span class="pd__mark">{{ t.mark }}</span>
            <span class="pd__text">{{ t.title }}</span>
          </div>
          <p v-if="!rightTasks.length" class="pd__none">（空）</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'

const state = reactive({
  loading: true,
  busy: false,
  versions: [],
  fromVersion: 1,
  toVersion: 1,
  diff: null,
})

const leftTasks = computed(() => {
  const d = state.diff
  if (!d) return []
  const removed = new Set(d.removed.map((t) => t.title))
  const changed = new Set(d.changed.map((c) => c.title))
  const all = []
  d.removed.forEach((t) => all.push({ title: t.title, state: 'removed', mark: '−' }))
  d.changed.forEach((c) => all.push({ title: c.title, state: 'changed', mark: '~' }))
  return all
})

const rightTasks = computed(() => {
  const d = state.diff
  if (!d) return []
  const all = []
  d.added.forEach((t) => all.push({ title: t.title, state: 'added', mark: '+' }))
  d.changed.forEach((c) => all.push({ title: c.title, state: 'changed', mark: '~' }))
  return all
})

function token() {
  try {
    const raw = localStorage.getItem('__VTJ_AUTH_STATE__')
    if (raw) { const o = JSON.parse(raw); if (o && o.token) return o.token }
  } catch (e) { /* ignore */ }
  return localStorage.getItem('token') || ''
}

async function loadVersions() {
  const t = token()
  if (!t) { state.loading = false; return }
  try {
    const res = await fetch('/api/v1/growth/plan-snapshot/list', {
      headers: { Authorization: 'Bearer ' + t },
    })
    const d = await res.json()
    state.versions = (d.items || []).slice().sort((a, b) => a.version - b.version)
    if (state.versions.length >= 2) {
      state.fromVersion = state.versions[state.versions.length - 2].version
      state.toVersion = state.versions[state.versions.length - 1].version
      await loadDiff()
    }
  } catch (e) { /* 静默 */ }
  finally { state.loading = false }
}

async function loadDiff() {
  const t = token()
  if (!t || state.fromVersion === state.toVersion) { state.diff = null; return }
  try {
    const res = await fetch(
      '/api/v1/growth/plan-snapshot/diff?from_version=' + state.fromVersion + '&to_version=' + state.toVersion,
      { headers: { Authorization: 'Bearer ' + t } },
    )
    if (!res.ok) { state.diff = null; return }
    state.diff = await res.json()
  } catch (e) { state.diff = null }
}

async function capture() {
  const t = token()
  if (!t) return
  state.busy = true
  try {
    const res = await fetch('/api/v1/growth/plan-snapshot/capture', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + t },
    })
    const d = await res.json()
    if (!res.ok) throw new Error(d.detail || '保存失败')
    await loadVersions()
  } catch (e) {
    // 没有计划时后端会 404，给出人话提示
    state.versions = state.versions || []
    window.alert(e.message || '保存失败：还没有学习计划')
  } finally {
    state.busy = false
  }
}

onMounted(loadVersions)
</script>

<style scoped>
.pd { margin: 12px 0 0; padding: 16px 18px; border-radius: 12px; background: #fff; border: 1px solid #eef1f7; box-shadow: 0 1px 4px rgba(17,24,39,.06); }
.pd__head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.pd__title { margin: 0; font-size: 14px; font-weight: 700; color: #1a2b5f; }
.pd__sub { margin: 3px 0 0; font-size: 11.5px; color: #8a8faa; }
.pd__btn { border: 1px solid #e3e6ec; background: #fff; border-radius: 8px; padding: 6px 12px; font-size: 12px; color: #5c6270; cursor: pointer; }
.pd__btn:hover:not(:disabled) { border-color: #c41e3a; color: #c41e3a; }
.pd__btn:disabled { opacity: .6; cursor: default; }
.pd__pickers { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 12px; color: #5c6270; }
.pd__pick { display: flex; align-items: center; gap: 6px; }
.pd__pick select { border: 1px solid #e3e6ec; border-radius: 7px; padding: 4px 8px; font-size: 12px; background: #fff; }
.pd__counts { margin-left: auto; font-size: 11.5px; color: #8a8faa; }
.pd__cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.pd__col { background: #fafbfe; border: 1px solid #eef1f7; border-radius: 10px; padding: 10px; }
.pd__col-head { margin: 0 0 8px; font-size: 12px; font-weight: 700; color: #1a2b5f; }
.pd__task { display: flex; align-items: flex-start; gap: 6px; padding: 6px 8px; border-radius: 7px; font-size: 12px; margin-bottom: 5px; background: #fff; border: 1px solid #eef1f7; color: #4b5563; }
.pd__task.added { border-color: #bbf7d0; background: #f0fdf4; color: #166534; }
.pd__task.removed { border-color: #fecaca; background: #fef2f2; color: #991b1b; }
.pd__task.changed { border-color: #fde68a; background: #fffbeb; color: #92400e; }
.pd__mark { font-weight: 700; }
.pd__text { flex: 1; }
.pd__none { margin: 0; font-size: 11.5px; color: #b6bcc8; }
.pd__empty { padding: 12px 0 4px; }
.pd__empty p { margin: 0; font-size: 12px; color: #9aa0aa; }
.pd__empty-tip { margin-top: 4px !important; font-size: 11px !important; color: #c2c7cf !important; }
.pd__skeleton { height: 90px; border-radius: 10px; background: #f3f5f9; }
@media (max-width: 900px) { .pd__cols { grid-template-columns: 1fr; } }
</style>
