<!-- 金币购模块（PC端） -->
<template>
  <div class="gold-purchase-page">
    <NavBar></NavBar>
    <main class="gp-main">
      <!-- 头部：标题 + 余额 -->
      <div class="gp-header">
        <h2>
          <XIcon :icon="ShoppingCartFull" :size="24" color="#f59e0b"></XIcon>
          <span> 金币购</span>
        </h2>
        <div class="gold-balance">
          <span class="balance-label"> 我的金币</span>
          <span class="balance-value"> {{ state.balance }}</span>
          <XIcon :icon="Medal" :size="20" color="#f59e0b"></XIcon>
        </div>
      </div>

      <!-- Tab 导航 -->
      <div class="gp-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['gp-tab', { active: state.activeTab === tab.key }]"
          @click="switchTab(tab.key)">
          {{ tab.label }}
        </button>
      </div>

      <!-- 商城 Tab -->
      <div v-if="state.activeTab === 'shop'" class="gp-panel">
        <div class="goods-grid">
          <div v-for="item in state.products" :key="item.id" class="goods-card" @click="openDetail(item)">
            <div class="goods-image"><span class="goods-emoji">{{ item.image_url || '🎁' }}</span></div>
            <div class="goods-info">
              <h4 class="goods-name">{{ item.name }}</h4>
              <p class="goods-desc">{{ item.description }}</p>
              <div class="goods-footer">
                <span class="goods-price">🪙 {{ item.coin_price }}</span>
                <button class="buy-btn" @click.stop="openDetail(item)">兑换</button>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!state.products.length" class="gp-empty">暂无商品</div>
      </div>

      <!-- 明细 Tab -->
      <div v-else-if="state.activeTab === 'records'" class="gp-panel">
        <div class="record-list">
          <div v-for="(r, idx) in state.records" :key="idx" class="record-item">
            <span class="record-amount" :class="r.coin_change > 0 ? 'plus' : 'minus'">
              {{ r.coin_change > 0 ? '+' : '' }}{{ r.coin_change }}
            </span>
            <span class="record-desc">{{ r.description }}</span>
            <span class="record-date">{{ formatTime(r.transaction_time) }}</span>
          </div>
        </div>
        <div v-if="!state.records.length" class="gp-empty">暂无流水</div>
      </div>

      <!-- 任务 Tab -->
      <div v-else-if="state.activeTab === 'tasks'" class="gp-panel">
        <!-- 签到 -->
        <div class="gp-card">
          <h4>📅 每日签到</h4>
          <p v-if="state.tasks.checkin.checked_in" class="task-note">
            今日已签到 · 连续 {{ state.tasks.checkin.continuous_days }} 天 · 今日奖励 🪙{{ state.tasks.checkin.today_reward }}
          </p>
          <p v-else class="task-note">今日尚未签到，完成任意学习行为即自动签到</p>
        </div>

        <!-- 每日任务 -->
        <div class="gp-card">
          <h4>📋 每日任务</h4>
          <div v-for="t in state.tasks.daily" :key="t.task_id" class="task-item">
            <span class="task-title">{{ t.title }}</span>
            <span class="task-progress">{{ t.current }}/{{ t.threshold }}</span>
            <span class="task-reward">🪙{{ t.reward_coins }}</span>
            <button class="task-btn" :disabled="!t.completed || t.claimed" @click="claimTask(t)">
              {{ t.claimed ? '已领取' : t.completed ? '领取' : '未完成' }}
            </button>
          </div>
        </div>

        <!-- 随机任务 -->
        <div class="gp-card">
          <h4>🎲 随机任务 <button class="refresh-btn" @click="refreshRandom">刷新</button></h4>
          <div v-for="t in state.tasks.random" :key="t.task_id" class="task-item">
            <span class="task-title">{{ t.title }}</span>
            <span class="task-progress">{{ t.current }}/{{ t.threshold }}</span>
            <span class="task-reward">🪙{{ t.reward_coins }}</span>
            <button class="task-btn" :disabled="!t.completed || t.claimed" @click="claimTask(t)">
              {{ t.claimed ? '已领取' : t.completed ? '领取' : '未完成' }}
            </button>
          </div>
          <div v-if="!state.tasks.random.length" class="gp-empty">暂无随机任务</div>
        </div>

        <!-- 周常任务 -->
        <div class="gp-card">
          <h4>📅 周常任务</h4>
          <div v-for="t in state.tasks.weekly" :key="t.task_id" class="task-item">
            <span class="task-title">{{ t.title }}</span>
            <span class="task-progress">{{ t.current }}/{{ t.threshold }}</span>
            <span class="task-reward">🪙{{ t.reward_coins }}</span>
            <button class="task-btn" :disabled="!t.completed || t.claimed" @click="claimTask(t)">
              {{ t.claimed ? '已领取' : t.completed ? '领取' : '未完成' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 目标 Tab -->
      <div v-else-if="state.activeTab === 'goals'" class="gp-panel">
        <button class="primary-btn" @click="showCreateGoal">+ 新建目标</button>
        <div v-for="g in state.goals" :key="g.goal_id" class="gp-card">
          <h4>{{ g.title }}</h4>
          <p class="goal-progress">{{ g.current_count }}/{{ g.target_count }} ({{ g.progress_percent }}%)</p>
          <div class="goal-actions">
            <span v-if="g.is_completed" class="goal-done">✅ 已完成 · 🪙{{ g.reward_coins || 0 }}</span>
            <button v-else class="task-btn" @click="completeGoal(g)">完成并结算</button>
          </div>
        </div>
        <div v-if="!state.goals.length" class="gp-empty">暂无目标</div>
      </div>

      <!-- 成就 Tab -->
      <div v-else-if="state.activeTab === 'achievements'" class="gp-panel">
        <div v-for="(items, cat) in state.achievements.categories" :key="cat" class="gp-card">
          <h4>{{ cat }}</h4>
          <div class="ach-list">
            <div v-for="a in items" :key="a.achievement_id" class="ach-item" :class="{ earned: a.earned }">
              <span>{{ a.icon }} {{ a.name }}</span>
              <span class="ach-reward">🪙{{ a.reward_coins }}</span>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 详情弹窗 -->
    <div v-if="state.detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ state.detailProduct ? state.detailProduct.name : '' }}</h3>
          <button class="close-btn" @click="closeDetail">✕</button>
        </div>
        <div class="modal-body">
          <p>{{ state.detailProduct ? state.detailProduct.description : '' }}</p>
          <p class="modal-price">所需金币：🪙 {{ state.detailProduct ? state.detailProduct.coin_price : 0 }}</p>
          <p class="modal-balance">当前余额：🪙 {{ state.balance }} → 兑换后：🪙 {{ state.balance - (state.detailProduct ? state.detailProduct.coin_price : 0) }}</p>
        </div>
        <div class="modal-footer">
          <button class="primary-btn" :disabled="state.exchanging" @click="doExchange">确认兑换</button>
          <button class="cancel-btn" @click="closeDetail">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { ShoppingCartFull, Medal, Shop, GoldMedal, RefreshRight, CirclePlus } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';

  export default defineComponent({
    name: 'GoldPurchase',
    components: { NavBar, XIcon },
    setup(props) {
      const provider = useProvider({ id: 'gold_purchase', version: '1778918740312' });
      const state = reactive({
        balance: 0,
        activeTab: 'shop',
        products: [],
        records: [],
        tasks: { checkin: {}, daily: [], random: [], weekly: [] },
        goals: [],
        achievements: { categories: {} },
        detailVisible: false,
        detailProduct: null,
        exchanging: false
      });
      return {
        state,
        props,
        provider,
        ShoppingCartFull, Medal, Shop, GoldMedal, RefreshRight, CirclePlus
      };
    },
    computed: {
      tabs() {
        return [
          { key: 'shop', label: '商城' },
          { key: 'records', label: '明细' },
          { key: 'tasks', label: '任务' },
          { key: 'goals', label: '目标' },
          { key: 'achievements', label: '成就' }
        ];
      }
    },
    methods: {
      switchTab(key) {
        this.state.activeTab = key;
        if (key === 'records') this.loadRecords();
        if (key === 'tasks') this.loadTasks();
        if (key === 'goals') this.loadGoals();
        if (key === 'achievements') this.loadAchievements();
      },
      formatTime(t) {
        if (!t) return '';
        return String(t).replace('T', ' ').slice(5, 16);
      },
      async loadBalance() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/coins/overview');
          const data = await res.json();
          if (res.ok) this.state.balance = data.balance || 0;
        } catch (e) { /* 静默 */ }
      },
      async loadProducts() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/shop/products?page_size=100');
          const data = await res.json();
          if (res.ok) this.state.products = data.items || [];
        } catch (e) { /* 静默 */ }
      },
      openDetail(item) {
        this.state.detailProduct = item;
        this.state.detailVisible = true;
      },
      closeDetail() {
        this.state.detailVisible = false;
        this.state.detailProduct = null;
      },
      async doExchange() {
        const p = this.state.detailProduct;
        if (!p) return;
        if (p.coin_price > this.state.balance) {
          ElMessage.warning('金币不足，快去任务中心赚金币吧');
          return;
        }
        this.state.exchanging = true;
        try {
          const requestId = 'ex-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
          const res = await window.__VTJ_AUTH__.apiFetch('/api/shop/exchange', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: p.id, request_id: requestId })
          });
          const data = await res.json();
          if (res.ok) {
            ElMessage.success('兑换成功！');
            this.state.balance = data.balance;
            this.closeDetail();
            this.loadProducts();
          } else {
            ElMessage.error(data.detail || '兑换失败');
          }
        } catch (e) {
          ElMessage.error('兑换失败');
        } finally {
          this.state.exchanging = false;
        }
      },
      async loadRecords() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/coins/transactions?page_size=50');
          const data = await res.json();
          if (res.ok) this.state.records = data.items || [];
        } catch (e) { /* 静默 */ }
      },
      async loadTasks() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/tasks/overview');
          const data = await res.json();
          if (res.ok) this.state.tasks = data;
        } catch (e) { /* 静默 */ }
      },
      async claimTask(t) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/tasks/' + t.task_id + '/claim', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
          const data = await res.json();
          if (res.ok) {
            ElMessage.success('领取成功！🪙' + data.reward_coins);
            this.state.balance = data.balance;
            this.loadTasks();
          } else {
            ElMessage.warning(data.detail || '领取失败');
          }
        } catch (e) {
          ElMessage.error('领取失败');
        }
      },
      async refreshRandom() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/tasks/random/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
          const data = await res.json();
          if (res.ok) {
            ElMessage.success('刷新成功');
            this.loadTasks();
          } else {
            ElMessage.warning(data.detail || '刷新失败');
          }
        } catch (e) {
          ElMessage.error('刷新失败');
        }
      },
      async loadGoals() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/goals/');
          const data = await res.json();
          if (res.ok) this.state.goals = data.items || [];
        } catch (e) { /* 静默 */ }
      },
      showCreateGoal() {
        const title = window.prompt('请输入目标标题（如：每日完成30题）');
        if (!title) return;
        const target = window.prompt('请输入目标数量');
        if (!target) return;
        this.createGoal(title, parseInt(target, 10));
      },
      async createGoal(title, targetCount) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/goals/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, target_count: targetCount, goal_type: 'DAILY' })
          });
          const data = await res.json();
          if (res.ok) {
            ElMessage.success('目标已创建');
            this.loadGoals();
          } else {
            ElMessage.warning(data.detail || '创建失败');
          }
        } catch (e) {
          ElMessage.error('创建失败');
        }
      },
      async completeGoal(g) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/goals/' + g.goal_id + '/complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
          const data = await res.json();
          if (res.ok) {
            ElMessage.success('目标完成！🪙' + data.reward_coins);
            this.state.balance = (this.state.balance || 0) + (data.reward_coins || 0);
            this.loadGoals();
            this.loadBalance();
          } else {
            ElMessage.warning(data.detail || '操作失败');
          }
        } catch (e) {
          ElMessage.error('操作失败');
        }
      },
      async loadAchievements() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/achievements');
          const data = await res.json();
          if (res.ok) this.state.achievements = data;
        } catch (e) { /* 静默 */ }
      }
    },
    mounted() {
      this.loadBalance();
      this.loadProducts();
    }
  });
</script>

<style lang="css" scoped>
  .gold-purchase-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
  }
  .gp-main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  .gp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  .gp-header h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 22px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .gold-balance {
    display: flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #fffbeb, #fef3c7);
    padding: 12px 24px;
    border-radius: 18px;
    box-shadow: 0 2px 10px rgba(245, 158, 11, 0.2);
  }
  .balance-label { font-size: 13px; color: #92400e; font-weight: 500; }
  .balance-value { font-size: 28px; font-weight: 900; color: #b45309; font-family: 'DIN Alternate', sans-serif; }
  .gp-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    border-bottom: 2px solid #e5e7eb;
  }
  .gp-tab {
    padding: 10px 22px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 15px;
    font-weight: 600;
    color: #6b7280;
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
  }
  .gp-tab.active {
    color: #1a2b5f;
    border-bottom-color: #c41e3a;
  }
  .gp-panel { min-height: 300px; }
  .goods-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  .goods-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 14px rgba(26, 43, 95, 0.05);
    transition: all 0.3s;
    cursor: pointer;
    display: flex;
    gap: 16px;
  }
  .goods-card:hover { transform: translateY(-3px); box-shadow: 0 6px 24px rgba(26, 43, 95, 0.1); }
  .goods-image {
    width: 64px; height: 64px; border-radius: 16px;
    background: linear-gradient(135deg, #f8f9fc, #f0f2f5);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .goods-emoji { font-size: 30px; }
  .goods-info { flex: 1; display: flex; flex-direction: column; }
  .goods-name { font-size: 15px; font-weight: 700; color: #1a2b5f; margin: 0 0 4px; }
  .goods-desc { font-size: 12px; color: #8a8faa; margin: 0 0 12px; flex: 1; }
  .goods-footer { display: flex; align-items: center; justify-content: space-between; }
  .goods-price { font-size: 14px; font-weight: 700; color: #b45309; }
  .buy-btn {
    padding: 6px 16px; background: linear-gradient(135deg, #1a2b5f, #1e3470);
    color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: 600;
  }
  .gp-card {
    background: #fff; border-radius: 16px; padding: 20px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04); margin-bottom: 16px;
  }
  .gp-card h4 { font-size: 15px; font-weight: 700; color: #1a2b5f; margin: 0 0 12px; }
  .task-note { font-size: 13px; color: #6b7280; margin: 0; }
  .record-list { display: flex; flex-direction: column; gap: 8px; }
  .record-item {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; background: #fff; border-radius: 10px; font-size: 13px;
  }
  .record-amount { font-weight: 700; min-width: 60px; }
  .record-amount.plus { color: #10b981; }
  .record-amount.minus { color: #ef4444; }
  .record-desc { flex: 1; color: #333; }
  .record-date { color: #8a8faa; font-size: 11px; }
  .task-item {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; background: #f8f9fc; border-radius: 10px; margin-bottom: 8px; font-size: 13px;
  }
  .task-title { flex: 1; color: #333; font-weight: 500; }
  .task-progress { color: #6b7280; min-width: 60px; text-align: center; }
  .task-reward { color: #b45309; font-weight: 700; min-width: 50px; }
  .task-btn {
    padding: 5px 14px; background: #1a2b5f; color: #fff; border: none;
    border-radius: 8px; cursor: pointer; font-size: 12px;
  }
  .task-btn:disabled { background: #d1d5db; cursor: default; }
  .refresh-btn {
    margin-left: 8px; padding: 3px 10px; background: #f59e0b; color: #fff;
    border: none; border-radius: 6px; cursor: pointer; font-size: 12px;
  }
  .primary-btn {
    padding: 8px 18px; background: linear-gradient(135deg, #c41e3a, #e8384f);
    color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-bottom: 12px;
  }
  .primary-btn:disabled { background: #d1d5db; cursor: default; }
  .cancel-btn {
    padding: 8px 18px; background: #e5e7eb; color: #333; border: none; border-radius: 8px; cursor: pointer;
  }
  .goal-progress { font-size: 13px; color: #6b7280; }
  .goal-actions { margin-top: 8px; }
  .goal-done { color: #10b981; font-weight: 600; }
  .ach-list { display: flex; flex-wrap: wrap; gap: 8px; }
  .ach-item {
    padding: 8px 14px; background: #f8f9fc; border-radius: 8px; font-size: 13px;
    display: flex; align-items: center; gap: 8px; color: #9ca3af;
  }
  .ach-item.earned { background: #fef3c7; color: #92400e; }
  .ach-reward { font-weight: 700; }
  .gp-empty { text-align: center; color: #9ca3af; padding: 40px 0; }
  .modal-mask {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    display: flex; align-items: center; justify-content: center; z-index: 1000;
  }
  .modal {
    background: #fff; border-radius: 16px; width: 440px; max-width: 90vw;
    padding: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
  }
  .modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .modal-header h3 { margin: 0; font-size: 18px; color: #1a2b5f; }
  .close-btn { background: none; border: none; font-size: 18px; cursor: pointer; color: #6b7280; }
  .modal-body p { font-size: 14px; color: #4b5563; margin: 8px 0; }
  .modal-price { font-weight: 700; color: #b45309; font-size: 16px !important; }
  .modal-balance { color: #6b7280; }
  .modal-footer { display: flex; gap: 12px; margin-top: 20px; }
</style>
