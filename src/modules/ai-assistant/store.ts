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
import {
  nextSuggestions,
  SUGGESTION_BATCH_SIZE,
  OPENING_HINT,
  type SuggestionCategory
} from './suggestions';

/** 本域状态（外壳字段 + 会话业务字段） */
export interface AiAssistantState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
  sessions: ChatSessionItem[];
  activeSessionId: number | null;
  messages: ChatMessageItem[];
  /** A2「动态问题」：当前展示的推荐问题 */
  suggestions: string[];
}

/** A2 推荐问题的取数参数 */
export interface RefreshSuggestionsOptions {
  sessionId?: number | null;
  exclude?: string[];
  size?: number;
  category?: SuggestionCategory;
}

/** 开场问候（供 A1 询问页动画使用） */
export const AI_ASSISTANT_OPENING_HINT = OPENING_HINT;

export function createAiAssistantInitialState(): AiAssistantState {
  return {
    loading: false,
    error: null,
    initialized: false,
    sessions: [],
    activeSessionId: null,
    messages: [],
    suggestions: []
  };
}

export const useAiAssistantStore = defineStore('ai-assistant', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);
  const sessions = ref<ChatSessionItem[]>([]);
  const activeSessionId = ref<number | null>(null);
  const messages = ref<ChatMessageItem[]>([]);
  const suggestions = ref<string[]>([]);

  const ready = computed(() => initialized.value && error.value === null);

  function reset(): void {
    const initial = createAiAssistantInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    sessions.value = initial.sessions;
    activeSessionId.value = initial.activeSessionId;
    messages.value = initial.messages;
    suggestions.value = initial.suggestions;
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
      refreshSuggestions({ sessionId });
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
    refreshSuggestions({ sessionId: session.session_id });
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

  /** A2「动态问题」：取下一批推荐问题（纯前端固定池轮换，零网络请求） */
  function refreshSuggestions(options: RefreshSuggestionsOptions = {}): string[] {
    const list = nextSuggestions({
      sessionId: options.sessionId ?? activeSessionId.value,
      exclude: options.exclude ?? [],
      size: options.size ?? SUGGESTION_BATCH_SIZE,
      category: options.category
    });
    suggestions.value = list;
    return list;
  }

  /** A2：用户点走一条推荐后，把它从当前候选中摘下；再次 refresh 时请把它放进 exclude */
  function markSuggestionUsed(text: string): void {
    suggestions.value = suggestions.value.filter((item) => item !== text);
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
    suggestions,
    reset,
    load,
    loadSessions,
    openSession,
    newSession,
    sendMessage,
    removeSession,
    refreshSuggestions,
    markSuggestionUsed
  };
});
