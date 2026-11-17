<template>
  <div class="teacher-questions-page">
    <header class="tq-top">
      <div class="tq-title">
        <span class="tq-badge">教师</span>
        <b>题目管理</b>
        <span class="tq-platform">{{ platformLabel }}</span>
      </div>
      <div class="tq-actions">
        <button class="tq-back" @click="goHome">返回工作台</button>
      </div>
    </header>

    <section class="tq-filters">
      <input
        v-model="keyword"
        class="tq-input"
        type="search"
        placeholder="搜索题干 / 知识点…"
        @keyup.enter="reload(1)"
      />
      <select v-model="subjectId" class="tq-select" @change="reload(1)">
        <option value="">全部科目</option>
        <option v-for="s in subjects" :key="s.id" :value="String(s.id)">{{ s.name }}</option>
      </select>
      <button class="tq-search" :disabled="loading" @click="reload(1)">搜索</button>
    </section>

    <section v-if="error" class="tq-alert">
      加载失败：{{ error }}
      <button class="tq-retry" @click="reload(page)">重试</button>
    </section>

    <section class="tq-list">
      <div class="tq-listhead">
        <span>共 <b>{{ total }}</b> 题 · 第 {{ page }} / {{ pageCount }} 页</span>
        <span class="tq-readonly">只读（编辑请在电脑端）</span>
      </div>

      <div v-if="loading" class="tq-empty">加载中…</div>
      <div v-else-if="!items.length" class="tq-empty">没有匹配的题目</div>

      <div
        v-for="item in items"
        :key="item.question_id"
        class="tq-row"
        @click="openPreview(item)"
      >
        <div class="tq-rowmain">
          <span class="tq-no">{{ item.question_id }}</span>
          <span class="tq-stem" v-html="stemOf(item)"></span>
        </div>
        <div class="tq-rowmeta">
          <span>{{ item.subject_name || '—' }} · {{ item.type_name || '—' }}</span>
          <span class="tq-diff">难度 {{ item.difficulty || '—' }}</span>
          <span class="tq-preview">预览</span>
        </div>
      </div>

      <div class="tq-pager">
        <button :disabled="page <= 1 || loading" @click="reload(page - 1)">上一页</button>
        <button :disabled="page >= pageCount || loading" @click="reload(page + 1)">下一页</button>
      </div>
    </section>

    <div v-if="preview" class="tq-mask" @click.self="preview = null">
      <div class="tq-dialog">
        <h3>第 {{ preview.question_id }} 题 · {{ preview.subject_name || '—' }} {{ preview.type_name || '' }}</h3>
        <div class="tq-stem-full" v-html="stemOf(preview)"></div>
        <div v-if="optionsOf(preview).length" class="tq-options">
          <div v-for="(opt, idx) in optionsOf(preview)" :key="idx" class="tq-option">
            <span class="tq-optkey">{{ optionKey(idx) }}</span>
            <span v-html="stripHtml(opt)"></span>
          </div>
        </div>
        <p v-if="preview.answer" class="tq-answer">
          答案：{{ preview.answer }}<span v-if="preview.answer_analysis">（含解析）</span>
        </p>
        <p v-else class="tq-answer tq-answer-muted">该题暂无答案/解析（可在电脑端补录）</p>
        <button class="tq-dialog-btn" @click="preview = null">关闭</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
/**
 * 教师设备端「题目管理」只读列表（P3，2026-11-16）
 *
 * 数据来源：`GET /api/teacher/questions`（教师专用，已有 require_teacher_or_admin 守卫）
 *   · 返回 { success, total, page, page_size, items[] }
 *   · 支持 keyword / subject_id / page / page_size（已实测）
 *
 * 为什么只做只读：
 *   D-10/D-19 定的是「设备端查看优先、写操作显示功能待开发」；
 *   编辑/新建/导入都在电脑端 `/teacher/questions`，避免手机上误改题库。
 *
 * 为什么自己写列表而不复用 el-table：
 *   平板/手机两端的列宽与交互不同（卡片式更合适），手写 DOM 更好控制；
 *   预览用手写弹层（与 ParseDraftDrawer 的做法一致），不依赖可能未全局注册的 el-dialog。
 *
 * 为什么 v-html：题目题干在库里是富文本（含 <p>、图片），与 PC 端渲染口径一致；
 *   内容来自我们自己的题库接口（管理员/教师录入），不是外部输入。
 */
import { defineComponent } from 'vue'

interface QuestionRow {
  question_id: number
  subject_id?: number
  subject_name?: string
  type_id?: number
  type_name?: string
  question_content?: string
  full_content?: string
  options?: unknown
  answer?: string
  answer_analysis?: string
  difficulty?: number
  score?: number
}

const PAGE_SIZE = 20
const SUBJECTS = [
  { id: 1, name: '行测' },
  { id: 2, name: '申论' },
  { id: 3, name: '公专' },
]

export default defineComponent({
  name: 'TeacherDeviceQuestions',
  data() {
    return {
      keyword: '',
      subjectId: '',
      subjects: SUBJECTS,
      page: 1,
      total: 0,
      pageSize: PAGE_SIZE,
      items: [] as QuestionRow[],
      loading: false,
      error: '',
      preview: null as QuestionRow | null,
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
    pageCount(): number {
      return Math.max(1, Math.ceil(this.total / this.pageSize))
    },
  },
  mounted() {
    this.reload(1)
  },
  methods: {
    goHome() {
      if (this.$router) this.$router.push(`/${this.prefix}/teacher/home`)
    },
    async apiGet(path: string): Promise<any> {
      const auth = (window as any).__VTJ_AUTH__
      if (!auth || !auth.apiFetch) throw new Error('认证模块未就绪')
      const res = await auth.apiFetch(path)
      if (!res || !res.ok) throw new Error(`HTTP ${res && res.status}`)
      return res.json()
    },
    async reload(page: number) {
      this.loading = true
      this.error = ''
      try {
        const params = new URLSearchParams()
        params.set('page', String(page))
        params.set('page_size', String(this.pageSize))
        if (this.keyword.trim()) params.set('keyword', this.keyword.trim())
        if (this.subjectId) params.set('subject_id', this.subjectId)
        const data = await this.apiGet(`/api/teacher/questions?${params.toString()}`)
        this.items = Array.isArray(data.items) ? data.items : []
        this.total = Number(data.total) || 0
        this.page = Number(data.page) || page
        if (Number(data.page_size)) this.pageSize = Number(data.page_size)
      } catch (e: any) {
        this.error = e?.message || '网络错误'
        this.items = []
      } finally {
        this.loading = false
      }
    },
    stemOf(item: QuestionRow): string {
      return String(item.question_content || item.full_content || '（无题干）')
    },
    stripHtml(html: unknown): string {
      return String(html || '').replace(/<[^>]+>/g, '').trim() || '（空）'
    },
    optionsOf(item: QuestionRow): unknown[] {
      const raw = item.options as any
      if (!raw) return []
      if (Array.isArray(raw)) return raw
      if (typeof raw === 'string') {
        try {
          const parsed = JSON.parse(raw)
          return Array.isArray(parsed) ? parsed : []
        } catch (e) {
          return []
        }
      }
      return []
    },
    optionKey(idx: number): string {
      return String.fromCharCode(65 + idx)
    },
    openPreview(item: QuestionRow) {
      this.preview = item
    },
  },
})
</script>

<style scoped>
.teacher-questions-page {
  min-height: 100vh;
  background: #f2f5f9;
  color: #1f2d3d;
  padding: 16px;
  font-size: 14px;
}
.tq-top {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  background: #163a5f; color: #fff; border-radius: 12px; padding: 12px 16px; margin-bottom: 14px;
}
.tq-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tq-title b { font-size: 16px; }
.tq-badge { background: rgba(255,255,255,.18); border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.tq-platform { font-size: 12px; opacity: .8; }
.tq-back {
  border: 1px solid rgba(255,255,255,.35); background: transparent; color: #fff;
  border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer;
}

.tq-filters { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.tq-input, .tq-select {
  border: 1px solid #e6ebf2; border-radius: 10px; padding: 9px 12px;
  font-size: 13px; background: #fff; color: #1f2d3d;
}
.tq-input { flex: 1; min-width: 180px; }
.tq-search {
  border: 0; border-radius: 10px; padding: 9px 16px;
  background: #163a5f; color: #fff; font-size: 13px; cursor: pointer;
}
.tq-search:disabled { opacity: .6; cursor: default; }

.tq-alert {
  background: #fdf1f1; border: 1px solid #f3c9c9; color: #d64545;
  border-radius: 10px; padding: 10px 12px; font-size: 13px; margin-bottom: 12px;
}
.tq-retry { margin-left: 8px; border: 0; background: #d64545; color: #fff; border-radius: 8px; padding: 3px 10px; cursor: pointer; }

.tq-list { background: #fff; border: 1px solid #e6ebf2; border-radius: 12px; overflow: hidden; }
.tq-listhead {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
  padding: 10px 14px; border-bottom: 1px solid #e6ebf2; font-size: 12px; color: #7a8797;
}
.tq-readonly { color: #c97a2b; }
.tq-empty { padding: 26px; text-align: center; color: #7a8797; font-size: 13px; }

.tq-row {
  display: flex; flex-direction: column; gap: 6px;
  padding: 12px 14px; border-bottom: 1px solid #e6ebf2; cursor: pointer;
}
.tq-row:hover { background: #f8fafd; }
.tq-rowmain { display: flex; gap: 8px; align-items: baseline; }
.tq-no { color: #163a5f; font-weight: 600; font-size: 12px; min-width: 34px; }
.tq-stem {
  flex: 1; overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.tq-rowmeta { display: flex; gap: 10px; font-size: 12px; color: #7a8797; padding-left: 42px; }
.tq-diff { color: #b4becb; }
.tq-preview { margin-left: auto; color: #2f6bd8; }

.tq-pager { display: flex; gap: 10px; justify-content: center; padding: 12px; }
.tq-pager button {
  border: 1px solid #e6ebf2; background: #fff; border-radius: 8px;
  padding: 6px 14px; font-size: 13px; cursor: pointer; color: #163a5f;
}
.tq-pager button:disabled { opacity: .5; cursor: default; }

.tq-mask {
  position: fixed; inset: 0; background: rgba(16,42,71,.45);
  display: grid; place-items: center; padding: 20px; z-index: 60;
}
.tq-dialog {
  background: #fff; border-radius: 14px; padding: 20px;
  width: min(680px, 94vw); max-height: 84vh; overflow: auto; box-shadow: 0 24px 60px rgba(0,0,0,.26);
}
.tq-dialog h3 { margin: 0 0 10px; font-size: 16px; color: #163a5f; }
.tq-stem-full { font-size: 14px; line-height: 1.8; }
.tq-options { margin: 10px 0 0; display: grid; gap: 6px; }
.tq-option { display: flex; gap: 8px; font-size: 13px; line-height: 1.7; }
.tq-optkey { color: #2f6bd8; font-weight: 600; }
.tq-answer { margin: 12px 0 0; font-size: 13px; color: #2f9e6e; }
.tq-answer-muted { color: #7a8797; }
.tq-dialog-btn {
  margin-top: 16px; width: 100%; border: 0; border-radius: 9px;
  padding: 10px; background: #163a5f; color: #fff; font-size: 14px; cursor: pointer;
}

@media (max-width: 640px) {
  .teacher-questions-page { padding: 12px; }
  .tq-input, .tq-select { width: 100%; }
  .tq-rowmeta { padding-left: 0; flex-wrap: wrap; }
}
</style>
