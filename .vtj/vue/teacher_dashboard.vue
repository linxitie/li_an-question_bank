<template>
  <div class="teacher-dashboard">
    <TeacherNavHeader activeNav="dashboard" @logout="handleLogout" />

    <!-- 工具栏 -->
    <div class="dash-toolbar" v-if="!loadError">
      <h2 class="dash-title">📊 工作台</h2>
      <div class="dash-toolbar-actions">
        <button class="btn-tool" @click="loadDashboard" title="刷新">🔄 刷新</button>
      </div>
    </div>

    <div class="error-banner" v-if="loadError">{{ loadError }}</div>

    <!-- 统计卡片（设计文档 §2.1.2 四卡布局） -->
    <div class="stats-row" v-if="!loadError">
      <div class="stat-card" v-for="(card, i) in statCards" :key="i" @click="card.route && router.push(card.route)" :class="{ 'clickable': card.route }">
        <div class="stat-icon">{{ card.icon }}</div>
        <div class="stat-body">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-trend" v-if="card.trend">{{ card.trend }}</div>
        </div>
      </div>
    </div>

    <!-- 待办事项 + 最新动态（双栏） -->
    <div class="content-row" v-if="!loadError">
      <!-- 待办事项（设计文档 §2.1.2 左栏） -->
      <div class="panel">
        <h3 class="panel-title">📋 待办事项</h3>
        <div v-if="pendingPapers.length === 0 && pendingQuestionCount === 0 && pendingClassCount === 0" class="empty-tip">暂无待办事项</div>
        <!-- 待审批试卷 -->
        <div v-for="p in pendingPapers" :key="'paper-' + p.paper_id" class="todo-item">
          <span class="todo-icon">📄</span>
          <span class="todo-text">{{ p.paper_name }} 待审批</span>
          <button class="btn-sm-link" @click="router.push('/teacher/papers')">处理</button>
        </div>
        <!-- 待回复提问 -->
        <div v-if="pendingQuestionCount > 0" class="todo-item">
          <span class="todo-icon">❓</span>
          <span class="todo-text">{{ pendingQuestionCount }}条学生提问待回复</span>
          <button class="btn-sm-link" @click="router.push('/teacher/messages')">查看</button>
        </div>
        <!-- 待确认班级 -->
        <div v-if="pendingClassCount > 0" class="todo-item">
          <span class="todo-icon">👥</span>
          <span class="todo-text">{{ pendingClassCount }}个班级待确认</span>
          <button class="btn-sm-link" @click="router.push('/teacher/classes')">处理</button>
        </div>
      </div>

      <!-- 最新动态 + 系统通知（设计文档 §2.1.2 右栏） -->
      <div class="panel">
        <h3 class="panel-title">📢 最新动态</h3>
        <div v-if="announcements.length === 0 && recentActivities.length === 0" class="empty-tip">暂无新动态</div>
        <!-- 系统公告 -->
        <div v-for="(ann, i) in announcements" :key="'ann-' + i" class="activity-item announcement">
          <span class="ai-action">🔔 {{ ann.content }}</span>
          <span class="ai-time">{{ ann.time }}</span>
        </div>
        <!-- 学生动态 -->
        <div v-for="(act, i) in recentActivities" :key="'act-' + i" class="activity-item">
          <span class="ai-user">{{ act.user_name }}</span>
          <span class="ai-action">{{ act.action }}</span>
          <span class="ai-time">{{ act.action_time }}</span>
        </div>
      </div>
    </div>

    <!-- 快捷入口（设计文档 §2.1.2 底部） -->
    <div class="quick-entry-row" v-if="!loadError">
      <h3 class="panel-title" style="max-width:1200px;margin:0 auto 12px;">🚀 快捷入口</h3>
      <div class="quick-entry-bar">
        <button class="quick-btn" v-for="entry in quickEntries" :key="entry.key" @click="router.push(entry.path)">
          <span class="qb-icon">{{ entry.icon }}</span>
          <span class="qb-label">{{ entry.label }}</span>
        </button>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts-row" v-if="!loadError">
      <div class="panel chart-panel">
        <h3 class="panel-title">近7天练习人数</h3>
        <XChart v-if="hasTrendData" width="100%" height="280px" :option="barChartOption"></XChart>
        <div v-else class="empty-tip">暂无练习数据</div>
      </div>
      <div class="panel chart-panel">
        <h3 class="panel-title">三大科目正确率</h3>
        <XChart v-if="hasAccuracyData" width="100%" height="280px" :option="pieChartOption"></XChart>
        <div v-else class="empty-tip">暂无答题数据</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';
import { XChart } from '@vtj/charts';
import TeacherNavHeader from './TeacherNavHeader.vue';

export default defineComponent({
  name: 'TeacherDashboard',
  components: { XChart, TeacherNavHeader },
  setup() {
    const provider = useProvider({ id: 'teacher_dashboard', version: '1785750000004' });
    const router = useRouter();

    const pendingPapers = ref([]);
    const recentActivities = ref([]);
    const announcements = ref([]);
    const pendingQuestionCount = ref(0);
    const pendingClassCount = ref(0);

    const statCards = ref([
      { icon: '📝', label: '题目总数', value: '--', trend: '', route: '/teacher/questions' },
      { icon: '📝', label: '今日练习', value: '--', trend: '', route: '/teacher/scores' },
      { icon: '📄', label: '待审批', value: '--', trend: '', route: '/teacher/papers' },
      { icon: '📊', label: '平均正确率', value: '--', trend: '' },
    ]);

    const quickEntries = ref([
      { key: 'create-paper', icon: '📄', label: '新建试卷', path: '/teacher/papers' },
      { key: 'import-questions', icon: '📥', label: '导入题目', path: '/teacher/questions' },
      { key: 'view-scores', icon: '📊', label: '查看成绩', path: '/teacher/scores' },
      { key: 'manage-classes', icon: '👥', label: '管理班级', path: '/teacher/classes' },
      { key: 'ai-paper', icon: '🤖', label: 'AI组卷', path: '/teacher/papers' },
    ]);

    // API 加载错误状态
    const loadError = ref('');

    // 图表数据：近7天练习人数趋势 + 三大科目正确率
    const practiceTrend = ref({ dates: [], counts: [] });
    const subjectAccuracy = ref([]);

    onMounted(async () => {
      await loadDashboard();
    });

    async function loadDashboard() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) { loadError.value = '未登录，请重新登录'; return; }
      loadError.value = '';
      try {
        const res = await auth.apiFetch('/api/teacher/dashboard');
        if (res.status === 403) { loadError.value = '权限不足，请联系管理员'; return; }
        const data = await res.json();
        if (data.stats || data.success) {
          const stats = data.stats || {};
          statCards.value = [
            { icon: '📝', label: '题目总数', value: String(stats.total_questions ?? '--'), trend: stats.questions_trend || '', route: '/teacher/questions' },
            { icon: '📝', label: '今日练习', value: String(stats.today_practice_users ?? '--'), trend: stats.practice_trend_text || '', route: '/teacher/scores' },
            { icon: '📄', label: '待审批', value: String(stats.pending_papers ?? (data.pending_approvals || []).length), trend: '', route: '/teacher/papers' },
            { icon: '📊', label: '平均正确率', value: String(stats.avg_accuracy ?? '--'), trend: '' },
          ];
          pendingPapers.value = data.pending_approvals || [];
          recentActivities.value = data.recent_activities || [];
          announcements.value = data.announcements || [];
          pendingQuestionCount.value = stats.pending_questions || 0;
          pendingClassCount.value = stats.pending_classes || 0;
          practiceTrend.value = data.practice_trend || { dates: [], counts: [] };
          subjectAccuracy.value = data.subject_accuracy || [];
        } else {
          loadError.value = '数据格式异常，请稍后重试';
        }
      } catch (e) {
        loadError.value = '加载工作台数据失败';
        console.error('加载工作台数据失败:', e);
      }
    }

    const barChartOption = computed(() => ({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: practiceTrend.value.dates },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          name: '练习人数',
          type: 'bar',
          data: practiceTrend.value.counts,
          itemStyle: { color: '#1A3C6D' },
          barMaxWidth: 40,
        },
      ],
    }));

    const pieChartOption = computed(() => {
      const acc = subjectAccuracy.value;
      return {
        tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
        legend: { bottom: 0 },
        series: [
          {
            name: '正确率',
            type: 'pie',
            radius: ['40%', '68%'],
            center: ['50%', '45%'],
            avoidLabelOverlap: true,
            itemStyle: { borderColor: '#fff', borderWidth: 2 },
            label: { formatter: '{b}: {c}%' },
            data: acc.map((a) => ({ name: a.subject_name, value: a.accuracy })),
          },
        ],
      };
    });

    const hasTrendData = computed(() => practiceTrend.value.counts.some((c) => c > 0));
    const hasAccuracyData = computed(() => subjectAccuracy.value.some((a) => a.total > 0));

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    return { provider, statCards, pendingPapers, recentActivities, announcements, pendingQuestionCount, pendingClassCount, loadError, practiceTrend, subjectAccuracy, barChartOption, pieChartOption, hasTrendData, hasAccuracyData, quickEntries, handleLogout, router };
  }
})
</script>

<style scoped>
.teacher-dashboard { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.dash-toolbar { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px 0; max-width: 1200px; margin: 0 auto; }
.dash-title { font-size: 20px; font-weight: 700; color: #1A3C6D; margin: 0; }
.btn-tool { background: none; border: 1px solid #ddd; border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px; color: #555; }
.btn-tool:hover { background: #f0f0f0; }
.stats-row { display: flex; gap: 20px; padding: 16px 24px; max-width: 1200px; margin: 0 auto; }
.stat-card { flex: 1; background: #fff; border-radius: 12px; padding: 20px; display: flex; align-items: center; gap: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: box-shadow .2s; }
.stat-card.clickable { cursor: pointer; }
.stat-card.clickable:hover { box-shadow: 0 4px 16px rgba(26,60,109,0.12); }
.stat-icon { font-size: 36px; line-height: 1; }
.stat-body { flex: 1; }
.stat-label { font-size: 13px; color: #888; margin-bottom: 4px; }
.stat-value { font-size: 28px; font-weight: 700; color: #1A3C6D; }
.stat-trend { font-size: 12px; color: #67C23A; margin-top: 2px; }
.content-row { display: flex; gap: 20px; padding: 0 24px 24px; max-width: 1200px; margin: 0 auto; }
.charts-row { display: flex; gap: 20px; padding: 0 24px 24px; max-width: 1200px; margin: 0 auto; }
.panel { flex: 1; background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.panel-title { font-size: 16px; font-weight: 700; color: #1A3C6D; margin: 0 0 16px; padding-bottom: 12px; border-bottom: 2px solid #F5F7FA; }
.empty-tip { color: #999; text-align: center; padding: 24px; }
.todo-item { display: flex; align-items: center; gap: 8px; padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.todo-item:last-child { border-bottom: none; }
.todo-icon { font-size: 16px; }
.todo-text { flex: 1; color: #333; }
.btn-sm-link { background: none; border: none; color: #409EFF; cursor: pointer; font-size: 13px; padding: 2px 8px; border-radius: 4px; }
.btn-sm-link:hover { background: #ecf5ff; }
.quick-entry-row { padding: 0 24px 24px; max-width: 1200px; margin: 0 auto; }
.quick-entry-bar { display: flex; gap: 16px; background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.quick-btn { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 16px 8px; border: 1px solid #e8e8e8; border-radius: 10px; background: #fafbfc; cursor: pointer; transition: all .2s; font-size: 14px; }
.quick-btn:hover { border-color: #409EFF; background: #ecf5ff; color: #409EFF; }
.qb-icon { font-size: 24px; }
.qb-label { font-weight: 500; }
.activity-item { display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.activity-item:last-child { border-bottom: none; }
.activity-item.announcement { background: #fdf6ec; margin: 0 -8px; padding: 8px; border-radius: 6px; border-bottom: none; margin-bottom: 6px; }
.ai-user { font-weight: 600; color: #1A3C6D; }
.ai-action { color: #666; flex: 1; }
.ai-time { color: #aaa; font-size: 12px; }
</style>
