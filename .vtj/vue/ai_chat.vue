<!-- 联考小智 - AI 聊天页 -->
<template>
  <div class="ai-layout" :class="{ drawer_open: drawerOpen }">
    <!-- 左侧历史会话栏 -->
    <aside class="history-panel">
      <div class="history-head">
        <span class="history-title">历史对话</span>
        <button class="new-btn" @click="newChat">
          <XIcon :icon="Plus" :size="14"></XIcon>
          <span>新对话</span>
        </button>
      </div>
      <div class="history-list">
        <div
          v-for="s in sessions"
          :key="s.session_id"
          class="history-item"
          :class="{ active: s.session_id === state.sessionId }"
          @click="openSession(s)">
          <div class="hi-main">
            <div class="hi-title">{{ s.title || '新会话' }}</div>
            <div class="hi-meta">
              {{ sceneLabel(s.scene) }} · {{ fmtTime(s.update_time) }}
            </div>
          </div>
          <div class="hi-del" @click.stop="removeSession(s)">×</div>
        </div>
        <div v-if="sessions.length === 0" class="history-empty">
          还没有历史对话
        </div>
      </div>
    </aside>
    <div v-if="drawerOpen" class="mask" @click="drawerOpen = false"></div>

    <!-- 右侧聊天主区 -->
    <div class="ai-chat-page">
      <!-- 顶部藏蓝横幅 -->
      <div class="chat-header">
        <div class="header-glow"></div>
        <div class="header-row">
          <button class="back-btn" @click="goBack" title="返回">‹</button>
          <button class="hamburger" @click="drawerOpen = !drawerOpen">
            <XIcon :icon="Menu" :size="18" color="#fff"></XIcon>
          </button>
          <div class="ai-avatar">智</div>
          <div class="header-meta">
            <div class="header-title-row">
              <span class="header-title">联考小智</span>
              <span class="online-dot"><i></i>在线</span>
              <button class="kb-entry" @click="toggleDashboard" title="学习数据面板">📊 数据</button>
              <a class="kb-entry" href="/#/memories" title="小智对你的了解"
                >👤 我的画像</a
              >
            </div>
            <div class="header-sub">你的公安联考专属备考伙伴</div>
          </div>
        </div>
        <div class="mode-tabs">
          <div
            class="mode-tab"
            :class="{ active: !state.workMode }"
            @click="switchMode(false)">
            💬 对话
          </div>
          <div
            class="mode-tab"
            :class="{ active: state.workMode }"
            @click="switchMode(true)">
            🧰 工作台
          </div>
        </div>
        <div v-if="!state.workMode" class="scene-tabs">
          <div
            v-for="s in sceneOptions"
            :key="s.value"
            class="scene-tab"
            :class="{ active: state.scene === s.value }"
            @click="switchScene(s.value)">
            <XIcon :icon="s.icon" :size="14"></XIcon>
            <span>{{ s.label }}</span>
          </div>
        </div>
        <div v-if="state.agentName" class="agent-bar">
          <span class="agent-dot"></span>
          <span class="agent-label">当前顾问：{{ state.agentName }}</span>
        </div>
      </div>

      <!-- 学习仪表盘（右侧浮动） -->
      <div v-if="state.showDashboard" class="dashboard-panel">
        <div class="dash-head">
          <span>📊 学习数据</span>
          <button @click="toggleDashboard">×</button>
        </div>
        <div class="dash-body">
          <div class="dash-card">
            <div class="dash-num">12.5h</div>
            <div class="dash-label">本周学习时长</div>
          </div>
          <div class="dash-card">
            <div class="dash-num">78%</div>
            <div class="dash-label">平均正确率</div>
          </div>
          <div class="dash-section">
            <div class="dash-section-title">薄弱科目</div>
            <div class="dash-bar">
              <span class="dash-bar-label">资料分析</span>
              <div class="dash-bar-track"><div class="dash-bar-fill" style="width: 45%"></div></div>
              <span class="dash-bar-pct">45%</span>
            </div>
            <div class="dash-bar">
              <span class="dash-bar-label">数量关系</span>
              <div class="dash-bar-track"><div class="dash-bar-fill" style="width: 38%"></div></div>
              <span class="dash-bar-pct">38%</span>
            </div>
            <div class="dash-bar">
              <span class="dash-bar-label">申论</span>
              <div class="dash-bar-track"><div class="dash-bar-fill" style="width: 52%"></div></div>
              <span class="dash-bar-pct">52%</span>
            </div>
          </div>
          <div class="dash-section">
            <div class="dash-section-title">连续打卡</div>
            <div class="dash-streak">🔥 7天</div>
          </div>
        </div>
      </div>

      <!-- 消息流 -->
      <div class="message-list" ref="messageList">
        <!-- 工作台模式：任务清单 + 表单 + 结果 -->
        <div v-if="state.workMode" class="work-panel">
          <div class="work-head">
            <div class="work-title">工作台 · 结构化备考任务</div>
            <div class="work-sub">点选任务 → 填参数 → 生成可直接用的结果</div>
          </div>
          <div class="work-tasks">
            <div
              v-for="t in state.workTasks"
              :key="t.task_id"
              class="work-task"
              :class="{
                open: state.activeTask && state.activeTask.task_id === t.task_id
              }"
              @click="selectTask(t)">
              <div class="wt-row">
                <span class="wt-title">{{ t.title }}</span>
                <span class="wt-agent">{{ agentLabel(t.agent) }}</span>
              </div>
              <div class="wt-desc">{{ t.desc }}</div>
              <div
                v-if="
                  state.activeTask && state.activeTask.task_id === t.task_id
                "
                class="wt-form"
                @click.stop>
                <div v-for="f in t.fields" :key="f.key" class="wf-row">
                  <label class="wf-label"
                    >{{ f.label }}{{ f.required ? ' *' : '' }}</label
                  >
                  <select
                    v-if="f.type === 'select'"
                    v-model="state.workParams[f.key]"
                    class="wf-input">
                    <option v-for="o in f.options" :key="o" :value="o">
                      {{ o }}
                    </option>
                  </select>
                  <input
                    v-else
                    v-model="state.workParams[f.key]"
                    class="wf-input"
                    :placeholder="f.placeholder || '选填'" />
                </div>
                <button
                  class="wf-run"
                  :disabled="state.workRunning"
                  @click="runWorkTask(t)">
                  {{ state.workRunning ? '生成中…' : '运行任务' }}
                </button>
              </div>
            </div>
          </div>
          <div v-if="state.workReply" class="work-reply">
            <div class="wr-head">
              <span>📋 {{ state.workTitle }} 结果</span>
              <button
                v-if="state.workTaskId === 'shenlun_week'"
                class="wi-btn"
                :disabled="state.workImporting || state.workImportDone"
                @click="importToToday()">
                {{
                  state.workImportDone
                    ? '已写入✓'
                    : state.workImporting
                      ? '写入中…'
                      : '一键写入今日任务'
                }}
              </button>
            </div>
            <div class="wr-body" v-html="renderMd(state.workReply)"></div>
          </div>
          <div v-if="state.workNotice" class="work-notice">
            {{ state.workNotice }}
          </div>
        </div>

        <div
          v-if="!state.workMode && state.messages.length === 0"
          class="welcome-card">
          <!-- 粒子动画背景 -->
          <div class="particles">
            <div v-for="i in 20" :key="i" class="particle"
              :style="{
                left: Math.random() * 100 + '%',
                animationDelay: Math.random() * 5 + 's',
                animationDuration: (3 + Math.random() * 4) + 's'
              }">
            </div>
          </div>
          <!-- AI学习教练每日日报 -->
          <div v-if="state.showCoachCard" class="coach-daily-card">
            <div class="coach-header">
              <span class="coach-icon">📊</span>
              <span class="coach-title">AI学习教练 · 今日日报</span>
              <span class="coach-date">{{ todayDate }}</span>
            </div>
            <div class="coach-stats">
              <div class="stat-item">
                <div class="stat-num">12.5h</div>
                <div class="stat-label">昨日学习</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">78%</div>
                <div class="stat-label">正确率</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">328题</div>
                <div class="stat-label">完成题目</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">🔥7天</div>
                <div class="stat-label">连续打卡</div>
              </div>
            </div>
            <div class="coach-suggest">
              <div class="suggest-item">
                <span class="suggest-label">今日推荐：</span>
                <span class="suggest-value">资料分析 · 20题 · 重点：增长率</span>
              </div>
              <div class="suggest-item">
                <span class="suggest-label">待复习：</span>
                <span class="suggest-value">判断推理-图形推理、言语理解-逻辑填空</span>
              </div>
            </div>
            <div class="coach-quote">
              💪 {{ coachQuote }}
            </div>
            <div class="coach-actions">
              <button class="coach-btn primary" @click="startTodayStudy">🚀 一键开始今日学习</button>
              <button class="coach-btn" @click="hideCoachCard">收起</button>
            </div>
          </div>

          <!-- 功能入口卡片 -->
          <div class="feature-grid">
            <div class="feature-card" @click="startInterview">
              <div class="feature-icon">🎤</div>
              <div class="feature-name">模拟面试</div>
              <div class="feature-desc">公安面试对练</div>
            </div>
            <div class="feature-card" @click="startMoodDiary">
              <div class="feature-icon">💬</div>
              <div class="feature-name">心情日记</div>
              <div class="feature-desc">AI听你吐槽</div>
            </div>
          </div>

          <!-- 模拟面试模式 -->
          <div v-if="state.interviewMode" class="interview-panel">
            <div class="interview-header">
              <span class="interview-title">🎤 AI模拟面试</span>
              <button class="interview-close" @click="exitInterview">✕ 退出</button>
            </div>
            <div class="interview-role-select">
              <div class="role-label">选择考官：</div>
              <div class="role-options">
                <div class="role-opt" :class="{ active: state.interviewRole === 'strict' }" @click="setInterviewRole('strict')">
                  😤 严肃考官
                </div>
                <div class="role-opt" :class="{ active: state.interviewRole === 'gentle' }" @click="setInterviewRole('gentle')">
                  😊 温和考官
                </div>
                <div class="role-opt" :class="{ active: state.interviewRole === 'pro' }" @click="setInterviewRole('pro')">
                  👮 专业考官
                </div>
              </div>
            </div>
            <div class="interview-question">
              <div class="q-label">第1题：</div>
              <div class="q-content">{{ state.interviewQuestion }}</div>
              <div class="q-timer">⏱️ 思考3分钟，作答5分钟</div>
            </div>
            <div class="interview-actions">
              <button class="interview-btn" @click="nextQuestion">下一题</button>
              <button class="interview-btn primary" @click="submitAnswer">提交作答</button>
            </div>
            <div v-if="state.interviewResult" class="interview-result">
              <div class="result-title">📊 面试点评</div>
              <div class="result-scores">
                <div class="score-item">
                  <div class="score-num">{{ state.interviewResult.content }}</div>
                  <div class="score-label">内容</div>
                </div>
                <div class="score-item">
                  <div class="score-num">{{ state.interviewResult.expression }}</div>
                  <div class="score-label">表达</div>
                </div>
                <div class="score-item">
                  <div class="score-num">{{ state.interviewResult.presence }}</div>
                  <div class="score-label">仪态</div>
                </div>
                <div class="score-item">
                  <div class="score-num">{{ state.interviewResult.logic }}</div>
                  <div class="score-label">逻辑</div>
                </div>
              </div>
              <div class="result-comment">{{ state.interviewResult.comment }}</div>
            </div>
          </div>

          <!-- 心情日记模式 -->
          <div v-if="state.moodMode" class="mood-panel">
            <div class="mood-header">
              <span class="mood-title">💬 心情日记</span>
              <button class="mood-close" @click="exitMood">✕ 关闭</button>
            </div>
            <div class="mood-question">今天学习感觉怎么样？</div>
            <div class="mood-emojis">
              <div v-for="m in moodOptions" :key="m.emoji" 
                class="mood-emoji" :class="{ selected: state.selectedMood === m.value }"
                @click="selectMood(m.value)">
                <div class="m-emoji">{{ m.emoji }}</div>
                <div class="m-label">{{ m.label }}</div>
              </div>
            </div>
            <div class="mood-chat">
              <div class="mood-ai">{{ state.moodReply }}</div>
            </div>
            <div class="mood-curve">
              <div class="curve-title">📈 近7天心情曲线</div>
              <div class="curve-chart">
                <svg width="100%" height="80">
                  <polyline points="0,60 40,40 80,50 120,30 160,45 200,25 240,35" 
                    fill="none" stroke="#d32f2f" stroke-width="3"/>
                  <circle cx="0" cy="60" r="4" fill="#d32f2f"/>
                  <circle cx="40" cy="40" r="4" fill="#d32f2f"/>
                  <circle cx="80" cy="50" r="4" fill="#d32f2f"/>
                  <circle cx="120" cy="30" r="4" fill="#d32f2f"/>
                  <circle cx="160" cy="45" r="4" fill="#d32f2f"/>
                  <circle cx="200" cy="25" r="4" fill="#d32f2f"/>
                  <circle cx="240" cy="35" r="4" fill="#d32f2f"/>
                </svg>
              </div>
            </div>
          </div>

          <div class="welcome-emoji">🎯</div>
          <p class="welcome-title">你好，我是联考小智</p>
          <p class="welcome-sub">选个场景，从下面挑一个问题开始问我</p>
          
          <!-- AI角色选择 -->
          <div class="role-select">
            <div class="role-title">选择你的AI伙伴：</div>
            <div class="role-list">
              <div class="role" :class="{ active: state.role === 'strict' }" @click="switchRole('strict')">
                <div class="role-emoji">😤</div>
                <div class="role-name">严厉教官</div>
              </div>
              <div class="role" :class="{ active: state.role === 'gentle' }" @click="switchRole('gentle')">
                <div class="role-emoji">😊</div>
                <div class="role-name">温柔学姐</div>
              </div>
              <div class="role" :class="{ active: state.role === 'funny' }" @click="switchRole('funny')">
                <div class="role-emoji">😄</div>
                <div class="role-name">幽默学长</div>
              </div>
            </div>
          </div>

          <div class="quick-chips">
            <div
              v-for="q in quickQuestions"
              :key="q"
              class="chip"
              @click="quickAsk(q)">
              {{ q }}
            </div>
          </div>

          <!-- 学习对战 -->
          <div class="battle-card">
            <div class="battle-title">⚔️ 学习对战</div>
            <div class="battle-body">
              <div class="battle-player">
                <div class="player-avatar">😎</div>
                <div class="player-name">你</div>
                <div class="player-score">1250分</div>
              </div>
              <div class="battle-vs">VS</div>
              <div class="battle-player">
                <div class="player-avatar">🤖</div>
                <div class="player-name">AI学长</div>
                <div class="player-score">1180分</div>
              </div>
            </div>
            <button class="battle-btn">开始对战</button>
          </div>
        </div>

        <div
          v-for="(m, idx) in state.messages"
          :key="idx"
          class="msg-row"
          :class="m.role === 'user' ? 'me' : 'bot'">
          <div v-if="m.role !== 'user'" class="mini-avatar">智</div>
          <div class="bubble" :class="m.role === 'user' ? 'me' : 'bot'">
            <div class="bubble-content" v-html="renderMd(m.content)"></div>
            <div v-if="m.role !== 'user'" class="msg-actions">
              <button class="msg-action-btn" @click="showMindMap(idx)">
                🧠 思维导图
              </button>
            </div>
          </div>
          <div v-if="m.role === 'user'" class="mini-avatar me">我</div>
        </div>

        <!-- 思维导图弹窗 -->
        <div v-if="state.showMindMap" class="mindmap-modal" @click="state.showMindMap = false">
          <div class="mindmap-content" @click.stop>
            <div class="mindmap-head">
              <span>🧠 AI思维导图</span>
              <button @click="state.showMindMap = false">×</button>
            </div>
            <div class="mindmap-body">
              <div class="mindmap-layout">
                <div class="mindmap-branch left">
                  <div class="branch-item">
                    <div class="branch-title">📚 核心知识点</div>
                    <div class="branch-sub">
                      <div v-for="item in state.mindMapData.knowledge" :key="item" class="branch-sub-item">{{ item }}</div>
                    </div>
                  </div>
                  <div class="branch-item">
                    <div class="branch-title">📝 答题技巧</div>
                    <div class="branch-sub">
                      <div v-for="item in state.mindMapData.skills" :key="item" class="branch-sub-item">{{ item }}</div>
                    </div>
                  </div>
                  <div class="branch-item">
                    <div class="branch-title">⚠️ 易错点</div>
                    <div class="branch-sub">
                      <div v-for="item in state.mindMapData.mistakes" :key="item" class="branch-sub-item">{{ item }}</div>
                    </div>
                  </div>
                </div>
                <div class="mindmap-center">{{ state.mindMapTopic || '联考小智' }}</div>
                <div class="mindmap-branch right">
                  <div class="branch-item">
                    <div class="branch-title">✅ 学习方法</div>
                    <div class="branch-sub">
                      <div v-for="item in state.mindMapData.methods" :key="item" class="branch-sub-item">{{ item }}</div>
                    </div>
                  </div>
                  <div class="branch-item">
                    <div class="branch-title">🎯 备考策略</div>
                    <div class="branch-sub">
                      <div v-for="item in state.mindMapData.strategy" :key="item" class="branch-sub-item">{{ item }}</div>
                    </div>
                  </div>
                  <div class="branch-item">
                    <div class="branch-title">📊 进步方向</div>
                    <div class="branch-sub">
                      <div v-for="item in state.mindMapData.progress" :key="item" class="branch-sub-item">{{ item }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="state.loading" class="msg-row bot">
          <div class="mini-avatar">智</div>
          <div class="bubble bot typing">
            <span class="typing-cursor"></span>
          </div>
        </div>
      </div>

      <!-- 操作提示（加载/删除失败时显示，发送后自动消失） -->
      <div v-if="state.notice" class="notice-bar">{{ state.notice }}</div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-card">
          <button
            class="mic-btn"
            :class="{ recording: state.recording }"
            @click="toggleMic"
            title="语音输入">
            🎤
            <div v-if="state.recording" class="mic-waves">
              <span></span>
              <span></span>
              <span></span>
              <span></span>
              <span></span>
            </div>
          </button>
          <textarea
            v-model="state.input"
            :placeholder="inputPlaceholder"
            class="chat-input"
            rows="2"
            @keydown.enter.exact.prevent="send"></textarea>
          <button
            class="send-btn"
            :disabled="state.loading || !state.input.trim()"
            @click="send">
            <XIcon :icon="Promotion" :size="16" color="#fff"></XIcon>
            <span>发送</span>
          </button>
        </div>
        <div class="input-tip">Enter 发送 · Shift+Enter 换行 · 🎤 语音输入</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, ref, onMounted, nextTick } from 'vue';
import { XIcon } from '@vtj/ui';
import {
  Promotion,
  ReadingLamp,
  Document,
  TrophyBase,
  Plus,
  Menu
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'AiAssistant',
  components: { XIcon },
  setup() {
    const provider = useProvider({ id: 'ai_chat', version: '20261028002' });
    const state = reactive({
      scene: 'qa',
      input: '',
      messages: [],
      sessionId: null,
      loading: false,
      notice: '',
      agentName: '', // 模块7 v2：当前路由命中的专业 Agent
      // 工作台模式（模块7 v2）
      workMode: false,
      workTasks: [],
      activeTask: null,
      workParams: {},
      workRunning: false,
      workReply: '',
      workTitle: '',
      workTaskId: '',
      workImporting: false,
      workImportDone: false,
      workNotice: '',
      // 学习仪表盘
      showDashboard: false,
      // 语音输入
      recording: false,
      recognition: null,
      // 思维导图
      showMindMap: false,
      mindMapTopic: '',
      mindMapData: {
        knowledge: [],
        skills: [],
        mistakes: [],
        methods: [],
        strategy: [],
        progress: []
      },
      // AI角色
      role: 'gentle',
      // AI学习教练
      showCoachCard: true,
      // 模拟面试
      interviewMode: false,
      interviewRole: 'gentle',
      interviewQuestion: '如果让你组织一次校园反诈宣传活动，你会怎么开展？',
      interviewResult: null,
      // 心情日记
      moodMode: false,
      selectedMood: '',
      moodReply: '',
    });
    const sessions = ref([]);
    const drawerOpen = ref(false);

    const sceneOptions = [
      { value: 'psychological', label: '心理疏导', icon: ReadingLamp },
      { value: 'qa', label: '答疑解惑', icon: Document },
      { value: 'advice', label: '提升建议', icon: TrophyBase }
    ];

    const inputPlaceholderMap = {
      psychological: '最近压力大吗？跟我说说…',
      qa: '问一个行测 / 申论 / 公专的知识点吧',
      advice: '想怎么复习？我来给你出主意'
    };

    const quickQuestions = [
      '行测资料分析总是做不完怎么办？',
      '申论大作文总是跑题，怎么破？',
      '最近模考成绩上不去，有点焦虑'
    ];

    function sceneLabel(v) {
      const o = sceneOptions.find((x) => x.value === v);
      return o ? o.label : '问答';
    }
    function fmtTime(iso) {
      if (!iso) return '';
      try {
        const d = new Date(iso);
        return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      } catch (e) {
        return '';
      }
    }

    // 极简 markdown：转义 HTML → **加粗** → 换行 → 列表
    function renderMd(text) {
      if (!text) return '';
      let s = String(text);
      s = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      s = s.replace(/^\s*[-•]\s+/gm, '<br>• ');
      s = s.replace(/\n/g, '<br>');
      return s;
    }

    function scrollToBottom() {
      nextTick(() => {
        const el = state.__listEl;
        if (el) el.scrollTop = el.scrollHeight;
      });
    }

    async function loadSessions() {
      try {
        const res = await window.__VTJ_AUTH__.apiFetch('/api/llm/sessions');
        const data = await res.json();
        if (res.ok && data.items) sessions.value = data.items;
        else state.notice = '历史会话加载失败，请稍后刷新';
      } catch (e) {
        state.notice = '网络异常，历史会话暂不可用';
      }
    }

    async function loadMessages(sid) {
      try {
        const hRes = await window.__VTJ_AUTH__.apiFetch(
          `/api/llm/sessions/${sid}/messages`
        );
        const hData = await hRes.json();
        if (hRes.ok && hData.items) {
          state.messages = hData.items.map((m) => ({
            role: m.role,
            content: m.content
          }));
          scrollToBottom();
        } else {
          state.notice = '对话记录加载失败';
        }
      } catch (e) {
        state.notice = '网络异常，对话记录暂不可用';
      }
    }

    async function openSession(s) {
      state.sessionId = s.session_id;
      state.scene = s.scene || 'qa';
      state.messages.splice(0, state.messages.length);
      drawerOpen.value = false;
      await loadMessages(s.session_id);
    }

    function newChat() {
      state.sessionId = null;
      state.messages.splice(0, state.messages.length);
      drawerOpen.value = false;
    }

    function goBack() {
      if (window.history.length > 1) {
        window.history.back();
      } else {
        window.location.href = '/#/';
      }
    }

    async function removeSession(s) {
      if (!confirm('删除这条对话记录？')) return;
      try {
        const r = await window.__VTJ_AUTH__.apiFetch(
          `/api/llm/sessions/${s.session_id}`,
          { method: 'DELETE' }
        );
        if (!r.ok) {
          state.notice = '删除失败，请稍后重试';
          return;
        }
        sessions.value = sessions.value.filter(
          (x) => x.session_id !== s.session_id
        );
        if (state.sessionId === s.session_id) newChat();
      } catch (e) {
        state.notice = '网络异常，删除未生效';
      }
    }

    async function typewriter(fullText) {
      // 打字机效果：逐字 push 到最后一条 assistant 消息
      state.messages.push({ role: 'assistant', content: '' });
      const lastIdx = state.messages.length - 1;
      let i = 0;
      await new Promise((resolve) => {
        const timer = setInterval(() => {
          i += 2;
          state.messages[lastIdx].content = fullText.slice(0, i);
          scrollToBottom();
          if (i >= fullText.length) {
            clearInterval(timer);
            state.messages[lastIdx].content = fullText;
            resolve();
          }
        }, 18);
      });
    }

    async function send() {
      const text = state.input.trim();
      if (!text || state.loading) return;
      state.notice = '';
      state.messages.push({ role: 'user', content: text });
      state.input = '';
      state.loading = true;
      scrollToBottom();

      try {
        const res = await window.__VTJ_AUTH__.apiFetch('/api/llm/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            session_id: state.sessionId,
            scene: state.scene
          })
        });
        const data = await res.json();
        state.loading = false;
        if (res.ok && data.reply) {
          state.sessionId = data.session_id;
          state.agentName = data.agent_name || '';
          await typewriter(data.reply);
          loadSessions();
        } else {
          state.messages.push({
            role: 'assistant',
            content: data.detail || '抱歉，我暂时回答不了。'
          });
        }
      } catch (e) {
        state.loading = false;
        state.messages.push({
          role: 'assistant',
          content: '网络异常，请稍后再试。'
        });
      } finally {
        scrollToBottom();
      }
    }

    function quickAsk(q) {
      state.input = q;
      send();
    }

    function switchScene(scene) {
      if (state.scene === scene) return;
      state.scene = scene;
      newChat();
    }

    const AGENT_LABELS = {
      choose_post: '选岗顾问',
      interview: '面试教练',
      psychology: '心理辅导',
      shenlun: '申论教练',
      xingce: '行测讲师',
      gongzhuan: '公专导师',
      qa: '联考小智'
    };
    function agentLabel(a) {
      return AGENT_LABELS[a] || '联考小智';
    }

    function toggleDashboard() {
      state.showDashboard = !state.showDashboard;
    }

    function toggleMic() {
      if (state.recording) {
        // 停止录音
        if (state.recognition) {
          state.recognition.stop();
        }
        state.recording = false;
        return;
      }

      // 开始录音
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        state.notice = '浏览器不支持语音识别，请用Chrome';
        setTimeout(() => state.notice = '', 3000);
        return;
      }

      const recognition = new SpeechRecognition();
      recognition.lang = 'zh-CN';
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        state.recording = true;
      };

      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map(r => r[0].transcript)
          .join('');
        state.input = transcript;
      };

      recognition.onend = () => {
        state.recording = false;
      };

      recognition.onerror = () => {
        state.recording = false;
        state.notice = '语音识别失败，请重试';
        setTimeout(() => state.notice = '', 3000);
      };

      state.recognition = recognition;
      recognition.start();
    }

    function showMindMap(idx) {
      // 获取当前消息内容
      const msg = state.messages[idx];
      let topic = msg?.content?.slice(0, 10) || '联考小智';
      // 如果太长，加省略号
      if (msg?.content?.length > 10) {
        topic += '...';
      }

      // 根据问题关键词生成思维导图内容
      const content = msg?.content || '';
      let knowledge = [], skills = [], mistakes = [], methods = [], strategy = [], progress = [];

      if (content.includes('资料分析') || content.includes('行测')) {
        knowledge = ['增长率', '比重', '倍数', '平均数', '速算技巧'];
        skills = ['截位直除法', '特殊分数法', '尾数法', '快速找数据', '先看问题再读材料'];
        mistakes = ['找错数据', '单位换算错', '时间看错', '计算粗心', '公式记错'];
        methods = ['每天练20题', '总结错题', '限时训练', '先易后难', '错题本复习'];
        strategy = ['每天30分钟', '每周模考', '薄弱项专项突破', '错题反复做', '总结答题套路'];
        progress = ['提升做题速度', '提高正确率', '减少粗心错误', '掌握速算技巧', '形成答题节奏'];
      } else if (content.includes('申论')) {
        knowledge = ['归纳概括', '综合分析', '提出对策', '应用文写作', '大作文'];
        skills = ['找点方法', '加工整合', '规范表达', '结构清晰', '字数控制'];
        mistakes = ['要点不全', '逻辑混乱', '语言不规范', '字数超标', '跑题偏题'];
        methods = ['每天写1题', '背诵规范表达', '总结答题框架', '积累素材', '对照答案修改'];
        strategy = ['每天1小时', '每周写1篇大作文', '积累人民日报素材', '总结万能模板', '限时写作'];
        progress = ['提高找点能力', '规范语言表达', '提升文章结构', '积累素材库', '提高写作速度'];
      } else {
        knowledge = ['核心概念', '基本原理', '常见题型', '解题思路', '易错考点'];
        skills = ['审题技巧', '快速定位', '排除法', '代入法', '蒙题技巧'];
        mistakes = ['审题不清', '概念混淆', '计算错误', '时间不够', '粗心大意'];
        methods = ['系统学习知识点', '多做练习题', '整理错题本', '总结规律', '定期复习'];
        strategy = ['制定学习计划', '分模块突破', '每天坚持学习', '每周模考', '考前冲刺'];
        progress = ['夯实基础', '提高正确率', '加快做题速度', '掌握应试技巧', '建立知识体系'];
      }

      state.mindMapTopic = topic;
      state.mindMapData = { knowledge, skills, mistakes, methods, strategy, progress };
      state.showMindMap = true;
    }

    async function switchMode(work) {
      if (state.workMode === work) return;
      state.workMode = work;
      if (work && state.workTasks.length === 0) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/agent/tasks');
          if (res.ok) {
            const d = await res.json();
            state.workTasks = d.tasks || [];
          }
        } catch (e) {}
      }
    }

    function selectTask(t) {
      state.activeTask =
        state.activeTask && state.activeTask.task_id === t.task_id ? null : t;
      state.workParams = {};
      state.workNotice = '';
      state.workReply = '';
    }

    async function runWorkTask(t) {
      state.workRunning = true;
      state.workNotice = '';
      try {
        const res = await window.__VTJ_AUTH__.apiFetch('/api/agent/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_id: t.task_id, params: state.workParams })
        });
        const d = await res.json();
        if (res.ok && d.reply) {
          state.workReply = d.reply;
          state.workTitle = d.title;
          state.workTaskId = t.task_id;
          state.workImportDone = false;
          state.agentName = d.agent_name || '';
        } else {
          state.workNotice = d.detail || '任务执行失败，请稍后重试';
        }
      } catch (e) {
        state.workNotice = '网络异常，任务未执行';
      } finally {
        state.workRunning = false;
      }
    }

    async function importToToday() {
      state.workImporting = true;
      state.workNotice = '';
      try {
        const res = await window.__VTJ_AUTH__.apiFetch(
          '/api/agent/import-today',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: state.workTitle || '申论计划·今日任务',
              content: (state.workReply || '').slice(0, 500),
              coin_reward: 10
            })
          }
        );
        const d = await res.json();
        if (res.ok && d.goal_id) {
          state.workImportDone = true;
          state.workNotice = d.message;
        } else {
          state.workNotice = d.detail || '写入失败，请稍后重试';
        }
      } catch (e) {
        state.workNotice = '网络异常，写入失败';
      } finally {
        state.workImporting = false;
      }
    }

    function switchRole(role) {
      state.role = role;
    }

    // AI学习教练
    const todayDate = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' });
    const coachQuotes = [
      '距离联考还有不到100天，每一道题都是上岸的台阶！',
      '昨天的努力不会白费，今天继续加油！',
      '你比自己想象的更强大，坚持住！',
      '上岸的人都在默默努力，你也可以！',
      '今天多学一小时，考试少慌一分。',
      '坚持到最后的人，运气都不会太差。',
      '你已经坚持了7天，离上岸又近了一步！'
    ];
    const coachQuote = ref(coachQuotes[new Date().getDay() % coachQuotes.length]);

    // 一次性 AI 任务调用（/api/llm/chat，persist=false：不落会话、不写消息）
    async function callAiOneShot(message, scene) {
      const res = await window.__VTJ_AUTH__.apiFetch('/api/llm/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, scene, persist: false })
      });
      const data = await res.json();
      if (!res.ok || !data.reply) throw new Error((data && data.detail) || 'AI 服务暂不可用');
      return data.reply;
    }

    // 容错解析大模型返回的 JSON（去 ```json 围栏 → 截取首尾 {} → JSON.parse）
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

    // AI学习教练：按真实今日计划生成今日建议（失败保留每日金句兜底）
    async function loadCoachSuggestion() {
      try {
        let ctxText = '暂无今日计划数据';
        const r = await window.__VTJ_AUTH__.apiFetch('/api/plan/today');
        if (r.ok) {
          const d = await r.json();
          const items = d && d.today ? d.today : (d.items || []);
          const lines = items.slice(0, 6).map((t) => (t.title || '') + (t.is_completed === 1 ? '（已完成）' : ''));
          if (lines.length) ctxText = lines.join('；');
        }
        const reply = await callAiOneShot('【学习数据】今日计划：' + ctxText, 'coach');
        const parsed = parseAiJson(reply);
        if (parsed && parsed.suggestion) coachQuote.value = String(parsed.suggestion);
      } catch (e) { /* 保留每日金句兜底 */ }
    }

    function startTodayStudy() {
      state.input = '帮我制定今日学习计划';
      send();
    }

    function hideCoachCard() {
      state.showCoachCard = false;
    }

    // 模拟面试
    const interviewQuestions = [
      '如果让你组织一次校园反诈宣传活动，你会怎么开展？',
      '你为什么想当一名移民管理警察？',
      '如果在执勤时遇到群众不配合，你会怎么处理？',
      '请谈谈你对“科技强警”的理解。',
      '如果领导给你安排了一项你不熟悉的工作，你会怎么做？',
    ];

    function startInterview() {
      state.interviewMode = true;
      state.moodMode = false;
    }

    function exitInterview() {
      state.interviewMode = false;
      state.interviewResult = null;
    }

    function setInterviewRole(role) {
      state.interviewRole = role;
    }

    async function nextQuestion() {
      state.interviewResult = null;
      state.notice = '';
      const roleLabel = { strict: '严肃考官', gentle: '温和考官', pro: '专业考官' }[state.interviewRole] || '专业考官';
      try {
        const reply = await callAiOneShot('【出题】考官风格：' + roleLabel + '。请出一道公安联考面试题。', 'interview');
        const parsed = parseAiJson(reply);
        if (parsed && parsed.question) {
          state.interviewQuestion = String(parsed.question);
          return;
        }
      } catch (e) {
        state.notice = 'AI 出题暂不可用，已使用备用题';
      }
      const randomIdx = Math.floor(Math.random() * interviewQuestions.length);
      state.interviewQuestion = interviewQuestions[randomIdx];
    }

    async function submitAnswer() {
      const answer = window.prompt('请输入你的作答内容（将交给 AI 考官评分）：', '');
      if (answer === null) return;
      if (!answer.trim()) {
        alert('请先输入作答内容！');
        return;
      }
      state.interviewResult = null;
      state.notice = '';
      const roleLabel = { strict: '严肃考官', gentle: '温和考官', pro: '专业考官' }[state.interviewRole] || '专业考官';
      try {
        const reply = await callAiOneShot(
          '【评分】考官风格：' + roleLabel
            + '\n面试题：' + state.interviewQuestion
            + '\n考生作答：' + answer.trim(),
          'interview'
        );
        const parsed = parseAiJson(reply);
        if (parsed && parsed.content !== undefined && parsed.logic !== undefined) {
          state.interviewResult = {
            content: Number(parsed.content) || 0,
            expression: Number(parsed.expression) || 0,
            presence: Number(parsed.presence) || 0,
            logic: Number(parsed.logic) || 0,
            comment: String(parsed.comment || ''),
          };
          return;
        }
      } catch (e) {
        state.notice = 'AI 评分暂不可用，已展示示例点评';
      }
      state.interviewResult = {
        content: 82,
        expression: 78,
        presence: 85,
        logic: 80,
        comment: '（示例点评，非 AI 实时结果）整体表现不错！内容方面有一定的思路和框架，但可以再结合一些公安实际案例。表达比较流畅，仪态方面可以再自信一点。逻辑上层次比较清晰，但开头和结尾可以更精炼。继续加油！',
      };
    }

    // 心情日记
    const moodOptions = [
      { emoji: '😄', label: '很开心', value: 'great' },
      { emoji: '😊', label: '还不错', value: 'good' },
      { emoji: '😐', label: '一般般', value: 'ok' },
      { emoji: '😔', label: '有点累', value: 'tired' },
      { emoji: '😫', label: '想放弃', value: 'bad' },
    ];

    const moodReplies = {
      great: '太棒了！保持这个状态，上岸指日可待！🎉',
      good: '不错哦！今天又是充实的一天，继续加油！💪',
      ok: '平平淡淡才是真，坚持就是胜利！😊',
      tired: '累了就休息一下，去喝杯水、伸个懒腰，然后再继续～☕',
      bad: '抱抱你😢 学不会的时候很正常，慢慢来，你已经很努力了！明天会更好的！',
    };

    function startMoodDiary() {
      state.moodMode = true;
      state.interviewMode = false;
    }

    function exitMood() {
      state.moodMode = false;
    }

    function selectMood(mood) {
      state.selectedMood = mood;
      state.moodReply = moodReplies[mood] || '谢谢你的分享！❤️';
    }

    onMounted(() => {
      state.__listEl = document.querySelector('.ai-chat-page .message-list');
      loadSessions();
      loadCoachSuggestion();
    });

    return {
      state,
      sessions,
      drawerOpen,
      provider,
      sceneOptions,
      quickQuestions,
      inputPlaceholder: '输入消息…',
      send,
      quickAsk,
      switchScene,
      newChat,
      goBack,
      openSession,
      removeSession,
      sceneLabel,
      fmtTime,
      renderMd,
      agentLabel,
      switchMode,
      toggleDashboard,
      toggleMic,
      switchRole,
      showMindMap,
      todayDate,
      coachQuote,
      startTodayStudy,
      hideCoachCard,
      startInterview,
      exitInterview,
      setInterviewRole,
      nextQuestion,
      submitAnswer,
      startMoodDiary,
      exitMood,
      selectMood,
      moodOptions,
      selectTask,
      runWorkTask,
      importToToday,
      Plus,
      Menu,
      Promotion
    };
  }
});
</script>

<style lang="css" scoped>
/* ===== 思维导图 ===== */
.msg-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.msg-action-btn {
  background: #f0f2f5;
  border: none;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
}
.msg-action-btn:hover {
  background: #e0e3e9;
  color: #333;
}
.mindmap-modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mindmap-content {
  background: #fff;
  border-radius: 16px;
  width: 750px;
  max-width: 95%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.3s ease;
}
@keyframes slideUp {
  from { transform: translateY(50px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.mindmap-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #1a2b5f, #2a4080);
  color: #fff;
  font-weight: 600;
}
.mindmap-head button {
  background: none;
  border: none;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
}
.mindmap-body {
  padding: 20px;
  overflow-y: auto;
  background: linear-gradient(135deg, #f8f9ff 0%, #fff5f5 100%);
  flex: 1;
}
.mindmap-layout {
  display: flex;
  align-items: center;
  gap: 20px;
  min-height: 400px;
}
.mindmap-center {
  flex-shrink: 0;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  text-align: center;
  padding: 10px;
  line-height: 1.3;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
  word-break: break-all;
}
.mindmap-branch {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.branch-item {
  background: #fff;
  padding: 12px 20px;
  border-radius: 12px;
  font-size: 14px;
  color: #333;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  position: relative;
  transition: all 0.3s ease;
}
.branch-item:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(0,0,0,0.15);
}
.branch-item::before {
  content: '';
  position: absolute;
  top: 50%;
  width: 40px;
  height: 2px;
  background: linear-gradient(90deg, #667eea, transparent);
}
.mindmap-branch.left .branch-item::before {
  right: -40px;
}
.mindmap-branch.right .branch-item::before {
  left: -40px;
  background: linear-gradient(90deg, transparent, #764ba2);
}
.branch-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.branch-sub {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.branch-sub-item {
  font-size: 12px;
  color: #666;
  padding: 4px 8px;
  background: #f8f9fc;
  border-radius: 6px;
}

/* ===== 语音输入按钮 ===== */
.mic-btn {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  border: none;
  background: #f0f2f5;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}
.mic-btn:hover {
  background: #e0e3e9;
}
.mic-btn.recording {
  background: #c41e3a;
  color: #fff;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(196, 30, 58, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(196, 30, 58, 0); }
}

/* 声波动画 */
.mic-waves {
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 2px;
  align-items: center;
}
.mic-waves span {
  width: 3px;
  background: #c41e3a;
  border-radius: 2px;
  animation: wave 1s ease-in-out infinite;
}
.mic-waves span:nth-child(1) { height: 8px; animation-delay: 0s; }
.mic-waves span:nth-child(2) { height: 12px; animation-delay: 0.15s; }
.mic-waves span:nth-child(3) { height: 16px; animation-delay: 0.3s; }
.mic-waves span:nth-child(4) { height: 12px; animation-delay: 0.45s; }
.mic-waves span:nth-child(5) { height: 8px; animation-delay: 0.6s; }
@keyframes wave {
  0%, 100% { transform: scaleY(0.5); }
  50% { transform: scaleY(1.5); }
}

/* ===== 学习仪表盘 ===== */
.dashboard-panel {
  position: absolute;
  right: 20px;
  top: 80px;
  width: 280px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  z-index: 100;
  overflow: hidden;
  animation: slideIn 0.3s ease;
}
@keyframes slideIn {
  from { transform: translateX(300px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.dash-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #1a2b5f, #2a4080);
  color: #fff;
  font-weight: 600;
}
.dash-head button {
  background: none;
  border: none;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
}
.dash-body {
  padding: 20px;
}
.dash-card {
  text-align: center;
  padding: 16px;
  background: #f8f9fc;
  border-radius: 12px;
  margin-bottom: 12px;
}
.dash-num {
  font-size: 28px;
  font-weight: 800;
  background: linear-gradient(135deg, #c41e3a, #ff6b6b);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.dash-label {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
.dash-section {
  margin-top: 16px;
}
.dash-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}
.dash-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.dash-bar-label {
  width: 60px;
  font-size: 12px;
  color: #666;
}
.dash-bar-track {
  flex: 1;
  height: 8px;
  background: #eee;
  border-radius: 4px;
  overflow: hidden;
}
.dash-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #c41e3a, #ff6b6b);
  border-radius: 4px;
  transition: width 0.5s ease;
}
.dash-bar-pct {
  width: 36px;
  font-size: 12px;
  color: #666;
  text-align: right;
}
.dash-streak {
  font-size: 32px;
  font-weight: 800;
  color: #ff6b35;
  text-align: center;
  padding: 12px;
  background: #fff5f0;
  border-radius: 12px;
}

.ai-layout {
  display: flex;
  height: 100vh;
  background: #f3f5f9;
}

/* ===== 左侧历史栏 ===== */
.history-panel {
  width: 240px;
  background: #1a2a4a;
  color: #cfd8e3;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 14px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.history-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  letter-spacing: 1px;
}
.new-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  background: #c8161e;
  color: #fff;
  border: none;
  border-radius: 14px;
  font-size: 12px;
  cursor: pointer;
}
.new-btn:hover {
  background: #e63946;
}
.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}
.history-item:hover {
  background: rgba(255, 255, 255, 0.08);
}
.history-item.active {
  background: rgba(200, 22, 30, 0.25);
  border-left: 3px solid #c8161e;
}
.hi-main {
  flex: 1;
  min-width: 0;
}
.hi-title {
  font-size: 13px;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hi-meta {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 2px;
}
.hi-del {
  opacity: 0;
  color: #ff8a8a;
  font-size: 16px;
  padding: 0 4px;
}
.history-item:hover .hi-del {
  opacity: 1;
}
.history-empty {
  text-align: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 30px;
}
.mask {
  display: none;
}

/* ===== 右侧聊天区 ===== */
.ai-chat-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 760px;
  margin: 0 auto;
  background: #f3f5f9;
}
.chat-header {
  position: relative;
  background: linear-gradient(135deg, #1a2a4a 0%, #243b6b 60%, #2c4a82 100%);
  padding: 14px 20px 12px;
  color: #fff;
  overflow: hidden;
}
.header-glow {
  position: absolute;
  right: -40px;
  top: -40px;
  width: 160px;
  height: 160px;
  background: radial-gradient(
    circle,
    rgba(200, 22, 30, 0.18) 0%,
    transparent 70%
  );
  border-radius: 50%;
}
.header-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.hamburger {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: none;
}
.back-btn {
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.back-btn:hover {
  background: rgba(255, 255, 255, 0.25);
}
.ai-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #c8161e, #e63946);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(200, 22, 30, 0.4);
}
.header-meta {
  flex: 1;
}
.header-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-title {
  font-size: 17px;
  font-weight: 700;
}
.kb-entry {
  margin-left: 4px;
  padding: 2px 10px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 999px;
  text-decoration: none;
  line-height: 18px;
}
.kb-entry:hover {
  background: rgba(255, 255, 255, 0.28);
}
.online-dot {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #9fe6b0;
}
.online-dot i {
  width: 6px;
  height: 6px;
  background: #4ade80;
  border-radius: 50%;
  box-shadow: 0 0 6px #4ade80;
}
.header-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 2px;
}
.scene-tabs {
  display: flex;
  gap: 8px;
  position: relative;
  z-index: 1;
}
.scene-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 13px;
  border-radius: 18px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  cursor: pointer;
  transition: all 0.2s;
}
.scene-tab.active {
  background: #c8161e;
  border-color: #c8161e;
  color: #fff;
  box-shadow: 0 4px 10px rgba(200, 22, 30, 0.35);
}
.agent-bar {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.16);
  width: fit-content;
}
.agent-dot {
  width: 6px;
  height: 6px;
  background: #4ade80;
  border-radius: 50%;
}
.mode-tabs {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
.mode-tab {
  padding: 5px 14px;
  border-radius: 18px;
  font-size: 13px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  transition: all 0.2s;
}
.mode-tab.active {
  background: #1a2a4a;
  border-color: #1a2a4a;
  color: #fff;
}

/* 工作台 */
.work-panel {
  padding: 2px 0 16px;
}
.work-head {
  margin-bottom: 12px;
}
.work-title {
  font-size: 15px;
  font-weight: 700;
  color: #1a2a4a;
}
.work-sub {
  font-size: 12px;
  color: #8899aa;
  margin-top: 2px;
}
.work-tasks {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.work-task {
  background: #fff;
  border: 1px solid #e6ebf2;
  border-radius: 12px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.work-task:hover {
  border-color: #c8161e;
}
.work-task.open {
  border-color: #c8161e;
  box-shadow: 0 4px 12px rgba(200, 22, 30, 0.08);
}
.wt-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.wt-title {
  font-size: 14px;
  font-weight: 600;
  color: #2c3e50;
}
.wt-agent {
  font-size: 11px;
  color: #c8161e;
  background: #fdecec;
  border-radius: 10px;
  padding: 2px 8px;
}
.wt-desc {
  font-size: 12px;
  color: #8899aa;
  margin-top: 4px;
}
.wt-form {
  margin-top: 10px;
  border-top: 1px dashed #e6ebf2;
  padding-top: 10px;
}
.wf-row {
  margin-bottom: 8px;
}
.wf-label {
  display: block;
  font-size: 12px;
  color: #5a6a7a;
  margin-bottom: 4px;
}
.wf-input {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid #dce3ec;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}
.wf-run {
  width: 100%;
  padding: 9px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  background: #c8161e;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s;
}
.wf-run:hover {
  background: #a81218;
}
.wf-run:disabled {
  background: #e6b0b3;
  cursor: not-allowed;
}
.work-reply {
  margin-top: 12px;
  background: #fff;
  border: 1px solid #e6ebf2;
  border-radius: 12px;
  padding: 12px 14px;
}
.wr-head {
  font-size: 13px;
  font-weight: 600;
  color: #1a2a4a;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.wi-btn {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid #d33;
  color: #d33;
  background: #fff;
  cursor: pointer;
}
.wi-btn:disabled {
  border-color: #999;
  color: #999;
  cursor: default;
}
.wr-body {
  font-size: 13px;
  color: #2c3e50;
  line-height: 1.6;
}
.work-notice {
  margin-top: 10px;
  font-size: 12px;
  color: #c8161e;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
}
/* AI学习教练卡片 */
.coach-daily-card {
  background: linear-gradient(135deg, #fff5f5 0%, #fff 100%);
  border: 1px solid #ffd0d0;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: 0 4px 20px rgba(229, 57, 53, 0.08);
  animation: slideDown 0.5s ease;
}
@keyframes slideDown {
  from { transform: translateY(-20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.coach-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ffe0e0;
}
.coach-icon {
  font-size: 20px;
}
.coach-title {
  font-size: 16px;
  font-weight: 700;
  color: #d32f2f;
  flex: 1;
}
.coach-date {
  font-size: 12px;
  color: #999;
}
.coach-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-item {
  background: #fff;
  border-radius: 10px;
  padding: 12px 8px;
  text-align: center;
  border: 1px solid #f0f0f0;
}
.stat-num {
  font-size: 18px;
  font-weight: 700;
  color: #d32f2f;
}
.stat-label {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}
.coach-suggest {
  background: #fff;
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 12px;
  border: 1px solid #f0f0f0;
}
.suggest-item {
  font-size: 13px;
  line-height: 1.8;
}
.suggest-label {
  color: #d32f2f;
  font-weight: 600;
}
.suggest-value {
  color: #333;
}
.coach-quote {
  font-size: 14px;
  color: #d32f2f;
  text-align: center;
  padding: 12px;
  background: linear-gradient(90deg, #fff5f5, #fff, #fff5f5);
  border-radius: 10px;
  margin-bottom: 16px;
  font-style: italic;
}
.coach-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.coach-btn {
  padding: 10px 24px;
  border-radius: 20px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
}
.coach-btn.primary {
  background: linear-gradient(135deg, #e53935, #d32f2f);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(229, 57, 53, 0.3);
}
.coach-btn.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(229, 57, 53, 0.4);
}
.coach-btn {
  background: #f5f5f5;
  color: #666;
}
/* 功能入口卡片 */
.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}
.feature-card {
  background: #fff;
  border: 2px solid #f0f0f0;
  border-radius: 16px;
  padding: 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}
.feature-card:hover {
  border-color: #d32f2f;
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(211, 47, 47, 0.15);
}
.feature-icon {
  font-size: 36px;
  margin-bottom: 8px;
}
.feature-name {
  font-size: 16px;
  font-weight: 700;
  color: #333;
  margin-bottom: 4px;
}
.feature-desc {
  font-size: 12px;
  color: #999;
}
/* 模拟面试面板 */
.interview-panel {
  background: linear-gradient(135deg, #1a2b5f, #2a4080);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  color: #fff;
}
.interview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.interview-title {
  font-size: 18px;
  font-weight: 700;
}
.interview-close {
  background: rgba(255,255,255,0.2);
  border: none;
  color: #fff;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.interview-role-select {
  margin-bottom: 20px;
}
.role-label {
  font-size: 14px;
  margin-bottom: 10px;
  opacity: 0.8;
}
.role-options {
  display: flex;
  gap: 10px;
}
.role-opt {
  flex: 1;
  padding: 10px;
  background: rgba(255,255,255,0.1);
  border-radius: 10px;
  text-align: center;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.3s;
}
.role-opt.active {
  background: #d32f2f;
  font-weight: 600;
}
.interview-question {
  background: rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}
.q-label {
  font-size: 14px;
  opacity: 0.8;
  margin-bottom: 8px;
}
.q-content {
  font-size: 16px;
  line-height: 1.6;
  margin-bottom: 12px;
}
.q-timer {
  font-size: 12px;
  opacity: 0.7;
}
.interview-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.interview-btn {
  flex: 1;
  padding: 12px;
  background: rgba(255,255,255,0.2);
  border: none;
  color: #fff;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}
.interview-btn.primary {
  background: #d32f2f;
  font-weight: 600;
}
.interview-result {
  background: rgba(255,255,255,0.15);
  border-radius: 12px;
  padding: 16px;
}
.result-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
}
.result-scores {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.score-item {
  text-align: center;
}
.score-num {
  font-size: 24px;
  font-weight: 700;
  color: #ffd54f;
}
.score-label {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 4px;
}
.result-comment {
  font-size: 13px;
  line-height: 1.6;
  opacity: 0.9;
}
/* 心情日记面板 */
.mood-panel {
  background: linear-gradient(135deg, #e8f5e9, #fff3e0);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
}
.mood-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.mood-title {
  font-size: 18px;
  font-weight: 700;
  color: #333;
}
.mood-close {
  background: #f5f5f5;
  border: none;
  color: #666;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.mood-question {
  font-size: 16px;
  color: #333;
  margin-bottom: 16px;
  text-align: center;
}
.mood-emojis {
  display: flex;
  justify-content: space-around;
  margin-bottom: 20px;
}
.mood-emoji {
  text-align: center;
  cursor: pointer;
  padding: 12px;
  border-radius: 12px;
  transition: all 0.3s;
}
.mood-emoji:hover {
  background: rgba(255,255,255,0.5);
}
.mood-emoji.selected {
  background: #fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: scale(1.1);
}
.m-emoji {
  font-size: 32px;
  margin-bottom: 6px;
}
.m-label {
  font-size: 12px;
  color: #666;
}
.mood-chat {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.mood-ai {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
}
.mood-curve {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
}
.curve-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}
.welcome-card {
  background: #fff;
  border-radius: 16px;
  padding: 26px 20px 20px;
  text-align: center;
  box-shadow: 0 4px 16px rgba(26, 42, 74, 0.06);
  margin-top: 16px;
  position: relative;
  overflow: hidden;
}

/* 粒子动画 */
.particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.particle {
  position: absolute;
  bottom: -10px;
  width: 6px;
  height: 6px;
  background: linear-gradient(135deg, #c41e3a, #ff6b6b);
  border-radius: 50%;
  opacity: 0.3;
  animation: float-up linear infinite;
}
@keyframes float-up {
  0% {
    transform: translateY(0) rotate(0deg);
    opacity: 0.3;
  }
  50% {
    opacity: 0.6;
  }
  100% {
    transform: translateY(-300px) rotate(360deg);
    opacity: 0;
  }
}
.welcome-emoji {
  font-size: 34px;
  margin-bottom: 6px;
}
.welcome-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2a4a;
  margin: 0 0 6px;
}
.welcome-sub {
  font-size: 13px;
  color: #6b7a99;
  margin: 0 0 16px;
}

/* AI角色选择 */
.role-select {
  margin-bottom: 16px;
}
.role-title {
  font-size: 13px;
  color: #666;
  margin-bottom: 10px;
}
.role-list {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.role {
  flex: 1;
  max-width: 100px;
  padding: 10px;
  border-radius: 12px;
  border: 2px solid #e8ecf2;
  cursor: pointer;
  transition: all 0.2s;
  background: #f8f9fc;
}
.role:hover {
  border-color: #c41e3a;
  transform: translateY(-2px);
}
.role.active {
  border-color: #c41e3a;
  background: #fff5f6;
  box-shadow: 0 4px 12px rgba(196, 30, 58, 0.15);
}
.role-emoji {
  font-size: 24px;
  margin-bottom: 4px;
}
.role-name {
  font-size: 12px;
  color: #333;
  font-weight: 600;
}

/* 学习对战 */
.battle-card {
  margin-top: 16px;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  color: #fff;
  text-align: center;
}
.battle-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 12px;
}
.battle-body {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  margin-bottom: 12px;
}
.battle-player {
  flex: 1;
}
.player-avatar {
  font-size: 32px;
  margin-bottom: 4px;
}
.player-name {
  font-size: 12px;
  opacity: 0.9;
}
.player-score {
  font-size: 18px;
  font-weight: 700;
  margin-top: 2px;
}
.battle-vs {
  font-size: 20px;
  font-weight: 900;
  opacity: 0.8;
}
.battle-btn {
  background: #fff;
  color: #667eea;
  border: none;
  border-radius: 12px;
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.battle-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(0,0,0,0.2);
}
.quick-chips {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chip {
  padding: 10px 14px;
  background: #f3f5f9;
  border: 1px solid #e6ebf2;
  border-radius: 10px;
  font-size: 13px;
  color: #3a4a6a;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}
.chip:hover {
  background: #fff5f5;
  border-color: #c8161e;
  color: #c8161e;
}

.msg-row {
  display: flex;
  margin-bottom: 14px;
  align-items: flex-end;
  gap: 8px;
  animation: fadeUp 0.25s ease;
}
@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
.msg-row.me {
  justify-content: flex-end;
}
.mini-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1a2a4a, #2c4a82);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.mini-avatar.me {
  background: linear-gradient(135deg, #c8161e, #e63946);
}
.bubble {
  max-width: 72%;
  padding: 10px 13px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}
.bubble.me {
  background: linear-gradient(135deg, #c8161e, #e63946);
  color: #fff;
  border-radius: 16px 16px 4px 16px;
  box-shadow: 0 3px 10px rgba(200, 22, 30, 0.2);
}
.bubble.bot {
  background: #fff;
  color: #2c3e50;
  border-radius: 16px 16px 16px 4px;
  box-shadow: 0 2px 8px rgba(26, 42, 74, 0.08);
}
.bubble-content :deep(strong) {
  color: #c8161e;
  font-weight: 600;
}
.typing {
  padding: 14px 16px !important;
  min-width: 40px;
}
.typing-cursor {
  display: inline-block;
  width: 3px;
  height: 18px;
  background: #c41e3a;
  vertical-align: middle;
  animation: cursor-blink 1s infinite;
}
@keyframes cursor-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  40% {
    opacity: 1;
    transform: scale(1);
  }
}

.input-area {
  padding: 10px 16px 12px;
  background: #fff;
  border-top: 1px solid #e8ecf1;
}
.input-card {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  background: #f5f7fa;
  border: 1px solid #e6ebf2;
  border-radius: 14px;
  padding: 8px;
  transition: all 0.2s;
}
.input-card:focus-within {
  border-color: #1a2a4a;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(26, 42, 74, 0.08);
}
.chat-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 6px 8px;
  font-size: 14px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  max-height: 120px;
}
.send-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  background: linear-gradient(135deg, #1a2a4a, #2c4a82);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 42, 74, 0.3);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.input-tip {
  text-align: center;
  font-size: 11px;
  color: #aab4c0;
  margin-top: 6px;
}
.notice-bar {
  margin: 0 16px 8px;
  padding: 8px 12px;
  background: #fff3f3;
  color: #c8161e;
  border-radius: 8px;
  font-size: 12px;
}
/* 隐藏 VTJ 开发态浮窗按钮 */
#vtjLink {
  display: none !important;
}

/* 窄屏：历史栏变抽屉 */
@media (max-width: 720px) {
  .history-panel {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(-100%);
    transition: transform 0.25s;
    box-shadow: 4px 0 16px rgba(0, 0, 0, 0.2);
  }
  .ai-layout.drawer_open .history-panel {
    transform: translateX(0);
  }
  .ai-layout.drawer_open .mask {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 99;
  }
  .hamburger {
    display: inline-flex;
  }
  .header-title-row {
    flex-wrap: wrap;
  }
  .kb-entry {
    padding: 1px 8px;
    font-size: 10px;
  }
}
</style>
