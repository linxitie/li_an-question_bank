<!-- 学习计划智能推荐 - 模块4 全面改造版 -->
<template>
  <div class="plan-page">
    <!-- 顶部导航：与首页同一套导航，保证各页观感一致 -->
    <NavBar />

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
          </div>
        </div>
      </div>
    </div>

    <!-- 画像问卷内嵌（模块7）：放在正文第一步，答完自动回填表单 -->
    <div v-if="state.showQuiz" class="page-pad">
      <ProfileQuizInline @done="onQuizDone" @skip="skipQuiz" />
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
          📌 今日排课
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

        <!-- 智能排课（数据来自 /api/plan/today.schedule：按人按天生成，任务变化即重算） -->
        <div class="smart-schedule-card" v-if="state.schedule && state.schedule.slots && state.schedule.slots.length">
          <div class="dist-title">⏰ 智能排课 · {{ state.schedule.date }}</div>
          <div class="schedule-timeline">
            <div class="time-slot" v-for="p in state.schedule.slots" :key="p.period">
              <div class="time-label">{{ p.label }} · {{ p.planned_minutes }} 分钟</div>
              <div class="task-list">
                <div class="task-item" v-for="(it, idx) in p.items" :key="p.period + '-' + idx" :class="{ done: it.done }">
                  <span class="task-subject">{{ it.subject }}</span>
                  <span class="task-detail">{{ it.title }} · {{ it.minutes }} 分钟</span>
                  <button v-if="it.kind === 'task' && it.goal_id" class="task-check" @click="toggleScheduleItem(it)">
                    {{ it.done ? '✓' : '○' }}
                  </button>
                  <span v-else class="task-check" title="错题复习项到错题集完成">·</span>
                </div>
              </div>
            </div>
          </div>
          <div class="schedule-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: schedulePercent + '%' }"></div>
            </div>
            <div class="progress-text">
              已安排 {{ state.schedule.planned_minutes }} / {{ state.schedule.budget_minutes }} 分钟 · 完成 {{ schedulePercent }}%
            </div>
          </div>
        </div>
        <div class="smart-schedule-card" v-else>
          <div class="dist-title">⏰ 智能排课</div>
          <div class="schedule-empty">
            <p>{{ (state.schedule && state.schedule.hint) || '今天还没有排任务，先在上方生成或调整计划' }}</p>
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

        <!-- 能力画像（与「我的」同源：/api/plan/current.capability） -->
        <ProfileRadar class="plan-radar" />

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

        <!-- ⑤ 调整已实际应用：本次变更 + 撤销 + 最近调整历史 -->
        <div v-if="state.adjustResult && state.adjustResult.applied_count" class="adjust-applied">
          <p class="adjust-applied__title">
            本次已实际调整 {{ state.adjustResult.applied_count }} 项
            <span v-if="state.adjustResult.rejected && state.adjustResult.rejected.length">
              （{{ state.adjustResult.rejected.length }} 项被拒）
            </span>
          </p>
          <ul>
            <li v-for="(c, i) in state.adjustResult.applied" :key="i">
              {{ c.op === 'add' ? '新增' : c.op === 'move' ? '改期' : c.op === 'modify' ? '改时长' : '删除' }}
              {{ c.title }}<template v-if="c.date"> → {{ c.date }}</template>
              <template v-if="c.minutes_to"> · {{ c.minutes_to }} 分钟</template>
            </li>
          </ul>
          <button class="ask-send" @click="undoAdjust">撤销这次调整</button>
        </div>
        <div v-if="state.adjustHistory && state.adjustHistory.length" class="adjust-history">
          <p class="adjust-applied__title">最近调整</p>
          <p v-for="h in state.adjustHistory" :key="h.adjust_id">
            {{ (h.created_at || '').slice(0, 16) }} · {{ h.reason }} · {{ h.change_count }} 项
            <span v-if="!h.applied">（已撤销）</span>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, onMounted, computed, nextTick } from 'vue';
  import ProfileQuizInline from '@/components/plan/ProfileQuizInline.vue';
  import ProfileRadar from '@/components/profile/ProfileRadar.vue';
  import NavBar from './navbar.vue';
  import { bindTaskFeedback } from '@/composables/useTaskFeedback';

  export default defineComponent({
    name: 'StudyPlan',
    components: { ProfileQuizInline, ProfileRadar, NavBar },
    setup() {
      const state = reactive({
        loading: false,
        error: '',
        plan: null,
        showQuiz: false,      // 画像问卷内嵌在学习计划里（未完成画像时展开）
        today: null,
        schedule: null,       // ① 今日排课（/api/plan/today.schedule）
        adjustResult: null,   // ⑤ 最近一次 AI 调整的落地结果
        adjustHistory: [],    // ⑤ 最近调整记录（/api/plan/current.recent_adjustments）
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
        // 学习报告（周/月，前端模拟汇总）
        report: {
          period: 'week',
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
            // ① 今日排课（后端按任务+画像+待复习错题生成，任务变化即重算）
            state.schedule = (state.today && state.today.schedule) || null;
            state.error = '';
            // 2026-11-15：已完成但金币没到账（历史数据/上次请求中断）时兜底补发
            await settlePendingGoalCoins();
          }
        } catch (e) { /* 今日面板加载失败不影响主流程 */ }
      }

      /**
       * 计划任务金币兜底（2026-11-15，与 badge_task 的 /api/tasks/auto-claim 同一通道）。
       * 只在「已完成且未到账」时调一次，接口本身幂等，失败不打扰用户。
       */
      async function settlePendingGoalCoins() {
        const tasks = (state.today && state.today.tasks) || [];
        const pending = tasks.filter(
          (t) => t.is_completed === 1 && t.coin_claimed === 0 && (t.coin_reward || 0) > 0
        );
        if (!pending.length) return;
        try {
          const r = await window.__VTJ_AUTH__.apiFetch('/api/tasks/auto-claim', { method: 'POST' });
          if (!r.ok) return;
          const data = await r.json().catch(() => ({}));
          const mine = (data.granted || []).filter((g) => g && g.source === 'study_goal');
          if (!mine.length) return;
          const coins = mine.reduce((sum, g) => sum + (g.reward_coins || 0), 0);
          if (coins > 0) state.coinNotice = `已自动到账 ${coins} 金币`;
          const again = await window.__VTJ_AUTH__.apiFetch('/api/plan/today');
          if (again.ok) state.today = await again.json();
        } catch (e) { /* 兜底失败不影响今日面板 */ }
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
            const data = await res.json().catch(() => ({}));
            t.is_completed = typeof data.is_completed === 'number'
              ? data.is_completed
              : (t.is_completed === 1 ? 0 : 1);
            const total = state.plan.tasks.length;
            const done = state.plan.tasks.filter(x => x.is_completed === 1).length;
            state.plan.progress.done = done;
            state.plan.progress.percent = Math.round(done / total * 100);
            // 2026-11-15：完成即自动到账，不再需要额外点「领取」
            if (data && data.auto_claimed_coins > 0) {
              t.coin_claimed = 1;
              state.coinNotice = `任务完成，自动到账 +${data.auto_claimed_coins} 金币`;
            }
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

      // ===== 学习报告（周/月，前端模拟汇总，后续可接真实统计接口） =====
      const reportData = {
        week: {
          minutes: 326,
          questions: 148,
          accuracy: 78,
          weak: [
            { name: '资料分析', rate: 62 },
            { name: '数量关系', rate: 58 },
            { name: '图形推理', rate: 55 },
          ],
          trend: [65, 70, 74, 72, 78, 81, 84],
          labels: ['一', '二', '三', '四', '五', '六', '日'],
          comment: '本周整体状态稳步上升，正确率连续 3 天走高。资料分析仍是短板，建议每天加练 2 篇增长率/比重题。',
        },
        month: {
          minutes: 1280,
          questions: 562,
          accuracy: 75,
          weak: [
            { name: '数量关系', rate: 55 },
            { name: '资料分析', rate: 60 },
            { name: '申论大作文', rate: 63 },
          ],
          trend: [68, 73, 76, 79],
          labels: ['第1周', '第2周', '第3周', '第4周'],
          comment: '本月累计学习时长充足，正确率环比提升 7 个百分点。数量关系基础薄弱，建议优先攻克工程、行程等高频题型。',
        },
      };

      const rpt = computed(() => {
        const base = reportData[state.report.period] || reportData.week;
        return { ...base, streak: state.streak };
      });

      function setReportPeriod(p) {
        state.report.period = p;
      }

      function printReport() {
        window.print();
      }

      function reset() {
        state.plan = null;
        state.error = '';
        state.askReply = '';
      }

      function askAI() {
        // 2026-11-23：原来只 toggle，输入框在页面底部且不滚动/不聚焦，用户以为按钮没反应
        const willOpen = !state.showAsk;
        state.showAsk = willOpen;
        if (!willOpen) return;
        state.askReply = '';
        nextTick(() => {
          const box = document.querySelector('.ask-box');
          if (!box) return;
          box.scrollIntoView({ behavior: 'smooth', block: 'center' });
          const input = box.querySelector('input');
          if (input && input.focus) input.focus();
        });
      }

      /** ① 排课项勾选：调任务 toggle（后端会重算排课），再刷新今日面板与计划 */
      async function toggleScheduleItem(item) {
        if (!item || !item.goal_id) return;
        try {
          const res = await window.__VTJ_AUTH__.apiFetch(`/api/plan/task/${item.goal_id}/toggle`, { method: 'POST' });
          if (!res.ok) return;
          await loadToday();
          const cur = await window.__VTJ_AUTH__.apiFetch('/api/plan/current');
          if (cur.ok) {
            const d = await cur.json();
            if (d && d.has_plan !== false) {
              state.plan = d;
              state.adjustHistory = d.recent_adjustments || [];
            }
          }
        } catch (e) { /* 单次勾选失败不影响其它区块 */ }
      }

      /** ① 排课完成度：按"已完成分钟 / 已安排分钟"算（替代原写死的 getScheduleProgress） */
      const schedulePercent = computed(() => {
        const s = state.schedule;
        if (!s || !s.slots) return 0;
        let total = 0, done = 0;
        s.slots.forEach((p) => (p.items || []).forEach((it) => {
          total += it.minutes || 0;
          if (it.done) done += it.minutes || 0;
        }));
        return total ? Math.round((done / total) * 100) : 0;
      });

      /** ⑤ 撤销最近一次 AI 调整（同端点 body undo=true） */
      async function undoAdjust() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/plan/adjust', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instruction: '', undo: true }),
          });
          const data = await res.json().catch(() => ({}));
          if (res.ok) {
            state.askReply = data.message || '已撤销上一次调整';
            state.adjustResult = null;
            const cur = await window.__VTJ_AUTH__.apiFetch('/api/plan/current');
            if (cur.ok) {
              const d = await cur.json();
              if (d && d.has_plan !== false) {
                state.plan = d;
                state.adjustHistory = d.recent_adjustments || [];
              }
            }
            await loadToday();
          } else {
            state.askReply = data.detail || '撤销失败';
          }
        } catch (e) { state.askReply = '网络异常，撤销未生效'; }
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
            state.adjustResult = data;
            const applied = Array.isArray(data.applied) ? data.applied : [];
            const lines = applied.map((c) => {
              const verb = c.op === 'add' ? '新增' : c.op === 'move' ? '改期' : c.op === 'modify' ? '改时长' : '删除';
              return '· ' + verb + ' ' + (c.title || '') + (c.date ? ' → ' + c.date : '') + (c.minutes_to ? ' · ' + c.minutes_to + ' 分钟' : '');
            });
            state.askReply = applied.length
              ? '✅ 已实际调整 ' + applied.length + ' 项：' + (data.summary || '计划已更新') + '\n' + lines.join('\n')
              : (data.message || 'AI 只给了建议，未改动任务');
            // 刷新计划摘要（plan_meta 已更新）与调整历史
            try {
              const r2 = await window.__VTJ_AUTH__.apiFetch('/api/plan/current');
              const d2 = await r2.json();
              if (r2.ok && d2.has_plan !== false) {
                state.plan = d2;
                state.adjustHistory = d2.recent_adjustments || [];
              }
              await loadToday();
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
        // 2026-11-23：原锚点 .section（今日任务卡）已按需求删除，改为滚动到"智能排课"卡
        const el = document.querySelector('.smart-schedule-card') || document.querySelector('.plan-radar');
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

      onMounted(async () => {
        // 任务勾选反馈（4-5）：音效 + 卡片弹动，模板零改动
        bindTaskFeedback();
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/plan/current');
          const data = await res.json();
          if (res.ok && data.has_plan) {
            state.plan = data;
            // 剩余天数以后端计算口径为准
            state.daysLeft = data.days_left !== undefined ? data.days_left : 0;
            // ⑤ 最近调整历史（退出重进也能看到"上次调整了什么"）
            state.adjustHistory = data.recent_adjustments || [];
          }
        } catch (e) {}
        loadToday();
        // 画像内嵌：未完成画像就先在本页答完，再生成方案
        try {
          const pr = await window.__VTJ_AUTH__.apiFetch('/api/profile');
          const pd = await pr.json();
          // /api/profile 无画像时只返回 { has_profile: false }，有画像才带 profile_status
          const has = pr.ok && pd && pd.has_profile !== false;
          const status = pd ? pd.profile_status : undefined;
          const done = has && (status === undefined || status === null ? true : Number(status) === 1);
          state.showQuiz = !done;
        } catch (e) { state.showQuiz = false }
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

      /** 画像答完：把答案映射到生成表单，减少重复填写 */
      function onQuizDone(answers) {
        state.showQuiz = false;
        if (!answers) return;
        const map = { '行测': '行测', '申论': '申论', '公安': '公专' };
        const weak = (answers.subject_weaknesses || [])
          .map((s) => {
            const key = String(s).slice(0, 2);
            return map[key] || null;
          })
          .filter(Boolean);
        if (weak.length) state.form.weak_subjects = Array.from(new Set(weak));
        if (answers.daily_hours) state.form.daily_hours = Number(answers.daily_hours);
        if (answers.self_level) state.form.level = String(answers.self_level);
        if (answers.exam_date) state.form.exam_date = answers.exam_date;
      }

      function skipQuiz() {
        state.showQuiz = false;
      }

      return {
        state, subjects, levels, weekDays, getSubjectStats,
        onQuizDone, skipQuiz,
        toggleSubject, generate, toggleTask, claimCoin, reset, askAI, sendAsk, goBack,
        formatTime, togglePomodoro, resetPomodoro,
        toggleSlotTask, getScheduleProgress, gradeEssay,
        toggleScheduleItem, schedulePercent, undoAdjust,
        slot: state.slot, essay: state.essay, scrollToOverview, scrollToToday,
        rpt, setReportPeriod, printReport,
      };
    },
  });
</script>

<style lang="css" scoped>
  .plan-page { min-height: 100vh; background: #f0f3f8; }
  .page-pad { padding: 16px 20px 0; }

  /* ===== 学习报告 ===== */
  .report-card {
    background: #fff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  }
  .report-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 16px;
  }
  .report-tabs { display: flex; gap: 6px; background: #f2f4f8; border-radius: 10px; padding: 3px; }
  .report-tab {
    padding: 5px 14px; border-radius: 8px; font-size: 13px; color: #666; cursor: pointer;
  }
  .report-tab.active {
    background: linear-gradient(135deg, #c8161e, #ef4444);
    color: #fff; font-weight: 600;
  }
  .report-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 18px;
  }
  .report-item {
    background: #f8f9fc; border-radius: 12px; padding: 12px 8px; text-align: center;
  }
  .report-num { font-size: 18px; font-weight: 700; color: #c8161e; }
  .report-label { font-size: 11px; color: #888; margin-top: 4px; }
  .report-trend { margin-bottom: 18px; }
  .report-trend-title { font-size: 13px; font-weight: 600; color: #333; margin-bottom: 10px; }
  .report-bars { display: flex; align-items: flex-end; gap: 10px; height: 90px; }
  .report-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; }
  .report-bar {
    width: 100%; max-width: 26px; border-radius: 6px 6px 0 0;
    background: linear-gradient(180deg, #ef4444, #c8161e);
    min-height: 6px;
  }
  .report-bar-label { font-size: 10px; color: #888; }
  .report-weak { margin-bottom: 16px; }
  .report-weak-title { font-size: 13px; font-weight: 600; color: #333; margin-bottom: 10px; }
  .report-weak-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .report-weak-name { width: 72px; font-size: 12px; color: #555; }
  .report-weak-bar { flex: 1; height: 10px; background: #f0f2f6; border-radius: 6px; overflow: hidden; }
  .report-weak-fill { height: 100%; border-radius: 6px; background: linear-gradient(90deg, #f59e0b, #ef4444); }
  .report-weak-rate { width: 40px; text-align: right; font-size: 12px; color: #666; }
  .report-comment {
    background: #fff5f5; border-left: 3px solid #c8161e; border-radius: 8px;
    padding: 10px 12px; font-size: 12px; color: #555; line-height: 1.6; margin-bottom: 14px;
  }
  .report-print-btn {
    width: 100%; background: linear-gradient(135deg, #c8161e, #ef4444);
    color: #fff; border: none; border-radius: 12px; padding: 12px;
    font-size: 14px; font-weight: 600; cursor: pointer;
  }

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

  /* ⑤ 调整落地结果 / 历史 / ① 排课空态 / ④ 雷达容器 */
  .adjust-applied {
    margin-top: 10px; padding: 12px; border-radius: 10px;
    background: #f0fdf4; border: 1px solid #bbf7d0; font-size: 13px; color: #14532d;
  }
  .adjust-applied__title { margin: 0 0 6px; font-weight: 700; }
  .adjust-applied ul { margin: 0 0 8px; padding-left: 18px; line-height: 1.7; }
  .adjust-history {
    margin-top: 10px; padding: 10px 12px; border-radius: 10px;
    background: #f8fafc; border: 1px dashed #dfe5ef; font-size: 12px; color: #4b5563;
  }
  .adjust-history p { margin: 2px 0; }
  .schedule-empty {
    padding: 14px 0 4px; text-align: center; font-size: 12.5px; color: #9ca3af;
  }
  .plan-radar { display: block; margin-bottom: 16px; }

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

/* ===== 与首页视觉统一（2026-11-15 团队要求）
   首页令牌：底色 linear-gradient(180deg,#f8f9fc,#f1f3f8)、主容器 1400px/24px 32px、
   深蓝标题 #1a2b5f、强调红 #c41e3a、次文字 #8a8faa、卡片圆角 12px + 轻阴影 ===== */
.plan-page {
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.hero { background: #ffffff; border-bottom: 1px solid #e8ecf4; box-shadow: 0 1px 4px rgba(17, 24, 39, 0.04); }
.hero-bg { display: none; }
.hero-title { color: #1a2b5f; font-weight: 700; }
.hero-sub { color: #8a8faa; }
.hero-badge { background: rgba(196, 30, 58, 0.1); color: #c41e3a; }
/* 内容宽度与首页一致：首页主容器 1400px / 24px 32px */
.plan-main, .page-pad { max-width: 1400px; margin: 0 auto; padding-left: 32px; padding-right: 32px; }
.plan-body { max-width: 1400px; margin: 0 auto; padding: 24px 32px 48px; }
.hero-content { max-width: 1400px; margin: 0 auto; padding: 18px 32px; }
/* hero 与首页卡片同款：不再是全宽色带，而是内容区里的一张白卡 */
.hero { margin: 0 auto; max-width: 1400px; border: 1px solid #eef1f7; border-radius: 12px; box-shadow: 0 1px 4px rgba(17, 24, 39, 0.06); }
.page-pad { padding-top: 28px; }
.card, .panel, .section { border-radius: 12px; background: #fff; box-shadow: 0 1px 4px rgba(17, 24, 39, 0.06); border: 1px solid #eef1f7; }
.section-title { color: #1a2b5f; font-weight: 700; }
.stat-num, .wb-num, .report-num { color: #1a2b5f; }
.stat-label, .report-label, .time-label { color: #8a8faa; }
.action-btn:not(.ghost), .btn-primary, .primary-btn { background: #c41e3a; border-color: #c41e3a; }
.action-btn:not(.ghost):hover, .btn-primary:hover, .primary-btn:hover { background: #a8172f; }
.task-item { border-radius: 10px; background: #fff; border: 1px solid #eef1f7; box-shadow: none; }
.task-item:hover { border-color: #dfe5f2; }
@media (max-width: 900px) { .plan-main, .page-pad { padding-left: 16px; padding-right: 16px; } }
</style>
