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
      <!-- 成就系统 -->
      <div class="achievement-card">
        <div class="ach-left">
          <div class="ach-avatar">🎓</div>
          <div class="ach-info">
            <div class="ach-level">Lv.3 高手</div>
            <div class="ach-exp">经验值 350/500</div>
            <div class="ach-exp-bar">
              <div class="ach-exp-fill" style="width: 70%"></div>
            </div>
          </div>
        </div>
        <div class="ach-right">
          <div class="badge" title="连续打卡7天">🔥</div>
          <div class="badge" title="100题全对">💯</div>
          <div class="badge" title="模考高分">🏆</div>
          <div class="badge locked" title="还未解锁">🔒</div>
        </div>
      </div>

      <!-- 视图切换tab -->
      <div v-if="state.plan" class="view-tabs">
        <div class="view-tab" @click="scrollToOverview">
          📊 计划总览
        </div>
        <div class="view-tab" @click="scrollToToday">
          📌 今日任务
        </div>
      </div>

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
        <!-- 操作错误提示（任务勾选等失败时显示） -->
        <div v-if="state.error" class="error-tip" style="margin-bottom:12px">{{ state.error }}</div>

        <!-- 自动调整建议 -->
        <div v-if="state.plan.adjustment_suggestion" class="adjust-hint" :class="state.plan.adjustment_suggestion.type">
          <span>{{ state.plan.adjustment_suggestion.message }}</span>
          <button class="adjust-btn" @click="askAI">去调整</button>
        </div>
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

        <!-- 3D学习日历 -->
        <div class="calendar-3d-card">
          <div class="dist-title">📅 3D学习日历</div>
          <div class="calendar-3d-wrap">
            <div class="calendar-3d">
              <div v-for="day in 30" :key="day" class="calendar-day"
                :class="{ done: day < 20, today: day === 15 }">
                {{ day }}
              </div>
            </div>
          </div>
        </div>

        <!-- 智能排课 -->
        <div class="smart-schedule-card">
          <div class="dist-title">⏰ 智能排课 · 今日时间表</div>
          <div class="schedule-timeline">
            <div class="time-slot morning">
              <div class="time-label">🌅 上午 9:00-12:00</div>
              <div class="task-list">
                <div class="task-item" :class="{ done: slot.morning.done }">
                  <span class="task-subject">资料分析</span>
                  <span class="task-detail">20题 · 重点：增长率</span>
                  <button class="task-check" @click="toggleSlotTask('morning')">{{ slot.morning.done ? '✓' : '○' }}</button>
                </div>
                <div class="task-item" :class="{ done: slot.morning2.done }">
                  <span class="task-subject">言语理解</span>
                  <span class="task-detail">15题 · 重点：逻辑填空</span>
                  <button class="task-check" @click="toggleSlotTask('morning2')">{{ slot.morning2.done ? '✓' : '○' }}</button>
                </div>
              </div>
            </div>
            <div class="time-slot afternoon">
              <div class="time-label">☀️ 下午 14:00-17:00</div>
              <div class="task-list">
                <div class="task-item" :class="{ done: slot.afternoon.done }">
                  <span class="task-subject">判断推理</span>
                  <span class="task-detail">15题 · 重点：图形推理</span>
                  <button class="task-check" @click="toggleSlotTask('afternoon')">{{ slot.afternoon.done ? '✓' : '○' }}</button>
                </div>
                <div class="task-item" :class="{ done: slot.afternoon2.done }">
                  <span class="task-subject">数量关系</span>
                  <span class="task-detail">10题 · 重点：工程问题</span>
                  <button class="task-check" @click="toggleSlotTask('afternoon2')">{{ slot.afternoon2.done ? '✓' : '○' }}</button>
                </div>
              </div>
            </div>
            <div class="time-slot evening">
              <div class="time-label">🌙 晚上 19:00-21:30</div>
              <div class="task-list">
                <div class="task-item" :class="{ done: slot.evening.done }">
                  <span class="task-subject">申论</span>
                  <span class="task-detail">大作文 · 1篇</span>
                  <button class="task-check" @click="toggleSlotTask('evening')">{{ slot.evening.done ? '✓' : '○' }}</button>
                </div>
                <div class="task-item" :class="{ done: slot.evening2.done }">
                  <span class="task-subject">错题复习</span>
                  <span class="task-detail">复习今日错题 · 艾宾浩斯</span>
                  <button class="task-check" @click="toggleSlotTask('evening2')">{{ slot.evening2.done ? '✓' : '○' }}</button>
                </div>
              </div>
            </div>
          </div>
          <div class="schedule-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: getScheduleProgress() + '%' }"></div>
            </div>
            <div class="progress-text">今日已完成 {{ getScheduleProgress() }}%</div>
          </div>
        </div>

        <!-- AI作文批改 -->
        <div class="essay-grading-card">
          <div class="dist-title">✍️ AI作文批改 · 申论大作文</div>
          <div class="essay-intro">
            <p>把你的申论大作文粘贴进来，AI专家帮你打分点评！</p>
          </div>
          <div class="essay-topic-input">
            <label>作文题目：</label>
            <input type="text" v-model="essay.topic" placeholder="例如：请以“新时代公安使命”为主题写一篇议论文" />
          </div>
          <div class="essay-content-input">
            <label>作文内容：</label>
            <textarea v-model="essay.content" rows="6" placeholder="把你的作文内容粘贴在这里..."></textarea>
          </div>
          <button class="essay-submit-btn" @click="gradeEssay">🤖 开始AI批改</button>

          <!-- 批改结果 -->
          <div v-if="essay.result" class="essay-result">
            <div class="result-score">
              <div class="score-num">{{ essay.result.total }}<span>分</span></div>
              <div class="score-label">总分（百分制）</div>
            </div>
            <div class="result-dimensions">
              <div v-for="dim in essay.result.dimensions" :key="dim.name" class="dim-item">
                <div class="dim-name">{{ dim.name }}</div>
                <div class="dim-bar">
                  <div class="dim-fill" :style="{ width: (dim.score / dim.max) * 100 + '%', background: dim.color }"></div>
                </div>
                <div class="dim-score">{{ dim.score }}/{{ dim.max }}</div>
              </div>
            </div>
            <div class="result-comment">
              <div class="comment-title">📝 AI评语：</div>
              <p>{{ essay.result.comment }}</p>
            </div>
            <div class="result-suggest">
              <div class="suggest-title">💡 改进建议：</div>
              <ul>
                <li v-for="(s, i) in essay.result.suggestions" :key="i">{{ s }}</li>
              </ul>
            </div>
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

        <!-- 能力雷达图 -->
        <div class="radar-card">
          <div class="dist-title">🎯 能力雷达图</div>
          <div class="radar-wrap">
            <svg viewBox="0 0 200 200" class="radar-svg">
              <!-- 背景多边形 -->
              <polygon points="100,20 170,60 170,140 100,180 30,140 30,60" fill="none" stroke="#e0e3e9" stroke-width="1"/>
              <polygon points="100,50 150,75 150,125 100,150 50,125 50,75" fill="none" stroke="#e0e3e9" stroke-width="1"/>
              <polygon points="100,80 130,95 130,105 100,120 70,105 70,95" fill="none" stroke="#e0e3e9" stroke-width="1"/>
              <!-- 轴线 -->
              <line x1="100" y1="20" x2="100" y2="180" stroke="#e0e3e9" stroke-width="1"/>
              <line x1="30" y1="60" x2="170" y2="140" stroke="#e0e3e9" stroke-width="1"/>
              <line x1="30" y1="140" x2="170" y2="60" stroke="#e0e3e9" stroke-width="1"/>
              <!-- 数据多边形 -->
              <polygon points="100,40 160,70 150,130 100,160 40,130 50,70"
                fill="rgba(196, 30, 58, 0.2)" stroke="#c41e3a" stroke-width="2"/>
            </svg>
            <div class="radar-labels">
              <span class="radar-label top">言语理解</span>
              <span class="radar-label right-top">数量关系</span>
              <span class="radar-label right-bottom">判断推理</span>
              <span class="radar-label bottom">资料分析</span>
              <span class="radar-label left-bottom">申论</span>
              <span class="radar-label left-top">面试</span>
            </div>
          </div>
        </div>

        <!-- 遗忘曲线复习提醒 -->
        <div class="review-card">
          <div class="review-head">
            <span class="dist-title">🧠 遗忘曲线复习</span>
            <span class="review-badge">3个待复习</span>
          </div>
          <div class="review-list">
            <div class="review-item">
              <div class="review-info">
                <div class="review-topic">资料分析-增长率</div>
                <div class="review-desc">1天前学过，现在复习最佳</div>
              </div>
              <button class="review-btn">去复习</button>
            </div>
            <div class="review-item">
              <div class="review-info">
                <div class="review-topic">判断推理-图形推理</div>
                <div class="review-desc">3天前学过，现在复习最佳</div>
              </div>
              <button class="review-btn">去复习</button>
            </div>
            <div class="review-item">
              <div class="review-info">
                <div class="review-topic">言语理解-逻辑填空</div>
                <div class="review-desc">7天前学过，现在复习最佳</div>
              </div>
              <button class="review-btn">去复习</button>
            </div>
          </div>
        </div>

        <!-- 自适应学习推荐 -->
        <div class="adaptive-card">
          <div class="adaptive-head">
            <span class="dist-title">🤖 自适应学习推荐</span>
            <span class="adaptive-badge">AI</span>
          </div>
          <div class="adaptive-body">
            <div class="adaptive-tip">
              <div class="adaptive-tip-icon">📈</div>
              <div class="adaptive-tip-text">
                <div class="adaptive-tip-title">建议提升难度</div>
                <div class="adaptive-tip-desc">你最近答对率85%，可以挑战更难的题目</div>
              </div>
            </div>
            <div class="adaptive-tip">
              <div class="adaptive-tip-icon">📉</div>
              <div class="adaptive-tip-text">
                <div class="adaptive-tip-title">建议巩固基础</div>
                <div class="adaptive-tip-desc">资料分析正确率偏低，建议先练基础题</div>
              </div>
            </div>
            <button class="adaptive-btn">开始自适应练习</button>
          </div>
        </div>

        <!-- AI错题本 -->
        <div class="wrongbook-card">
          <div class="wrongbook-head">
            <span class="dist-title">📕 AI错题本</span>
            <span class="wrongbook-badge">23道错题</span>
          </div>
          <div class="wrongbook-body">
            <div class="wrongbook-stats">
              <div class="wb-stat">
                <div class="wb-num">12</div>
                <div class="wb-label">资料分析</div>
              </div>
              <div class="wb-stat">
                <div class="wb-num">8</div>
                <div class="wb-label">判断推理</div>
              </div>
              <div class="wb-stat">
                <div class="wb-num">3</div>
                <div class="wb-label">言语理解</div>
              </div>
            </div>
            <div class="wrongbook-tip">
              <span class="wb-tip-icon">💡</span>
              <span>AI分析：你资料分析的增长率题型错得最多，建议重点复习</span>
            </div>
            <button class="wrongbook-btn">开始错题重做</button>
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
            <span class="section-hint">完成勾选 → 领取金币</span>
          </div>
          <div v-if="state.coinNotice" class="coin-notice">{{ state.coinNotice }}</div>
          <div class="task-list">
            <template v-if="state.today && state.today.tasks.length">
              <div v-for="t in state.today.tasks" :key="t.goal_id"
                class="task-item" :class="{ done: t.is_completed }">
                <div class="task-main" @click="toggleTask(t)">
                  <span class="checkbox">{{ t.is_completed ? '✓' : '' }}</span>
                  <span class="task-title">{{ t.title }}</span>
                  <span class="coin-badge" :class="{ dim: t.coin_claimed }">🪙 {{ t.coin_reward || 0 }}</span>
                </div>
                <button v-if="t.is_completed === 1 && t.coin_claimed === 0" class="claim-btn"
                  @click.stop="claimCoin(t)">领取</button>
                <span v-else-if="t.coin_claimed === 1" class="claimed-tag">已领取</span>
              </div>
            </template>
            <div v-else class="task-empty">今日暂无任务，先重新生成学习计划吧</div>
          </div>
        </div>

        <!-- 番茄钟专注记录 -->
        <div class="pomodoro-card">
          <div class="pomodoro-head">
            <span class="section-title">⏱️ 番茄钟专注</span>
            <span class="pomodoro-today">今日专注 {{ state.pomodoro.minutes }} 分钟</span>
          </div>
          <div class="pomodoro-body">
            <div class="pomodoro-display" :class="{ running: state.pomodoro.running, break: state.pomodoro.isBreak }">
              <div class="pomodoro-time">{{ formatTime(state.pomodoro.seconds) }}</div>
              <div class="pomodoro-mode">{{ state.pomodoro.isBreak ? '休息时间' : '专注时间' }}</div>
            </div>
            <div class="pomodoro-controls">
              <button class="pomodoro-btn primary" @click="togglePomodoro">
                {{ state.pomodoro.running ? '暂停' : '开始' }}
              </button>
              <button class="pomodoro-btn" @click="resetPomodoro">重置</button>
            </div>
            <div class="pomodoro-stats">
              <div class="ps-item">
                <div class="ps-num">{{ state.pomodoro.completed }}</div>
                <div class="ps-label">已完成番茄</div>
              </div>
              <div class="ps-item">
                <div class="ps-num">25:00</div>
                <div class="ps-label">单番茄时长</div>
              </div>
              <div class="ps-item">
                <div class="ps-num">5:00</div>
                <div class="ps-label">休息时长</div>
              </div>
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
        today: null,
        daysLeft: 0,
        streak: 0,
        coinNotice: '',
        showAsk: false,
        askText: '',
        askReply: '',
        form: {
          exam_date: defaultDate(),
          weak_subjects: ['行测'],
          daily_hours: 3,
          level: '有基础',
        },
        // 番茄钟
        pomodoro: {
          seconds: 25 * 60,
          running: false,
          isBreak: false,
          completed: 0,
          minutes: 0,
          timer: null,
        },
        // 智能排课
        slot: {
          morning: { done: false },
          morning2: { done: false },
          afternoon: { done: false },
          afternoon2: { done: false },
          evening: { done: false },
          evening2: { done: false },
        },
        // AI作文批改
        essay: {
          topic: '',
          content: '',
          result: null,
          grading: false,
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
            // 用后端返回的剩余天数（向下取整口径），避免 Math.ceil 多算一天
            state.daysLeft = data.days_left !== undefined ? data.days_left : 0;
            await loadToday();
          } else {
            state.error = data.detail || '生成失败，请重试';
          }
        } catch (e) {
          state.error = '网络异常，请稍后再试';
        } finally {
          state.loading = false;
        }
      }

      async function loadToday() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/plan/today');
          if (res.ok) {
            state.today = await res.json();
            state.error = '';
          }
        } catch (e) { /* 今日面板加载失败不影响主流程 */ }
      }

      async function toggleTask(t) {
        // 标记完成前二次确认，防止假勾选
        if (t.is_completed !== 1) {
          const confirmed = window.confirm(`确认你已经完成「${t.title}」了吗？\n\n💡 小智建议：真实完成学习后再标记哦，这样计划才能越调越准~`);
          if (!confirmed) return;
        }
        try {
          const res = await window.__VTJ_AUTH__.apiFetch(`/api/plan/task/${t.goal_id}/toggle`, { method: 'POST' });
          if (res.ok) {
            t.is_completed = t.is_completed === 1 ? 0 : 1;
            const total = state.plan.tasks.length;
            const done = state.plan.tasks.filter(x => x.is_completed === 1).length;
            state.plan.progress.done = done;
            state.plan.progress.percent = Math.round(done / total * 100);
            state.error = '';
          } else {
            const data = await res.json().catch(() => ({}));
            state.error = (data && data.detail) || '操作失败，请稍后重试';
          }
        } catch (e) {
          state.error = '网络异常，操作未生效';
        }
      }

      async function claimCoin(t) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch(`/api/plan/task/${t.goal_id}/claim`, { method: 'POST' });
          if (res.ok) {
            const data = await res.json();
            t.coin_claimed = 1;
            state.coinNotice = data.message || `领取成功，+${data.coin_reward} 金币`;
            state.error = '';
          } else {
            const data = await res.json().catch(() => ({}));
            state.error = (data && data.detail) || '领取失败，请稍后重试';
          }
        } catch (e) {
          state.error = '网络异常，领取未生效';
        }
      }

      // 番茄钟：格式化时间
      function formatTime(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
      }

      // 番茄钟：切换开始/暂停
      function togglePomodoro() {
        const p = state.pomodoro;
        if (p.running) {
          // 暂停
          clearInterval(p.timer);
          p.running = false;
        } else {
          // 开始
          p.running = true;
          p.timer = setInterval(() => {
            p.seconds--;
            if (!p.isBreak) {
              p.minutes = Math.round((p.minutes * 60 + 1) / 60);
            }
            if (p.seconds <= 0) {
              if (!p.isBreak) {
                // 专注完成，进入休息
                p.completed++;
                p.isBreak = true;
                p.seconds = 5 * 60;
              } else {
                // 休息完成，进入下一个专注
                p.isBreak = false;
                p.seconds = 25 * 60;
              }
            }
          }, 1000);
        }
      }

      // 番茄钟：重置
      function resetPomodoro() {
        const p = state.pomodoro;
        clearInterval(p.timer);
        p.running = false;
        p.isBreak = false;
        p.seconds = 25 * 60;
      }

      // 智能排课：切换任务完成状态
      function toggleSlotTask(slotKey) {
        state.slot[slotKey].done = !state.slot[slotKey].done;
      }

      // 智能排课：计算今日完成进度
      function getScheduleProgress() {
        const slots = Object.values(state.slot);
        const done = slots.filter(s => s.done).length;
        return Math.round((done / slots.length) * 100);
      }

      // AI作文批改（真 LLM：/api/llm/chat 一次性任务，scene=essay；失败回退示例评分）
      function buildEssayPrompt() {
        return [
          '【任务】申论作文批改',
          '作文题目：' + (state.essay.topic.trim() || '（未填写题目）'),
          '作文正文：',
          state.essay.content.trim(),
        ].join('\n');
      }

      function parseAiJson(text) {
        if (!text) return null;
        let s = String(text).trim();
        s = s.replace(/^```(?:json)?/i, '').replace(/```$/, '').trim();
        const start = s.indexOf('{');
        const end = s.lastIndexOf('}');
        if (start >= 0 && end > start) s = s.slice(start, end + 1);
        try {
          return JSON.parse(s);
        } catch (e) {
          return null;
        }
      }

      function normalizeEssayResult(raw) {
        const colors = { '立意': '#4caf50', '结构': '#ff9800', '内容': '#2196f3', '语言': '#9c27b0', '卷面': '#607d8b' };
        const dims = Array.isArray(raw.dimensions) ? raw.dimensions : [];
        const dimensions = dims.map((d) => ({
          name: String(d.name || ''),
          score: Number(d.score) || 0,
          max: Number(d.max) || 0,
          color: colors[String(d.name || '')] || '#607d8b',
        }));
        const total = typeof raw.total === 'number'
          ? raw.total
          : dimensions.reduce((acc, d) => acc + d.score, 0);
        return {
          total: Math.max(0, Math.min(100, Math.round(total))),
          dimensions,
          comment: String(raw.comment || ''),
          suggestions: Array.isArray(raw.suggestions) ? raw.suggestions.map(String) : [],
        };
      }

      // AI 不可用时的兜底示例（保留旧版固定评分，页面不白屏）
      function fallbackEssayResult() {
        return {
          total: 78,
          dimensions: [
            { name: '立意', score: 16, max: 20, color: '#4caf50' },
            { name: '结构', score: 15, max: 20, color: '#ff9800' },
            { name: '内容', score: 24, max: 30, color: '#2196f3' },
            { name: '语言', score: 16, max: 20, color: '#9c27b0' },
            { name: '卷面', score: 7, max: 10, color: '#607d8b' },
          ],
          comment: '（示例评分，非 AI 实时结果）这篇作文立意明确，紧扣新时代公安使命的主题，结合了公安实际工作，有一定的深度。但结构上略显松散，分论点之间的逻辑衔接可以更紧密。内容上论据比较充分，但可以再增加一些具体的案例和数据支撑。语言表达比较流畅，但个别地方可以更精炼。整体来看是一篇中等偏上的作文，继续加油！',
          suggestions: [
            '开头可以更吸引人，用一个生动的案例或名言引入主题',
            '分论点之间增加过渡句，让文章结构更清晰',
            '增加1-2个具体的公安工作案例，让内容更有说服力',
            '结尾可以升华主题，呼应开头，让文章更有感染力',
            '注意段落划分，每段不要太长，200-300字一段比较合适',
          ],
        };
      }

      async function gradeEssay() {
        if (!state.essay.content.trim()) {
          alert('请先输入作文内容！');
          return;
        }
        if (state.essay.grading) return;
        state.essay.grading = true;
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/llm/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: buildEssayPrompt(),
              scene: 'essay',
              persist: false,
            }),
          });
          const data = await res.json();
          const parsed = res.ok && data && data.reply ? parseAiJson(data.reply) : null;
          if (parsed && parsed.total !== undefined && Array.isArray(parsed.dimensions)) {
            state.essay.result = normalizeEssayResult(parsed);
            state.error = '';
          } else {
            state.essay.result = fallbackEssayResult();
            state.error = (data && data.detail) || 'AI 批改暂不可用，已展示示例评分';
          }
        } catch (e) {
          state.essay.result = fallbackEssayResult();
          state.error = '网络异常，已展示示例评分';
        } finally {
          state.essay.grading = false;
        }
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
        state.askReply = '';
        try {
          // 走 /api/plan/adjust：LLM 生成调整 + 落 PlanAdjustment + 应用更新计划摘要
          const res = await window.__VTJ_AUTH__.apiFetch('/api/plan/adjust', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instruction: q }),
          });
          const data = await res.json();
          if (res.ok) {
            const dots = (data.adjustments || []).map((a) => '· ' + a).join('\n');
            state.askReply = '✅ 已应用调整：' + (data.summary || '计划已更新') + (dots ? '\n' + dots : '');
            // 刷新计划摘要（plan_meta 已更新）
            try {
              const r2 = await window.__VTJ_AUTH__.apiFetch('/api/plan/current');
              const d2 = await r2.json();
              if (r2.ok && d2.has_plan !== false) state.plan = d2;
            } catch (e) { /* 刷新失败不阻塞提示 */ }
          } else {
            state.askReply = data.detail || '调整失败，请稍后再试';
          }
        } catch (e) {
          state.askReply = '网络异常';
        }
      }

      function goBack() {
        if (window.history.length > 1) window.history.back();
        else window.location.href = '/#/';
      }

      function scrollToOverview() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }

      function scrollToToday() {
        const el = document.querySelector('.section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      }

      onMounted(async () => {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/plan/current');
          const data = await res.json();
          if (res.ok && data.has_plan) {
            state.plan = data;
            // 剩余天数以后端计算口径为准
            state.daysLeft = data.days_left !== undefined ? data.days_left : 0;
          }
        } catch (e) {}
        loadToday();
        // 连续打卡：拉真实签到数据（不再硬编码假数据）
        try {
          const ck = await window.__VTJ_AUTH__.apiFetch('/api/v1/growth/checkin/status');
          const ckData = await ck.json();
          if (ck.ok && ckData && typeof ckData.continuous_days === 'number') {
            state.streak = ckData.continuous_days;
          }
        } catch (e) {}
        // 桌面通知：请求授权 + 今日任务未完成/周日复盘提醒（模块4/7 v2）
        try {
          const dn = await import('../../src/utils/desktopNotify.ts');
          dn.ensurePermission().then(() => {
            dn.startTodayReminderPolling(async () => {
              const r = await window.__VTJ_AUTH__.apiFetch('/api/plan/today');
              if (!r.ok) return [];
              const d = await r.json();
              return d && d.today ? d.today : (d.items || []);
            });
          });
        } catch (e) {}
      });

      return {
        state, subjects, levels, weekDays, getSubjectStats,
        toggleSubject, generate, toggleTask, claimCoin, reset, askAI, sendAsk, goBack,
        formatTime, togglePomodoro, resetPomodoro,
        toggleSlotTask, getScheduleProgress, gradeEssay,
      };
    },
  });
</script>

<style lang="css" scoped>
  .plan-page { min-height: 100vh; background: #f0f3f8; }

  /* ===== 智能排课 ===== */
  .smart-schedule-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }
  .schedule-timeline {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 16px;
  }
  .time-slot {
    border-radius: 12px;
    padding: 12px 16px;
    border-left: 4px solid;
  }
  .time-slot.morning {
    background: linear-gradient(90deg, #fff8e1, #fff);
    border-left-color: #ff9800;
  }
  .time-slot.afternoon {
    background: linear-gradient(90deg, #e3f2fd, #fff);
    border-left-color: #2196f3;
  }
  .time-slot.evening {
    background: linear-gradient(90deg, #f3e5f5, #fff);
    border-left-color: #9c27b0;
  }
  .time-label {
    font-size: 14px;
    font-weight: 600;
    color: #333;
    margin-bottom: 10px;
  }
  .task-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .task-item {
    display: flex;
    align-items: center;
    gap: 12px;
    background: #fff;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid #f0f0f0;
    transition: all 0.3s;
  }
  .task-item.done {
    opacity: 0.6;
    background: #f5f5f5;
  }
  .task-item.done .task-subject {
    text-decoration: line-through;
  }
  .task-subject {
    font-weight: 600;
    color: #d32f2f;
    min-width: 80px;
  }
  .task-detail {
    flex: 1;
    font-size: 13px;
    color: #666;
  }
  .task-check {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid #ddd;
    background: #fff;
    cursor: pointer;
    font-size: 14px;
    color: #999;
    transition: all 0.3s;
  }
  .task-item.done .task-check {
    background: #4caf50;
    border-color: #4caf50;
    color: #fff;
  }
  .schedule-progress {
    margin-top: 16px;
  }
  .progress-bar {
    height: 8px;
    background: #f0f0f0;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #d32f2f, #ff5722);
    border-radius: 4px;
    transition: width 0.5s ease;
  }
  .progress-text {
    text-align: center;
    font-size: 13px;
    color: #666;
  }

  /* ===== AI作文批改 ===== */
  .essay-grading-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }
  .essay-intro {
    font-size: 14px;
    color: #666;
    margin-bottom: 16px;
  }
  .essay-topic-input,
  .essay-content-input {
    margin-bottom: 16px;
  }
  .essay-topic-input label,
  .essay-content-input label {
    display: block;
    font-size: 14px;
    font-weight: 600;
    color: #333;
    margin-bottom: 8px;
  }
  .essay-topic-input input,
  .essay-content-input textarea {
    width: 100%;
    padding: 12px;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
    resize: vertical;
    box-sizing: border-box;
  }
  .essay-topic-input input:focus,
  .essay-content-input textarea:focus {
    outline: none;
    border-color: #d32f2f;
  }
  .essay-submit-btn {
    width: 100%;
    padding: 14px;
    background: linear-gradient(135deg, #d32f2f, #ff5722);
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
  }
  .essay-submit-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(211, 47, 47, 0.3);
  }
  .essay-result {
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid #f0f0f0;
  }
  .result-score {
    text-align: center;
    margin-bottom: 24px;
  }
  .score-num {
    font-size: 48px;
    font-weight: 700;
    color: #d32f2f;
  }
  .score-num span {
    font-size: 20px;
    font-weight: 400;
  }
  .score-label {
    font-size: 14px;
    color: #666;
  }
  .result-dimensions {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 20px;
  }
  .dim-item {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .dim-name {
    width: 60px;
    font-size: 13px;
    color: #333;
    font-weight: 600;
  }
  .dim-bar {
    flex: 1;
    height: 10px;
    background: #f0f0f0;
    border-radius: 5px;
    overflow: hidden;
  }
  .dim-fill {
    height: 100%;
    border-radius: 5px;
    transition: width 0.5s ease;
  }
  .dim-score {
    width: 60px;
    text-align: right;
    font-size: 13px;
    color: #666;
  }
  .result-comment {
    background: #fff8e1;
    padding: 16px;
    border-radius: 10px;
    margin-bottom: 16px;
  }
  .comment-title {
    font-size: 14px;
    font-weight: 600;
    color: #f57c00;
    margin-bottom: 8px;
  }
  .result-comment p {
    font-size: 14px;
    line-height: 1.8;
    color: #333;
    margin: 0;
  }
  .result-suggest {
    background: #e8f5e9;
    padding: 16px;
    border-radius: 10px;
  }
  .suggest-title {
    font-size: 14px;
    font-weight: 600;
    color: #388e3c;
    margin-bottom: 8px;
  }
  .result-suggest ul {
    margin: 0;
    padding-left: 20px;
  }
  .result-suggest li {
    font-size: 14px;
    line-height: 1.8;
    color: #333;
  }

  /* ===== 番茄钟专注 ===== */
  .pomodoro-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }
  .pomodoro-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  .pomodoro-today {
    font-size: 12px;
    color: #666;
    background: #f0f2f5;
    padding: 4px 12px;
    border-radius: 12px;
  }
  .pomodoro-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
  .pomodoro-display {
    width: 160px;
    height: 160px;
    border-radius: 50%;
    background: linear-gradient(135deg, #f0f2f5, #e8ecf2);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
  }
  .pomodoro-display.running {
    background: linear-gradient(135deg, #c41e3a, #ff6b6b);
    color: #fff;
    box-shadow: 0 4px 30px rgba(196, 30, 58, 0.4);
  }
  .pomodoro-display.break {
    background: linear-gradient(135deg, #10b981, #34d399);
    color: #fff;
    box-shadow: 0 4px 30px rgba(16, 185, 129, 0.4);
  }
  .pomodoro-time {
    font-size: 32px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .pomodoro-mode {
    font-size: 12px;
    opacity: 0.9;
    margin-top: 4px;
  }
  .pomodoro-controls {
    display: flex;
    gap: 12px;
  }
  .pomodoro-btn {
    padding: 10px 24px;
    border: none;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    background: #f0f2f5;
    color: #333;
  }
  .pomodoro-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }
  .pomodoro-btn.primary {
    background: linear-gradient(135deg, #c41e3a, #ff6b6b);
    color: #fff;
  }
  .pomodoro-stats {
    display: flex;
    gap: 24px;
  }
  .ps-item {
    text-align: center;
  }
  .ps-num {
    font-size: 18px;
    font-weight: 700;
    color: #333;
  }
  .ps-label {
    font-size: 11px;
    color: #999;
    margin-top: 2px;
  }

  /* ===== 3D学习日历 ===== */
  .calendar-3d-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }
  .calendar-3d-wrap {
    perspective: 1000px;
    margin-top: 16px;
  }
  .calendar-3d {
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 8px;
    transform: rotateX(10deg);
    transform-style: preserve-3d;
  }
  .calendar-day {
    aspect-ratio: 1;
    background: #f0f2f5;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: #666;
    transition: all 0.3s ease;
    cursor: pointer;
  }
  .calendar-day:hover {
    transform: translateY(-4px) rotateX(10deg);
    box-shadow: 0 8px 16px rgba(0,0,0,0.1);
  }
  .calendar-day.done {
    background: linear-gradient(135deg, #10b981, #34d399);
    color: #fff;
  }
  .calendar-day.today {
    background: linear-gradient(135deg, #c41e3a, #ff6b6b);
    color: #fff;
    box-shadow: 0 4px 12px rgba(196, 30, 58, 0.4);
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { box-shadow: 0 4px 12px rgba(196, 30, 58, 0.4); }
    50% { box-shadow: 0 4px 20px rgba(196, 30, 58, 0.8); }
  }

  /* ===== AI错题本 ===== */
  .wrongbook-card {
    background: linear-gradient(135deg, #fff 0%, #fff5f6 100%);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(196, 30, 58, 0.1);
    border: 1px solid #ffe0e6;
  }
  .wrongbook-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  .wrongbook-badge {
    background: linear-gradient(135deg, #c41e3a, #ff6b6b);
    color: #fff;
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 12px;
    font-weight: 600;
  }
  .wrongbook-body {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .wrongbook-stats {
    display: flex;
    gap: 12px;
  }
  .wb-stat {
    flex: 1;
    text-align: center;
    padding: 12px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  }
  .wb-num {
    font-size: 24px;
    font-weight: 700;
    color: #c41e3a;
  }
  .wb-label {
    font-size: 12px;
    color: #666;
    margin-top: 4px;
  }
  .wrongbook-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    background: #fffbeb;
    border-radius: 12px;
    border-left: 4px solid #f59e0b;
  }
  .wb-tip-icon {
    font-size: 18px;
  }
  .wrongbook-tip span:last-child {
    font-size: 13px;
    color: #92400e;
  }
  .wrongbook-btn {
    background: linear-gradient(135deg, #c41e3a, #ff6b6b);
    color: #fff;
    border: none;
    border-radius: 12px;
    padding: 12px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .wrongbook-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(196, 30, 58, 0.3);
  }

  /* ===== 自适应学习 ===== */
  .adaptive-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
    color: #fff;
  }
  .adaptive-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  .adaptive-head .dist-title {
    color: #fff;
  }
  .adaptive-badge {
    background: rgba(255,255,255,0.2);
    color: #fff;
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 12px;
    font-weight: 600;
  }
  .adaptive-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .adaptive-tip {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(255,255,255,0.15);
    border-radius: 12px;
    backdrop-filter: blur(10px);
  }
  .adaptive-tip-icon {
    font-size: 24px;
  }
  .adaptive-tip-text {
    flex: 1;
  }
  .adaptive-tip-title {
    font-size: 14px;
    font-weight: 600;
  }
  .adaptive-tip-desc {
    font-size: 12px;
    opacity: 0.8;
    margin-top: 2px;
  }
  .adaptive-btn {
    background: #fff;
    color: #667eea;
    border: none;
    border-radius: 12px;
    padding: 12px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 4px;
  }
  .adaptive-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.2);
  }

  /* ===== 遗忘曲线复习 ===== */
  .review-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }
  .review-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  .review-badge {
    background: linear-gradient(135deg, #ff6b35, #ff8e53);
    color: #fff;
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 12px;
    font-weight: 600;
  }
  .review-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .review-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #f8f9fc;
    border-radius: 12px;
    transition: all 0.2s;
  }
  .review-item:hover {
    background: #f0f2f5;
  }
  .review-info {
    flex: 1;
  }
  .review-topic {
    font-size: 14px;
    font-weight: 600;
    color: #333;
  }
  .review-desc {
    font-size: 12px;
    color: #666;
    margin-top: 2px;
  }
  .review-btn {
    background: linear-gradient(135deg, #c41e3a, #ff6b6b);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.2s;
  }
  .review-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(196, 30, 58, 0.3);
  }

  /* ===== 成就系统 ===== */
  .achievement-card {
    background: linear-gradient(135deg, #fff 0%, #f8f9ff 100%);
    border-radius: 16px;
    padding: 16px 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .ach-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .ach-avatar {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea, #764ba2);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  }
  .ach-info {
    flex: 1;
  }
  .ach-level {
    font-size: 16px;
    font-weight: 700;
    color: #333;
  }
  .ach-exp {
    font-size: 12px;
    color: #666;
    margin-top: 2px;
  }
  .ach-exp-bar {
    width: 150px;
    height: 6px;
    background: #eee;
    border-radius: 3px;
    margin-top: 6px;
    overflow: hidden;
  }
  .ach-exp-fill {
    height: 100%;
    background: linear-gradient(90deg, #667eea, #764ba2);
    border-radius: 3px;
    transition: width 0.5s ease;
  }
  .ach-right {
    display: flex;
    gap: 12px;
  }
  .badge {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: #f0f2f5;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .badge:hover {
    transform: scale(1.1);
  }
  .badge.locked {
    opacity: 0.5;
    filter: grayscale(100%);
  }

  /* ===== 能力雷达图 ===== */
  .radar-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }
  .radar-wrap {
    position: relative;
    width: 200px;
    height: 200px;
    margin: 0 auto;
  }
  .radar-svg {
    width: 100%;
    height: 100%;
  }
  .radar-labels {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .radar-label {
    position: absolute;
    font-size: 10px;
    color: #666;
    white-space: nowrap;
  }
  .radar-label.top { top: -10px; left: 50%; transform: translateX(-50%); }
  .radar-label.right-top { top: 20px; right: -20px; }
  .radar-label.right-bottom { bottom: 20px; right: -20px; }
  .radar-label.bottom { bottom: -10px; left: 50%; transform: translateX(-50%); }
  .radar-label.left-bottom { bottom: 20px; left: -20px; }
  .radar-label.left-top { top: 20px; left: -20px; }

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
  .view-tabs { display: flex; background: #fff; border-radius: 12px; padding: 4px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(15,30,61,0.06); position: sticky; top: 10px; z-index: 100; }
  .view-tab { flex: 1; text-align: center; padding: 10px; border-radius: 10px; font-size: 14px; font-weight: 500; color: #6b7280; cursor: pointer; transition: all .2s; }
  .view-tab:hover { background: #f3f4f6; color: #2563eb; }
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

  .adjust-hint { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-radius: 12px; margin-bottom: 12px; font-size: 13px; }
  .adjust-hint.increase { background: #f0fdf4; color: #166534; }
  .adjust-hint.decrease { background: #fffbeb; color: #92400e; }
  .adjust-btn { padding: 6px 14px; border-radius: 8px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; margin-left: 12px; flex-shrink: 0; }
  .adjust-hint.increase .adjust-btn { background: #16a34a; color: #fff; }
  .adjust-hint.decrease .adjust-btn { background: #d97706; color: #fff; }

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
    display: flex; align-items: center; gap: 8px; padding: 12px;
    border-bottom: 1px solid #eef2f6;
  }
  .task-item:last-child { border-bottom: none; }
  .task-main { display: flex; align-items: center; gap: 10px; flex: 1; cursor: pointer; min-width: 0; }
  .task-item.done .task-title { text-decoration: line-through; color: #aab4c0; }
  .checkbox {
    width: 20px; height: 20px; border: 2px solid #c8d0da; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: #fff; background: #fff; flex-shrink: 0;
    transition: all 0.2s;
  }
  .task-item.done .checkbox { background: #c8161e; border-color: #c8161e; }
  .task-title { font-size: 14px; color: #2c3e50; flex: 1; }
  .coin-badge {
    font-size: 12px; color: #b8860b; background: #fff8e6; border-radius: 20px;
    padding: 2px 8px; white-space: nowrap; flex-shrink: 0;
  }
  .coin-badge.dim { color: #aab4c0; background: #f1f5f9; }
  .claim-btn {
    padding: 4px 14px; border-radius: 20px; font-size: 12px; font-weight: 600;
    border: none; background: #16a34a; color: #fff; cursor: pointer; flex-shrink: 0;
    transition: all 0.2s;
  }
  .claim-btn:hover { background: #15803d; }
  .claimed-tag { font-size: 12px; color: #aab4c0; flex-shrink: 0; }
  .coin-notice {
    margin-bottom: 8px; padding: 8px 12px; border-radius: 8px;
    background: #f0fdf4; color: #16a34a; font-size: 12px;
  }
  .task-empty { padding: 16px; text-align: center; font-size: 13px; color: #aab4c0; }

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
