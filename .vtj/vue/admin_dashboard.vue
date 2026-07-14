<template>
  <div class="admin-page">
    <aside class="aside"><div class="aside-logo">砺安题库·管理端</div>
      <a v-for="m in menu" :key="m.key" :class="['aside-item', { active: m.key === 'dashboard' }]" @click="$router.push(m.path)"><span class="ai-icon">{{ m.icon }}</span>{{ m.label }}</a>
    </aside>
    <div class="main-area">
      <div class="topbar"><span>系统总览</span><span>{{ username }} | <a @click="logout" style="color:#C41E3A;cursor:pointer">退出</a></span></div>
      <div class="content">
        <div class="cards"><div class="card" v-for="c in cards" :key="c.label"><div class="cv">{{ c.value }}</div><div class="cl">{{ c.label }}</div></div></div>
        <div class="panels">
          <div class="panel"><h3>近7天活跃趋势</h3><div class="trend-chart"><div class="trend-bar" v-for="(v,i) in trend" :key="i" :style="{height: v/maxTrend*120+'px'}"><div class="tv">{{ v }}</div><div class="td">{{ trendDates[i] }}</div></div></div></div>
          <div class="panel"><h3>最近操作</h3><div v-for="l in logs" :key="l.time" class="log-item"><span>{{ l.time }}</span><span>{{ l.user }}</span><span>{{ l.desc }}</span></div></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'AdminDashboard',
  setup() {
    const provider = useProvider({ id: 'admin_dashboard', version: '1' });
    const router = useRouter();
    const username = ref('');
    const cards = ref([{ label: '总用户数', value: '--' }, { label: '总题目数', value: '--' }, { label: '总试卷数', value: '--' }, { label: '今日活跃', value: '--' }]);
    const trend = ref([]);
    const trendDates = ref([]);
    const maxTrend = ref(1);
    const logs = ref([]);
    const menu = [
      { key: 'dashboard', label: '系统总览', path: '/admin/dashboard', icon: '📊' },
      { key: 'users', label: '用户管理', path: '/admin/users', icon: '👥' },
      { key: 'questions', label: '题库管理', path: '/admin/questions', icon: '📋' },
      { key: 'settings', label: '系统设置', path: '/admin/settings', icon: '⚙️' },
      { key: 'logs', label: '日志审计', path: '/admin/logs', icon: '📝' },
      { key: 'backup', label: '数据备份', path: '/admin/backup', icon: '💾' },
      { key: 'permissions', label: '权限管理', path: '/admin/permissions', icon: '🔐' },
    ];

    onMounted(async () => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) username.value = auth.getUsername() || '管理员';
      try {
        const res = await auth.apiFetch('/api/admin/dashboard');
        const data = await res.json();
        if (data.success) {
          cards.value = [
            { label: '总用户数', value: String(data.stats.total_users) },
            { label: '总题目数', value: String(data.stats.total_questions) },
            { label: '总试卷数', value: String(data.stats.total_papers) },
            { label: '今日活跃', value: String(data.stats.today_active_users) },
          ];
          trend.value = data.weekly_trend?.active_counts || [];
          trendDates.value = data.weekly_trend?.dates || [];
          maxTrend.value = Math.max(...trend.value, 1);
          logs.value = data.recent_logs || [];
        }
      } catch (e) { console.error(e); }
    });

    function logout() { (window as any).__VTJ_AUTH__?.logout(); router.push('/login'); }
    return { provider, username, cards, trend, trendDates, maxTrend, logs, menu, logout };
  }
});
</script>

<style scoped>
.admin-page { display: flex; min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.aside { width: 200px; background: #1A3C6D; color: #fff; padding-top: 16px; flex-shrink: 0; }
.aside-logo { text-align: center; font-size: 15px; font-weight: 600; padding: 0 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 8px; }
.aside-item { display: flex; align-items: center; padding: 12px 20px; color: rgba(255,255,255,0.7); text-decoration: none; cursor: pointer; font-size: 14px; border-left: 3px solid transparent; }
.aside-item:hover, .aside-item.active { color: #fff; background: rgba(255,255,255,0.1); border-left-color: #C41E3A; }
.ai-icon { margin-right: 10px; font-size: 16px; }
.main-area { flex: 1; display: flex; flex-direction: column; }
.topbar { display: flex; justify-content: space-between; align-items: center; height: 52px; padding: 0 20px; background: #fff; font-weight: 600; color: #1A3C6D; border-bottom: 1px solid #e8e8e8; }
.content { padding: 20px; }
.cards { display: flex; gap: 16px; margin-bottom: 20px; }
.card { flex: 1; background: #fff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
.cv { font-size: 28px; font-weight: 700; color: #1A3C6D; }
.cl { font-size: 13px; color: #888; margin-top: 4px; }
.panels { display: flex; gap: 20px; }
.panel { flex: 1; background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
.panel h3 { color: #1A3C6D; margin: 0 0 16px; font-size: 16px; }
.trend-chart { display: flex; align-items: flex-end; gap: 12px; height: 140px; justify-content: center; }
.trend-bar { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; width: 40px; }
.trend-bar > div:first-child { flex: 1; display: flex; align-items: flex-start; font-size: 12px; color: #1A3C6D; margin-bottom: 4px; }
.tv { font-size: 12px; color: #1A3C6D; margin-bottom: 4px; }
.td { font-size: 11px; color: #888; }
.trend-bar::before { content: ''; display: block; width: 32px; background: linear-gradient(180deg, #1A3C6D, #2B5A9C); border-radius: 4px 4px 0 0; }
.log-item { display: flex; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f5f5f5; font-size: 13px; }
.log-item span:first-child { color: #888; min-width: 80px; }
</style>
