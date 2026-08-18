<template>
  <div class="admin-content">
    <!-- 骨架屏加载 -->
    <div v-if="loading" class="skeleton-container">
      <div class="skeleton-card" v-for="i in 4" :key="i"></div>
      <div class="skeleton-chart"></div>
    </div>
    
    <!-- 主内容 -->
    <div v-else class="content-wrapper">
      <!-- 顶部操作栏 -->
      <div class="action-bar">
        <h2 class="page-title">📊 系统总览</h2>
        <div class="action-buttons">
          <button class="btn-refresh" @click="loadDashboard">🔄 刷新</button>
          <button class="btn-fullscreen" @click="toggleFullscreen">⛶ 全屏</button>
        </div>
      </div>
      
      <!-- 统计卡片 -->
      <div class="stats-cards">
        <div class="stat-card" v-for="card in cards" :key="card.label" @click="navigateTo(card.route)">
          <div class="stat-icon">{{ card.icon }}</div>
          <div class="stat-info">
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-change" v-if="card.change">{{ card.change }}</div>
          </div>
        </div>
      </div>
      
      <!-- 图表区域 -->
      <div class="charts-row">
        <div class="chart-container">
          <h3>📈 近7天活跃趋势</h3>
          <div ref="trendChart" class="chart"></div>
        </div>
        <div class="chart-container">
          <h3>📊 各科目题目占比</h3>
          <div ref="pieChart" class="chart"></div>
        </div>
      </div>
      
      <!-- 最新动态和待办事项 -->
      <div class="bottom-row">
        <div class="panel">
          <h3>📋 最新动态</h3>
          <div class="log-list">
            <div v-for="log in recentLogs" :key="log.id" class="log-item">
              <span class="log-time">{{ log.time }}</span>
              <span class="log-user">{{ log.user }}</span>
              <span class="log-action">{{ log.action }}</span>
            </div>
            <div v-if="recentLogs.length === 0" class="empty-state">暂无动态</div>
          </div>
        </div>
        
        <div class="panel">
          <h3>📝 待办事项</h3>
          <div class="todo-list">
            <div v-for="todo in todos" :key="todo.id" class="todo-item">
              <span class="todo-icon">{{ todo.icon }}</span>
              <span class="todo-text">{{ todo.text }}</span>
              <button class="todo-action" @click="handleTodo(todo)">查看</button>
            </div>
            <div v-if="todos.length === 0" class="empty-state">暂无待办</div>
          </div>
        </div>
      </div>
      
      <!-- 系统状态 -->
      <div class="system-status">
        <span class="status-item">🟢 系统状态：正常运行</span>
        <span class="status-item" v-if="diskUsage > 0">💿 磁盘：{{ diskUsage }}%</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'AdminDashboard',
  setup() {
    const provider = useProvider({ id: 'admin_dashboard', version: '1785750000003' });
    const router = useRouter();
    const loading = ref(true);
    const cards = ref([
      { label: '总用户数', value: '--', icon: '👥', route: '/admin/users', change: '' },
      { label: '总题目数', value: '--', icon: '📚', route: '/admin/questions', change: '' },
      { label: '总试卷数', value: '--', icon: '📝', route: '/admin/papers', change: '' },
      { label: '今日活跃', value: '--', icon: '📈', route: '/admin/dashboard', change: '' }
    ]);
    const recentLogs = ref([]);
    const todos = ref([]);
    const diskUsage = ref(0);
    const trendChart = ref(null);
    const pieChart = ref(null);
    let refreshInterval = null;
    let trendInstance: any = null;
    let pieInstance: any = null;

    const auth = () => (window as any).__VTJ_AUTH__;

    async function initCharts() {
      const echarts = await import('echarts');
      // 趋势图
      if (trendChart.value) {
        trendInstance = echarts.init(trendChart.value);
        trendInstance.setOption({
          tooltip: { trigger: 'axis' },
          grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
          xAxis: { type: 'category', data: [] },
          yAxis: { type: 'value' },
          series: [{ name:'活跃用户', type:'line', smooth:true, data:[], itemStyle:{color:'#1A3C6D'}, areaStyle:{color:'rgba(26,60,109,0.1)'} }]
        });
      }
      // 饼图
      if (pieChart.value) {
        pieInstance = echarts.init(pieChart.value);
        pieInstance.setOption({
          tooltip: { trigger:'item', formatter:'{b}: {c} ({d}%)' },
          legend: { bottom:'5%', left:'center' },
          series: [{ type:'pie', radius:['40%','70%'], avoidLabelOverlap:false, itemStyle:{borderRadius:8,borderColor:'#fff',borderWidth:2}, label:{show:false,position:'center'}, emphasis:{label:{show:true,fontSize:16,fontWeight:'bold'}}, data:[] }]
        });
      }
      window.addEventListener('resize', handleResize);
    }

    function handleResize() { trendInstance?.resize(); pieInstance?.resize(); }

    onMounted(async () => {
      await loadDashboard();
      await initCharts();
      refreshInterval = setInterval(loadDashboard, 30000);
    });

    onUnmounted(() => {
      if (refreshInterval) clearInterval(refreshInterval);
      window.removeEventListener('resize', handleResize);
      trendInstance?.dispose();
      pieInstance?.dispose();
    });

    async function loadDashboard() {
      try {
        loading.value = true;
        const res = await auth().apiFetch('/api/admin/dashboard');
        if (res.status === 403) {
          console.error('权限不足');
          return;
        }
        const data = await res.json();
        if (data.stats) {
          cards.value = [
            { label: '总用户数', value: String(data.stats.total_users ?? '--'), icon: '👥', route: '/admin/users', change: data.stats.users_change ? `↑${data.stats.users_change}%` : '' },
            { label: '总题目数', value: String(data.stats.total_questions ?? '--'), icon: '📚', route: '/admin/questions', change: data.stats.questions_change ? `↑${data.stats.questions_change}%` : '' },
            { label: '总试卷数', value: String(data.stats.total_papers ?? '--'), icon: '📝', route: '/admin/papers', change: '' },
            { label: '今日活跃', value: String(data.stats.today_active_users ?? '--'), icon: '📈', route: '/admin/dashboard', change: data.stats.active_change ? `↑${data.stats.active_change}%` : '' },
            { label: '待审批试卷', value: String(data.stats?.pending_approval_papers ?? '--'), icon: '📝', route: '/admin/papers', change: '' }
          ];
          recentLogs.value = data.recent_logs || [];
          todos.value = data.todos || [];
          diskUsage.value = data.disk_usage || 0;
          // 用真实数据更新图表
          if (data.weekly_trend && trendInstance) {
            trendInstance.setOption({
              xAxis: { data: data.weekly_trend.dates || [] },
              series: [{ data: data.weekly_trend.active_counts || [] }]
            });
          }
          if (data.subject_distribution && pieInstance) {
            const colorMap: Record<string, string> = { '行测': '#1A3C6D', '申论': '#C41E3A', '公专': '#E6A23C' };
            pieInstance.setOption({
              series: [{
                data: data.subject_distribution.map((item: any) => ({
                  name: item.subject,
                  value: item.count,
                  itemStyle: { color: colorMap[item.subject] || '#999' }
                }))
              }]
            });
          }
        }
      } catch (e) {
        console.error('加载仪表盘失败:', e);
      } finally {
        loading.value = false;
      }
    }

    function navigateTo(route) {
      if (route) router.push(route);
    }

    function toggleFullscreen() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
      } else {
        document.exitFullscreen();
      }
    }

    function handleTodo(todo) {
      if (todo.route) router.push(todo.route);
    }

    return {
      provider, loading, cards, recentLogs, todos, diskUsage,
      trendChart, pieChart, loadDashboard, navigateTo, toggleFullscreen, handleTodo
    };
  }
})
</script>

<style scoped>
.admin-content {
  padding: 20px;
  min-height: calc(100vh - 60px);
}

/* 骨架屏 */
.skeleton-container {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.skeleton-card {
  flex: 1;
  min-width: 200px;
  height: 120px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 10px;
}

.skeleton-chart {
  width: 100%;
  height: 300px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 10px;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 操作栏 */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  color: #1A3C6D;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.btn-refresh, .btn-fullscreen {
  padding: 8px 16px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-refresh:hover, .btn-fullscreen:hover {
  border-color: #1A3C6D;
  color: #1A3C6D;
}

/* 统计卡片 */
.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  cursor: pointer;
  transition: all 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.stat-icon {
  font-size: 32px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1A3C6D;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}

.stat-change {
  font-size: 12px;
  color: #67C23A;
  margin-top: 2px;
}

/* 图表区域 */
.charts-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.chart-container {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.chart-container h3 {
  margin: 0 0 16px;
  color: #1A3C6D;
}

.chart {
  height: 300px;
}

/* 底部区域 */
.bottom-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.panel {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.panel h3 {
  margin: 0 0 16px;
  color: #1A3C6D;
}

/* 日志和待办列表 */
.log-list, .todo-list {
  max-height: 300px;
  overflow-y: auto;
}

.log-item, .todo-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.log-time {
  color: #999;
  font-size: 13px;
  min-width: 80px;
}

.log-user {
  font-weight: 500;
  min-width: 80px;
}

.log-action {
  flex: 1;
  color: #666;
}

.todo-icon {
  font-size: 18px;
}

.todo-text {
  flex: 1;
}

.todo-action {
  padding: 4px 12px;
  border: 1px solid #1A3C6D;
  border-radius: 4px;
  background: transparent;
  color: #1A3C6D;
  cursor: pointer;
  font-size: 13px;
}

.todo-action:hover {
  background: #1A3C6D;
  color: #fff;
}

.empty-state {
  text-align: center;
  color: #999;
  padding: 40px 0;
}

/* 系统状态 */
.system-status {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.status-item {
  font-size: 14px;
  color: #666;
}
</style>

