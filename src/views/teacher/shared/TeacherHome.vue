<template>
  <div class="teacher-device-page">
    <header class="tdp-top">
      <div class="tdp-title">
        <span class="tdp-badge">教师</span>
        <b>教师工作台</b>
        <span class="tdp-platform">{{ platformLabel }}</span>
      </div>
      <div class="tdp-user">{{ username }}</div>
    </header>

    <section v-if="loadError" class="tdp-alert">
      数据加载失败：{{ loadError }}
      <button class="tdp-retry" @click="loadData">重试</button>
    </section>

    <section class="tdp-kpis">
      <div v-for="k in kpis" :key="k.key" class="tdp-kpi">
        <b>{{ k.value }}</b>
        <span>{{ k.label }}</span>
      </div>
    </section>

    <section class="tdp-entries">
      <component
        :is="'div'"
        v-for="item in navItems"
        :key="item.key"
        class="tdp-entry"
        :class="{ 'is-todo': item.status !== 'ready' }"
        @click="onEntryClick(item)"
      >
        <span class="t">{{ item.title }}</span>
        <span class="d">{{ item.desc }}</span>
        <span class="tag" :class="statusTone(item.status)">{{ statusLabel(item.status) }}</span>
      </component>
    </section>

    <p class="tdp-note">
      设备端为「查看优先」：可用功能点卡片直接进入；标「功能待开发」的为设备端尚未开发（电脑端已可用）。
      <br />「上传资料 / 课件」位置已预留，等上传功能在设备端落地后启用。
    </p>

    <!-- 说明弹层：手写 div，避免依赖未全局注册的 el-dialog -->
    <div v-if="dialog" class="tdp-mask" @click.self="dialog = null">
      <div class="tdp-dialog">
        <h3>{{ dialog.title }}</h3>
        <p>{{ dialog.body }}</p>
        <button class="tdp-dialog-btn" @click="dialog = null">知道了</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
/**
 * 教师设备端工作台（P3，2026-11-16；P2 时是占位页）
 *
 * 数据来源（真实接口，均已有 require_teacher_or_admin 守卫，未新增任何端点）：
 *   · GET /api/teacher/dashboard  → stats.pending_approval_count / my_papers_count /
 *                                   today_practice_users / total_questions
 *   · GET /api/teacher/classes    → total（班级数）
 *   · GET /api/teacher/papers/stats → total / pending（试卷数、待审批）
 *
 * 为什么用 `window.__VTJ_AUTH__.apiFetch` 而不是 axios：与三端其余手写页保持一致
 * （token 由 auth 模块统一注入，401 时由它统一处理）。
 *
 * 为什么写操作只弹说明、不做控件：D-19 决定设备端写操作显示「功能待开发」，
 * 预留「上传」位置；不提供任何写控件，避免误触改数据，也不用为写操作做权限回归。
 */
import { defineComponent } from 'vue'
import {
  TEACHER_NAV_ITEMS,
  TEACHER_NAV_STATUS_LABEL,
  TEACHER_NAV_STATUS_TONE,
  deviceNavPath,
  type TeacherNavItem,
  type TeacherNavStatus,
} from './teacherDeviceNav'

interface KpiItem { key: string; label: string; value: string }

export default defineComponent({
  name: 'TeacherDeviceHome',
  data() {
    return {
      navItems: TEACHER_NAV_ITEMS as TeacherNavItem[],
      stats: null as null | Record<string, number>,
      classCount: null as number | null,
      paperTotal: null as number | null,
      loading: false,
      loadError: '',
      dialog: null as null | { title: string; body: string },
    }
  },
  computed: {
    platformLabel(): string {
      const platform = (this.$route.meta as any)?.platform
      if (platform === 'tablet') return '平板'
      if (platform === 'mobile') return '手机'
      return '设备端'
    },
    prefix(): 'tablet' | 'mobile' {
      return (this.$route.meta as any)?.platform === 'mobile' ? 'mobile' : 'tablet'
    },
    username(): string {
      const auth = (window as any).__VTJ_AUTH__
      try {
        const state = auth && auth.getState ? auth.getState() : null
        return (state && state.username) || ''
      } catch (e) {
        return ''
      } finally {
        // 仅读取，不改变登录态
      }
    },
    kpis(): KpiItem[] {
      const s = this.stats || {}
      return [
        { key: 'papers', label: '我的试卷', value: this.fmt(s.my_papers_count, this.paperTotal) },
        { key: 'pending', label: '待审批卷', value: this.fmt(s.pending_approval_count, null) },
        { key: 'classes', label: '班级数', value: this.fmt(this.classCount, null) },
        { key: 'practice', label: '今日练习', value: this.fmt(s.today_practice_users, null) },
      ]
    },
  },
  mounted() {
    this.loadData()
  },
  methods: {
    fmt(primary: number | null | undefined, fallback: number | null): string {
      if (typeof primary === 'number' && Number.isFinite(primary)) return String(primary)
      if (typeof fallback === 'number' && Number.isFinite(fallback)) return String(fallback)
      return '—'
    },
    statusLabel(status: TeacherNavStatus): string {
      return TEACHER_NAV_STATUS_LABEL[status]
    },
    statusTone(status: TeacherNavStatus): string {
      return TEACHER_NAV_STATUS_TONE[status]
    },
    async apiGet(path: string): Promise<any> {
      const auth = (window as any).__VTJ_AUTH__
      if (!auth || !auth.apiFetch) throw new Error('认证模块未就绪')
      const res = await auth.apiFetch(path)
      if (!res || !res.ok) throw new Error(`HTTP ${res && res.status}`)
      return res.json()
    },
    async loadData() {
      this.loading = true
      this.loadError = ''
      const results = await Promise.allSettled([
        this.apiGet('/api/teacher/dashboard'),
        this.apiGet('/api/teacher/classes'),
        this.apiGet('/api/teacher/papers/stats'),
      ])
      const [dash, classes, paperStats] = results
      if (dash.status === 'fulfilled') this.stats = (dash.value && dash.value.stats) || {}
      if (classes.status === 'fulfilled') this.classCount = Number(classes.value && classes.value.total) || 0
      if (paperStats.status === 'fulfilled') this.paperTotal = Number(paperStats.value && paperStats.value.total) || 0
      const failed = results.filter((r) => r.status === 'rejected')
      if (failed.length === results.length) {
        this.loadError = (failed[0] as PromiseRejectedResult).reason?.message || '网络错误'
      }
      this.loading = false
    },
    onEntryClick(item: TeacherNavItem) {
      if (item.status === 'ready') {
        const target = deviceNavPath(this.prefix, item)
        if (target && this.$router) {
          this.$router.push(target)
          return
        }
      }
      this.dialog = {
        title: item.status === 'reserved' ? '位置预留' : '功能待开发',
        body: item.reason || '该功能在设备端尚未开发。',
      }
    },
  },
})
</script>

<style scoped>
.teacher-device-page {
  min-height: 100vh;
  background: #f2f5f9;
  color: #1f2d3d;
  padding: 16px;
  font-size: 15px;
}
.tdp-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #163a5f;
  color: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 14px;
}
.tdp-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tdp-title b { font-size: 16px; letter-spacing: 0.4px; }
.tdp-badge { background: rgba(255,255,255,.18); border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.tdp-platform { font-size: 12px; opacity: .8; }
.tdp-user { font-size: 13px; opacity: .9; white-space: nowrap; }

.tdp-alert {
  background: #fdf1f1; border: 1px solid #f3c9c9; color: #d64545;
  border-radius: 10px; padding: 10px 12px; font-size: 13px; margin-bottom: 12px;
}
.tdp-retry { margin-left: 8px; border: 0; background: #d64545; color: #fff; border-radius: 8px; padding: 3px 10px; cursor: pointer; }

.tdp-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.tdp-kpi { background: #fff; border: 1px solid #e6ebf2; border-radius: 12px; padding: 14px; }
.tdp-kpi b { display: block; font-size: 22px; color: #163a5f; }
.tdp-kpi span { font-size: 12px; color: #7a8797; }

.tdp-entries { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.tdp-entry {
  display: flex; flex-direction: column; gap: 6px; align-items: flex-start;
  background: #fff; border: 1px solid #e6ebf2; border-radius: 12px; padding: 14px;
  cursor: pointer; transition: box-shadow .2s, transform .2s;
}
.tdp-entry:hover { box-shadow: 0 6px 18px rgba(22,58,95,.10); transform: translateY(-1px); }
.tdp-entry.is-todo { background: #fbfcfe; }
.tdp-entry .t { font-weight: 600; font-size: 14px; }
.tdp-entry .d { font-size: 12px; color: #7a8797; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.tag.ok { background: #eaf4ee; color: #2f9e6e; }
.tag.warn { background: #fdf0e6; color: #c97a2b; }
.tag.gray { background: #eef1f6; color: #7a8797; }

.tdp-note {
  margin: 14px 0 0; border: 1px dashed #e6ebf2; border-radius: 10px;
  padding: 10px 12px; font-size: 12px; color: #7a8797; background: #fbfcfe; line-height: 1.7;
}

.tdp-mask {
  position: fixed; inset: 0; background: rgba(16,42,71,.45);
  display: grid; place-items: center; padding: 20px; z-index: 60;
}
.tdp-dialog {
  background: #fff; border-radius: 14px; padding: 20px;
  width: min(420px, 92vw); box-shadow: 0 24px 60px rgba(0,0,0,.26);
}
.tdp-dialog h3 { margin: 0 0 8px; font-size: 17px; }
.tdp-dialog p { margin: 0 0 16px; font-size: 14px; color: #5a6488; line-height: 1.7; }
.tdp-dialog-btn {
  width: 100%; border: 0; border-radius: 9px; padding: 10px;
  background: #163a5f; color: #fff; font-size: 14px; cursor: pointer;
}

@media (max-width: 1024px) {
  .tdp-entries { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .teacher-device-page { padding: 12px; }
  .tdp-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .tdp-entries { grid-template-columns: 1fr; }
}
</style>
