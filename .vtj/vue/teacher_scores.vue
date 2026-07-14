<template>
  <div class="teacher-scores">
    <div class="top-nav">
      <span class="nav-logo">砺安题库 · 教师端</span>
      <div class="nav-links">
        <span v-for="tab in navTabs" :key="tab.key" :class="['nav-tab', { active: activeNav === tab.key }]" @click="goTab(tab.key)">{{ tab.label }}</span>
      </div>
      <span class="nav-user">{{ username }}</span>
    </div>

    <div class="page-content">
      <!-- 筛选 -->
      <div class="filter-bar">
        <select class="filter-select" v-model="selectedPaper" @change="loadData">
          <option :value="0">全部试卷</option>
          <option v-for="p in paperList" :key="p.paper_id" :value="p.paper_id">{{ p.paper_name }}</option>
        </select>
      </div>

      <!-- 统计概览 -->
      <div class="stats-row">
        <div class="stat-card"><div class="sv">{{ overview.avg_score }}</div><div class="sl">平均分</div></div>
        <div class="stat-card"><div class="sv">{{ overview.max_score }}</div><div class="sl">最高分</div></div>
        <div class="stat-card"><div class="sv">{{ overview.pass_rate }}%</div><div class="sl">及格率</div></div>
        <div class="stat-card"><div class="sv">{{ overview.total_students }}</div><div class="sl">参考人数</div></div>
      </div>

      <!-- 成绩分布图(简易) -->
      <div class="chart-panel">
        <h3>成绩分布</h3>
        <div class="bar-chart">
          <div class="bar-col" v-for="(item, i) in distribution" :key="i">
            <div class="bar-value">{{ item.count }}</div>
            <div class="bar-fill" :style="{ height: barHeight(item.count) }"></div>
            <div class="bar-label">{{ item.range }}</div>
          </div>
        </div>
      </div>

      <!-- 学生成绩表 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>排名</th><th>学号</th><th>姓名</th><th>班级</th><th>总分</th><th>用时</th></tr></thead>
          <tbody>
            <tr v-for="s in studentScores" :key="s.user_id">
              <td>{{ s.rank }}</td><td>{{ s.user_no }}</td><td>{{ s.user_name }}</td>
              <td>{{ s.class_name }}</td><td>{{ s.total_score }}</td><td>{{ s.duration_used }}分钟</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TeacherScores',
  setup() {
    const provider = useProvider({ id: 'teacher_scores', version: '1' });
    const router = useRouter();
    const activeNav = ref('scores');
    const username = ref('');
    const selectedPaper = ref(0);
    const paperList: any = ref([]);
    const overview = reactive({ avg_score: '--', max_score: '--', pass_rate: '--', total_students: '--' });
    const distribution: any = ref([]);
    const studentScores: any = ref([]);

    const navTabs = [
      { key: 'dashboard', label: '工作台', path: '/teacher/dashboard' },
      { key: 'questions', label: '题目管理', path: '/teacher/questions' },
      { key: 'papers', label: '试卷管理', path: '/teacher/papers' },
      { key: 'scores', label: '成绩管理', path: '/teacher/scores' },
    ];

    onMounted(async () => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) username.value = auth.getUsername() || '教师';
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

    function goTab(key: string) { activeNav.value = key; const tab = navTabs.find(t => t.key === key); if (tab) router.push(tab.path); }

    return { provider, activeNav, username, navTabs, selectedPaper, paperList, overview, distribution, studentScores, barHeight, goTab, loadData };
  }
});
</script>

<style scoped>
.teacher-scores { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.top-nav { display: flex; align-items: center; padding: 0 24px; height: 56px; background: #1A3C6D; color: #fff; }
.nav-logo { font-size: 16px; font-weight: 600; margin-right: 32px; }
.nav-links { display: flex; gap: 4px; flex: 1; }
.nav-tab { padding: 8px 16px; border-radius: 6px; cursor: pointer; color: rgba(255,255,255,0.7); }
.nav-tab:hover, .nav-tab.active { color: #fff; background: rgba(255,255,255,0.15); font-weight: 600; }
.nav-user { font-size: 14px; }
.page-content { max-width: 1200px; margin: 0 auto; padding: 24px; }
.filter-bar { margin-bottom: 20px; }
.filter-select { padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; min-width: 200px; }
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
.table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
</style>
