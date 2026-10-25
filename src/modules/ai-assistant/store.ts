/**
 * 联考小智（ai-assistant）域 Store —— 模块⑦「联考小智」实现
 *
 * 状态契约继承外壳（loading/error/initialized/ready），并扩展会话业务状态。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchSessions,
  sendChat,
  createSession,
  fetchSessionMessages,
  deleteSession,
  type ChatScene,
  type ChatSessionItem,
  type ChatMessageItem
} from './api';

/** 本域状态（外壳字段 + 会话业务字段） */
export interface AiAssistantState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
  sessions: ChatSessionItem[];
  activeSessionId: number | null;
  messages: ChatMessageItem[];
}

export function createAiAssistantInitialState(): AiAssistantState {
  return {
    loading: false,
    error: null,
    initialized: false,
    sessions: [],
    activeSessionId: null,
    messages: []
  };
}

export const useAiAssistantStore = defineStore('ai-assistant', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);
  const sessions = ref<ChatSessionItem[]>([]);
  const activeSessionId = ref<number | null>(null);
  const messages = ref<ChatMessageItem[]>([]);

  const ready = computed(() => initialized.value && error.value === null);

  function reset(): void {
    const initial = createAiAssistantInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    sessions.value = initial.sessions;
    activeSessionId.value = initial.activeSessionId;
    messages.value = initial.messages;
  }

  /** 加载会话列表（幂等，失败置 error） */
  async function loadSessions(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const res = await fetchSessions();
      sessions.value = res.items;
      initialized.value = true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载会话列表失败';
    } finally {
      loading.value = false;
    }
  }

  /** 打开某会话并加载历史消息 */
  async function openSession(sessionId: number): Promise<void> {
    activeSessionId.value = sessionId;
    error.value = null;
    loading.value = true;
    try {
      const res = await fetchSessionMessages(sessionId);
      messages.value = res.items;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载会话历史失败';
    } finally {
      loading.value = false;
    }
  }

  /** 新建会话并加入列表 */
  async function newSession(title?: string, scene: ChatScene = 'qa'): Promise<ChatSessionItem> {
    const session = await createSession(title, scene);
    sessions.value = [session, ...sessions.value];
    activeSessionId.value = session.session_id;
    messages.value = [];
    return session;
  }

  /** 发送消息；成功后把 user/assistant 两条追加进 messages */
  async function sendMessage(text: string, scene: ChatScene = 'qa'): Promise<string> {
    error.value = null;
    loading.value = true;
    try {
      const res = await sendChat(text, activeSessionId.value ?? undefined, scene);
      // 新建会话场景：后端返回的 session_id 可能不同于本地 active
      if (activeSessionId.value === null || activeSessionId.value !== res.session_id) {
        activeSessionId.value = res.session_id;
        await loadSessions();
      }
      messages.value.push(
        { message_id: Date.now() + 1, role: 'user', content: text, create_time: new Date().toISOString() },
        { message_id: Date.now() + 2, role: 'assistant', content: res.reply, create_time: new Date().toISOString() }
      );
      return res.reply;
    } catch (e) {
      error.value = e instanceof Error ? e.message : '发送消息失败';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  /** 删除会话（软删）并从列表移除 */
  async function removeSession(sessionId: number): Promise<void> {
    await deleteSession(sessionId);
    sessions.value = sessions.value.filter((s) => s.session_id !== sessionId);
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null;
      messages.value = [];
    }
  }

  /** 兼容外壳契约：加载本域数据（= 会话列表） */
  async function load(): Promise<void> {
    await loadSessions();
  }

  return {
    loading,
    error,
    initialized,
    ready,
    sessions,
    activeSessionId,
    messages,
    reset,
    load,
    loadSessions,
    openSession,
    newSession,
    sendMessage,
    removeSession
  };
});
