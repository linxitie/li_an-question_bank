<template>
  <div class="score-workspace">
    <TeacherNavHeader activeNav="scores" @logout="handleLogout" />

    <main class="sw-main">
      <header class="sw-head">
        <div>
          <h1>成绩管理</h1>
          <p class="sw-sub">原「成绩管理 + 数据分析」合并为一张驾驶舱：全校 / 本班、正确率、错题类型、知识点与逐生明细。</p>
        </div>
        <div class="sw-scope" role="group" aria-label="统计范围">
          <button type="button" :class="{ on: scope === 'school' }" @click="setScope('school')">全校</button>
          <button type="button" :class="{ on: scope === 'class' }" @click="setScope('class')">本班</button>
        </div>
      </header>

      <section class="sw-filters">
        <label v-if="scope === 'class'" class="sw-field">
          <span>班级</span>
          <select v-model.number="selectedClass" @change="loadAll">
            <option :value="0">请选择班级</option>
            <option v-for="c in classes" :key="c.class_id" :value="c.class_id">{{ c.class_name }}</option>
          </select>
        </label>
        <label class="sw-field">
          <span>试卷</span>
          <select v-model.number="selectedPaper" @change="loadAll">
            <option :value="0">全部试卷</option>
            <option v-for="p in papers" :key="p.paper_id" :value="p.paper_id">{{ p.paper_name }}</option>
          </select>
        </label>
        <label class="sw-field">
          <span>趋势窗口</span>
          <select v-model.number="days" @change="loadAll">
            <option :value="30">近 30 天</option>
            <option :value="90">近 90 天</option>
            <option :value="180">近 180 天</option>
          </select>
        </label>
        <button type="button" class="sw-refresh" :disabled="loading" @click="loadAll">
          {{ loading ? '加载中…' : '刷新数据' }}
        </button>
      </section>

      <div v-if="error" class="sw-alert" role="alert">
        {{ error }}
        <button type="button" @click="loadAll">重试</button>
      </div>

      <section class="sw-kpis" :class="{ dim: loading }">
        <article v-for="kpi in kpis" :key="kpi.label" class="sw-kpi">
          <span class="sw-kpi-label">{{ kpi.label }}</span>
          <strong>{{ kpi.value }}</strong>
          <small>{{ kpi.hint }}</small>
        </article>
      </section>

      <nav class="sw-tabs" aria-label="成绩视图">
        <button v-for="tab in tabs" :key="tab.key" type="button"
                :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
          {{ tab.label }}
        </button>
      </nav>

      <section v-if="loading && !overview.total_students" class="sw-state">正在汇总成绩…</section>

      <template v-else>
        <!-- 总览 -->
        <section v-show="activeTab === 'overview'" class="sw-grid two">
          <article class="sw-card">
            <h2>成绩分布</h2>
            <p class="sw-hint">按总分区间统计参考人次，红色为不及格区间。</p>
            <XChart v-if="studentScores.length" width="100%" height="300px" :option="distributionOption" />
            <div v-else class="sw-state">当前范围暂无已完成考试。</div>
          </article>
          <article class="sw-card">
            <h2>及格结构</h2>
            <p class="sw-hint">及格线按 60 分计，与成绩概览一致。</p>
            <XChart v-if="studentScores.length" width="100%" height="300px" :option="passPieOption" />
            <div v-else class="sw-state">暂无及格率数据。</div>
          </article>
          <article class="sw-card span-2">
            <h2>成绩趋势</h2>
            <p class="sw-hint">{{ scope === 'school' ? '全校' : '本班' }}已完成考试的平均分走势（近 {{ days }} 天）。</p>
            <XChart v-if="scoreTrend.length" width="100%" height="320px" :option="trendOption" />
            <div v-else class="sw-state">当前窗口没有考试记录，试试放宽到 180 天。</div>
          </article>
          <article class="sw-card span-2 advice">
            <h2>分析建议</h2>
            <ul v-if="advice.length">
              <li v-for="(item, i) in advice" :key="i" :class="item.level">{{ item.text }}</li>
            </ul>
            <div v-else class="sw-state">数据量不足，暂不生成建议；先完成一次考试或选择具体试卷。</div>
          </article>
        </section>

        <!-- 班级对比 -->
        <section v-show="activeTab === 'classes'" class="sw-grid">
          <article class="sw-card span-2">
            <h2>班级横向对比</h2>
            <p class="sw-hint">平均分（柱）与及格率（折线）同图，点击图例可隐藏序列。</p>
            <XChart v-if="classCompare.length" width="100%" height="360px" :option="classCompareOption" />
            <div v-else class="sw-state">暂无班级数据。</div>
          </article>
          <article class="sw-card span-2 table-card">
            <table class="sw-table">
              <thead><tr><th>班级</th><th>学生数</th><th>参考人次</th><th>平均分</th><th>及格率</th><th>诊断</th></tr></thead>
              <tbody>
                <tr v-for="row in classCompare" :key="row.class_id">
                  <td>{{ row.class_name }}</td>
                  <td>{{ row.student_count }}</td>
                  <td>{{ row.exam_count }}</td>
                  <td>{{ row.avg_score }}</td>
                  <td>{{ row.pass_rate }}%</td>
                  <td><span class="sw-chip" :class="row.pass_rate >= 60 ? 'ok' : 'bad'">{{ row.pass_rate >= 60 ? '达标' : '需关注' }}</span></td>
                </tr>
                <tr v-if="!classCompare.length"><td colspan="6" class="sw-empty">暂无班级对比数据</td></tr>
              </tbody>
            </table>
          </article>
        </section>

        <!-- 错题分析 -->
        <section v-show="activeTab === 'wrong'" class="sw-grid">
          <article class="sw-card">
            <h2>主要错题类型</h2>
            <p class="sw-hint">按正确率从低到高排序，仅统计作答过的题。</p>
            <XChart v-if="typeRows.length" width="100%" height="340px" :option="typeOption" />
            <div v-else class="sw-state">选择一份具体试卷后，才能按题型统计正确率。</div>
          </article>
          <article class="sw-card">
            <h2>薄弱知识点</h2>
            <p class="sw-hint">悬浮查看考点全名；正确率越低越靠上。</p>
            <div v-if="weakPoints.length" class="sw-point-list">
              <div v-for="point in weakPoints" :key="point.point_id" class="sw-point-row"
                   :title="point.point_name + ' · ' + point.subject_name + ' · 作答 ' + point.total_attempts + ' 次'">
                <span class="sw-point-name">{{ point.point_name }}</span>
                <span class="sw-point-bar"><i :style="{ width: point.mastery_rate + '%' }"></i></span>
                <b>{{ point.mastery_rate }}%</b>
              </div>
            </div>
            <div v-else class="sw-state">暂无知识点作答数据。</div>
          </article>
          <article class="sw-card span-2 table-card">
            <div class="sw-card-head">
              <h2>逐题正确率</h2>
              <span class="sw-hint">共 {{ questionRows.length }} 题{{ selectedPaper ? '' : '（全部试卷汇总）' }}</span>
            </div>
            <table class="sw-table">
              <thead><tr><th>题目</th><th>题型</th><th>知识点</th><th>作答</th><th>正确率</th><th>常见错答</th></tr></thead>
              <tbody>
                <tr v-for="q in questionRows" :key="q.question_id">
                  <td class="sw-q" :title="q.question_content">{{ truncate(q.question_content, 46) }}</td>
                  <td>{{ q.type_name || '未标注' }}</td>
                  <td><span class="sw-tip" :title="q.point_name || '未标注知识点'">{{ q.point_name || '未标注' }}</span></td>
                  <td>{{ q.total_attempts }}</td>
                  <td><span :class="q.correct_rate >= 60 ? 'sw-rate ok' : 'sw-rate bad'">{{ q.correct_rate }}%</span></td>
                  <td class="sw-mistakes">
                    <template v-if="q.common_mistakes && q.common_mistakes.length">
                      <span v-for="m in q.common_mistakes" :key="m[0]">{{ m[0] }} × {{ m[1] }}</span>
                    </template>
                    <span v-else>—</span>
                  </td>
                </tr>
                <tr v-if="!questionRows.length"><td colspan="6" class="sw-empty">暂无逐题统计</td></tr>
              </tbody>
            </table>
          </article>
        </section>

        <!-- 知识点 -->
        <section v-show="activeTab === 'points'" class="sw-grid">
          <article class="sw-card span-2">
            <h2>知识点掌握度</h2>
            <p class="sw-hint">仅展示有作答记录的三级知识点；悬浮柱条可看考点全名与作答次数。</p>
            <XChart v-if="knowledgeItems.length" width="100%" height="420px" :option="pointOption" />
            <div v-else class="sw-state">暂无知识点掌握度数据。</div>
          </article>
          <article class="sw-card span-2">
            <h2>薄弱考点清单</h2>
            <div class="sw-kp-grid">
              <div v-for="point in weakPoints" :key="point.point_id" class="sw-kp"
                   :title="point.point_name + ' · 作答 ' + point.total_attempts + ' 次'">
                <div class="sw-kp-top"><strong>{{ point.point_name }}</strong><span>{{ point.mastery_rate }}%</span></div>
                <div class="sw-kp-bar"><i :style="{ width: point.mastery_rate + '%' }"></i></div>
                <small>{{ point.subject_name || '未标注科目' }} · 正确 {{ point.correct_count }}/{{ point.total_attempts }}</small>
              </div>
            </div>
          </article>
        </section>

        <!-- 学生成绩 -->
        <section v-show="activeTab === 'students'" class="sw-grid">
          <article class="sw-card span-2 table-card">
            <div class="sw-card-head">
              <h2>学生成绩明细</h2>
              <input v-model.trim="studentKeyword" class="sw-search" type="search" placeholder="搜索姓名 / 学号 / 班级" />
            </div>
            <table class="sw-table">
              <thead><tr><th>排名</th><th>学号</th><th>姓名</th><th>班级</th><th>总分</th><th>用时</th><th>风险</th><th></th></tr></thead>
              <tbody>
                <tr v-for="s in filteredStudents" :key="s.user_id">
                  <td>{{ s.rank }}</td>
                  <td>{{ s.user_no }}</td>
                  <td>{{ s.user_name }}</td>
                  <td>{{ s.class_name || '—' }}</td>
                  <td :class="s.total_score >= 60 ? 'sw-rate ok' : 'sw-rate bad'">{{ s.total_score }}</td>
                  <td>{{ s.duration_used || 0 }} 分钟</td>
                  <td><span class="sw-chip" :class="s.total_score >= 60 ? 'ok' : 'bad'">{{ s.total_score >= 60 ? '达标' : '待提升' }}</span></td>
                  <td><button type="button" class="sw-link" @click="openStudent(s)">详情</button></td>
                </tr>
                <tr v-if="!filteredStudents.length"><td colspan="8" class="sw-empty">没有匹配的学生成绩</td></tr>
              </tbody>
            </table>
          </article>
        </section>
      </template>
    </main>

    <div v-if="studentModal.open" class="sw-modal-mask" @click.self="closeStudent">
      <section class="sw-modal" role="dialog" aria-label="学生成绩详情">
        <header>
          <div>
            <h2>{{ studentModal.data.user_name || '学生' }}</h2>
            <p>{{ studentModal.data.user_no }} · {{ studentModal.data.class_name }} · 共 {{ studentModal.data.exam_count || 0 }} 次考试</p>
          </div>
          <button type="button" @click="closeStudent" aria-label="关闭">×</button>
        </header>
        <div v-if="studentModal.loading" class="sw-state">加载中…</div>
        <template v-else>
          <XChart v-if="studentModal.data.exams && studentModal.data.exams.length"
                  width="100%" height="240px" :option="studentTrendOption" />
          <table class="sw-table">
            <thead><tr><th>试卷</th><th>得分</th><th>用时</th><th>提交时间</th></tr></thead>
            <tbody>
              <tr v-for="ex in studentModal.data.exams || []" :key="ex.record_id">
                <td>{{ ex.paper_name }}</td>
                <td :class="ex.total_score >= 60 ? 'sw-rate ok' : 'sw-rate bad'">{{ ex.total_score }}</td>
                <td>{{ ex.duration_used || 0 }} 分钟</td>
                <td>{{ formatTime(ex.submit_time) }}</td>
              </tr>
              <tr v-if="!studentModal.data.exams || !studentModal.data.exams.length"><td colspan="4" class="sw-empty">暂无考试记录</td></tr>
            </tbody>
          </table>
        </template>
      </section>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { computed, defineComponent, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { XChart } from '@vtj/charts';
import TeacherNavHeader from '$vtj/vue/TeacherNavHeader.vue';

const TABS = [
  { key: 'overview', label: '总览' },
  { key: 'classes', label: '班级对比' },
  { key: 'wrong', label: '错题分析' },
  { key: 'points', label: '知识点' },
  { key: 'students', label: '学生成绩' },
];

function safeJson(res: any) {
  return res.json().catch(function () { return {}; });
}

export default defineComponent({
  name: 'TeacherScoresWorkspace',
  components: { XChart, TeacherNavHeader },
  setup() {
    const router = useRouter();
    const scope = ref('school');
    const selectedClass = ref(0);
    const selectedPaper = ref(0);
    const days = ref(90);
    const activeTab = ref('overview');
    const loading = ref(false);
    const error = ref('');
    const studentKeyword = ref('');

    const papers = ref<any[]>([]);
    const classes = ref<any[]>([]);
    const classCompare = ref<any[]>([]);
    const questionStats = ref<any[]>([]);
    const knowledgeItems = ref<any[]>([]);
    const studentScores = ref<any[]>([]);
    const analytics = reactive<any>({ score_trend: { dates: [], scores: [] }, total_exams: 0 });
    const overview = reactive<any>({
      avg_score: 0, max_score: 0, min_score: 0, pass_rate: 0, total_students: 0,
      distribution: { score_ranges: [], student_counts: [] }, question_rates: [],
    });

    const studentModal = reactive<any>({ open: false, loading: false, data: {} });

    const tabs = TABS;
    const currentClassId = computed(function () { return scope.value === 'class' ? selectedClass.value : 0; });
    const scoreTrend = computed(function () { return analytics.score_trend && analytics.score_trend.scores ? analytics.score_trend.scores : []; });

    const kpis = computed(function () {
      return [
        { label: '平均分', value: overview.avg_score, hint: scope.value === 'school' ? '全校已完成考试' : '本班已完成考试' },
        { label: '及格率', value: overview.pass_rate + '%', hint: '总分 ≥ 60 分' },
        { label: '参考人数', value: overview.total_students, hint: '去重后的学生数' },
        { label: '考试人次', value: analytics.total_exams || 0, hint: '近 ' + days.value + ' 天' },
        { label: '薄弱考点', value: weakPoints.value.length, hint: '掌握度 < 60%' },
      ];
    });

    const filteredStudents = computed(function () {
      const key = studentKeyword.value.toLowerCase();
      if (!key) return studentScores.value;
      return studentScores.value.filter(function (s) {
        return [s.user_name, s.user_no, s.class_name].some(function (v) {
          return String(v || '').toLowerCase().indexOf(key) >= 0;
        });
      });
    });

    const questionRows = computed(function () {
      if (questionStats.value.length) return questionStats.value;
      return (overview.question_rates || []).map(function (q: any) {
        return Object.assign({ correct_count: Math.round(q.total_attempts * q.correct_rate / 100) }, q);
      });
    });

    const weakPoints = computed(function () {
      return knowledgeItems.value
        .filter(function (p: any) { return p.mastery_rate < 60; })
        .slice()
        .sort(function (a: any, b: any) { return a.mastery_rate - b.mastery_rate; })
        .slice(0, 8);
    });

    const typeRows = computed(function () {
      const map: any = {};
      questionRows.value.forEach(function (q: any) {
        const key = q.type_name || '未标注题型';
        if (!map[key]) map[key] = { name: key, attempts: 0, correct: 0 };
        map[key].attempts += Number(q.total_attempts || 0);
        map[key].correct += Number(q.correct_count || 0);
      });
      return Object.keys(map).map(function (key) {
        const row = map[key];
        return { name: key, attempts: row.attempts, rate: row.attempts ? Math.round(row.correct / row.attempts * 1000) / 10 : 0 };
      }).sort(function (a, b) { return a.rate - b.rate; });
    });

    const advice = computed(function () {
      const list: any[] = [];
      if (!overview.total_students) return list;
      if (overview.pass_rate < 60) {
        list.push({ level: 'bad', text: '及格率 ' + overview.pass_rate + '%，低于 60% 警戒线：优先安排基础题限时训练，并跟踪后 20% 学生。' });
      } else {
        list.push({ level: 'ok', text: '及格率 ' + overview.pass_rate + '%，整体达标；下一步把平均分 ' + overview.avg_score + ' 向高分段推进。' });
      }
      const worstType = typeRows.value[0];
      if (worstType && worstType.rate < 60) {
        list.push({ level: 'bad', text: '最薄弱题型是「' + worstType.name + '」，正确率 ' + worstType.rate + '%；建议按该题型做 20 题专项。' });
      }
      const worstPoint = weakPoints.value[0];
      if (worstPoint) {
        list.push({ level: 'bad', text: '最薄弱考点「' + worstPoint.point_name + '」掌握度 ' + worstPoint.mastery_rate + '%，可回看对应题组材料与解析。' });
      }
      if (scoreTrend.value.length >= 2) {
        const first = scoreTrend.value[0];
        const last = scoreTrend.value[scoreTrend.value.length - 1];
        const delta = Math.round((last - first) * 10) / 10;
        list.push({ level: delta >= 0 ? 'ok' : 'bad', text: '近 ' + days.value + ' 天平均分' + (delta >= 0 ? '上升 ' : '下降 ') + Math.abs(delta) + ' 分。' });
      }
      return list;
    });

    const distributionOption = computed(function () {
      const ranges = (overview.distribution && overview.distribution.score_ranges) || [];
      const counts = (overview.distribution && overview.distribution.student_counts) || [];
      return {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: 12, right: 12, top: 24, bottom: 8, containLabel: true },
        xAxis: { type: 'category', data: ranges, axisTick: { show: false } },
        yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#eef2f7' } } },
        series: [{
          type: 'bar', data: counts, barMaxWidth: 46,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: function (p: any) { return p.dataIndex === 0 ? '#dc2626' : '#1a3c6d'; },
          },
        }],
      };
    });

    const passPieOption = computed(function () {
      const counts = (overview.distribution && overview.distribution.student_counts) || [];
      const fail = counts[0] || 0;
      const pass = counts.slice(1).reduce(function (a: number, b: number) { return a + b; }, 0);
      return {
        tooltip: { trigger: 'item', formatter: '{b}: {c} 人次 ({d}%)' },
        legend: { bottom: 0, icon: 'circle' },
        series: [{
          type: 'pie', radius: ['48%', '72%'], center: ['50%', '45%'],
          label: { formatter: '{b}\n{d}%' },
          data: [
            { name: '及格', value: pass, itemStyle: { color: '#16a34a' } },
            { name: '不及格', value: fail, itemStyle: { color: '#dc2626' } },
          ],
        }],
      };
    });

    const trendOption = computed(function () {
      const dates = (analytics.score_trend && analytics.score_trend.dates) || [];
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: 12, right: 16, top: 30, bottom: 12, containLabel: true },
        xAxis: { type: 'category', data: dates, boundaryGap: false },
        yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: '#eef2f7' } } },
        series: [{
          name: '平均分', type: 'line', data: scoreTrend.value, smooth: true,
          symbolSize: 7, lineStyle: { width: 3, color: '#2563eb' },
          itemStyle: { color: '#2563eb' },
          areaStyle: { color: 'rgba(37,99,235,0.12)' },
        }],
      };
    });

    const classCompareOption = computed(function () {
      const names = classCompare.value.map(function (c) { return c.class_name; });
      return {
        tooltip: { trigger: 'axis' },
        legend: { top: 0, data: ['平均分', '及格率'] },
        grid: { left: 12, right: 20, top: 40, bottom: 10, containLabel: true },
        xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: names.length > 8 ? 28 : 0 } },
        yAxis: [
          { type: 'value', name: '平均分', splitLine: { lineStyle: { color: '#eef2f7' } } },
          { type: 'value', name: '及格率 %', max: 100, splitLine: { show: false } },
        ],
        series: [
          { name: '平均分', type: 'bar', barMaxWidth: 38, data: classCompare.value.map(function (c) { return c.avg_score; }), itemStyle: { color: '#1a3c6d', borderRadius: [5, 5, 0, 0] } },
          { name: '及格率', type: 'line', yAxisIndex: 1, smooth: true, symbolSize: 7, data: classCompare.value.map(function (c) { return c.pass_rate; }), itemStyle: { color: '#f59e0b' }, lineStyle: { width: 2 } },
        ],
      };
    });

    const typeOption = computed(function () {
      const rows = typeRows.value.slice().reverse();
      return {
        tooltip: { trigger: 'axis', formatter: '{b}<br/>正确率 {c}%（作答 {a}）' },
        grid: { left: 12, right: 40, top: 16, bottom: 8, containLabel: true },
        xAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: '#eef2f7' } } },
        yAxis: { type: 'category', data: rows.map(function (r) { return r.name; }) },
        series: [{
          type: 'bar', data: rows.map(function (r) { return r.rate; }), barMaxWidth: 24,
          label: { show: true, position: 'right', formatter: '{c}%' },
          itemStyle: { color: function (p: any) { return rows[p.dataIndex].rate < 60 ? '#dc2626' : '#16a34a'; }, borderRadius: [0, 5, 5, 0] },
        }],
      };
    });

    const pointOption = computed(function () {
      const rows = knowledgeItems.value.slice(0, 18).sort(function (a, b) { return a.mastery_rate - b.mastery_rate; });
      return {
        tooltip: {
          trigger: 'axis',
          formatter: function (params: any) {
            const row = rows[params[0].dataIndex];
            return row.point_name + '<br/>' + row.subject_name + '<br/>掌握度 ' + row.mastery_rate + '% · 作答 ' + row.total_attempts + ' 次';
          },
        },
        grid: { left: 12, right: 48, top: 12, bottom: 8, containLabel: true },
        xAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: '#eef2f7' } } },
        yAxis: { type: 'category', data: rows.map(function (p) { return p.point_name; }) },
        series: [{
          type: 'bar', data: rows.map(function (p) { return p.mastery_rate; }), barMaxWidth: 18,
          label: { show: true, position: 'right', formatter: '{c}%' },
          itemStyle: { color: function (p: any) { return rows[p.dataIndex].mastery_rate < 60 ? '#dc2626' : '#2563eb'; }, borderRadius: [0, 5, 5, 0] },
        }],
      };
    });

    const studentTrendOption = computed(function () {
      const exams = (studentModal.data.exams || []).slice().reverse();
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: 12, right: 16, top: 20, bottom: 10, containLabel: true },
        xAxis: { type: 'category', data: exams.map(function (e: any) { return e.paper_name; }), axisLabel: { rotate: 20, fontSize: 11 } },
        yAxis: { type: 'value', min: 0 },
        series: [{
          type: 'line', data: exams.map(function (e: any) { return e.total_score; }), smooth: true,
          itemStyle: { color: '#1a3c6d' }, areaStyle: { color: 'rgba(26,60,109,0.10)' },
        }],
      };
    });

    function authFetch(url: string, options?: any) {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth || !auth.apiFetch) return Promise.reject(new Error('登录态失效，请重新登录'));
      return auth.apiFetch(url, options);
    }

    async function loadStatic() {
      const tasks = [
        authFetch('/api/teacher/papers').then(safeJson).then(function (d) { papers.value = d.items || []; }).catch(function () {}),
        authFetch('/api/teacher/classes').then(safeJson).then(function (d) { classes.value = d.items || []; }).catch(function () {}),
      ];
      await Promise.all(tasks);
      if (!selectedClass.value && classes.value.length) selectedClass.value = classes.value[0].class_id;
    }

    async function loadAll() {
      loading.value = true;
      error.value = '';
      try {
        const paperQuery = selectedPaper.value ? '&paper_id=' + selectedPaper.value : '';
        const classQuery = currentClassId.value ? '&class_id=' + currentClassId.value : '';
        const overviewUrl = '/api/teacher/scores/overview?1=1' + paperQuery + classQuery;
        const analyticsUrl = '/api/teacher/analytics/overview?days=' + days.value + '&scope=' + (currentClassId.value ? 'mine' : 'school') + classQuery;
        const knowledgeUrl = '/api/teacher/analytics/knowledge-mastery';
        const classUrl = '/api/teacher/scores/class-compare?' + (selectedPaper.value ? 'paper_id=' + selectedPaper.value : '');
        const questionUrl = selectedPaper.value ? '/api/teacher/scores/question-stats/' + selectedPaper.value : '';

        const results = await Promise.all([
          authFetch(overviewUrl).then(safeJson),
          authFetch(analyticsUrl).then(safeJson),
          authFetch(knowledgeUrl).then(safeJson),
          authFetch(classUrl).then(safeJson),
          questionUrl ? authFetch(questionUrl).then(safeJson) : Promise.resolve({ questions: [] }),
        ]);
        const ov = results[0] || {};
        if (ov.success === false) throw new Error(ov.detail || '成绩总览加载失败');
        Object.assign(overview, {
          avg_score: ov.avg_score || 0,
          max_score: ov.max_score || 0,
          min_score: ov.min_score || 0,
          pass_rate: ov.pass_rate || 0,
          total_students: ov.total_students || 0,
          distribution: ov.distribution || { score_ranges: [], student_counts: [] },
          question_rates: ov.question_rates || [],
        });
        studentScores.value = ov.student_scores || [];
        Object.assign(analytics, results[1] || {});
        knowledgeItems.value = (results[2] && results[2].items) || [];
        classCompare.value = (results[3] && results[3].items) || [];
        questionStats.value = (results[4] && results[4].questions) || [];
      } catch (e: any) {
        error.value = e && e.message ? e.message : '成绩数据加载失败';
      } finally {
        loading.value = false;
      }
    }

    function setScope(next: string) {
      if (scope.value === next) return;
      scope.value = next;
      loadAll();
    }

    async function openStudent(student: any) {
      studentModal.open = true;
      studentModal.loading = true;
      studentModal.data = { user_name: student.user_name, user_no: student.user_no, class_name: student.class_name, exams: [], exam_count: 0 };
      try {
        const res = await authFetch('/api/teacher/scores/student/' + student.user_id);
        const data = await safeJson(res);
        if (data.success) studentModal.data = data;
      } catch (e) {
        // 保留表头信息，弹窗内显示空态
      } finally {
        studentModal.loading = false;
      }
    }

    function closeStudent() { studentModal.open = false; }
    function formatTime(value: string) { return value ? value.substring(0, 16).replace('T', ' ') : '—'; }
    function truncate(text: string, len: number) { return text && text.length > len ? text.substring(0, len) + '…' : text || ''; }

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    onMounted(async function () {
      await loadStatic();
      await loadAll();
    });

    return {
      scope, selectedClass, selectedPaper, days, activeTab, loading, error, studentKeyword,
      papers, classes, classCompare, questionStats, knowledgeItems, studentScores, analytics, overview,
      studentModal, tabs, kpis, filteredStudents, questionRows, weakPoints, typeRows, advice,
      distributionOption, passPieOption, trendOption, classCompareOption, typeOption, pointOption,
      studentTrendOption, scoreTrend, openStudent, closeStudent, setScope, loadAll, formatTime, truncate, handleLogout,
    };
  },
});
</script>

<style scoped>
.score-workspace { min-height: 100vh; background: #f5f7fa; color: #1f2937; }
.sw-main { max-width: 1280px; margin: 0 auto; padding: 24px 24px 48px; }
.sw-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.sw-head h1 { margin: 0; font-size: 24px; color: #1a3c6d; }
.sw-sub { margin: 6px 0 0; color: #64748b; font-size: 13px; line-height: 1.6; max-width: 720px; }
.sw-scope { display: inline-flex; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; background: #fff; }
.sw-scope button { border: 0; background: transparent; padding: 9px 20px; cursor: pointer; color: #475569; font-size: 14px; }
.sw-scope button.on { background: #1a3c6d; color: #fff; font-weight: 600; }
.sw-filters { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; padding: 14px 16px; background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(15, 23, 42, .05); }
.sw-field { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: #64748b; }
.sw-field select { min-width: 190px; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 7px; background: #fff; color: #1f2937; font-size: 14px; }
.sw-refresh { margin-left: auto; border: 1px solid #1a3c6d; background: #1a3c6d; color: #fff; border-radius: 7px; padding: 9px 18px; cursor: pointer; }
.sw-refresh:disabled { opacity: .6; cursor: wait; }
.sw-alert { margin-top: 14px; padding: 12px 16px; border: 1px solid #fecaca; background: #fef2f2; color: #991b1b; border-radius: 8px; }
.sw-alert button { margin-left: 10px; border: 1px solid #fca5a5; background: #fff; border-radius: 5px; padding: 2px 9px; cursor: pointer; }
.sw-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }
.sw-kpi { background: #fff; border-radius: 10px; padding: 16px 18px; box-shadow: 0 2px 8px rgba(15, 23, 42, .05); border-top: 3px solid #1a3c6d; }
.sw-kpi-label { font-size: 12px; color: #64748b; }
.sw-kpi strong { display: block; margin: 6px 0 2px; font-size: 28px; color: #1a3c6d; line-height: 1.1; }
.sw-kpi small { color: #94a3b8; font-size: 12px; }
.sw-kpis.dim { opacity: .6; }
.sw-tabs { display: flex; gap: 6px; border-bottom: 1px solid #e2e8f0; margin-bottom: 16px; overflow-x: auto; }
.sw-tabs button { border: 0; background: transparent; padding: 11px 18px; cursor: pointer; color: #64748b; font-size: 14px; border-bottom: 2px solid transparent; white-space: nowrap; }
.sw-tabs button.active { color: #1a3c6d; font-weight: 700; border-bottom-color: #2563eb; }
.sw-grid { display: grid; gap: 16px; }
.sw-grid.two { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.sw-card { background: #fff; border-radius: 10px; padding: 18px; box-shadow: 0 2px 8px rgba(15, 23, 42, .05); min-width: 0; }
.sw-card h2 { margin: 0 0 4px; font-size: 16px; color: #1a3c6d; }
.sw-hint { margin: 0 0 12px; color: #94a3b8; font-size: 12px; }
.span-2 { grid-column: span 2; }
.advice ul { margin: 0; padding-left: 18px; line-height: 1.9; color: #334155; font-size: 14px; }
.advice li.bad { color: #b91c1c; }
.advice li.ok { color: #15803d; }
.sw-state { padding: 40px 16px; text-align: center; color: #94a3b8; }
.table-card { padding: 0; overflow: auto; }
.sw-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 18px 12px; }
.sw-card-head h2 { margin: 0; }
.sw-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sw-table th { background: #f8fafc; color: #475569; text-align: left; font-weight: 600; padding: 11px 14px; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.sw-table td { padding: 10px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
.sw-table tbody tr:hover { background: #f8fbff; }
.sw-q { max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sw-rate { font-weight: 700; }
.sw-rate.ok { color: #15803d; }
.sw-rate.bad { color: #b91c1c; }
.sw-chip { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 12px; }
.sw-chip.ok { background: #dcfce7; color: #166534; }
.sw-chip.bad { background: #fee2e2; color: #991b1b; }
.sw-link { border: 0; background: transparent; color: #2563eb; cursor: pointer; padding: 2px 4px; }
.sw-link:hover { text-decoration: underline; }
.sw-empty { text-align: center; color: #94a3b8; padding: 28px !important; }
.sw-tip { border-bottom: 1px dashed #94a3b8; cursor: help; }
.sw-mistakes span { display: inline-block; margin-right: 6px; color: #b45309; }
.sw-search { width: 240px; padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; }
.sw-point-list { display: flex; flex-direction: column; gap: 9px; }
.sw-point-row { display: grid; grid-template-columns: minmax(90px, 1.2fr) 2fr auto; gap: 10px; align-items: center; font-size: 13px; cursor: help; }
.sw-point-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #334155; }
.sw-point-bar { height: 7px; background: #eef2f7; border-radius: 999px; overflow: hidden; }
.sw-point-bar i { display: block; height: 100%; background: #dc2626; border-radius: 999px; }
.sw-point-row b { color: #b91c1c; font-size: 12px; }
.sw-kp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
.sw-kp { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; cursor: help; }
.sw-kp-top { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }
.sw-kp-top strong { color: #1a3c6d; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sw-kp-top span { color: #b91c1c; font-weight: 700; }
.sw-kp-bar { height: 6px; background: #eef2f7; border-radius: 999px; margin: 8px 0 6px; overflow: hidden; }
.sw-kp-bar i { display: block; height: 100%; background: #dc2626; }
.sw-kp small { color: #94a3b8; font-size: 11px; }
.sw-modal-mask { position: fixed; inset: 0; z-index: 1200; background: rgba(15, 23, 42, .5); display: flex; align-items: center; justify-content: center; padding: 20px; }
.sw-modal { width: min(860px, 96vw); max-height: 88vh; overflow: auto; background: #fff; border-radius: 12px; padding: 20px; }
.sw-modal header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.sw-modal h2 { margin: 0; color: #1a3c6d; }
.sw-modal header p { margin: 4px 0 0; color: #64748b; font-size: 13px; }
.sw-modal header button { border: 0; background: transparent; font-size: 24px; color: #64748b; cursor: pointer; }
@media (max-width: 1080px) { .sw-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 820px) {
  .sw-grid.two { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1; }
  .sw-head { flex-direction: column; }
  .sw-refresh { margin-left: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .sw-kpi, .sw-card { transition: none; }
}
</style>
