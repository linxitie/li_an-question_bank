<!-- 联考小智 - AI 聊天页（ChatGPT风格重新设计） -->
<template>
  <div class="ai-layout" :class="{ drawer_open: drawerOpen }">
    <!-- 左侧历史对话栏 -->
    <aside class="sidebar">
      <div class="sidebar-head">
        <button class="new-chat-btn" @click="newChat">
          <Plus :size="16" />
          <span>新对话</span>
        </button>
      </div>
      <div class="sidebar-list">
        <div
          v-for="s in sessions"
          :key="s.session_id"
          class="history-item"
          :class="{ active: s.session_id === state.sessionId }"
          @click="openSession(s)">
          <span class="hi-title">{{ s.title || '新会话' }}</span>
          <span class="hi-del" @click.stop="removeSession(s)">×</span>
        </div>
        <div v-if="sessions.length === 0" class="sidebar-empty">
          还没有历史对话
        </div>
      </div>
      <!-- 长期记忆 -->
      <div class="sidebar-memories">
        <div class="memories-title">🧠 小智记住你的</div>
        <div v-for="m in state.memories" :key="m.memory_id" class="memory-item">
          {{ m.content }}
        </div>
        <div v-if="state.memories.length === 0" class="memories-empty">
          聊得越多，小智越懂你
        </div>
      </div>
    </aside>

    <!-- 移动端遮罩 -->
    <div v-if="drawerOpen" class="mask" @click="drawerOpen = false"></div>

    <!-- 主区域 -->
    <div class="main-area">
      <!-- 顶部栏 -->
      <header class="topbar">
        <button class="hamburger" @click="drawerOpen = !drawerOpen">
          <Menu :size="20" />
        </button>
        <div class="topbar-title">
          <span class="title-text">联考小智</span>
          <span v-if="state.agentName" class="agent-badge">{{
            state.agentName
          }}</span>
        </div>
        <!-- 模式切换 -->
        <div class="mode-switch">
          <button
            class="mode-btn"
            :class="{ active: !state.workMode }"
            @click="switchMode(false)">
            聊天
          </button>
          <button
            class="mode-btn"
            :class="{ active: state.workMode }"
            @click="switchMode(true)">
            工作台
          </button>
        </div>
      </header>

      <!-- 消息列表区 -->
      <div class="message-list" ref="messageList">
        <!-- 工作台模式 -->
        <div v-if="state.workMode" class="work-panel">
          <div class="work-welcome">
            <h2 class="work-title">选择一个备考任务</h2>
            <p class="work-sub">点选任务 → 填参数 → 生成可直接用的结果</p>
          </div>
          <div class="work-grid">
            <div
              v-for="t in state.workTasks"
              :key="t.task_id"
              class="work-card"
              :class="{
                open: state.activeTask && state.activeTask.task_id === t.task_id
              }"
              @click="selectTask(t)">
              <div class="wc-title">{{ t.title }}</div>
              <div class="wc-desc">{{ t.desc }}</div>
              <div class="wc-agent">{{ agentLabel(t.agent) }}</div>
            </div>
          </div>

          <!-- 选中任务后的表单 -->
          <div v-if="state.activeTask" class="work-form" @click.stop>
            <div
              v-for="f in state.activeTask.fields"
              :key="f.key"
              class="form-row">
              <label class="form-label"
                >{{ f.label }}{{ f.required ? ' *' : '' }}</label
              >
              <select
                v-if="f.type === 'select'"
                v-model="state.workParams[f.key]"
                class="form-input">
                <option value="">请选择</option>
                <option v-for="opt in f.options" :key="opt" :value="opt">
                  {{ opt }}
                </option>
              </select>
              <input
                v-else-if="f.type === 'number'"
                v-model="state.workParams[f.key]"
                type="number"
                class="form-input"
                :placeholder="f.placeholder || ''" />
              <textarea
                v-else
                v-model="state.workParams[f.key]"
                class="form-input"
                rows="3"
                :placeholder="f.placeholder || ''"></textarea>
            </div>
            <button
              class="run-btn"
              :disabled="state.workRunning"
              @click="runWorkTask(state.activeTask)">
              {{ state.workRunning ? '⏳ 生成中...' : '🚀 开始生成' }}
            </button>
          </div>

          <!-- 工作台结果 -->
          <div v-if="state.workReply" class="work-result">
            <div class="wr-header">
              <span class="wr-title"
                >📋 {{ state.workTitle || '生成结果' }}</span
              >
              <button
                class="import-btn"
                :disabled="state.workImporting || state.workImportDone"
                @click="importToToday">
                {{
                  state.workImporting
                    ? '⏳ 写入中...'
                    : state.workImportDone
                      ? '✅ 已写入今日任务'
                      : '📌 一键写入今日任务'
                }}
              </button>
            </div>
            <div class="wr-body" v-html="renderMd(state.workReply)"></div>
          </div>
          <div v-if="state.workNotice" class="work-notice">
            {{ state.workNotice }}
          </div>
        </div>

        <!-- 聊天模式 - 欢迎界面 -->
        <div
          v-if="!state.workMode && state.messages.length === 0"
          class="welcome">
          <h1 class="welcome-title">我们要做什么？</h1>
          <p class="welcome-sub">
            联考小智帮你备考公安联考，从下面挑一个功能开始
          </p>
          <div class="welcome-grid">
            <div
              class="wg-item"
              @click="quickAsk('行测资料分析总是做不完怎么办？')">
              <div class="wg-icon">📊</div>
              <div class="wg-title">行测提分</div>
              <div class="wg-desc">资料分析、判断推理快速突破</div>
            </div>
            <div
              class="wg-item"
              @click="quickAsk('申论大作文总是跑题，怎么破？')">
              <div class="wg-icon">✍️</div>
              <div class="wg-title">申论写作</div>
              <div class="wg-desc">大作文、归纳概括高分技巧</div>
            </div>
            <div
              class="wg-item"
              @click="quickAsk('最近模考成绩上不去，有点焦虑')">
              <div class="wg-icon">💭</div>
              <div class="wg-title">心理疏导</div>
              <div class="wg-desc">缓解焦虑，调整备考状态</div>
            </div>
            <div class="wg-item" @click="quickAsk('帮我选个岗位')">
              <div class="wg-icon">🎯</div>
              <div class="wg-title">选岗建议</div>
              <div class="wg-desc">根据成绩和意向推荐岗位</div>
            </div>
          </div>
        </div>

        <!-- 聊天模式 - 消息流 -->
        <div
          v-if="!state.workMode && state.messages.length > 0"
          class="messages">
          <div
            v-for="(m, idx) in state.messages"
            :key="idx"
            class="msg-row"
            :class="m.role">
            <div class="msg-avatar">{{ m.role === 'user' ? '我' : '智' }}</div>
            <div class="msg-content-wrap">
              <div class="msg-bubble" v-html="renderMd(m.content)"></div>
              <!-- AI消息的操作按钮 -->
              <div
                v-if="m.role === 'assistant' && m.content"
                class="msg-actions">
                <button
                  class="action-btn"
                  @click="copyMessage(m.content)"
                  title="复制">
                  📋
                </button>
                <button
                  class="action-btn"
                  @click="regenerateMessage(idx)"
                  title="重新生成">
                  🔄
                </button>
                <button
                  class="action-btn"
                  @click="likeMessage(idx, true)"
                  title="赞">
                  👍
                </button>
                <button
                  class="action-btn"
                  @click="likeMessage(idx, false)"
                  title="踩">
                  👎
                </button>
              </div>
            </div>
          </div>
          <!-- 加载中 -->
          <div v-if="state.loading" class="msg-row assistant">
            <div class="msg-avatar">智</div>
            <div class="msg-bubble typing">正在思考...</div>
          </div>
        </div>
      </div>

      <!-- 底部输入区 -->
      <div class="input-area" v-if="!state.workMode">
        <!-- 快捷指令面板 -->
        <div v-if="showQuickCommands" class="quick-panel">
          <div class="qp-item" @click="useQuickCommand('帮我制定今日学习计划')">
            📋 制定学习计划
          </div>
          <div class="qp-item" @click="useQuickCommand('分析我的错题')">
            📊 错题分析
          </div>
          <div class="qp-item" @click="useQuickCommand('申论批改')">
            ✍️ 申论批改
          </div>
          <div class="qp-item" @click="useQuickCommand('行测错题诊断')">
            📈 行测诊断
          </div>
          <div class="qp-item" @click="useQuickCommand('公专法条梳理')">
            ⚖️ 法条速查
          </div>
          <div class="qp-item" @click="useQuickCommand('选岗建议')">
            🎯 选岗建议
          </div>
          <div class="qp-item" @click="useQuickCommand('模拟面试')">
            🎤 面试模拟
          </div>
          <div class="qp-item" @click="useQuickCommand('心理疏导')">
            💭 心理疏导
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-box">
          <div class="input-toolbar">
            <button class="tool-btn" title="上传文件" @click="uploadFile">
              📎
            </button>
            <button class="tool-btn" title="语音输入" @click="voiceInput">
              🎤
            </button>
            <button
              class="tool-btn"
              :class="{ active: showQuickCommands }"
              title="快捷指令"
              @click="showQuickCommands = !showQuickCommands">
              ➕
            </button>
          </div>
          <textarea
            v-model="state.input"
            :placeholder="inputPlaceholder"
            class="chat-input"
            rows="2"
            @keydown.enter.exact.prevent="send"></textarea>
          <button
            class="send-btn"
            :disabled="!state.input.trim() || state.loading"
            @click="send">
            <Promotion :size="18" />
          </button>
        </div>
      </div>

      <!-- 提示 -->
      <div v-if="state.notice" class="toast">{{ state.notice }}</div>
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
      agentName: '',
      memories: [],
      // 工作台模式
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
      workNotice: ''
    });
    const showQuickCommands = ref(false);
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

    // Markdown 渲染
    function renderMd(text) {
      if (!text) return '';
      let s = String(text);
      s = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      s = s.replace(
        /```(\w*)\n([\s\S]*?)```/g,
        '<pre style="background:#f5f7fa;padding:12px;border-radius:8px;overflow-x:auto;margin:8px 0;"><code>$2</code></pre>'
      );
      s = s.replace(
        /`([^`]+)`/g,
        '<code style="background:#f5f7fa;padding:2px 6px;border-radius:4px;font-size:13px;">$1</code>'
      );
      s = s.replace(
        /^### (.*)$/gm,
        '<div style="font-size:15px;font-weight:bold;color:#1a2a4a;margin:12px 0 6px;">$1</div>'
      );
      s = s.replace(
        /^## (.*)$/gm,
        '<div style="font-size:16px;font-weight:bold;color:#1a2a4a;margin:14px 0 8px;">$1</div>'
      );
      s = s.replace(
        /^# (.*)$/gm,
        '<div style="font-size:18px;font-weight:bold;color:#1a2a4a;margin:16px 0 10px;">$1</div>'
      );
      s = s.replace(
        /^&gt; (.*)$/gm,
        '<div style="border-left:3px solid #c8161e;padding-left:12px;margin:8px 0;color:#666;">$1</div>'
      );
      s = s.replace(
        /\*\*([^*]+)\*\*/g,
        '<strong style="color:#c8161e;">$1</strong>'
      );
      s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      s = s.replace(/^\s*[-•]\s+/gm, '<br>• ');
      s = s.replace(/^\s*\d+\.\s+/gm, '<br>');
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

    // 文件上传
    function uploadFile() {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*,.pdf,.doc,.docx';
      input.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
          state.notice = `📎 已选择文件：${file.name}（上传功能即将上线）`;
          setTimeout(() => (state.notice = ''), 3000);
        }
      };
      input.click();
    }

    // 语音输入
    function voiceInput() {
      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = 'zh-CN';
        recognition.onstart = () => {
          state.notice = '🎤 正在录音，请说话...';
        };
        recognition.onresult = (event) => {
          const text = event.results[0][0].transcript;
          state.input = text;
          state.notice = '';
        };
        recognition.onerror = () => {
          state.notice = '🎤 语音识别失败，请重试';
          setTimeout(() => (state.notice = ''), 2000);
        };
        recognition.start();
      } else {
        state.notice = '🎤 你的浏览器不支持语音输入，请用Chrome浏览器';
        setTimeout(() => (state.notice = ''), 3000);
      }
    }

    function useQuickCommand(cmd) {
      showQuickCommands.value = false;
      state.input = cmd;
      send();
    }

    // 消息操作
    function copyMessage(content) {
      navigator.clipboard.writeText(content).then(() => {
        state.notice = '✅ 已复制到剪贴板';
        setTimeout(() => (state.notice = ''), 2000);
      });
    }

    function regenerateMessage(idx) {
      for (let i = idx - 1; i >= 0; i--) {
        if (state.messages[i].role === 'user') {
          const userText = state.messages[i].content;
          state.messages.splice(idx, 1);
          state.input = userText;
          send();
          break;
        }
      }
    }

    function likeMessage(idx, isLike) {
      state.notice = isLike
        ? '👍 感谢点赞！你的反馈对我很重要'
        : '👎 我们会改进的，抱歉这次没帮到你';
      setTimeout(() => (state.notice = ''), 2000);
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

    async function loadMemories() {
      try {
        const res = await window.__VTJ_AUTH__.apiFetch('/api/agent/memories');
        const d = await res.json();
        if (res.ok) {
          state.memories = d.items || [];
        }
      } catch (e) {}
    }

    onMounted(() => {
      state.__listEl = document.querySelector('.message-list');
      loadSessions();
      loadMemories();
    });

    return {
      state,
      sessions,
      drawerOpen,
      showQuickCommands,
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
      selectTask,
      runWorkTask,
      importToToday,
      uploadFile,
      voiceInput,
      useQuickCommand,
      copyMessage,
      regenerateMessage,
      likeMessage,
      Plus,
      Menu,
      Promotion
    };
  }
});
</script>

<style lang="css" scoped>
/* ===== 全局布局 ===== */
.ai-layout {
  display: flex;
  height: 100vh;
  background: #f7f7f8;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Microsoft YaHei', sans-serif;
}

/* ===== 左侧边栏 ===== */
.sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e5e5e5;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-head {
  padding: 12px;
}
.new-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #c8161e;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.new-chat-btn:hover {
  background: #a80f16;
}
.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #333;
  margin-bottom: 2px;
  transition: background 0.15s;
}
.history-item:hover {
  background: #f5f5f5;
}
.history-item.active {
  background: #fdecec;
  color: #c8161e;
}
.hi-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.hi-del {
  margin-left: 8px;
  color: #999;
  font-size: 16px;
  padding: 0 4px;
}
.hi-del:hover {
  color: #c8161e;
}
.sidebar-empty {
  padding: 20px;
  text-align: center;
  color: #999;
  font-size: 13px;
}
.sidebar-memories {
  border-top: 1px solid #e5e5e5;
  padding: 12px;
}
.memories-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}
.memory-item {
  font-size: 12px;
  color: #555;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
}
.memories-empty {
  font-size: 12px;
  color: #999;
}

/* ===== 主区域 ===== */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* ===== 顶部栏 ===== */
.topbar {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #e5e5e5;
  background: #fff;
}
.hamburger {
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
}
.topbar-title {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}
.title-text {
  font-size: 16px;
  font-weight: 600;
  color: #1a2a4a;
}
.agent-badge {
  font-size: 12px;
  color: #c8161e;
  background: #fdecec;
  padding: 2px 8px;
  border-radius: 10px;
}
.mode-switch {
  display: flex;
  background: #f0f0f0;
  border-radius: 8px;
  padding: 2px;
}
.mode-btn {
  padding: 6px 16px;
  border: none;
  background: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  color: #666;
  transition: all 0.2s;
}
.mode-btn.active {
  background: #fff;
  color: #c8161e;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* ===== 消息列表 ===== */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* ===== 欢迎界面 ===== */
.welcome {
  max-width: 760px;
  margin: 60px auto;
  text-align: center;
}
.welcome-title {
  font-size: 32px;
  font-weight: 700;
  color: #1a2a4a;
  margin: 0 0 12px;
}
.welcome-sub {
  font-size: 15px;
  color: #888;
  margin: 0 0 40px;
}
.welcome-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.wg-item {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  padding: 20px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;
}
.wg-item:hover {
  border-color: #c8161e;
  box-shadow: 0 4px 12px rgba(200, 22, 30, 0.1);
  transform: translateY(-2px);
}
.wg-icon {
  font-size: 24px;
  margin-bottom: 8px;
}
.wg-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2a4a;
  margin-bottom: 4px;
}
.wg-desc {
  font-size: 13px;
  color: #888;
}

/* ===== 消息流 ===== */
.messages {
  max-width: 760px;
  margin: 0 auto;
}
.msg-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.msg-row.user {
  flex-direction: row-reverse;
}
.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}
.msg-row.assistant .msg-avatar {
  background: #c8161e;
  color: #fff;
}
.msg-row.user .msg-avatar {
  background: #1a2a4a;
  color: #fff;
}
.msg-content-wrap {
  max-width: 80%;
}
.msg-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.msg-row.assistant .msg-bubble {
  background: #fff;
  border: 1px solid #e5e5e5;
  color: #333;
}
.msg-row.user .msg-bubble {
  background: #c8161e;
  color: #fff;
}
.msg-bubble.typing {
  color: #999;
  font-style: italic;
}
.msg-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
}
.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 6px;
  border-radius: 4px;
  opacity: 0.6;
  transition: opacity 0.2s;
}
.action-btn:hover {
  opacity: 1;
}

/* ===== 工作台 ===== */
.work-panel {
  max-width: 900px;
  margin: 0 auto;
}
.work-welcome {
  text-align: center;
  margin-bottom: 32px;
  padding: 20px 0;
}
.work-title {
  font-size: 28px;
  font-weight: 700;
  color: #1a2a4a;
  margin: 0 0 8px;
}
.work-sub {
  font-size: 14px;
  color: #888;
}
.work-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}
.work-card {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.work-card:hover {
  border-color: #c8161e;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.work-card.open {
  border-color: #c8161e;
  box-shadow: 0 4px 16px rgba(200, 22, 30, 0.15);
}
.wc-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2a4a;
  margin-bottom: 4px;
}
.wc-desc {
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
}
.wc-agent {
  font-size: 11px;
  color: #c8161e;
  background: #fdecec;
  padding: 2px 8px;
  border-radius: 10px;
  display: inline-block;
}
.work-form {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}
.form-row {
  margin-bottom: 12px;
}
.form-label {
  display: block;
  font-size: 13px;
  color: #333;
  margin-bottom: 6px;
  font-weight: 500;
}
.form-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}
.form-input:focus {
  outline: none;
  border-color: #c8161e;
}
.run-btn {
  width: 100%;
  padding: 12px;
  background: #c8161e;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  margin-top: 8px;
}
.run-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.work-result {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  padding: 20px;
}
.wr-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}
.wr-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2a4a;
}
.import-btn {
  padding: 8px 16px;
  background: #fdecec;
  color: #c8161e;
  border: 1px solid #c8161e;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}
.import-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.wr-body {
  font-size: 14px;
  line-height: 1.6;
}
.work-notice {
  margin-top: 12px;
  padding: 10px;
  background: #fff3cd;
  border-radius: 8px;
  font-size: 13px;
  color: #856404;
}

/* ===== 输入区 ===== */
.input-area {
  padding: 16px 20px;
  background: #f7f7f8;
}
.quick-panel {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  max-width: 760px;
  margin: 0 auto 12px;
}
.qp-item {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}
.qp-item:hover {
  border-color: #c8161e;
  color: #c8161e;
}
.input-box {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 760px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 16px;
  padding: 12px;
}
.input-box:focus-within {
  border-color: #c8161e;
  box-shadow: 0 0 0 3px rgba(200, 22, 30, 0.1);
}
.input-toolbar {
  display: flex;
  gap: 4px;
}
.tool-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  padding: 6px;
  border-radius: 6px;
  transition: background 0.2s;
}
.tool-btn:hover {
  background: #f5f5f5;
}
.tool-btn.active {
  background: #fdecec;
}
.chat-input {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.5;
  max-height: 120px;
  font-family: inherit;
}
.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #c8161e;
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.send-btn:disabled {
  background: #ddd;
  cursor: not-allowed;
}

/* ===== Toast提示 ===== */
.toast {
  position: fixed;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: #1a2a4a;
  color: #fff;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  z-index: 1000;
  animation: fadeIn 0.2s;
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

/* ===== 移动端遮罩 ===== */
.mask {
  display: none;
}

/* ===== 响应式（移动端） ===== */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: -260px;
    top: 0;
    bottom: 0;
    z-index: 100;
    transition: left 0.3s;
  }
  .drawer_open .sidebar {
    left: 0;
  }
  .drawer_open .mask {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99;
  }
  .hamburger {
    display: block;
  }
  .welcome-grid {
    grid-template-columns: 1fr;
  }
  .work-grid {
    grid-template-columns: 1fr;
  }
  .quick-panel {
    grid-template-columns: repeat(2, 1fr);
  }
  .msg-content-wrap {
    max-width: 90%;
  }
}
</style>
