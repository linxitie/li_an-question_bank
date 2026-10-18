<!-- 金币购模块（手机端） -->
<template>
  <div class="mobile-gp-page">
    <div class="gp-header">
      <span class="gp-title">金币购</span>
      <div class="gold-balance">🪙 {{ state.balance }}</div>
    </div>

    <div class="gp-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['gp-tab', { active: state.activeTab === tab.key }]"
        @click="switchTab(tab.key)">{{ tab.label }}</button>
    </div>

    <!-- 商城 -->
    <div v-if="state.activeTab === 'shop'" class="gp-panel">
      <div v-for="item in state.products" :key="item.id" class="goods-card" @click="openDetail(item)">
        <span class="goods-emoji">{{ item.image_url || '🎁' }}</span>
        <div class="goods-info">
          <h4 class="goods-name">{{ item.name }}</h4>
          <p class="goods-desc">{{ item.description }}</p>
        </div>
        <div class="goods-footer">
          <span class="goods-price">🪙 {{ item.coin_price }}</span>
          <button class="buy-btn" @click.stop="openDetail(item)">兑换</button>
        </div>
      </div>
      <div v-if="!state.products.length" class="gp-empty">暂无商品</div>
    </div>

    <!-- 明细 -->
    <div v-else-if="state.activeTab === 'records'" class="gp-panel">
      <div v-for="(r, idx) in state.records" :key="idx" class="record-item">
        <span class="record-amount" :class="r.coin_change > 0 ? 'plus' : 'minus'">{{ r.coin_change > 0 ? '+' : '' }}{{ r.coin_change }}</span>
        <div class="record-mid">
          <span class="record-desc">{{ r.description }}</span>
          <span class="record-date">{{ formatTime(r.transaction_time) }}</span>
        </div>
      </div>
      <div v-if="!state.records.length" class="gp-empty">暂无流水</div>
    </div>

    <!-- 任务 -->
    <div v-else-if="state.activeTab === 'tasks'" class="gp-panel">
      <div class="gp-card">
        <h4>📅 签到</h4>
        <p class="task-note">{{ state.tasks.checkin.checked_in ? '已签到 · 连续' + state.tasks.checkin.continuous_days + '天' : '完成学习行为即自动签到' }}</p>
      </div>
      <div class="gp-card">
        <h4>📋 每日任务</h4>
        <div v-for="t in state.tasks.daily" :key="t.task_id" class="task-item">
          <span class="task-title">{{ t.title }} ({{ t.current }}/{{ t.threshold }})</span>
          <button class="task-btn" :disabled="!t.completed || t.claimed" @click="claimTask(t)">{{ t.claimed ? '已领取' : t.completed ? '领取' : '未完成' }}</button>
        </div>
      </div>
      <div class="gp-card">
        <h4>🎲 随机任务 <button class="refresh-btn" @click="refreshRandom">刷新</button></h4>
        <div v-for="t in state.tasks.random" :key="t.task_id" class="task-item">
          <span class="task-title">{{ t.title }} ({{ t.current }}/{{ t.threshold }})</span>
          <button class="task-btn" :disabled="!t.completed || t.claimed" @click="claimTask(t)">{{ t.claimed ? '已领取' : t.completed ? '领取' : '未完成' }}</button>
        </div>
      </div>
      <div class="gp-card">
        <h4>📅 周常任务</h4>
        <div v-for="t in state.tasks.weekly" :key="t.task_id" class="task-item">
          <span class="task-title">{{ t.title }} ({{ t.current }}/{{ t.threshold }})</span>
          <button class="task-btn" :disabled="!t.completed || t.claimed" @click="claimTask(t)">{{ t.claimed ? '已领取' : t.completed ? '领取' : '未完成' }}</button>
        </div>
      </div>
    </div>

    <!-- 目标 -->
    <div v-else-if="state.activeTab === 'goals'" class="gp-panel">
      <button class="primary-btn" @click="showCreateGoal">+ 新建目标</button>
      <div v-for="g in state.goals" :key="g.goal_id" class="gp-card">
        <h4>{{ g.title }}</h4>
        <p class="goal-progress">{{ g.current_count }}/{{ g.target_count }}</p>
        <span v-if="g.is_completed" class="goal-done">✅ 🪙{{ g.reward_coins || 0 }}</span>
        <button v-else class="task-btn" @click="completeGoal(g)">完成结算</button>
      </div>
    </div>

    <!-- 成就 -->
    <div v-else-if="state.activeTab === 'achievements'" class="gp-panel">
      <div v-for="(items, cat) in state.achievements.categories" :key="cat" class="gp-card">
        <h4>{{ cat }}</h4>
        <div class="ach-list">
          <div v-for="a in items" :key="a.achievement_id" class="ach-item" :class="{ earned: a.earned }">{{ a.icon }} {{ a.name }}</div>
        </div>
      </div>
    </div>

    <div v-if="state.detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <div class="modal-header"><h3>{{ state.detailProduct ? state.detailProduct.name : '' }}</h3><button class="close-btn" @click="closeDetail">✕</button></div>
        <div class="modal-body">
          <p>{{ state.detailProduct ? state.detailProduct.description : '' }}</p>
          <p class="modal-price">🪙 {{ state.detailProduct ? state.detailProduct.coin_price : 0 }}</p>
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
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  import { useRewardStore } from '@/modules/reward/store';

  export default defineComponent({
    name: 'MobileGoldPurchase',
    setup(props) {
      const provider = useProvider({ id: 'mobile_gold_purchase', version: '1778918740312' });
      const rewardStore = useRewardStore();
      const state = reactive({
        balance: 0, activeTab: 'shop', products: [], records: [],
        tasks: { checkin: {}, daily: [], random: [], weekly: [] },
        goals: [], achievements: { categories: {} },
        detailVisible: false, detailProduct: null, exchanging: false
      });
      return { state, props, provider, rewardStore };
    },
    computed: {
      tabs() {
        return [
          { key: 'shop', label: '商城' }, { key: 'records', label: '明细' },
          { key: 'tasks', label: '任务' }, { key: 'goals', label: '目标' }, { key: 'achievements', label: '成就' }
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
      formatTime(t) { return t ? String(t).replace('T', ' ').slice(5, 16) : ''; },
      async loadBalance() {
        this.state.balance = await this.rewardStore.loadBalance();
      },
      async loadProducts() {
        await this.rewardStore.load({ pageSize: 100 });
        this.state.products = this.rewardStore.products;
      },
      openDetail(item) { this.state.detailProduct = item; this.state.detailVisible = true; },
      closeDetail() { this.state.detailVisible = false; this.state.detailProduct = null; },
      async doExchange() {
        const p = this.state.detailProduct;
        if (!p) return;
        if (p.coin_price > this.state.balance) { ElMessage.warning('金币不足'); return; }
        this.state.exchanging = true;
        try {
          const result = await this.rewardStore.exchange(p.id);
          if (result) { ElMessage.success('兑换成功'); this.state.balance = result.balance; this.closeDetail(); }
          else ElMessage.error(this.rewardStore.error || '兑换失败');
        } finally { this.state.exchanging = false; }
      },
      async loadRecords() {
        await this.rewardStore.loadRecords(1, 50);
        this.state.records = this.rewardStore.records;
      },
      async loadTasks() {
        try { const r = await window.__VTJ_AUTH__.apiFetch('/api/tasks/overview'); const d = await r.json(); if (r.ok) this.state.tasks = d; } catch (e) {}
      },
      async claimTask(t) {
        try {
          const r = await window.__VTJ_AUTH__.apiFetch('/api/tasks/' + t.task_id + '/claim', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
          const d = await r.json();
          if (r.ok) { ElMessage.success('🪙' + d.reward_coins); this.state.balance = d.balance; this.loadTasks(); }
          else ElMessage.warning(d.detail || '领取失败');
        } catch (e) { ElMessage.error('领取失败'); }
      },
      async refreshRandom() {
        try {
          const r = await window.__VTJ_AUTH__.apiFetch('/api/tasks/random/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
          const d = await r.json();
          if (r.ok) { ElMessage.success('刷新成功'); this.loadTasks(); } else ElMessage.warning(d.detail || '刷新失败');
        } catch (e) { ElMessage.error('刷新失败'); }
      },
      async loadGoals() {
        try { const r = await window.__VTJ_AUTH__.apiFetch('/api/goals/'); const d = await r.json(); if (r.ok) this.state.goals = d.items || []; } catch (e) {}
      },
      // 今日学习科目：与首页共用同一来源 /api/quick-practice/subjects，0 = 混科
      async fetchSubjectOptions() {
        const fallback = [{ id: 0, name: '混科（不限科目）' }];
        try {
          const r = await window.__VTJ_AUTH__.apiFetch('/api/quick-practice/subjects');
          const d = await r.json();
          if (!r.ok || !d.items || !d.items.length) return fallback;
          return fallback.concat(d.items.map((s) => ({ id: s.subject_id, name: s.subject_name })));
        } catch (e) { return fallback; }
      },
      async showCreateGoal() {
        const title = window.prompt('目标标题', '今日目标'); if (!title) return;
        const target = window.prompt('今日完成题目数量（题）', '40');
        if (!target) return;
        const targetCount = parseInt(target, 10);
        if (!targetCount || targetCount <= 0) { ElMessage.warning('请输入有效的题量'); return; }

        const options = await this.fetchSubjectOptions();
        const picked = window.prompt('今日学习科目（' + options.map((o) => o.name).join(' / ') + '）', options[0].name);
        if (picked === null) return;
        const hit = options.find((o) => o.name === picked);
        const subjectMode = hit ? hit.id : 0;

        const minutesRaw = window.prompt('单日预期学习时间（分钟，0 表示不限）', '30');
        if (minutesRaw === null) return;
        let expectedMinutes = parseInt(minutesRaw, 10);
        if (isNaN(expectedMinutes) || expectedMinutes < 0) expectedMinutes = 0;
        if (expectedMinutes > 1440) { ElMessage.warning('单日预期学习时间需在 0-1440 分钟之间'); return; }

        // 本周目标默认按与首页相同的推导规则：今日目标 x 7，允许单独覆盖
        const weeklyRaw = window.prompt('本周学习目标（题，留空则按今日目标 x 7 推导）', String(targetCount * 7));
        if (weeklyRaw === null) return;
        const weeklyCount = weeklyRaw ? parseInt(weeklyRaw, 10) : targetCount * 7;

        await this.createGoal(title, targetCount, subjectMode, expectedMinutes, weeklyCount);
      },
      async createGoal(title, targetCount, subjectMode, expectedMinutes, weeklyCount) {
        const auth = window.__VTJ_AUTH__;
        const post = (body) => auth.apiFetch('/api/goals/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        try {
          const r = await post({
            title,
            target_count: targetCount,
            goal_type: 'DAILY',
            subject_mode: subjectMode || 0,
            expected_minutes: expectedMinutes || 0
          });
          const d = await r.json();
          if (!r.ok) { ElMessage.warning(d.detail || '失败'); return; }
          // 本周目标独立成 WEEKLY 记录（与首页一致，不折叠进标题文本）。
          // 失败仅提示，不影响已保存的今日目标。
          try {
            const w = await post({ title: '本周目标', target_count: weeklyCount, goal_type: 'WEEKLY' });
            if (!w.ok) console.warn('本周目标创建失败', w.status);
          } catch (e2) { console.warn('本周目标创建异常', e2); }
          ElMessage.success('已创建');
          this.loadGoals();
        } catch (e) { ElMessage.error('失败'); }
      },
      async completeGoal(g) {
        try {
          const r = await window.__VTJ_AUTH__.apiFetch('/api/goals/' + g.goal_id + '/complete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
          const d = await r.json();
          if (r.ok) { ElMessage.success('🪙' + d.reward_coins); this.state.balance += d.reward_coins || 0; this.loadGoals(); }
          else ElMessage.warning(d.detail || '失败');
        } catch (e) { ElMessage.error('失败'); }
      },
      async loadAchievements() {
        try { const r = await window.__VTJ_AUTH__.apiFetch('/api/achievements'); const d = await r.json(); if (r.ok) this.state.achievements = d; } catch (e) {}
      }
    },
    mounted() { this.loadBalance(); this.loadProducts(); }
  });
</script>

<style lang="css" scoped>
  .mobile-gp-page { min-height: 100vh; background: #f4f6fa; padding: 12px 12px 60px; font-family: 'Noto Sans SC', sans-serif; }
  .gp-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 4px 12px; }
  .gp-title { font-size: 18px; font-weight: 800; color: #1a2b5f; }
  .gold-balance { background: #fef3c7; padding: 8px 16px; border-radius: 14px; font-weight: 800; color: #b45309; }
  .gp-tabs { display: flex; gap: 2px; margin-bottom: 12px; overflow-x: auto; }
  .gp-tab { flex: 1; padding: 8px 0; background: none; border: none; font-size: 13px; font-weight: 600; color: #6b7280; cursor: pointer; white-space: nowrap; }
  .gp-tab.active { color: #c41e3a; border-bottom: 2px solid #c41e3a; }
  .goods-card { background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 10px; display: flex; gap: 12px; align-items: center; cursor: pointer; }
  .goods-emoji { font-size: 30px; }
  .goods-info { flex: 1; }
  .goods-name { margin: 0 0 2px; font-size: 14px; color: #1a2b5f; }
  .goods-desc { font-size: 11px; color: #8a8faa; margin: 0; }
  .goods-footer { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
  .goods-price { color: #b45309; font-weight: 700; font-size: 13px; }
  .buy-btn { padding: 5px 12px; background: #1a2b5f; color: #fff; border: none; border-radius: 7px; cursor: pointer; font-size: 12px; }
  .gp-card { background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 10px; }
  .gp-card h4 { margin: 0 0 8px; font-size: 14px; color: #1a2b5f; }
  .task-note { font-size: 12px; color: #6b7280; margin: 0; }
  .record-item { display: flex; gap: 10px; padding: 10px 12px; background: #fff; border-radius: 10px; margin-bottom: 6px; font-size: 12px; }
  .record-amount { font-weight: 700; }
  .record-amount.plus { color: #10b981; } .record-amount.minus { color: #ef4444; }
  .record-mid { flex: 1; display: flex; flex-direction: column; }
  .record-desc { color: #333; } .record-date { color: #8a8faa; font-size: 10px; }
  .task-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 10px; background: #f8f9fc; border-radius: 8px; margin-bottom: 6px; font-size: 12px; }
  .task-title { flex: 1; }
  .task-btn { padding: 4px 10px; background: #1a2b5f; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 11px; }
  .task-btn:disabled { background: #d1d5db; }
  .refresh-btn { margin-left: 6px; padding: 2px 8px; background: #f59e0b; color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 11px; }
  .primary-btn { padding: 8px 16px; background: #c41e3a; color: #fff; border: none; border-radius: 8px; cursor: pointer; margin-bottom: 8px; }
  .cancel-btn { padding: 8px 16px; background: #e5e7eb; color: #333; border: none; border-radius: 8px; cursor: pointer; }
  .goal-progress { font-size: 12px; color: #6b7280; } .goal-done { color: #10b981; }
  .ach-list { display: flex; flex-wrap: wrap; gap: 6px; }
  .ach-item { padding: 6px 10px; background: #f8f9fc; border-radius: 6px; font-size: 12px; color: #9ca3af; }
  .ach-item.earned { background: #fef3c7; color: #92400e; }
  .gp-empty { text-align: center; color: #9ca3af; padding: 30px 0; }
  .modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: flex-end; justify-content: center; z-index: 1000; }
  .modal { background: #fff; border-radius: 16px 16px 0 0; width: 100%; max-width: 600px; padding: 20px; }
  .modal-header { display: flex; justify-content: space-between; align-items: center; }
  .modal-header h3 { margin: 0; } .close-btn { background: none; border: none; font-size: 16px; cursor: pointer; }
  .modal-price { font-weight: 700; color: #b45309; }
  .modal-footer { display: flex; gap: 10px; margin-top: 16px; }
</style>
