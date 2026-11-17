<template>
  <div class="teacher-scores-page">
    <header class="ts-top">
      <div class="ts-title">
        <span class="ts-badge">教师</span>
        <b>成绩概览</b>
        <span class="ts-platform">{{ platformLabel }}</span>
      </div>
      <button class="ts-back" @click="goHome">返回工作台</button>
    </header>

    <section class="ts-filter">
      <select v-model="paperId" class="ts-select" @change="reload">
        <option value="">全部试卷（汇总）</option>
        <option v-for="p in papers" :key="p.paper_id" :value="String(p.paper_id)">
          {{ p.paper_name }}
        </option>
      </select>
      <button class="ts-refresh" :disabled="loading" @click="reload">刷新</button>
    </section>

    <section v-if="error" class="ts-alert">
      加载失败：{{ error }}
      <button class="ts-retry" @click="reload">重试</button>
    </section>

    <section class="ts-kpis">
      <div class="ts-kpi"><b>{{ overview.total_students }}</b><span>参考人数</span></div>
      <div class="ts-kpi"><b>{{ fmt(overview.avg_score) }}</b><span>班级均分</span></div>
      <div class="ts-kpi"><b>{{ fmt(overview.max_score) }}</b><span>最高分</span></div>
      <div class="ts-kpi"><b>{{ fmt(overview.min_score) }}</b><span>最低分</span></div>
      <div class="ts-kpi"><b>{{ fmt(overview.pass_rate) }}%</b><span>及格率</span></div>
    </section>

    <section class="ts-card">
      <h3>分数段分布</h3>
      <div v-if="!overview.total_students" class="ts-empty">暂无可统计的成绩</div>
      <template v-else>
        <div class="ts-bars">
          <div v-for="(cnt, idx) in overview.distribution.student_counts" :key="idx" class="ts-barwrap">
            <div class="ts-bar" :style="{ height: barHeight(cnt) }">
              <span>{{ cnt }}</span>
            </div>
            <span class="ts-barlabel">{{ overview.distribution.score_ranges[idx] || '' }}</span>
          </div>
        </div>
        <p class="ts-hint">及格线按总分 ≥ 60 分统计（与电脑端成绩驾驶舱同口径）</p>
      </template>
    </section>

    <section class="ts-card">
      <h3>学生名单 <span v-if="overview.student_scores.length" class="ts-sub">按总分降序</span></h3>
      <div v-if="!overview.student_scores.length" class="ts-empty">暂无已交卷记录</div>
      <div v-for="row in overview.student_scores" :key="row.user_id" class="ts-row">
        <span class="ts-rank">{{ row.rank }}</span>
        <span class="ts-name">{{ row.user_name }}<em v-if="row.class_name"> · {{ row.class_name }}</em></span>
        <span class="ts-score">{{ fmt(row.total_score) }} 分</span>
        <span class="ts-meta">{{ row.user_no }}<template v-if="row.submit_time"> · {{ shortTime(row.submit_time) }}</template></span>
      </div>
    </section>

    <p class="ts-note">只读页面：逐题正确率、知识点分析等深度报表请在电脑端「成绩管理」查看。</p>
  </div>
</template>

<script lang="ts">
/**
 * 教师设备端「成绩概览」（P4，2026-11-16，D-21 选①：班级均分 / 分布 / 名单）
 *
 * 数据来源（已实测 200）：
 *   · GET /api/teacher/scores/overview?paper_id= → { total_students, avg_score, max_score,
 *       min_score, pass_rate, distribution:{score_ranges,student_counts}, student_scores[] }
 *   · GET /api/teacher/papers?page_size=100       → 试卷下拉
 *
 * 重要背景：该接口在本仓库原本**只要有一条已交卷记录就 500**
 * （`StudentScoreItem` 的 xingce/shenlun/police_score 是 Optional 但没默认值 → pydantic 必填）。
 * P4 期间已修复（schemas/teacher.py 补 `= None`）并加了回归测试
 * `backend/tests/test_teacher_scores_overview.py`。本页直接消费修复后的接口。
 *
 * 口径与电脑端一致：`pass_rate` 是 0–100 的百分数（PC 也是 `+ '%'` 展示）。
 */
import { defineComponent } from 'vue'

interface PaperOption { paper_id: number; paper_name: string }
interface StudentRow {
  rank: number
  user_id: number
  user_no: string
  user_name: string
  class_name?: string | null
  total_score: number
  submit_time?: string | null
}

const EMPTY_OVERVIEW = () => ({
  total_students: 0,
  avg_score: 0,
  max_score: 0,
  min_score: 0,
  pass_rate: 0,
  distribution: { score_ranges: [] as string[], student_counts: [] as number[] },
  student_scores: [] as StudentRow[],
})

export default defineComponent({
  name: 'TeacherDeviceScores',
  data() {
    return {
      papers: [] as PaperOption[],
      paperId: '',
      overview: EMPTY_OVERVIEW(),
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
  },
  mounted() {
    this.loadPapers()
    this.reload()
  },
  methods: {
    goHome() {
      if (this.$router) this.$router.push(`/${this.prefix}/teacher/home`)
    },
    fmt(value: unknown): string {
      const num = Number(value)
      if (!Number.isFinite(num)) return '—'
      return Number.isInteger(num) ? String(num) : num.toFixed(1)
    },
    shortTime(value?: string | null): string {
      if (!value) return ''
      const text = String(value).replace('T', ' ')
      return text.slice(0, 16)
    },
    barHeight(count: number): string {
      const max = Math.max(1, ...this.overview.distribution.student_counts.map((n) => Number(n) || 0))
      const pct = Math.round(((Number(count) || 0) / max) * 100)
      return `${Math.max(pct, 3)}%`
    },
    async apiGet(path: string): Promise<any> {
      const auth = (window as any).__VTJ_AUTH__
      if (!auth || !auth.apiFetch) throw new Error('认证模块未就绪')
      const res = await auth.apiFetch(path)
      if (!res || !res.ok) throw new Error(`HTTP ${res && res.status}`)
      return res.json()
    },
    async loadPapers() {
      try {
        const data = await this.apiGet('/api/teacher/papers?page=1&page_size=100')
        this.papers = Array.isArray(data.items)
          ? data.items.map((p: any) => ({ paper_id: p.paper_id, paper_name: p.paper_name }))
          : []
      } catch (e) {
        this.papers = []
      }
    },
    async reload() {
      this.loading = true
      this.error = ''
      try {
        const query = this.paperId ? `?paper_id=${encodeURIComponent(this.paperId)}` : ''
        const data = await this.apiGet(`/api/teacher/scores/overview${query}`)
        this.overview = {
          total_students: Number(data.total_students) || 0,
          avg_score: Number(data.avg_score) || 0,
          max_score: Number(data.max_score) || 0,
          min_score: Number(data.min_score) || 0,
          pass_rate: Number(data.pass_rate) || 0,
          distribution: {
            score_ranges: (data.distribution && data.distribution.score_ranges) || [],
            student_counts: (data.distribution && data.distribution.student_counts) || [],
          },
          student_scores: Array.isArray(data.student_scores) ? data.student_scores : [],
        }
      } catch (e: any) {
        this.error = e?.message || '网络错误'
        this.overview = EMPTY_OVERVIEW()
      } finally {
        this.loading = false
      }
    },
  },
})
</script>

<style scoped>
.teacher-scores-page { min-height: 100vh; background: #f2f5f9; color: #1f2d3d; padding: 16px; font-size: 14px; }
.ts-top {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  background: #163a5f; color: #fff; border-radius: 12px; padding: 12px 16px; margin-bottom: 12px;
}
.ts-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ts-title b { font-size: 16px; }
.ts-badge { background: rgba(255,255,255,.18); border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.ts-platform { font-size: 12px; opacity: .8; }
.ts-back {
  border: 1px solid rgba(255,255,255,.35); background: transparent; color: #fff;
  border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer;
}
.ts-filter { display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.ts-select {
  flex: 1; min-width: 200px; border: 1px solid #e6ebf2; border-radius: 10px;
  padding: 9px 12px; font-size: 13px; background: #fff; color: #1f2d3d;
}
.ts-refresh {
  border: 0; border-radius: 10px; padding: 9px 16px; background: #163a5f; color: #fff;
  font-size: 13px; cursor: pointer;
}
.ts-refresh:disabled { opacity: .6; cursor: default; }
.ts-alert { background: #fdf1f1; border: 1px solid #f3c9c9; color: #d64545; border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; }
.ts-retry { margin-left: 8px; border: 0; background: #d64545; color: #fff; border-radius: 8px; padding: 3px 10px; cursor: pointer; }

.ts-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.ts-kpi { background: #fff; border: 1px solid #e6ebf2; border-radius: 12px; padding: 12px; }
.ts-kpi b { display: block; font-size: 20px; color: #163a5f; }
.ts-kpi span { font-size: 12px; color: #7a8797; }

.ts-card { background: #fff; border: 1px solid #e6ebf2; border-radius: 12px; padding: 14px; margin-bottom: 12px; }
.ts-card h3 { margin: 0 0 12px; font-size: 15px; }
.ts-sub { font-size: 12px; color: #7a8797; font-weight: 400; margin-left: 6px; }
.ts-empty { padding: 18px; text-align: center; color: #7a8797; font-size: 13px; }

.ts-bars { display: flex; align-items: flex-end; gap: 12px; height: 150px; padding: 6px 2px 0; }
.ts-barwrap { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; }
.ts-bar {
  width: 100%; border-radius: 6px 6px 0 0;
  background: linear-gradient(180deg, #3f7ad6, #163a5f);
  position: relative; min-height: 8px;
}
.ts-bar span { position: absolute; top: -18px; left: 0; right: 0; text-align: center; font-size: 11px; color: #7a8797; }
.ts-barlabel { margin-top: 6px; font-size: 11px; color: #7a8797; }
.ts-hint { margin: 10px 0 0; font-size: 12px; color: #b4becb; }

.ts-row {
  display: grid; grid-template-columns: 32px 1fr auto; gap: 8px 10px;
  align-items: baseline; padding: 10px 0; border-bottom: 1px solid #f0f3f8;
}
.ts-row:last-child { border-bottom: 0; }
.ts-rank { color: #163a5f; font-weight: 600; }
.ts-name { font-size: 14px; }
.ts-name em { font-style: normal; color: #7a8797; font-size: 12px; }
.ts-score { color: #2f9e6e; font-weight: 600; }
.ts-meta { grid-column: 2 / -1; font-size: 12px; color: #b4becb; }

.ts-note { margin: 6px 0 0; font-size: 12px; color: #7a8797; }

@media (max-width: 900px) {
  .ts-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .ts-kpis .ts-kpi:nth-child(4), .ts-kpis .ts-kpi:nth-child(5) { grid-column: span 1; }
}
@media (max-width: 640px) {
  .teacher-scores-page { padding: 12px; }
  .ts-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ts-select { width: 100%; }
}
</style>
