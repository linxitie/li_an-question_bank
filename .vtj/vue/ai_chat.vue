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
          @click="openSession(s)"
        >
          <div class="hi-main">
            <div class="hi-title">{{ s.title || '新会话' }}</div>
            <div class="hi-meta">{{ sceneLabel(s.scene) }} · {{ fmtTime(s.update_time) }}</div>
          </div>
          <div class="hi-del" @click.stop="removeSession(s)">×</div>
        </div>
        <div v-if="sessions.length === 0" class="history-empty">还没有历史对话</div>
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
            </div>
            <div class="header-sub">你的公安联考专属备考伙伴</div>
          </div>
        </div>
        <div class="scene-tabs">
          <div
            v-for="s in sceneOptions"
            :key="s.value"
            class="scene-tab"
            :class="{ active: state.scene === s.value }"
            @click="switchScene(s.value)"
          >
            <XIcon :icon="s.icon" :size="14"></XIcon>
            <span>{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- 消息流 -->
      <div class="message-list" ref="messageList">
        <div v-if="state.messages.length === 0" class="welcome-card">
          <div class="welcome-emoji">🎯</div>
          <p class="welcome-title">你好，我是联考小智</p>
          <p class="welcome-sub">选个场景，从下面挑一个问题开始问我</p>
          <div class="quick-chips">
            <div v-for="q in quickQuestions" :key="q" class="chip" @click="quickAsk(q)">{{ q }}</div>
          </div>
        </div>

        <div
          v-for="(m, idx) in state.messages"
          :key="idx"
          class="msg-row"
          :class="m.role === 'user' ? 'me' : 'bot'"
        >
          <div v-if="m.role !== 'user'" class="mini-avatar">智</div>
          <div class="bubble" :class="m.role === 'user' ? 'me' : 'bot'">
            <div class="bubble-content" v-html="renderMd(m.content)"></div>
          </div>
          <div v-if="m.role === 'user'" class="mini-avatar me">我</div>
        </div>

        <div v-if="state.loading" class="msg-row bot">
          <div class="mini-avatar">智</div>
          <div class="bubble bot typing">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>

      <!-- 操作提示（加载/删除失败时显示，发送后自动消失） -->
      <div v-if="state.notice" class="notice-bar">{{ state.notice }}</div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-card">
          <textarea
            v-model="state.input"
            :placeholder="inputPlaceholder"
            class="chat-input"
            rows="2"
            @keydown.enter.exact.prevent="send"
          ></textarea>
          <button class="send-btn" :disabled="state.loading || !state.input.trim()" @click="send">
            <XIcon :icon="Promotion" :size="16" color="#fff"></XIcon>
            <span>发送</span>
          </button>
        </div>
        <div class="input-tip">Enter 发送 · Shift+Enter 换行</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, ref, onMounted, nextTick } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Promotion, ReadingLamp, Document, TrophyBase, Plus, Menu } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';

  export default defineComponent({
    name: 'AiAssistant',
    components: { XIcon },
    setup() {
      const provider = useProvider({ id: 'ai_chat', version: '20261027001' });
      const state = reactive({
        scene: 'qa',
        input: '',
        messages: [],
        sessionId: null,
        loading: false,
        notice: '',
      });
      const sessions = ref([]);
      const drawerOpen = ref(false);

      const sceneOptions = [
        { value: 'psychological', label: '心理疏导', icon: ReadingLamp },
        { value: 'qa', label: '答疑解惑', icon: Document },
        { value: 'advice', label: '提升建议', icon: TrophyBase },
      ];

      const inputPlaceholderMap = {
        psychological: '最近压力大吗？跟我说说…',
        qa: '问一个行测 / 申论 / 公专的知识点吧',
        advice: '想怎么复习？我来给你出主意',
      };

      const quickQuestions = [
        '行测资料分析总是做不完怎么办？',
        '申论大作文总是跑题，怎么破？',
        '最近模考成绩上不去，有点焦虑',
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
        } catch (e) { return ''; }
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
          const hRes = await window.__VTJ_AUTH__.apiFetch(`/api/llm/sessions/${sid}/messages`);
          const hData = await hRes.json();
          if (hRes.ok && hData.items) {
            state.messages = hData.items.map((m) => ({ role: m.role, content: m.content }));
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
          const r = await window.__VTJ_AUTH__.apiFetch(`/api/llm/sessions/${s.session_id}`, { method: 'DELETE' });
          if (!r.ok) {
            state.notice = '删除失败，请稍后重试';
            return;
          }
          sessions.value = sessions.value.filter((x) => x.session_id !== s.session_id);
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
            body: JSON.stringify({ message: text, session_id: state.sessionId, scene: state.scene }),
          });
          const data = await res.json();
          state.loading = false;
          if (res.ok && data.reply) {
            state.sessionId = data.session_id;
            await typewriter(data.reply);
            loadSessions();
          } else {
            state.messages.push({ role: 'assistant', content: data.detail || '抱歉，我暂时回答不了。' });
          }
        } catch (e) {
          state.loading = false;
          state.messages.push({ role: 'assistant', content: '网络异常，请稍后再试。' });
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

      onMounted(() => {
        state.__listEl = document.querySelector('.ai-chat-page .message-list');
        loadSessions();
      });

      return {
        state, sessions, drawerOpen,
        provider,
        sceneOptions, quickQuestions,
        inputPlaceholder: '输入消息…',
        send, quickAsk, switchScene, newChat, goBack,
        openSession, removeSession,
        sceneLabel, fmtTime, renderMd,
        Plus, Menu, Promotion,
      };
    },
  });
</script>

<style lang="css" scoped>
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
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .history-title { font-size: 13px; color: rgba(255,255,255,0.7); letter-spacing: 1px; }
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
  .new-btn:hover { background: #e63946; }
  .history-list { flex: 1; overflow-y: auto; padding: 8px; }
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
  .history-item:hover { background: rgba(255,255,255,0.08); }
  .history-item.active { background: rgba(200,22,30,0.25); border-left: 3px solid #c8161e; }
  .hi-main { flex: 1; min-width: 0; }
  .hi-title {
    font-size: 13px;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hi-meta { font-size: 11px; color: rgba(255,255,255,0.45); margin-top: 2px; }
  .hi-del {
    opacity: 0;
    color: #ff8a8a;
    font-size: 16px;
    padding: 0 4px;
  }
  .history-item:hover .hi-del { opacity: 1; }
  .history-empty { text-align: center; font-size: 12px; color: rgba(255,255,255,0.35); margin-top: 30px; }
  .mask { display: none; }

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
    position: absolute; right: -40px; top: -40px;
    width: 160px; height: 160px;
    background: radial-gradient(circle, rgba(200,22,30,0.18) 0%, transparent 70%);
    border-radius: 50%;
  }
  .header-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
  .hamburger {
    background: transparent; border: none; cursor: pointer;
    padding: 4px; display: none;
  }
  .back-btn {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    color: #fff;
    width: 30px; height: 30px;
    border-radius: 50%;
    font-size: 22px;
    line-height: 1;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
  }
  .back-btn:hover { background: rgba(255,255,255,0.25); }
  .ai-avatar {
    width: 40px; height: 40px; border-radius: 50%;
    background: linear-gradient(135deg, #c8161e, #e63946);
    color: #fff; font-size: 16px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 12px rgba(200,22,30,0.4);
  }
  .header-meta { flex: 1; }
  .header-title-row { display: flex; align-items: center; gap: 10px; }
  .header-title { font-size: 17px; font-weight: 700; }
  .online-dot { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #9fe6b0; }
  .online-dot i { width: 6px; height: 6px; background: #4ade80; border-radius: 50%; box-shadow: 0 0 6px #4ade80; }
  .header-sub { font-size: 12px; color: rgba(255,255,255,0.7); margin-top: 2px; }
  .scene-tabs { display: flex; gap: 8px; position: relative; z-index: 1; }
  .scene-tab {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 5px 13px; border-radius: 18px; font-size: 13px;
    color: rgba(255,255,255,0.85);
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.18);
    cursor: pointer; transition: all 0.2s;
  }
  .scene-tab.active { background: #c8161e; border-color: #c8161e; color: #fff; box-shadow: 0 4px 10px rgba(200,22,30,0.35); }

  .message-list { flex: 1; overflow-y: auto; padding: 18px; }
  .welcome-card {
    background: #fff; border-radius: 16px; padding: 26px 20px 20px;
    text-align: center; box-shadow: 0 4px 16px rgba(26,42,74,0.06);
    margin-top: 16px;
  }
  .welcome-emoji { font-size: 34px; margin-bottom: 6px; }
  .welcome-title { font-size: 16px; font-weight: 600; color: #1a2a4a; margin: 0 0 6px; }
  .welcome-sub { font-size: 13px; color: #8899aa; margin: 0 0 16px; }
  .quick-chips { display: flex; flex-direction: column; gap: 8px; }
  .chip {
    padding: 10px 14px; background: #f3f5f9;
    border: 1px solid #e6ebf2; border-radius: 10px;
    font-size: 13px; color: #3a4a6a; cursor: pointer; text-align: left;
    transition: all 0.2s;
  }
  .chip:hover { background: #fff5f5; border-color: #c8161e; color: #c8161e; }

  .msg-row { display: flex; margin-bottom: 14px; align-items: flex-end; gap: 8px; animation: fadeUp 0.25s ease; }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  .msg-row.me { justify-content: flex-end; }
  .mini-avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: linear-gradient(135deg, #1a2a4a, #2c4a82);
    color: #fff; font-size: 11px; font-weight: 600;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .mini-avatar.me { background: linear-gradient(135deg, #c8161e, #e63946); }
  .bubble { max-width: 72%; padding: 10px 13px; font-size: 14px; line-height: 1.65; word-break: break-word; }
  .bubble.me {
    background: linear-gradient(135deg, #c8161e, #e63946);
    color: #fff; border-radius: 16px 16px 4px 16px;
    box-shadow: 0 3px 10px rgba(200,22,30,0.2);
  }
  .bubble.bot {
    background: #fff; color: #2c3e50;
    border-radius: 16px 16px 16px 4px;
    box-shadow: 0 2px 8px rgba(26,42,74,0.08);
  }
  .bubble-content :deep(strong) { color: #c8161e; font-weight: 600; }
  .typing { padding: 14px 16px !important; }
  .typing .dot {
    display: inline-block; width: 7px; height: 7px;
    background: #aab4c0; border-radius: 50%; margin-right: 4px;
    animation: blink 1.2s infinite;
  }
  .typing .dot:nth-child(2) { animation-delay: 0.2s; }
  .typing .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes blink {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1); }
  }

  .input-area { padding: 10px 16px 12px; background: #fff; border-top: 1px solid #e8ecf1; }
  .input-card {
    display: flex; gap: 10px; align-items: flex-end;
    background: #f5f7fa; border: 1px solid #e6ebf2;
    border-radius: 14px; padding: 8px; transition: all 0.2s;
  }
  .input-card:focus-within {
    border-color: #1a2a4a; background: #fff;
    box-shadow: 0 0 0 3px rgba(26,42,74,0.08);
  }
  .chat-input {
    flex: 1; border: none; background: transparent;
    padding: 6px 8px; font-size: 14px; resize: none; outline: none;
    font-family: inherit; line-height: 1.5; max-height: 120px;
  }
  .send-btn {
    display: flex; align-items: center; gap: 6px;
    padding: 9px 18px;
    background: linear-gradient(135deg, #1a2a4a, #2c4a82);
    color: #fff; border: none; border-radius: 10px;
    font-size: 14px; cursor: pointer; transition: all 0.2s;
  }
  .send-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(26,42,74,0.3); }
  .send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .input-tip { text-align: center; font-size: 11px; color: #aab4c0; margin-top: 6px; }
  .notice-bar {
    margin: 0 16px 8px; padding: 8px 12px;
    background: #fff3f3; color: #c8161e; border-radius: 8px;
    font-size: 12px;
  }
  /* 隐藏 VTJ 开发态浮窗按钮 */
  #vtjLink { display: none !important; }

  /* 窄屏：历史栏变抽屉 */
  @media (max-width: 720px) {
    .history-panel {
      position: fixed; left: 0; top: 0; bottom: 0; z-index: 100;
      transform: translateX(-100%); transition: transform 0.25s;
      box-shadow: 4px 0 16px rgba(0,0,0,0.2);
    }
    .ai-layout.drawer_open .history-panel { transform: translateX(0); }
    .ai-layout.drawer_open .mask {
      display: block; position: fixed; inset: 0;
      background: rgba(0,0,0,0.4); z-index: 99;
    }
    .hamburger { display: inline-flex; }
  }
</style>
