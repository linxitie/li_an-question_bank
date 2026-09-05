<template>
  <div class="teacher-scores">
    <TeacherNavHeader activeNav="scores" @logout="handleLogout" />

    <div class="page-content">
      <!-- 筛选 -->
      <div class="filter-bar">
        <select class="filter-select" v-model="selectedPaper" @change="loadData">
          <option :value="0">全部试卷</option>
          <option v-for="p in paperList" :key="p.paper_id" :value="p.paper_id">{{ p.paper_name }}</option>
        </select>
        <div class="filter-spacer"></div>
        <button class="btn-tool" @click="loadData">🔄 刷新</button>
      </div>

      <!-- 统计概览 -->
      <div class="stats-row">
        <div class="stat-card"><div class="sv">{{ overview.avg_score }}</div><div class="sl">平均分</div></div>
        <div class="stat-card"><div class="sv">{{ overview.max_score }}</div><div class="sl">最高分</div></div>
        <div class="stat-card"><div class="sv">{{ overview.pass_rate }}%</div><div class="sl">及格率</div></div>
        <div class="stat-card"><div class="sv">{{ overview.total_students }}</div><div class="sl">参考人数</div></div>
      </div>

      <!-- 成绩分布图 -->
      <div class="chart-panel">
        <h3>成绩分布</h3>
        <div class="bar-chart">
          <div class="bar-col" v-for="(item, i) in distribution" :key="i">
            <div class="bar-value">{{ item.count }}</div>
            <div class="bar-fill" :style="{ height: barHeight(item.count) }"></div>
            <div class="bar-label">{{ item.range }}</div>
          </div>
          <div v-if="distribution.length === 0" class="empty-tip">暂无分布数据</div>
        </div>
      </div>

      <!-- 学生成绩表 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>排名</th><th>学号</th><th>姓名</th><th>班级</th><th>总分</th><th>用时</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in studentScores" :key="s.user_id">
              <td>{{ s.rank }}</td><td>{{ s.user_no }}</td><td>{{ s.user_name }}</td>
              <td>{{ s.class_name }}</td><td>{{ s.total_score }}</td><td>{{ s.duration_used }}分钟</td>
              <td><button class="btn-detail" @click="openStudentDetail(s)">📋 详情</button></td>
            </tr>
            <tr v-if="studentScores.length === 0">
              <td colspan="7" style="text-align:center;color:#909399;padding:30px;">暂无成绩数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 学生成绩详情弹窗（设计文档 §2.4.3） -->
    <div class="modal-overlay" v-if="showDetailModal" @click.self="showDetailModal = false">
      <div class="modal-content detail-modal">
        <div class="detail-header">
          <div class="detail-student-info">
            <div class="detail-avatar">{{ detailData.user_name ? detailData.user_name[0] : '?' }}</div>
            <div>
              <h3>{{ detailData.user_name }}</h3>
              <div class="detail-meta">学号: {{ detailData.user_no }} · 班级: {{ detailData.class_name }} · 考试次数: {{ detailData.exam_count }}</div>
            </div>
          </div>
          <button class="btn-close" @click="showDetailModal = false">✕</button>
        </div>

        <!-- 历次成绩曲线 -->
        <div class="detail-section">
          <h4>📈 历次考试成绩</h4>
          <XChart v-if="detailData.exams && detailData.exams.length > 0" width="100%" height="240px" :option="detailChartOption"></XChart>
          <div v-else class="empty-tip">暂无考试记录</div>
        </div>

        <!-- 各次考试明细 -->
        <div class="detail-section">
          <h4>📋 考试记录</h4>
          <table class="data-table mini-table" v-if="detailData.exams && detailData.exams.length > 0">
            <thead><tr><th>试卷</th><th>得分</th><th>用时</th><th>提交时间</th></tr></thead>
            <tbody>
              <tr v-for="ex in detailData.exams" :key="ex.record_id">
                <td>{{ ex.paper_name }}</td>
                <td :class="ex.total_score >= 60 ? 'score-pass' : 'score-fail'">{{ ex.total_score }}</td>
                <td>{{ ex.duration_used }}分钟</td>
                <td>{{ formatTime(ex.submit_time) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 各题正确率（需要选择试卷后加载） -->
        <div class="detail-section" v-if="selectedPaper > 0">
          <h4>📊 各题正确率（当前试卷）</h4>
          <div v-if="questionStats.length > 0">
            <div class="qstat-item" v-for="qs in questionStats" :key="qs.question_id">
              <div class="qstat-header">
                <span class="qstat-content">{{ truncate(qs.question_content, 50) }}</span>
                <span class="qstat-rate" :class="qs.correct_rate >= 60 ? 'rate-good' : 'rate-bad'">{{ qs.correct_rate }}%</span>
              </div>
              <div class="qstat-bar">
                <div class="qstat-fill" :style="{ width: qs.correct_rate + '%', background: qs.correct_rate >= 60 ? '#67C23A' : '#F56C6C' }"></div>
              </div>
              <div class="qstat-detail">正确 {{ qs.correct_count }}/{{ qs.total_attempts }} · 常见错误: <span v-for="(m, mi) in qs.common_mistakes" :key="mi">{{ m[0] }}({{ m[1] }}人){{ mi < qs.common_mistakes.length - 1 ? '、' : '' }}</span></div>
            </div>
          </div>
          <div v-else class="empty-tip">暂无题目统计数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';
import { XChart } from '@vtj/charts';
import TeacherNavHeader from './TeacherNavHeader.vue';

export default defineComponent({
  name: 'TeacherScores',
  components: { XChart, TeacherNavHeader },
  setup() {
    const provider = useProvider({ id: 'teacher_scores', version: '1' });
    const router = useRouter();
    const selectedPaper = ref(0);
    const paperList: any = ref([]);
    const overview = reactive({ avg_score: '--', max_score: '--', pass_rate: '--', total_students: '--' });
    const distribution: any = ref([]);
    const studentScores: any = ref([]);

    // 详情弹窗
    const showDetailModal = ref(false);
    const detailData: any = ref({});
    const questionStats: any = ref([]);

    onMounted(async () => {
      await loadPapers();
      await loadData();
    });

    async function loadPapers() {
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/papers');
        const data = await res.json();
        if (data.success) paperList.value = data.items || [];
      } catch (e) {}
    }

    async function loadData() {
      const auth = (window as any).__VTJ_AUTH__;
      const params = selectedPaper.value > 0 ? `?paper_id=${selectedPaper.value}` : '';
      try {
        const res = await auth.apiFetch(`/api/teacher/scores/overview${params}`);
        const data = await res.json();
        if (data.success) {
          overview.avg_score = String(data.avg_score);
          overview.max_score = String(data.max_score);
          overview.pass_rate = String(data.pass_rate);
          overview.total_students = String(data.total_students);
          distribution.value = (data.distribution?.score_ranges || []).map((r: string, i: number) => ({
            range: r, count: data.distribution?.student_counts?.[i] || 0
          }));
          studentScores.value = data.student_scores || [];
        }
      } catch (e) { console.error('加载成绩失败:', e); }
    }

    function barHeight(count: number) {
      const max = Math.max(...distribution.value.map((d: any) => d.count), 1);
      return (count / max * 160) + 'px';
    }

    async function openStudentDetail(student: any) {
      const auth = (window as any).__VTJ_AUTH__;
      showDetailModal.value = true;
      detailData.value = { user_name: student.user_name, user_no: student.user_no, class_name: student.class_name, exam_count: 0, exams: [] };
      questionStats.value = [];
      try {
        const res = await auth.apiFetch(`/api/teacher/scores/student/${student.user_id}`);
        const data = await res.json();
        if (data.success) {
          detailData.value = data;
        }
      } catch (e) { console.error('加载学生详情失败:', e); }
      // 如果当前选了试卷，加载各题正确率
      if (selectedPaper.value > 0) {
        try {
          const res2 = await auth.apiFetch(`/api/teacher/scores/question-stats/${selectedPaper.value}`);
          const data2 = await res2.json();
          if (data2.success) questionStats.value = data2.questions || [];
        } catch (e) {}
      }
    }

    const detailChartOption = computed(() => {
      const exams = detailData.value.exams || [];
      const reversed = [...exams].reverse();
      return {
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
        xAxis: { type: 'category', data: reversed.map((e: any) => e.paper_name), axisLabel: { rotate: 30, fontSize: 11 } },
        yAxis: { type: 'value', min: 0 },
        series: [{ name: '得分', type: 'line', data: reversed.map((e: any) => e.total_score), smooth: true, itemStyle: { color: '#1A3C6D' }, areaStyle: { color: 'rgba(26,60,109,0.1)' } }],
      };
    });

    function formatTime(t: string) { if (!t) return '-'; return t.substring(0, 16).replace('T', ' '); }
    function truncate(text: string, len: number) { return text && text.length > len ? text.substring(0, len) + '...' : text || ''; }

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    return { provider, selectedPaper, paperList, overview, distribution, studentScores, barHeight, loadData, showDetailModal, detailData, questionStats, openStudentDetail, detailChartOption, formatTime, truncate, handleLogout };
  }
});
</script>

<style scoped>
.teacher-scores { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.page-content { max-width: 1200px; margin: 0 auto; padding: 24px; }
.filter-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.filter-spacer { flex: 1; }
.filter-select { padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; min-width: 200px; }
.btn-tool { background: none; border: 1px solid #ddd; border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px; color: #555; }
.btn-tool:hover { background: #f0f0f0; }
.stats-row { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-card { flex: 1; background: #fff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
.sv { font-size: 28px; font-weight: 700; color: #1A3C6D; }
.sl { font-size: 13px; color: #888; margin-top: 4px; }
.chart-panel { background: #fff; border-radius: 10px; padding: 20px; margin-bottom: 24px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
.chart-panel h3 { color: #1A3C6D; margin: 0 0 16px; }
.bar-chart { display: flex; justify-content: center; align-items: flex-end; gap: 24px; height: 220px; padding: 0 40px; }
.bar-col { display: flex; flex-direction: column; align-items: center; }
.bar-value { font-size: 13px; color: #1A3C6D; margin-bottom: 6px; font-weight: 600; }
.bar-fill { width: 48px; background: linear-gradient(180deg, #1A3C6D, #2B5A9C); border-radius: 6px 6px 0 0; min-height: 4px; transition: height 0.3s; }
.bar-label { font-size: 12px; color: #888; margin-top: 6px; }
.empty-tip { color: #999; text-align: center; padding: 24px; }
.table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.btn-detail { background: #ecf5ff; border: 1px solid #b3d8ff; color: #409EFF; border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 13px; }
.btn-detail:hover { background: #409EFF; color: #fff; }

/* 详情弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.detail-modal { background: #fff; border-radius: 14px; width: 900px; max-width: 95vw; max-height: 90vh; overflow-y: auto; padding: 24px; }
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 2px solid #f0f0f0; }
.detail-student-info { display: flex; align-items: center; gap: 14px; }
.detail-avatar { width: 52px; height: 52px; border-radius: 50%; background: #1A3C6D; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; }
.detail-student-info h3 { margin: 0; font-size: 20px; color: #1A3C6D; }
.detail-meta { font-size: 13px; color: #888; margin-top: 4px; }
.btn-close { background: none; border: none; font-size: 22px; cursor: pointer; color: #999; padding: 4px 8px; }
.btn-close:hover { color: #333; }
.detail-section { margin-bottom: 24px; }
.detail-section h4 { font-size: 16px; color: #1A3C6D; margin: 0 0 12px; }
.mini-table td, .mini-table th { padding: 10px 12px; font-size: 13px; }
.score-pass { color: #67C23A; font-weight: 600; }
.score-fail { color: #F56C6C; font-weight: 600; }
.qstat-item { padding: 12px 0; border-bottom: 1px solid #f5f5f5; }
.qstat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.qstat-content { font-size: 14px; color: #333; }
.qstat-rate { font-size: 14px; font-weight: 700; }
.rate-good { color: #67C23A; }
.rate-bad { color: #F56C6C; }
.qstat-bar { height: 6px; background: #f0f0f0; border-radius: 3px; overflow: hidden; }
.qstat-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.qstat-detail { font-size: 12px; color: #999; margin-top: 4px; }
</style>
