<template>
  <div class="teacher-analytics">
    <TeacherNavHeader activeNav="analytics" @logout="handleLogout" />

    <div class="page-content">
      <!-- 筛选区 -->
      <div class="filter-bar">
        <select class="filter-select" v-model="selectedClass" @change="loadData">
          <option :value="0">全部班级</option>
          <option v-for="c in classList" :key="c.class_id" :value="c.class_id">{{ c.class_name }}</option>
        </select>
        <select class="filter-select" v-model="selectedSubject" @change="loadData">
          <option :value="0">全部科目</option>
          <option :value="1">行测</option>
          <option :value="2">申论</option>
          <option :value="3">公专</option>
        </select>
        <div class="time-range-group">
          <button v-for="tr in timeRanges" :key="tr.days" class="time-btn" :class="{ active: selectedDays === tr.days }" @click="switchTimeRange(tr.days)">{{ tr.label }}</button>
        </div>
        <div class="filter-spacer"></div>
        <button class="btn-export" @click="exportReport">📥 导出报告</button>
      </div>

      <!-- 总览卡片 -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon">👨‍🎓</div>
          <div class="sv">{{ overview.total_students }}</div>
          <div class="sl">学生总数</div>
          <div class="stat-trend" v-if="overview.students_trend > 0">↑{{ overview.students_trend }}本周新增</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">📝</div>
          <div class="sv">{{ overview.total_exams }}</div>
          <div class="sl">考试次数</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">📊</div>
          <div class="sv">{{ overview.avg_score }}</div>
          <div class="sl">平均分</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">✅</div>
          <div class="sv">{{ overview.pass_rate }}%</div>
          <div class="sl">及格率</div>
        </div>
      </div>

      <!-- 班级对比趋势图（SVG折线图） -->
      <div class="chart-panel" v-if="trendData.length > 0">
        <h3>📈 班级成绩趋势对比</h3>
        <div class="trend-chart-wrap">
          <svg :viewBox="'0 0 ' + trendSvgWidth + ' ' + trendSvgHeight" class="trend-svg">
            <!-- Y轴刻度线 -->
            <line v-for="tick in trendYTicks" :key="'tick-'+tick" :x1="40" :y1="trendY(tick)" :x2="trendSvgWidth - 10" :y2="trendY(tick)" stroke="#e8e8e8" stroke-width="1" />
            <text v-for="tick in trendYTicks" :key="'lbl-'+tick" :x="36" :y="trendY(tick) + 4" text-anchor="end" fill="#888" font-size="11">{{ tick }}</text>
            <!-- X轴标签 -->
            <text v-for="(pt, i) in trendPoints" :key="'xlabel-'+i" :x="trendX(i)" :y="trendSvgHeight - 4" text-anchor="middle" fill="#888" font-size="10">{{ pt.label }}</text>
            <!-- 每条折线（每个班级一条） -->
            <g v-for="(line, li) in trendLines" :key="'line-'+li">
              <polyline :points="line.points" fill="none" :stroke="trendColors[li % trendColors.length]" stroke-width="2" stroke-linejoin="round" />
              <circle v-for="(pt, pi) in line.dots" :key="'dot-'+li+'-'+pi" :cx="pt.x" :cy="pt.y" r="3" :fill="trendColors[li % trendColors.length]" />
            </g>
            <!-- 图例 -->
            <g v-for="(line, li) in trendLines" :key="'legend-'+li">
              <rect :x="60 + li * 120" :y="6" width="12" height="12" rx="2" :fill="trendColors[li % trendColors.length]" />
              <text :x="76 + li * 120" y="16" fill="#333" font-size="12">{{ line.name }}</text>
            </g>
          </svg>
        </div>
      </div>

      <!-- 双栏：科目对比 + 知识点雷达 -->
      <div class="dual-row">
        <!-- 科目对比柱状图 -->
        <div class="chart-panel half" v-if="overview.subject_comparison && overview.subject_comparison.length > 0">
          <h3>📊 科目成绩对比</h3>
          <div class="bar-chart">
            <div class="bar-col" v-for="(item, i) in overview.subject_comparison" :key="i">
              <div class="bar-value">{{ item.avg_score }}</div>
              <div class="bar-fill" :style="{ height: barHeight(item.avg_score) }"></div>
              <div class="bar-label">{{ item.subject_name }}</div>
              <div class="bar-count">{{ item.exam_count }}次</div>
            </div>
          </div>
        </div>

        <!-- 知识点掌握雷达图（SVG） -->
        <div class="chart-panel half" v-if="knowledgeMastery.length > 0">
          <h3>🕸️ 知识点掌握度雷达图</h3>
          <div class="radar-wrap">
            <svg :viewBox="'0 0 ' + radarSize + ' ' + radarSize" class="radar-svg">
              <!-- 同心多边形网格 -->
              <g v-for="level in 5" :key="'grid-'+level">
                <polygon :points="radarGridPolygon(level)" fill="none" stroke="#ddd" stroke-width="1" />
              </g>
              <!-- 轴线 -->
              <line v-for="(axis, ai) in radarAxes" :key="'axis-'+ai" :x1="radarCx" :y1="radarCy" :x2="axis.x" :y2="axis.y" stroke="#ccc" stroke-width="1" />
              <!-- 数据区域 -->
              <polygon :points="radarDataPolygon" :fill="radarFillColor" fill-opacity="0.3" stroke="#1A3C6D" stroke-width="2" />
              <!-- 数据点 + 标签 -->
              <g v-for="(dot, di) in radarDataDots" :key="'rdot-'+di">
                <circle :cx="dot.x" :cy="dot.y" r="4" fill="#1A3C6D" />
                <text :x="dot.labelX" :y="dot.labelY" text-anchor="middle" fill="#333" font-size="11" font-weight="600">{{ dot.value }}%</text>
                <text :x="dot.nameX" :y="dot.nameY" text-anchor="middle" fill="#666" font-size="10">{{ dot.name }}</text>
              </g>
            </svg>
          </div>
        </div>
      </div>

      <!-- 知识点掌握度条形列表 -->
      <div class="chart-panel" v-if="knowledgeMastery.length > 0">
        <h3>📋 知识点掌握度详情</h3>
        <div class="mastery-list">
          <div class="mastery-item" v-for="kp in knowledgeMastery" :key="kp.point_id">
            <div class="kp-name">{{ kp.point_name }}</div>
            <div class="kp-bar-wrap">
              <div class="kp-bar" :style="{ width: kp.mastery_rate + '%', background: kp.mastery_rate >= 70 ? '#22c55e' : kp.mastery_rate >= 50 ? '#E6A23C' : '#F56C6C' }"></div>
            </div>
            <div class="kp-rate">{{ kp.mastery_rate }}%</div>
          </div>
        </div>
      </div>

      <!-- 题目使用频率 -->
      <div class="chart-panel" v-if="questionUsage.length > 0">
        <h3>🔥 题目使用频率 TOP10</h3>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>题目</th><th>使用次数</th><th>正确率</th><th>科目</th></tr></thead>
            <tbody>
              <tr v-for="q in questionUsage" :key="q.question_id">
                <td v-html="renderQuestionContent(q.question_content)"></td>
                <td>{{ q.usage_count }}</td>
                <td :class="{ 'high-rate': q.correct_rate >= 70, 'low-rate': q.correct_rate < 40 }">{{ q.correct_rate }}%</td>
                <td>{{ q.subject_name }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import TeacherNavHeader from './TeacherNavHeader.vue';
import { renderQuestionContent } from '@/utils/questionRender';

export default defineComponent({
  name: 'TeacherAnalytics',
  components: { TeacherNavHeader },
  setup() {
    const router = useRouter();
    const classList = ref<any[]>([]);
    const selectedClass = ref(0);
    const selectedSubject = ref(0);
    const selectedDays = ref(30);
    const overview = ref<any>({ total_students: 0, total_exams: 0, avg_score: 0, pass_rate: 0, subject_comparison: [], students_trend: 0 });
    const knowledgeMastery = ref<any[]>([]);
    const questionUsage = ref<any[]>([]);
    const trendData = ref<any[]>([]);

    const timeRanges = [
      { label: '近7天', days: 7 },
      { label: '近30天', days: 30 },
      { label: '近90天', days: 90 },
    ];

    onMounted(async () => {
      await loadClasses();
      await loadData();
    });

    async function loadClasses() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      try {
        const res = await auth.apiFetch('/api/teacher/classes');
        const data = await res.json();
        if (data.success) classList.value = data.items || [];
      } catch (e) { /* ignore */ }
    }

    async function loadData() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      const params = new URLSearchParams();
      if (selectedClass.value) params.append('class_id', String(selectedClass.value));
      params.append('days', String(selectedDays.value));
      const subjectParam = selectedSubject.value ? '&subject_id=' + selectedSubject.value : '';
      try {
        const [overviewRes, masteryRes, usageRes] = await Promise.all([
          auth.apiFetch('/api/teacher/analytics/overview?' + params.toString()),
          auth.apiFetch('/api/teacher/analytics/knowledge-mastery?' + subjectParam.substring(1)),
          auth.apiFetch('/api/teacher/analytics/question-usage?limit=10' + subjectParam),
        ]);
        const overviewData = await overviewRes.json();
        const masteryData = await masteryRes.json();
        const usageData = await usageRes.json();
        if (overviewData.success !== false) overview.value = overviewData;
        if (masteryData.success) knowledgeMastery.value = masteryData.items || [];
        if (usageData.success) questionUsage.value = usageData.items || [];

        // 趋势数据：优先使用后端分班级序列；缺失时降级为全站平均分单序列
        const classTrend = overviewData.class_trend;
        if (Array.isArray(classTrend) && classTrend.length) {
          trendData.value = classTrend;
        } else {
          const st = overviewData.score_trend || {};
          const dates: string[] = st.dates || [];
          const scores: number[] = st.scores || [];
          trendData.value = dates.length
            ? [{
                class_name: '平均分',
                points: dates.map((d: string, i: number) => ({ date: d, avg_score: scores[i] ?? 0 })),
              }]
            : [];
        }
      } catch (e) { console.error('加载分析数据失败:', e); }
    }

    function switchTimeRange(days: number) {
      selectedDays.value = days;
      loadData();
    }

    function exportReport() {
      ElMessage.info('正在导出报告...');
    }

    // ==================== 班级成绩趋势对比（SVG 手绘） ====================
    const TREND_W = 640;
    const TREND_H = 260;
    const TREND_PAD_L = 40;
    const TREND_PAD_R = 10;
    const TREND_PAD_T = 28;
    const TREND_PAD_B = 24;

    const TREND_COLORS = [
      '#1A365D', '#f59e0b', '#22c55e', '#ef4444', '#8b5cf6',
      '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#64748b',
    ];

    const trendSvgWidth = TREND_W;
    const trendSvgHeight = TREND_H;

    const trendColors = TREND_COLORS;

    // X 轴日期标签：取所有班级序列日期的并集，按字典序排序
    // （后端对全站与各班级统一日期格式，%m-%d 与 %Y-%m-%d 均可正确字典序排序）
    const trendPoints = computed<{ label: string }[]>(() => {
      const seen = new Set<string>();
      for (const series of trendData.value) {
        for (const p of series?.points || []) {
          const label = String(p?.date ?? '');
          if (label) seen.add(label);
        }
      }
      return [...seen].sort().map((label) => ({ label }));
    });

    // Y 轴值域：0 到向上取整到 10 的倍数
    const trendMaxScore = computed<number>(() => {
      let max = 0;
      for (const series of trendData.value) {
        for (const p of series?.points || []) {
          const v = Number(p?.avg_score);
          if (Number.isFinite(v) && v > max) max = v;
        }
      }
      if (max <= 0) return 100;
      return Math.ceil(max / 10) * 10;
    });

    // Y 轴刻度：5 等分，值从 0 到 trendMaxScore
    const trendYTicks = computed<number[]>(() => {
      const top = trendMaxScore.value;
      const count = 5;
      return Array.from({ length: count + 1 }, (_, i) => Math.round((top / count) * i));
    });

    /** 刻度值 -> 像素 Y 坐标（与 trendYTicks 生成规则严格互逆） */
    function trendY(tick: number): number {
      const top = trendMaxScore.value;
      const innerH = TREND_H - TREND_PAD_T - TREND_PAD_B;
      if (top <= 0) return TREND_H - TREND_PAD_B;
      const ratio = Number(tick) / top;
      const clamped = Math.min(Math.max(ratio, 0), 1);
      return TREND_H - TREND_PAD_B - clamped * innerH;
    }

    /** 索引 -> 像素 X 坐标 */
    function trendX(i: number): number {
      const n = trendPoints.value.length;
      const innerW = TREND_W - TREND_PAD_L - TREND_PAD_R;
      if (n <= 0) return TREND_PAD_L + innerW / 2;
      if (n === 1) return TREND_PAD_L + innerW / 2;
      const step = innerW / (n - 1);
      return TREND_PAD_L + i * step;
    }

    /** 每个班级一条折线；某班在某日期无数据时跳过该点，不补 0 */
    const trendLines = computed<{ name: string; points: string; dots: { x: number; y: number }[] }[]>(() => {
      const labels = trendPoints.value.map((p) => p.label);
      const indexOf = new Map<string, number>(labels.map((l, i) => [l, i]));

      return trendData.value.map((series, si) => {
        const dots: { x: number; y: number }[] = [];
        for (const p of series?.points || []) {
          const label = String(p?.date ?? '');
          const i = indexOf.get(label);
          if (i === undefined) continue;
          const score = Number(p?.avg_score);
          if (!Number.isFinite(score)) continue;
          dots.push({ x: trendX(i), y: trendY(score) });
        }
        return {
          name: String(series?.class_name || `班级${si + 1}`),
          points: dots.map((d) => `${d.x},${d.y}`).join(' '),
          dots,
        };
      });
    });

    // Bar chart
    function barHeight(score: number) {
      const max = Math.max(...(overview.value.subject_comparison || []).map((s: any) => s.avg_score), 1);
      return (score / max * 160) + 'px';
    }

    // Radar chart
    const radarSize = 280;
    const radarCx = 140;
    const radarCy = 140;
    const radarRadius = 110;
    const radarFillColor = '#1A3C6D';

    const radarAxes = computed(() => {
      const n = knowledgeMastery.value.length || 1;
      return knowledgeMastery.value.map((_: any, i: number) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        return { x: radarCx + radarRadius * Math.cos(angle), y: radarCy + radarRadius * Math.sin(angle) };
      });
    });

    function radarGridPolygon(level: number) {
      const n = knowledgeMastery.value.length || 1;
      const r = (radarRadius * level) / 5;
      const pts: string[] = [];
      for (let i = 0; i < n; i++) {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        pts.push((radarCx + r * Math.cos(angle)).toFixed(1) + ',' + (radarCy + r * Math.sin(angle)).toFixed(1));
      }
      return pts.join(' ');
    }

    const radarDataPolygon = computed(() => {
      const n = knowledgeMastery.value.length || 1;
      const pts: string[] = [];
      for (let i = 0; i < n; i++) {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        const r = (radarRadius * (knowledgeMastery.value[i]?.mastery_rate || 0)) / 100;
        pts.push((radarCx + r * Math.cos(angle)).toFixed(1) + ',' + (radarCy + r * Math.sin(angle)).toFixed(1));
      }
      return pts.join(' ');
    });

    const radarDataDots = computed(() => {
      const n = knowledgeMastery.value.length || 1;
      return knowledgeMastery.value.map((kp: any, i: number) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        const r = (radarRadius * (kp.mastery_rate || 0)) / 100;
        const x = radarCx + r * Math.cos(angle);
        const y = radarCy + r * Math.sin(angle);
        const labelR = radarRadius + 20;
        const nameR = radarRadius + 32;
        return {
          x, y,
          value: kp.mastery_rate || 0,
          name: kp.point_name || '',
          labelX: radarCx + labelR * Math.cos(angle),
          labelY: radarCy + labelR * Math.sin(angle) + 4,
          nameX: radarCx + nameR * Math.cos(angle),
          nameY: radarCy + nameR * Math.sin(angle) + 4,
        };
      });
    });

    function handleLogout() { const auth = (window as any).__VTJ_AUTH__; if (auth) auth.logout(); router.push('/login'); }

    return {
      classList, selectedClass, selectedSubject, selectedDays, overview, knowledgeMastery,
      questionUsage, trendData, timeRanges, switchTimeRange, exportReport, barHeight,
      radarSize, radarCx, radarCy, radarFillColor, radarAxes, radarGridPolygon,
      radarDataPolygon, radarDataDots, handleLogout, renderQuestionContent,
      loadData,
      trendSvgWidth, trendSvgHeight, trendYTicks, trendY, trendPoints, trendX,
      trendLines, trendColors,
    };
  }
});
</script>

<style scoped>
.teacher-analytics { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.page-content { max-width: 1200px; margin: 0 auto; padding: 24px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }
.filter-select { padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; min-width: 160px; }
.filter-spacer { flex: 1; }
.time-range-group { display: flex; gap: 0; border: 1px solid #d9d9d9; border-radius: 6px; overflow: hidden; }
.time-btn { padding: 7px 16px; border: none; background: #fff; cursor: pointer; font-size: 13px; color: #666; transition: all 0.2s; }
.time-btn + .time-btn { border-left: 1px solid #d9d9d9; }
.time-btn.active { background: #1A3C6D; color: #fff; font-weight: 600; }
.btn-export { padding: 8px 18px; background: #fff; color: #1A3C6D; border: 1px solid #1A3C6D; border-radius: 6px; cursor: pointer; font-size: 14px; white-space: nowrap; }
.btn-export:hover { background: #f0f5ff; }
.stats-row { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-card { flex: 1; background: #fff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.05); position: relative; }
.stat-icon { font-size: 24px; margin-bottom: 4px; }
.sv { font-size: 28px; font-weight: 700; color: #1A3C6D; }
.sl { font-size: 13px; color: #888; margin-top: 4px; }
.stat-trend { font-size: 11px; color: #22c55e; margin-top: 4px; }
.chart-panel { background: #fff; border-radius: 10px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
.chart-panel h3 { color: #1A3C6D; margin: 0 0 16px; font-size: 16px; }
.dual-row { display: flex; gap: 24px; margin-bottom: 24px; }
.chart-panel.half { flex: 1; margin-bottom: 0; }
/* Trend chart */
.trend-chart-wrap { width: 100%; overflow-x: auto; }
.trend-svg { width: 100%; height: auto; min-width: 500px; }
/* Bar chart */
.bar-chart { display: flex; justify-content: center; align-items: flex-end; gap: 32px; height: 220px; padding: 0 40px; }
.bar-col { display: flex; flex-direction: column; align-items: center; }
.bar-value { font-size: 14px; color: #1A3C6D; margin-bottom: 6px; font-weight: 600; }
.bar-fill { width: 56px; background: linear-gradient(180deg, #1A3C6D, #2B5A9C); border-radius: 6px 6px 0 0; min-height: 4px; transition: height 0.3s; }
.bar-label { font-size: 13px; color: #666; margin-top: 8px; }
.bar-count { font-size: 11px; color: #aaa; }
/* Radar chart */
.radar-wrap { display: flex; justify-content: center; }
.radar-svg { width: 280px; height: 280px; }
/* Mastery list */
.mastery-list { display: flex; flex-direction: column; gap: 10px; }
.mastery-item { display: flex; align-items: center; gap: 12px; }
.kp-name { width: 120px; font-size: 13px; color: #333; text-align: right; flex-shrink: 0; }
.kp-bar-wrap { flex: 1; height: 20px; background: #f0f0f0; border-radius: 10px; overflow: hidden; }
.kp-bar { height: 100%; border-radius: 10px; transition: width 0.3s; }
.kp-rate { width: 50px; font-size: 13px; font-weight: 600; color: #1A3C6D; }
/* Table */
.table-wrap { background: #fff; border-radius: 10px; overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.high-rate { color: #22c55e; font-weight: 600; }
.low-rate { color: #F56C6C; font-weight: 600; }
</style>
