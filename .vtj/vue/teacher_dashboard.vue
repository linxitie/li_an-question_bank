<template>
  <div class="teacher-dashboard">
    <!-- 顶部导航栏 -->
    <div class="dashboard-nav">
      <span class="nav-logo">砺安题库 · 教师端</span>
      <div class="nav-links">
        <span
          v-for="tab in navTabs"
          :key="tab.key"
          :class="['nav-tab', { active: activeNav === tab.key }]"
          @click="goTab(tab.key)"
        >{{ tab.label }}</span>
      </div>
      <div class="nav-user">
        <span>{{ username }}</span>
        <button class="btn-logout" @click="handleLogout">退出</button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card" v-for="(card, i) in statCards" :key="i">
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="content-row">
      <!-- 待审批试卷 -->
      <div class="panel">
        <h3 class="panel-title">待审批试卷</h3>
        <div v-if="pendingPapers.length === 0" class="empty-tip">暂无待审批试卷</div>
        <div v-for="p in pendingPapers" :key="p.paper_id" class="pending-item">
          <div class="pi-name">{{ p.paper_name }}</div>
          <div class="pi-meta">{{ p.subject_name }} · {{ p.question_count }}题 · {{ p.total_score }}分</div>
          <div class="pi-footer">
            <span>提交人: {{ p.creator_name }}</span>
            <span class="pi-time">{{ p.create_time }}</span>
          </div>
        </div>
      </div>

      <!-- 最新学生动态 -->
      <div class="panel">
        <h3 class="panel-title">最新学生动态</h3>
        <div v-if="recentActivities.length === 0" class="empty-tip">暂无学生动态</div>
        <div v-for="(act, i) in recentActivities" :key="i" class="activity-item">
          <span class="ai-user">{{ act.user_name }}</span>
          <span class="ai-action">{{ act.action }}</span>
          <span class="ai-time">{{ act.action_time }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, reactive, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TeacherDashboard',
  setup() {
    const provider = useProvider({ id: 'teacher_dashboard', version: '1' });
    const router = useRouter();

    const activeNav = ref('dashboard');
    const username = ref('');
    const pendingPapers: any = ref([]);
    const recentActivities: any = ref([]);

    const navTabs = [
      { key: 'dashboard', label: '工作台', path: '/teacher/dashboard' },
      { key: 'questions', label: '题目管理', path: '/teacher/questions' },
      { key: 'papers', label: '试卷管理', path: '/teacher/papers' },
      { key: 'scores', label: '成绩管理', path: '/teacher/scores' },
    ];

    const statCards = ref([
      { label: '总题目数', value: '--' },
      { label: '本月新增试卷', value: '--' },
      { label: '今日练习人数', value: '--' },
    ]);

    onMounted(async () => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) username.value = auth.getUsername() || '教师';
      await loadDashboard();
    });

    async function loadDashboard() {
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/dashboard');
        const data = await res.json();
        if (data.success) {
          statCards.value = [
            { label: '总题目数', value: String(data.stats.total_questions) },
            { label: '本月新增试卷', value: String(data.stats.monthly_new_papers) },
            { label: '今日练习人数', value: String(data.stats.today_practice_users) },
          ];
          pendingPapers.value = data.pending_approvals || [];
          recentActivities.value = data.recent_activities || [];
        }
      } catch (e) {
        console.error('加载工作台数据失败:', e);
      }
    }

    function goTab(key: string) {
      activeNav.value = key;
      const tab = navTabs.find(t => t.key === key);
      if (tab) router.push(tab.path);
    }

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    return { provider, activeNav, username, navTabs, statCards, pendingPapers, recentActivities, goTab, handleLogout };
  }
});
</script>

<style scoped>
.teacher-dashboard { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.dashboard-nav { display: flex; align-items: center; padding: 0 24px; height: 56px; background: #1A3C6D; color: #fff; }
.nav-logo { font-size: 16px; font-weight: 600; margin-right: 32px; }
.nav-links { display: flex; gap: 4px; flex: 1; }
.nav-tab { padding: 8px 16px; border-radius: 6px; cursor: pointer; color: rgba(255,255,255,0.7); font-size: 15px; }
.nav-tab:hover, .nav-tab.active { color: #fff; background: rgba(255,255,255,0.15); font-weight: 600; }
.nav-user { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.btn-logout { padding: 5px 14px; border: 1px solid rgba(255,255,255,0.5); background: transparent; color: #fff; border-radius: 4px; cursor: pointer; }
.btn-logout:hover { background: #C41E3A; border-color: #C41E3A; }
.stats-row { display: flex; gap: 20px; padding: 24px; max-width: 1200px; margin: 0 auto; }
.stat-card { flex: 1; background: #fff; border-radius: 12px; padding: 24px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.stat-value { font-size: 32px; font-weight: 700; color: #1A3C6D; }
.stat-label { font-size: 14px; color: #888; margin-top: 6px; }
.content-row { display: flex; gap: 20px; padding: 0 24px 24px; max-width: 1200px; margin: 0 auto; }
.panel { flex: 1; background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.panel-title { font-size: 16px; font-weight: 700; color: #1A3C6D; margin: 0 0 16px; padding-bottom: 12px; border-bottom: 2px solid #F5F7FA; }
.empty-tip { color: #999; text-align: center; padding: 24px; }
.pending-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.pending-item:last-child { border-bottom: none; }
.pi-name { font-weight: 600; color: #333; }
.pi-meta { font-size: 13px; color: #888; margin: 4px 0; }
.pi-footer { display: flex; justify-content: space-between; font-size: 12px; color: #aaa; }
.activity-item { display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.activity-item:last-child { border-bottom: none; }
.ai-user { font-weight: 600; color: #1A3C6D; }
.ai-action { color: #666; flex: 1; }
.ai-time { color: #aaa; font-size: 12px; }
</style>
