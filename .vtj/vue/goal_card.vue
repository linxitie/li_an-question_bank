<template>
  <div class="goal-card">
    <div class="goal-header">
      <XIcon :icon="Flag" :size="20" color="#c41e3a"></XIcon>
      <span class="goal-title">个人小目标</span>
      <button class="add-goal-btn" @click="openCreateDialog">
        <span>+ 新增目标</span>
      </button>
    </div>

    <div class="goal-content">
      <!-- 加载中 -->
      <div v-if="state.loading" class="goal-loading">
        <span>加载中...</span>
      </div>

      <!-- 空状态 -->
      <div v-else-if="state.goals.length === 0" class="goal-empty">
        <span class="empty-icon">🎯</span>
        <p>还没有设计目标哦！</p>
      </div>

      <!-- 目标卡片列表 -->
      <div v-for="goal in state.goals" :key="goal.goal_id" class="goal-item-card">
        <div class="goal-card-top">
          <span :class="['goal-type-badge', goal.goal_type.toLowerCase()]">
            {{ getGoalTypeLabel(goal.goal_type) }}
          </span>
          <span v-if="getGoalStatus(goal) === 'completed'" class="status-badge completed">已完成</span>
          <span v-else-if="getGoalStatus(goal) === 'overdue'" class="status-badge overdue">未完成目标</span>
        </div>

        <div class="goal-card-title">{{ goal.title }}</div>

        <div class="goal-progress-bar">
          <div
            class="progress-fill"
            :style="{ width: (goal.progress_percent || 0) + '%' }"></div>
        </div>

        <div class="goal-stats">
          <span class="goal-percent">完成进度 {{ goal.progress_percent || 0 }}%</span>
          <span class="goal-count">完成题目数量: {{ goal.current_count || 0 }} / {{ goal.target_count || 0 }}</span>
        </div>

        <div v-if="goal.deadline" class="goal-deadline">
          <span class="deadline-label">完成时间</span>
          <span class="deadline-countdown">{{ getDeadlineCountdown(goal.deadline).text }}</span>
          <span class="deadline-sep">-- 结束时间</span>
          <span class="deadline-date">{{ formatDeadline(goal.deadline) }}</span>
        </div>

        <div class="goal-card-actions">
          <button
            v-if="!goal.is_completed"
            class="goal-action-btn progress-btn"
            @click="incrementProgress(goal.goal_id)">+1 进度</button>
          <button
            v-if="!goal.is_completed"
            class="goal-action-btn complete-btn"
            @click="confirmComplete(goal.goal_id)">标记完成</button>
          <button
            class="goal-action-btn edit-btn"
            @click="openEditDialog(goal)">编辑</button>
          <button
            class="goal-action-btn delete-btn"
            @click="deleteGoal(goal.goal_id)">删除</button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="state.showDialog" class="goal-dialog-overlay" @click.self="closeDialog">
      <div class="goal-dialog">
        <div class="dialog-header">
          <h3>{{ state.dialogMode === 'create' ? '新增目标' : '编辑目标' }}</h3>
          <button class="dialog-close-btn" @click="closeDialog">×</button>
        </div>
        <div class="dialog-body">
          <div class="dialog-field">
            <label>目标名称</label>
            <input
              v-model="state.dialogForm.title"
              type="text"
              placeholder="例如：每日做题100道"
              class="dialog-input" />
          </div>

          <div class="dialog-field">
            <label>目标数量（题）</label>
            <input
              v-model.number="state.dialogForm.target_count"
              type="number"
              min="1"
              class="dialog-input" />
          </div>

          <div class="dialog-field">
            <label>目标类型</label>
            <select v-model="state.dialogForm.goal_type" class="dialog-select">
              <option
                v-for="t in state.goalTypes"
                :key="t.value"
                :value="t.value">{{ t.label }}</option>
            </select>
          </div>

          <div class="dialog-field">
            <label>截止日期（可选）</label>
            <input
              v-model="state.dialogForm.deadline"
              type="date"
              class="dialog-input" />
          </div>

          <div class="dialog-field">
            <label>优先级</label>
            <select v-model.number="state.dialogForm.priority" class="dialog-select">
              <option :value="1">低</option>
              <option :value="2">中</option>
              <option :value="3">高</option>
            </select>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="dialog-btn cancel-btn" @click="closeDialog">取消</button>
          <button class="dialog-btn save-btn" @click="saveGoal">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { XIcon } from '@vtj/ui';
import { Flag } from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'GoalCard',
  components: { XIcon },
  setup(props) {
    const provider = useProvider({ id: 'goal_card', version: '1778917924916' });
    const state = reactive({
      goals: [],
      loading: false,
      showDialog: false,
      dialogMode: 'create',
      editingGoalId: null,
      dialogForm: {
        title: '',
        target_count: 1,
        goal_type: 'DAILY',
        deadline: '',
        priority: 2
      },
      goalTypes: [
        { value: 'DAILY', label: '每日' },
        { value: 'WEEKLY', label: '每周' },
        { value: 'MONTHLY', label: '每月' },
        { value: 'CUSTOM', label: '自定义' }
      ]
    });
    return { state, provider, Flag };
  },
  methods: {
    // ── 认证辅助 ────────────────────────────────────
    getJsonHeaders() {
      if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.getJsonHeaders) {
        return window.__VTJ_AUTH__.getJsonHeaders();
      }
      return { 'Content-Type': 'application/json' };
    },

    // ── 数据加载 ────────────────────────────────────
    async fetchGoals() {
      this.state.loading = true;
      try {
        const res = await window.__VTJ_AUTH__.apiFetch('/api/goals/');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        this.state.goals = data.items || [];
      } catch (e) {
        console.warn('加载目标失败:', e);
        this.state.goals = [];
      } finally {
        this.state.loading = false;
      }
    },

    // ── 弹窗管理 ────────────────────────────────────
    openCreateDialog() {
      this.state.dialogMode = 'create';
      this.state.editingGoalId = null;
      this.state.dialogForm = {
        title: '',
        target_count: 1,
        goal_type: 'DAILY',
        deadline: '',
        priority: 2
      };
      this.state.showDialog = true;
    },

    openEditDialog(goal) {
      this.state.dialogMode = 'edit';
      this.state.editingGoalId = goal.goal_id;
      this.state.dialogForm = {
        title: goal.title || '',
        target_count: goal.target_count || 1,
        goal_type: goal.goal_type || 'DAILY',
        deadline: goal.deadline ? goal.deadline.split('T')[0] : '',
        priority: goal.priority || 2
      };
      this.state.showDialog = true;
    },

    closeDialog() {
      this.state.showDialog = false;
    },

    // ── CRUD 操作 ────────────────────────────────────
    async saveGoal() {
      const form = this.state.dialogForm;
      if (!form.title.trim()) return;

      try {
        const isEdit = this.state.dialogMode === 'edit';
        const url = isEdit
          ? '/api/goals/' + this.state.editingGoalId
          : '/api/goals/';
        const method = isEdit ? 'PUT' : 'POST';

        const body = {
          title: form.title.trim(),
          target_count: Number(form.target_count) || 1,
          goal_type: form.goal_type,
          deadline: form.deadline || null,
          priority: Number(form.priority) || 2
        };

        const res = await window.__VTJ_AUTH__.apiFetch(url, {
          method: method,
          headers: this.getJsonHeaders(),
          body: JSON.stringify(body)
        });

        if (!res.ok) throw new Error('保存失败');

        this.state.showDialog = false;
        await this.fetchGoals();
      } catch (e) {
        console.warn('保存目标失败:', e);
      }
    },

    async deleteGoal(goalId) {
      try {
        const res = await window.__VTJ_AUTH__.apiFetch('/api/goals/' + goalId, {
          method: 'DELETE',
          headers: this.getJsonHeaders()
        });
        if (res.ok) {
          await this.fetchGoals();
        }
      } catch (e) {
        console.warn('删除目标失败:', e);
      }
    },

    async incrementProgress(goalId) {
      try {
        const res = await window.__VTJ_AUTH__.apiFetch(
          '/api/goals/' + goalId + '/progress?increment=1',
          { method: 'POST', headers: this.getJsonHeaders() }
        );
        if (res.ok) {
          await this.fetchGoals();
        }
      } catch (e) {
        console.warn('更新进度失败:', e);
      }
    },

    async confirmComplete(goalId) {
      try {
        const res = await window.__VTJ_AUTH__.apiFetch(
          '/api/goals/' + goalId + '/confirm-complete',
          { method: 'POST', headers: this.getJsonHeaders(), body: '{}' }
        );
        if (res.ok) {
          await this.fetchGoals();
        }
      } catch (e) {
        console.warn('确认完成失败:', e);
      }
    },

    // ── 模板辅助方法 ────────────────────────────────
    getGoalTypeLabel(type) {
      const map = { 'DAILY': '每日', 'WEEKLY': '每周', 'MONTHLY': '每月', 'CUSTOM': '自定义' };
      return map[type] || type;
    },

    getGoalStatus(goal) {
      if (goal.is_completed) return 'completed';
      if (goal.deadline && new Date(goal.deadline) < new Date()) return 'overdue';
      return 'active';
    },

    getDeadlineCountdown(deadline) {
      if (!deadline) return { expired: false, text: '' };
      const now = new Date();
      const target = new Date(deadline);
      const diff = target.getTime() - now.getTime();

      if (diff <= 0) return { expired: true, text: '已截止' };

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      return { expired: false, text: days + '天 ' + hours + '时 ' + mins + '分' };
    },

    formatDeadline(deadline) {
      if (!deadline) return '';
      const d = new Date(deadline);
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      const hour = String(d.getHours()).padStart(2, '0');
      const min = String(d.getMinutes()).padStart(2, '0');
      return month + '月' + day + '日 ' + hour + ':' + min;
    }
  },
  mounted() {
    this.fetchGoals();
  }
});
</script>

<style lang="css" scoped>
/* ── 卡片容器 ──────────────────────────────────── */
.goal-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
  transition: all 0.3s;
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
}
.goal-card:hover {
  box-shadow: 0 4px 20px rgba(26, 43, 95, 0.1);
}

/* ── 头部 ──────────────────────────────────────── */
.goal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.goal-title {
  font-size: 15px;
  font-weight: 700;
  color: #1a2b5f;
  flex: 1;
}
.add-goal-btn {
  padding: 4px 14px;
  border: 1.5px dashed #c41e3a;
  border-radius: 20px;
  background: transparent;
  color: #c41e3a;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}
.add-goal-btn:hover {
  background: #fef2f3;
  border-style: solid;
}

/* ── 内容区 ────────────────────────────────────── */
.goal-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

/* ── 加载/空状态 ───────────────────────────────── */
.goal-loading {
  text-align: center;
  padding: 24px;
  color: #8a8faa;
  font-size: 13px;
}
.goal-empty {
  text-align: center;
  padding: 28px 16px;
}
.goal-empty .empty-icon {
  font-size: 36px;
  display: block;
  margin-bottom: 10px;
}
.goal-empty p {
  font-size: 14px;
  color: #8a8faa;
  margin: 0;
}

/* ── 目标卡片 ──────────────────────────────────── */
.goal-item-card {
  background: #fafbfc;
  border-radius: 12px;
  padding: 14px;
  border: 1px solid #f0f2f5;
  transition: all 0.3s;
}
.goal-item-card:hover {
  border-color: #e0e3e8;
  box-shadow: 0 2px 8px rgba(26, 43, 95, 0.04);
}

.goal-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.goal-type-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  background: #eef2ff;
  color: #4f6ef7;
}
.goal-type-badge.weekly { background: #fef3c7; color: #b45309; }
.goal-type-badge.monthly { background: #ede9fe; color: #7c3aed; }
.goal-type-badge.custom { background: #fce7f3; color: #be185d; }

.status-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}
.status-badge.completed {
  background: #dcfce7;
  color: #16a34a;
}
.status-badge.overdue {
  background: #fee2e2;
  color: #dc2626;
}

.goal-card-title {
  font-size: 13px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 8px;
}

/* ── 进度条 ────────────────────────────────────── */
.goal-progress-bar {
  height: 6px;
  background: #f0f2f5;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #c41e3a, #ff4d5a);
  border-radius: 3px;
  transition: width 0.5s ease;
  min-width: 0;
}

/* ── 统计 ──────────────────────────────────────── */
.goal-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.goal-percent {
  font-size: 12px;
  font-weight: 600;
  color: #c41e3a;
}
.goal-count {
  font-size: 11px;
  color: #8a8faa;
  font-weight: 500;
}

/* ── 截止时间 ──────────────────────────────────── */
.goal-deadline {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #8a8faa;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.deadline-label {
  color: #8a8faa;
}
.deadline-countdown {
  color: #f59e0b;
  font-weight: 600;
}
.deadline-sep {
  color: #c0c4d0;
}
.deadline-date {
  color: #5a6488;
  font-weight: 500;
}

/* ── 操作按钮 ──────────────────────────────────── */
.goal-card-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.goal-action-btn {
  padding: 3px 10px;
  border-radius: 14px;
  border: 1px solid #e0e3e8;
  background: #ffffff;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s;
}
.progress-btn {
  color: #4f6ef7;
  border-color: #dbeafe;
}
.progress-btn:hover {
  background: #eef2ff;
  border-color: #4f6ef7;
}
.complete-btn {
  color: #16a34a;
  border-color: #dcfce7;
}
.complete-btn:hover {
  background: #f0fdf4;
  border-color: #16a34a;
}
.edit-btn {
  color: #8a8faa;
}
.edit-btn:hover {
  color: #1a2b5f;
  border-color: #1a2b5f;
}
.delete-btn {
  color: #dc2626;
  border-color: #fee2e2;
}
.delete-btn:hover {
  background: #fef2f2;
  border-color: #dc2626;
}

/* ── 弹窗遮罩 ──────────────────────────────────── */
.goal-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

/* ── 弹窗主体 ──────────────────────────────────── */
.goal-dialog {
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  width: 400px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(26, 43, 95, 0.15);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.dialog-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1a2b5f;
}
.dialog-close-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  font-size: 20px;
  color: #8a8faa;
  cursor: pointer;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dialog-close-btn:hover {
  background: #f0f2f5;
  color: #1a2b5f;
}

/* ── 表单字段 ──────────────────────────────────── */
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.dialog-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dialog-field label {
  font-size: 12px;
  font-weight: 600;
  color: #5a6488;
}
.dialog-input,
.dialog-select {
  padding: 8px 12px;
  border: 1.5px solid #e0e3e8;
  border-radius: 8px;
  font-size: 13px;
  color: #1a2b5f;
  background: #fafbfc;
  outline: none;
  transition: border-color 0.25s;
}
.dialog-input:focus,
.dialog-select:focus {
  border-color: #c41e3a;
  background: #ffffff;
}

/* ── 弹窗底部 ──────────────────────────────────── */
.dialog-footer {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}
.dialog-btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s;
  border: none;
}
.dialog-btn.cancel-btn {
  background: #f0f2f5;
  color: #8a8faa;
}
.dialog-btn.cancel-btn:hover {
  background: #e0e3e8;
  color: #1a2b5f;
}
.dialog-btn.save-btn {
  background: #c41e3a;
  color: #ffffff;
}
.dialog-btn.save-btn:hover {
  background: #a01830;
}
</style>
