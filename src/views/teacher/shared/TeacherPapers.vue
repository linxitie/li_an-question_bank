<template>
  <div class="teacher-papers-page">
    <header class="tp-top">
      <div class="tp-title">
        <span class="tp-badge">教师</span>
        <b>试卷</b>
        <span class="tp-platform">{{ platformLabel }}</span>
      </div>
      <button class="tp-back" @click="goHome">返回工作台</button>
    </header>

    <nav class="tp-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tp-tab"
        :class="{ on: status === tab.key }"
        @click="switchStatus(tab.key)"
      >
        {{ tab.label }}<span v-if="tabCount(tab.key) !== null" class="tp-count">{{ tabCount(tab.key) }}</span>
      </button>
    </nav>

    <section v-if="error" class="tp-alert">
      加载失败：{{ error }}
      <button class="tp-retry" @click="reload(page)">重试</button>
    </section>

    <section class="tp-list">
      <div class="tp-listhead">
        <span>共 <b>{{ total }}</b> 份 · 第 {{ page }} / {{ pageCount }} 页</span>
        <span class="tp-readonly">只读（组卷 / 发布请在电脑端）</span>
      </div>

      <div v-if="loading" class="tp-empty">加载中…</div>
      <div v-else-if="!items.length" class="tp-empty">该状态下没有试卷</div>

      <div v-for="item in items" :key="item.paper_id" class="tp-row">
        <div class="tp-rowmain">
          <span class="tp-name">{{ item.paper_name }}</span>
          <span class="tp-status" :class="statusTone(item.paper_type)">{{ statusText(item.paper_type) }}</span>
        </div>
        <div class="tp-rowmeta">
          <span>{{ item.subject_name || '—' }}</span>
          <span>{{ item.question_count || 0 }} 题 · {{ item.total_score || 0 }} 分</span>
          <span>{{ item.duration || 0 }} 分钟</span>
          <span v-if="item.paper_code" class="tp-code">{{ item.paper_code }}</span>
        </div>
      </div>

      <div class="tp-pager">
        <button :disabled="page <= 1 || loading" @click="reload(page - 1)">上一页</button>
        <button :disabled="page >= pageCount || loading" @click="reload(page + 1)">下一页</button>
      </div>
    </section>
  </div>
</template>

<script lang="ts">
/**
 * 教师设备端「试卷」只读列表（P4，2026-11-16）
 *
 * 数据来源（均已实测）：
 *   · GET /api/teacher/papers?status=&page=&page_size= → { success,total,page,page_size,items[] }
 *   · GET /api/teacher/papers/stats                    → { total,draft,pending,approved,published,ended }
 *
 * 为什么只读：D-10/D-19 —— 组卷、编辑、发布、删除都留在电脑端双栏工作台；
 * 设备端只负责"看清单与状态"，避免手机上误改已发布卷。
 */
import { defineComponent } from 'vue'

interface PaperRow {
  paper_id: number
  paper_name: string
  paper_code?: string
  subject_name?: string
  question_count?: number
  total_score?: number
  duration?: number
  paper_type?: string
  composition_method?: string
}

const PAGE_SIZE = 10
const STATUS_TEXT: Record<string, string> = {
  DRAFT: '草稿',
  PENDING: '待审批',
  APPROVED: '已通过',
  PUBLISHED: '已发布',
  ENDED: '已结束',
}

export default defineComponent({
  name: 'TeacherDevicePapers',
  data() {
    return {
      tabs: [
        { key: '', label: '全部' },
        { key: 'DRAFT', label: '草稿' },
        { key: 'PENDING', label: '待审批' },
        { key: 'PUBLISHED', label: '已发布' },
        { key: 'ENDED', label: '已结束' },
      ],
      status: '',
      stats: null as null | Record<string, number>,
      page: 1,
      total: 0,
      pageSize: PAGE_SIZE,
      items: [] as PaperRow[],
      loading: false,
      error: '',
    }
  },
  computed: {
    platformLabel(): string {
      const platform = (this.$route.meta as any)?.platform
      return platform === 'mobile' ? '手机' : platform === 'tablet' ? '平板' : '设备端'
    },
    prefix(): 'tablet' | 'mobile' {
      return (this.$route.meta as any)?.platform === 'mobile' ? 'mobile' : 'tablet'
    },
    pageCount(): number {
      return Math.max(1, Math.ceil(this.total / this.pageSize))
    },
  },
  mounted() {
    this.loadStats()
    this.reload(1)
  },
  methods: {
    goHome() {
      if (this.$router) this.$router.push(`/${this.prefix}/teacher/home`)
    },
    statusText(type?: string): string {
      return STATUS_TEXT[String(type || '')] || String(type || '—')
    },
    statusTone(type?: string): string {
      const key = String(type || '')
      if (key === 'PUBLISHED') return 'ok'
      if (key === 'PENDING') return 'warn'
      if (key === 'ENDED') return 'gray'
      return 'gray'
    },
    tabCount(key: string): string | number | null {
      const s = this.stats
      if (!s) return null
      if (!key) return s.total ?? null
      const map: Record<string, string> = {
        DRAFT: 'draft',
        PENDING: 'pending',
        PUBLISHED: 'published',
        ENDED: 'ended',
      }
      const field = map[key]
      return field && typeof s[field] === 'number' ? s[field] : null
    },
    switchStatus(key: string) {
      if (this.status === key) return
      this.status = key
      this.reload(1)
    },
    async apiGet(path: string): Promise<any> {
      const auth = (window as any).__VTJ_AUTH__
      if (!auth || !auth.apiFetch) throw new Error('认证模块未就绪')
      const res = await auth.apiFetch(path)
      if (!res || !res.ok) throw new Error(`HTTP ${res && res.status}`)
      return res.json()
    },
    async loadStats() {
      try {
        this.stats = await this.apiGet('/api/teacher/papers/stats')
      } catch (e) {
        this.stats = null
      }
    },
    async reload(page: number) {
      this.loading = true
      this.error = ''
      try {
        const params = new URLSearchParams()
        params.set('page', String(page))
        params.set('page_size', String(this.pageSize))
        if (this.status) params.set('status', this.status)
        const data = await this.apiGet(`/api/teacher/papers?${params.toString()}`)
        this.items = Array.isArray(data.items) ? data.items : []
        this.total = Number(data.total) || 0
        this.page = Number(data.page) || page
      } catch (e: any) {
        this.error = e?.message || '网络错误'
        this.items = []
      } finally {
        this.loading = false
      }
    },
  },
})
</script>

<style scoped>
.teacher-papers-page { min-height: 100vh; background: #f2f5f9; color: #1f2d3d; padding: 16px; font-size: 14px; }
.tp-top {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  background: #163a5f; color: #fff; border-radius: 12px; padding: 12px 16px; margin-bottom: 12px;
}
.tp-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tp-title b { font-size: 16px; }
.tp-badge { background: rgba(255,255,255,.18); border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.tp-platform { font-size: 12px; opacity: .8; }
.tp-back {
  border: 1px solid rgba(255,255,255,.35); background: transparent; color: #fff;
  border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer;
}
.tp-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.tp-tab {
  border: 1px solid #e6ebf2; background: #fff; color: #163a5f; border-radius: 999px;
  padding: 6px 14px; font-size: 13px; cursor: pointer;
}
.tp-tab.on { background: #163a5f; color: #fff; border-color: #163a5f; }
.tp-count { margin-left: 6px; font-size: 11px; opacity: .75; }
.tp-alert { background: #fdf1f1; border: 1px solid #f3c9c9; color: #d64545; border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; }
.tp-retry { margin-left: 8px; border: 0; background: #d64545; color: #fff; border-radius: 8px; padding: 3px 10px; cursor: pointer; }
.tp-list { background: #fff; border: 1px solid #e6ebf2; border-radius: 12px; overflow: hidden; }
.tp-listhead {
  display: flex; justify-content: space-between; gap: 10px; padding: 10px 14px;
  border-bottom: 1px solid #e6ebf2; font-size: 12px; color: #7a8797;
}
.tp-readonly { color: #c97a2b; }
.tp-empty { padding: 26px; text-align: center; color: #7a8797; font-size: 13px; }
.tp-row { padding: 12px 14px; border-bottom: 1px solid #e6ebf2; display: flex; flex-direction: column; gap: 6px; }
.tp-rowmain { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }
.tp-name { font-weight: 600; font-size: 14px; }
.tp-status { font-size: 11px; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.tp-status.ok { background: #eaf4ee; color: #2f9e6e; }
.tp-status.warn { background: #fdf0e6; color: #c97a2b; }
.tp-status.gray { background: #eef1f6; color: #7a8797; }
.tp-rowmeta { display: flex; gap: 12px; font-size: 12px; color: #7a8797; flex-wrap: wrap; }
.tp-code { color: #b4becb; }
.tp-pager { display: flex; gap: 10px; justify-content: center; padding: 12px; }
.tp-pager button {
  border: 1px solid #e6ebf2; background: #fff; border-radius: 8px; padding: 6px 14px;
  font-size: 13px; color: #163a5f; cursor: pointer;
}
.tp-pager button:disabled { opacity: .5; cursor: default; }
@media (max-width: 640px) {
  .teacher-papers-page { padding: 12px; }
  .tp-rowmeta { gap: 8px; }
}
</style>
