<!-- 学习计划智能推荐 - 模块4 全面改造版 -->
<template>
  <div class="plan-page">
    <!-- 顶部渐变横幅 -->
    <div class="hero">
      <div class="hero-bg"></div>
      <button class="back-btn" @click="goBack">‹</button>
      <div class="hero-content">
        <div class="hero-title-row">
          <span class="hero-title">学习计划</span>
          <span class="hero-badge">AI</span>
        </div>
        <div class="hero-sub">你的专属备考规划助手</div>

        <!-- 进度环 -->
        <div v-if="state.plan" class="progress-ring-wrap">
          <div class="ring">
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="40" class="ring-bg"/>
              <circle cx="50" cy="50" r="40" class="ring-fg"
                :style="{ strokeDashoffset: 251.2 - 251.2 * (state.plan.progress.percent / 100) }"/>
            </svg>
            <div class="ring-text">
              <div class="ring-percent">{{ state.plan.progress.percent }}%</div>
              <div class="ring-label">总进度</div>
            </div>
          </div>
          <div class="hero-stats">
            <div class="stat">
              <div class="stat-num">{{ state.plan.progress.done }}</div>
              <div class="stat-label">已完成</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ state.plan.progress.total }}</div>
              <div class="stat-label">总任务</div>
            </div>
            <div class="stat">
              <div class="stat-num">{{ state.daysLeft }}</div>
              <div class="stat-label">距考试</div>
            </div>
            <div class="stat">
              <div class="stat-num streak">🔥 {{ state.streak }}</div>
              <div class="stat-label">连续打卡</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="plan-body">
      <!-- 表单 -->
      <div v-if="!state.plan" class="form-card">
        <div class="form-title">📋 告诉小智你的情况</div>
        <div class="form-item">
          <label class="form-label">考试日期</label>
          <input type="date" v-model="state.form.exam_date" class="form-input"/>
        </div>
        <div class="form-item">
          <label class="form-label">薄弱科目（可多选）</label>
          <div class="chip-row">
            <div v-for="s in subjects" :key="s" class="chip"
              :class="{ active: state.form.weak_subjects.includes(s) }"
              @click="toggleSubject(s)">{{ s }}</div>
          </div>
        </div>
        <div class="form-item">
          <label class="form-label">每天可学时长：{{ state.form.daily_hours }} 小时</label>
          <input type="range" min="1" max="8" step="0.5" v-model.number="state.form.daily_hours" class="slider"/>
        </div>
        <div class="form-item">
          <label class="form-label">当前水平</label>
          <div class="chip-row">
            <div v-for="lv in levels" :key="lv" class="chip"
              :class="{ active: state.form.level === lv }"
              @click="state.form.level = lv">{{ lv }}</div>
          </div>
        </div>
        <button class="gen-btn" :disabled="state.loading" @click="generate">
          {{ state.loading ? '✨ AI 生成中...' : '🚀 生成我的复习计划' }}
        </button>
        <div v-if="state.error" class="error-tip">{{ state.error }}</div>
      </div>

      <!-- 结果 -->
      <div v-else class="result-area">
        <!-- 阶段卡片 -->
        <div v-if="state.plan.phases && state.plan.phases.length" class="phase-grid">
          <div v-for="(p, i) in state.plan.phases" :key="i" class="phase-card"
            :class="['phase-' + (i+1)]">
            <div class="phase-num">阶段{{ i+1 }}</div>
            <div class="phase-name">{{ p.name }}</div>
            <div class="phase-days">{{ p.days }} 天</div>
            <div class="phase-focus">{{ p.focus }}</div>
          </div>
        </div>

        <!-- 科目分布 -->
        <div class="subject-dist">
          <div class="dist-title">📊 任务科目分布</div>
          <div class="dist-bar">
            <div class="dist-seg" v-for="s in getSubjectStats()" :key="s.name"
              :style="{ width: s.percent + '%', background: s.color }">
              {{ s.percent > 15 ? s.name : '' }}
            </div>
          </div>
          <div class="dist-legend">
            <span v-for="s in getSubjectStats()" :key="s.name" class="legend-item">
              <span class="dot" :style="{ background: s.color }"></span>{{ s.name }} {{ s.count }}
            </span>
          </div>
        </div>

        <!-- 本周进度 -->
        <div class="week-progress">
          <div class="dist-title">📅 本周打卡</div>
          <div class="week-dots">
            <div v-for="(d, i) in weekDays" :key="i" class="week-dot"
              :class="{ done: i < state.plan.progress.percent / 100 * 7 }">
              {{ d }}
            </div>
          </div>
        </div>

        <!-- 今日任务 -->
        <div class="section">
          <div class="section-head">
            <span class="section-title">📌 今日任务</span>
            <span class="section-hint">点击勾选完成</span>
          </div>
          <div class="task-list">
            <div v-for="t in state.plan.tasks" :key="t.goal_id"
              class="task-item" :class="{ done: t.is_completed }"
              @click="toggleTask(t)">
              <span class="checkbox">{{ t.is_completed ? '✓' : '' }}</span>
              <span class="task-title">{{ t.title }}</span>
            </div>
          </div>
        </div>

        <!-- AI 提示 -->
        <div v-if="state.plan.tips" class="tips-card">
          <div class="tips-icon">💡</div>
          <div class="tips-body">
            <div class="tips-title">小智提示</div>
            <div class="tips-text">{{ state.plan.tips }}</div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-row">
          <button class="action-btn ghost" @click="reset">🔄 重新生成</button>
          <button class="action-btn ghost" @click="askAI">🤖 AI 调整计划</button>
        </div>

        <!-- AI 调整对话框 -->
        <div v-if="state.showAsk" class="ask-box">
          <input v-model="state.askText" class="ask-input"
            placeholder="比如：今天太累了，明天能不能少安排点？"
            @keyup.enter="sendAsk"/>
          <button class="ask-send" @click="sendAsk">发送</button>
        </div>
        <div v-if="state.askReply" class="ask-reply">{{ state.askReply }}</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, onMounted } from 'vue';

  export default defineComponent({
    name: 'StudyPlan',
    setup() {
      const state = reactive({
        loading: false,
        error: '',
        plan: null,
        daysLeft: 0,
        streak: 3,
        showAsk: false,
        askText: '',
        askReply: '',
        form: {
          exam_date: defaultDate(),
          weak_subjects: ['行测'],
          daily_hours: 3,
          level: '有基础',
        },
      });

      const subjects = ['行测', '申论', '公安专业科目'];
      const levels = ['零基础', '有基础', '冲刺'];
      const weekDays = ['一', '二', '三', '四', '五', '六', '日'];

      // 计算科目分布（动态）
      function getSubjectStats() {
        const stats = [
          { name: '行测', color: '#3b82f6', count: 0, percent: 0 },
          { name: '申论', color: '#f59e0b', count: 0, percent: 0 },
          { name: '公专', color: '#ef4444', count: 0, percent: 0 },
        ];
        if (state.plan && state.plan.tasks) {
          state.plan.tasks.forEach(t => {
            const title = t.title || '';
            if (title.includes('行测') || title.includes('言语') || title.includes('资料') || title.includes('判断')) {
              stats[0].count++;
            } else if (title.includes('申论') || title.includes('范文') || title.includes('归纳')) {
              stats[1].count++;
            } else if (title.includes('公专') || title.includes('公安') || title.includes('法律')) {
              stats[2].count++;
            }
          });
          const total = state.plan.tasks.length || 1;
          stats.forEach(s => { s.percent = Math.round(s.count / total * 100); });
        }
        return stats;
      }

      function defaultDate() {
        const d = new Date();
        d.setMonth(d.getMonth() + 3);
        return d.toISOString().slice(0, 10);
      }

      function toggleSubject(s) {
        const arr = state.form.weak_subjects;
        const idx = arr.indexOf(s);
        if (idx >= 0) arr.splice(idx, 1);
        else arr.push(s);
      }

      async function generate() {
        state.loading = true;
        state.error = '';
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/plan/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              exam_date: state.form.exam_date,
              weak_subjects: state.form.weak_subjects,
              daily_hours: state.form.daily_hours,
              level: state.form.level,
            }),
          });
          const data = await res.json();
          if (res.ok) {
            state.plan = data;
            const exam = new Date(state.form.exam_date);
            state.daysLeft = Math.ceil((exam - new Date()) / 86400000);
          } else {
            state.error = data.detail || '生成失败，请重试';
          }
        } catch (e) {
          state.error = '网络异常，请稍后再试';
        } finally {
          state.loading = false;
        }
      }

      async function toggleTask(t) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch(`/api/plan/task/${t.goal_id}/toggle`, { method: 'POST' });
          if (res.ok) {
            t.is_completed = t.is_completed === 1 ? 0 : 1;
            const total = state.plan.tasks.length;
            const done = state.plan.tasks.filter(x => x.is_completed === 1).length;
            state.plan.progress.done = done;
            state.plan.progress.percent = Math.round(done / total * 100);
          }
        } catch (e) {}
      }

      function reset() {
        state.plan = null;
        state.error = '';
        state.askReply = '';
      }

      function askAI() {
        state.showAsk = !state.showAsk;
        state.askReply = '';
      }

      async function sendAsk() {
        if (!state.askText.trim()) return;
        const q = state.askText;
        state.askText = '';
        try {
          // 带上当前计划上下文，让 AI 的建议更有针对性
          const planCtx = state.plan
            ? `我当前的学习计划：${(state.plan.summary || '').slice(0, 300)}，共 ${state.plan.tasks.length} 条任务，已完成 ${state.plan.progress.done} 条。`
            : '我还没有生成学习计划。';
          const res = await window.__VTJ_AUTH__.apiFetch('/api/llm/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scene: 'advice', message: (planCtx + '关于我的复习计划调整：' + q).slice(0, 2000) }),
          });
          const data = await res.json();
          if (res.ok) state.askReply = data.reply || data.message || '收到，按你的情况调整啦';
          else state.askReply = data.detail || '调整失败，请稍后再试';
        } catch (e) {
          state.askReply = '网络异常';
        }
      }

      function goBack() {
        if (window.history.length > 1) window.history.back();
        else window.location.href = '/#/';
      }

      onMounted(async () => {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/plan/current');
          const data = await res.json();
          if (res.ok && data.has_plan) {
            state.plan = data;
            // 用后端返回的实际考试日期算剩余天数
            if (data.exam_date) {
              const exam = new Date(data.exam_date);
              state.daysLeft = Math.ceil((exam - new Date()) / 86400000);
            }
          }
        } catch (e) {}
      });

      return {
        state, subjects, levels, weekDays, getSubjectStats,
        toggleSubject, generate, toggleTask, reset, askAI, sendAsk, goBack,
      };
    },
  });
</script>

<style lang="css" scoped>
  .plan-page { min-height: 100vh; background: #f0f3f8; }

  /* Hero */
  .hero { position: relative; overflow: hidden; color: #fff; }
  .hero-bg {
    position: absolute; inset: 0;
    background: linear-gradient(135deg, #0f1e3d 0%, #1e3a6e 50%, #2d5aa0 100%);
  }
  .hero-bg::after {
    content: ''; position: absolute; right: -40px; top: -40px;
    width: 200px; height: 200px; border-radius: 50%;
    background: radial-gradient(circle, rgba(200,22,30,0.3), transparent 70%);
  }
  .hero-content { position: relative; padding: 20px; }
  .hero-title-row { display: flex; align-items: center; gap: 8px; }
  .hero-title { font-size: 22px; font-weight: 700; }
  .hero-badge {
    background: #c8161e; padding: 2px 10px; border-radius: 10px;
    font-size: 12px; font-weight: 600;
  }
  .hero-sub { font-size: 13px; color: rgba(255,255,255,0.7); margin-top: 2px; }
  .back-btn {
    position: absolute; left: 16px; top: 16px; z-index: 2;
    background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
    color: #fff; width: 32px; height: 32px; border-radius: 50%;
    font-size: 22px; cursor: pointer;
  }

  /* 进度环 */
  .progress-ring-wrap { display: flex; align-items: center; gap: 24px; margin-top: 16px; }
  .ring { position: relative; width: 90px; height: 90px; }
  .ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .ring-bg { fill: none; stroke: rgba(255,255,255,0.15); stroke-width: 8; }
  .ring-fg {
    fill: none; stroke: #4ade80; stroke-width: 8; stroke-linecap: round;
    stroke-dasharray: 251.2; transition: stroke-dashoffset 0.6s;
  }
  .ring-text {
    position: absolute; inset: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
  }
  .ring-percent { font-size: 18px; font-weight: 700; }
  .ring-label { font-size: 10px; color: rgba(255,255,255,0.6); }
  .hero-stats { display: flex; gap: 20px; }
  .stat-num { font-size: 20px; font-weight: 700; }
  .stat-num.streak { color: #fbbf24; }
  .stat-label { font-size: 11px; color: rgba(255,255,255,0.6); }

  /* Body */
  .plan-body { max-width: 640px; margin: -12px auto 0; padding: 0 16px 40px; position: relative; z-index: 2; }
  .form-card, .result-area { background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 6px 20px rgba(15,30,61,0.08); }
  .form-title { font-size: 15px; font-weight: 600; color: #1a2a4a; margin-bottom: 16px; }
  .form-item { margin-bottom: 16px; }
  .form-label { display: block; font-size: 13px; color: #5a6a7a; margin-bottom: 8px; font-weight: 500; }
  .form-input {
    width: 100%; padding: 10px 12px; border: 1px solid #e0e4e8;
    border-radius: 10px; font-size: 14px; outline: none; box-sizing: border-box;
  }
  .form-input:focus { border-color: #1e3a6e; }
  .chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip {
    padding: 7px 14px; background: #f3f5f9; border: 1px solid #e6ebf2;
    border-radius: 16px; font-size: 13px; color: #3a4a6a; cursor: pointer;
    transition: all 0.2s;
  }
  .chip.active { background: #1e3a6e; color: #fff; border-color: #1e3a6e; }
  .slider { width: 100%; }
  .gen-btn {
    width: 100%; padding: 13px;
    background: linear-gradient(135deg, #c8161e, #e63946);
    color: #fff; border: none; border-radius: 12px;
    font-size: 15px; font-weight: 600; cursor: pointer;
    box-shadow: 0 4px 12px rgba(200,22,30,0.3);
  }
  .gen-btn:disabled { opacity: 0.6; cursor: not-allowed; }
  .error-tip { margin-top: 10px; color: #c8161e; font-size: 13px; text-align: center; }

  /* 阶段卡片 */
  .phase-grid { display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }
  .phase-card {
    flex: 1; min-width: 130px; border-radius: 12px; padding: 12px;
    color: #fff;
  }
  .phase-1 { background: linear-gradient(135deg, #3b82f6, #2563eb); }
  .phase-2 { background: linear-gradient(135deg, #f59e0b, #d97706); }
  .phase-3 { background: linear-gradient(135deg, #ef4444, #dc2626); }
  .phase-num { font-size: 11px; opacity: 0.9; }
  .phase-name { font-size: 14px; font-weight: 700; margin: 2px 0; }
  .phase-days { font-size: 12px; opacity: 0.9; margin-bottom: 4px; }
  .phase-focus { font-size: 11px; opacity: 0.85; line-height: 1.4; }

  /* Section */
  .section { margin-bottom: 16px; }
  .section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  .section-title { font-size: 14px; font-weight: 600; color: #1a2a4a; }
  .section-hint { font-size: 11px; color: #aab4c0; }
  .task-list { background: #f8fafc; border-radius: 10px; overflow: hidden; }
  .task-item {
    display: flex; align-items: center; gap: 10px; padding: 12px;
    border-bottom: 1px solid #eef2f6; cursor: pointer;
  }
  .task-item:last-child { border-bottom: none; }
  .task-item.done .task-title { text-decoration: line-through; color: #aab4c0; }
  .checkbox {
    width: 20px; height: 20px; border: 2px solid #c8d0da; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: #fff; background: #fff; flex-shrink: 0;
    transition: all 0.2s;
  }
  .task-item.done .checkbox { background: #c8161e; border-color: #c8161e; }
  .task-title { font-size: 14px; color: #2c3e50; }

  /* Tips */
  .tips-card {
    display: flex; gap: 10px; background: #fff8e6; border-radius: 10px;
    padding: 12px; margin-bottom: 16px;
  }
  .tips-icon { font-size: 18px; }
  .tips-title { font-size: 13px; font-weight: 600; color: #b8860b; margin-bottom: 2px; }
  .tips-text { font-size: 12px; color: #6a5a3a; line-height: 1.5; }

  /* Actions */
  .action-row { display: flex; gap: 10px; }
  .action-btn {
    flex: 1; padding: 10px; border-radius: 10px; font-size: 13px; cursor: pointer;
    border: 1px solid #e6ebf2; background: #fff; color: #5a6a7a;
  }
  .action-btn.ghost:hover { background: #f3f5f9; }

  /* Ask */
  .ask-box { display: flex; gap: 8px; margin-top: 12px; }
  .ask-input {
    flex: 1; padding: 10px 12px; border: 1px solid #e0e4e8;
    border-radius: 10px; font-size: 13px; outline: none;
  }
  .ask-send {
    padding: 0 16px; background: #1e3a6e; color: #fff; border: none;
    border-radius: 10px; font-size: 13px; cursor: pointer;
  }
  .ask-reply {
    margin-top: 10px; padding: 12px; background: #f0f7ff; border-radius: 10px;
    font-size: 13px; color: #1e3a6e; line-height: 1.5;
  }

  /* 科目分布 */
  .subject-dist { margin-bottom: 16px; }
  .dist-title { font-size: 13px; font-weight: 600; color: #1a2a4a; margin-bottom: 8px; }
  .dist-bar {
    display: flex; height: 28px; border-radius: 8px; overflow: hidden;
    background: #f0f2f6; margin-bottom: 8px;
  }
  .dist-seg {
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; color: #fff; font-weight: 600;
    transition: width 0.4s;
  }
  .dist-legend { display: flex; gap: 14px; flex-wrap: wrap; }
  .legend-item { font-size: 12px; color: #5a6a7a; display: flex; align-items: center; gap: 4px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

  /* 本周打卡 */
  .week-progress { margin-bottom: 16px; }
  .week-dots { display: flex; gap: 8px; }
  .week-dot {
    width: 36px; height: 36px; border-radius: 8px;
    background: #f0f2f6; display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: #aab4c0; font-weight: 600;
    transition: all 0.3s;
  }
  .week-dot.done {
    background: linear-gradient(135deg, #4ade80, #22c55e);
    color: #fff;
    box-shadow: 0 2px 8px rgba(74,222,128,0.4);
  }

  /* ========== 三端响应式 ========== */

  /* 手机竖屏 < 768px */
  @media (max-width: 767px) {
    .hero-content { padding: 16px; }
    .hero-title { font-size: 18px; }
    .hero-sub { font-size: 12px; }
    .progress-ring-wrap { flex-direction: column; align-items: flex-start; gap: 12px; }
    .ring { width: 70px; height: 70px; }
    .ring-percent { font-size: 14px; }
    .hero-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; width: 100%; }
    .stat-num { font-size: 16px; }
    .plan-body { padding: 0 12px 30px; }
    .phase-grid { flex-direction: column; }
    .phase-card { min-width: auto; }
    .week-dots { gap: 6px; }
    .week-dot { width: 40px; height: 32px; font-size: 11px; }
    .action-row { flex-direction: column; }
    .form-card, .result-area { padding: 16px; }
  }

  /* 平板 768-1023px */
  @media (min-width: 768px) and (max-width: 1023px) {
    .plan-body { max-width: 720px; }
    .phase-card { min-width: 160px; }
    .ring { width: 80px; height: 80px; }
  }

  /* PC 宽屏 >= 1024px */
  @media (min-width: 1024px) {
    .plan-body { max-width: 860px; padding-top: 24px; }
    .phase-card { min-width: 180px; padding: 16px; }
    .ring { width: 100px; height: 100px; }
    .ring-percent { font-size: 22px; }
    .hero-title { font-size: 26px; }
    .task-item { padding: 14px 16px; }
    .task-title { font-size: 15px; }
  }
</style>
