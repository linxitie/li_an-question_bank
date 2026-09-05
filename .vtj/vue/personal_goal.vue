<!-- 个人目标模块 -->
<template>
  <div class="goal-card">
    <div class="card-header">
      <div class="header-left">
        <XIcon :icon="TrophyBase" :size="20" color="#c8161e"></XIcon>
        <span class="header-title"> 个人小目标</span>
      </div>
      <div class="header-actions">
        <button class="set-goal-btn" @click="state.dialogVisible = true">
          <XIcon :icon="EditPen" :size="12" color="#c8161e"></XIcon>
          <span> 设定</span>
        </button>
      </div>
    </div>
    <div class="goal-progress-list">
      <div class="goal-item">
        <div class="goal-info">
          <span class="goal-name"> 今日目标</span>
          <span class="goal-value">
            <span>
              <span> {{ state.todayDone }}</span>
              <span> /</span>
              <span> {{ state.todayGoal }}</span>
              <span> 题</span></span
            ></span
          >
        </div>
        <div
          class="progress-bar div_26injvd4res"
          :style="{
            '--progress': (state.todayDone / state.todayGoal) * 100 + '%'
          }">
          <div
            class="progress-fill div_26iojvd4res"
            :style="{
              width: (state.todayDone / state.todayGoal) * 100 + '%'
            }"></div>
        </div>
      </div>
      <div class="goal-item">
        <div class="goal-info">
          <span class="goal-name"> 本周目标</span>
          <span class="goal-value">
            <span>
              <span> {{ state.weekDone }}</span>
              <span> /</span>
              <span> {{ state.weekGoal }}</span>
              <span> 题</span></span
            ></span
          >
        </div>
        <div
          class="progress-bar div_26itjvd4res"
          :style="{
            '--progress': (state.weekDone / state.weekGoal) * 100 + '%'
          }">
          <div
            class="progress-fill div_26iujvd4res"
            :style="{
              width: (state.weekDone / state.weekGoal) * 100 + '%'
            }"></div>
        </div>
      </div>
    </div>
    <div class="tomorrow-plan">
      <div class="plan-header">
        <XIcon :icon="Sunrise" :size="16" color="#e67e22"></XIcon>
        <span class="plan-title"> 明日计划</span>
      </div>
      <div class="plan-content">
        <div
          v-for="(item, idx) in state.tomorrowPlans"
          :key="idx"
          class="plan-item">
          <div
            class="plan-dot div_26j1jvd4res"
            :style="{ background: item.color }"></div>
          <span> {{ item.text }}</span>
        </div>
      </div>
    </div>
    <div
      v-if="state.dialogVisible"
      class="goal-dialog-overlay"
      @click.self="state.dialogVisible = false">
      <div class="goal-dialog">
        <div class="dialog-header">
          <span class="dialog-title"> 设定目标</span>
          <button class="dialog-close" @click="state.dialogVisible = false">
            <XIcon :icon="Close" :size="18" color="#8899aa"></XIcon>
          </button>
        </div>
        <div class="dialog-body">
          <div class="dialog-field">
            <label> 今日目标（题）</label>
            <input v-model="state.todayGoal" max="500" min="10" type="number" />
          </div>
          <div class="dialog-field">
            <label> 本周目标（题）</label>
            <input v-model="state.weekGoal" max="3000" min="50" type="number" />
          </div>
          <div class="dialog-field">
            <label> 明日计划科目</label>
            <input
              v-model="state.planSubject"
              type="text"
              placeholder="输入科目，如：行测" />
          </div>
          <div class="dialog-field">
            <label> 计划题量</label>
            <input v-model="state.planCount" max="200" min="5" type="number" />
          </div>
          <button class="dialog-save-btn" @click="handleSaveGoal">
            <XIcon :icon="Check" :size="16" color="#ffffff"></XIcon>
            <span> 保存</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { TrophyBase, EditPen, Sunrise, Close, Check } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  export default defineComponent({
    name: 'PersonalGoalCard',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'personal_goal', version: '1778916170174' });
      const state = reactive({
        weekDone: 320,
        weekGoal: 500,
        planCount: 60,
        todayDone: 56,
        todayGoal: 80,
        planSubject: '申论',
        dialogVisible: false,
        tomorrowPlans: [
          { text: '完成 行测 60 题', color: '#c8161e' },
          { text: '复习 公专 基础知识', color: '#2c3e50' }
        ]
      });
      return {
        state,
        props,
        provider,
        TrophyBase,
        EditPen,
        Sunrise,
        Close,
        Check
      };
    },
    methods: {
      async fetchGoals() {
        try {
          var res = await window.__VTJ_AUTH__.apiFetch('/api/goals/?limit=5');
          var data = await res.json();
          if (res.ok && data.items && data.items.length) {
            var g = data.items[0]; // 取最新目标
            this.state.todayGoal = g.target_count || 80;
            this.state.todayDone = g.current_progress || 0;
            this.state.weekGoal = Math.max((g.target_count || 80) * 7, 500);
            this.state.weekDone = Math.min(this.state.todayDone * 7, this.state.weekGoal);
            this.state.hasGoals = true;
          }
        } catch(e) { /* 使用默认值 */ }
      },
      async handleSaveGoal() {
        // 持久化到后端
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/goals/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: this.state.planSubject + '每日' + this.state.planCount + '题',
              goal_type: 'CUSTOM',
              target_count: this.state.todayGoal,
              current_progress: this.state.todayDone
            })
          });
        } catch(e) { /* 网络异常时仍保存本地 */ }
        this.state.tomorrowPlans = [
          { text: '完成 ' + this.state.planSubject + ' ' + this.state.planCount + ' 题', color: '#c8161e' },
          { text: '复习 公专 基础知识', color: '#2c3e50' }
        ];
        this.state.dialogVisible = false;
        ElMessage.success('个人目标已更新');
      }
    },
    mounted() {
      this.fetchGoals();
    }
  })
</script>
<style lang="css" scoped>
  /* 个人小目标卡片 */
  .goal-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    border: 1px solid #e8ecf1;
    box-shadow: 0 4px 20px rgba(10, 22, 40, 0.06);
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  /* 卡片标题 */
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .header-title {
    font-size: 20px;
    font-weight: 600;
    color: #1a2a4a;
    letter-spacing: 1px;
  }
  .header-actions {
    display: flex;
    gap: 8px;
  }
  .set-goal-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: 1px solid rgba(200, 22, 30, 0.25);
    color: #c8161e;
    font-size: 14px;
    font-weight: 500;
    padding: 5px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.25s ease;
  }
  .set-goal-btn:hover {
    background: rgba(200, 22, 30, 0.06);
    border-color: #c8161e;
  }
  /* 目标进度列表 */
  .goal-progress-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 16px;
  }
  /* 目标项 */
  .goal-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .goal-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .goal-name {
    font-size: 13px;
    font-weight: 500;
    color: #2c3e50;
  }
  .goal-value {
    font-size: 12px;
    font-weight: 600;
    color: #8899aa;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
  }
  /* 进度条 */
  .progress-bar {
    width: 100%;
    height: 8px;
    background: #f0f2f5;
    border-radius: 4px;
    overflow: hidden;
    position: relative;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #c8161e 0%, #e63946 50%, #ff6b6b 100%);
    border-radius: 4px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
  }
  .progress-fill::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.4),
      transparent
    );
    animation: shimmer 2s infinite;
  }
  @keyframes shimmer {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }
  /* 明日计划 */
  .tomorrow-plan {
    flex: 1;
    background: linear-gradient(
      135deg,
      rgba(230, 126, 34, 0.04) 0%,
      rgba(230, 126, 34, 0.01) 100%
    );
    border-radius: 10px;
    padding: 12px;
    border: 1px solid rgba(230, 126, 34, 0.1);
  }
  .plan-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
  }
  .plan-title {
    font-size: 13px;
    font-weight: 600;
    color: #e67e22;
  }
  .plan-content {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .plan-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #2c3e50;
  }
  .plan-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  /* 弹窗样式 */
  .goal-dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(10, 22, 40, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(4px);
  }
  .goal-dialog {
    background: #ffffff;
    border-radius: 16px;
    width: 500px;
    max-width: 90%;
    box-shadow: 0 20px 50px rgba(10, 22, 40, 0.3);
    animation: dialog-in 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    overflow: hidden;
  }
  @keyframes dialog-in {
    from {
      opacity: 0;
      transform: scale(0.9) translateY(20px);
    }
    to {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }
  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid #f0f2f5;
    background: linear-gradient(135deg, #fafbfc 0%, #f5f6f8 100%);
  }
  .dialog-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a2a4a;
  }
  .dialog-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: none;
    background: transparent;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .dialog-close:hover {
    background: #f0f2f5;
  }
  .dialog-body {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .dialog-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .dialog-field label {
    font-size: 13px;
    font-weight: 500;
    color: #2c3e50;
  }
  .dialog-field input {
    height: 40px;
    border: 1px solid #e0e4e8;
    border-radius: 8px;
    padding: 0 12px;
    font-size: 14px;
    color: #2c3e50;
    background: #fafbfc;
    transition: all 0.25s ease;
    outline: none;
  }
  .dialog-field input:focus {
    border-color: #c8161e;
    box-shadow: 0 0 0 3px rgba(200, 22, 30, 0.08);
    background: #ffffff;
  }
  .dialog-save-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    height: 42px;
    background: linear-gradient(135deg, #0d1b2a 0%, #152238 100%);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    margin-top: 4px;
  }
  .dialog-save-btn:hover {
    background: linear-gradient(135deg, #152238 0%, #1a2a4a 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(10, 22, 40, 0.25);
  }
  .dialog-save-btn:active {
    transform: scale(0.98);
  }
</style>
