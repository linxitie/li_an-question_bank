/**
 * 联考小智（ai-assistant）域 API 封装 —— 模块⑦「联考小智」实现
 *
 * 约束：
 *   1. 全域只使用 @/services/api/client 暴露的唯一 axios 实例，禁止自行 axios.create；
 *   2. 端点均挂在根路径 `/api/*`（非 `/api/v1`），沿用 growth 的 `baseURL: ''` 覆盖方式；
 *   3. 端点登记见 README「后端端点清单」。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用：所有请求都经由此实例发起 */
export const aiAssistantClient = apiClient;

/** 消息场景：psychological 心理调整 / qa 疑难解答 / advice 提升建议 */
export type ChatScene = 'psychological' | 'qa' | 'advice';

/** 会话摘要（列表项） */
export interface ChatSessionItem {
  session_id: number;
  title: string;
  scene: string;
  create_time: string | null;
  update_time: string | null;
}

/** 会话列表响应 */
export interface SessionListResult {
  total: number;
  items: ChatSessionItem[];
}

/** 发送消息响应 */
export interface ChatResult {
  reply: string;
  session_id: number;
  scene: string;
}

/** 历史消息项 */
export interface ChatMessageItem {
  message_id: number;
  role: 'user' | 'assistant';
  content: string;
  create_time: string | null;
}

/** 会话历史响应 */
export interface SessionMessagesResult {
  session_id: number;
  items: ChatMessageItem[];
}

interface AiAssistantRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, unknown>;
  data?: unknown;
}

async function request<T>(config: AiAssistantRequestConfig): Promise<T> {
  const response = await aiAssistantClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 发送一条消息（带 session_id 多轮；不带自动新建会话） */
export function sendChat(
  message: string,
  sessionId?: number,
  scene: ChatScene = 'qa'
): Promise<ChatResult> {
  return request<ChatResult>({
    url: '/api/llm/chat',
    method: 'POST',
    data: { message, session_id: sessionId, scene }
  });
}

/** 我的会话列表 */
export function fetchSessions(): Promise<SessionListResult> {
  return request<SessionListResult>({ url: '/api/llm/sessions', method: 'GET' });
}

/** 新建会话 */
export function createSession(title?: string, scene: ChatScene = 'qa'): Promise<ChatSessionItem> {
  return request<ChatSessionItem>({
    url: '/api/llm/sessions',
    method: 'POST',
    data: { title, scene }
  });
}

/** 某会话的历史消息 */
export function fetchSessionMessages(sessionId: number): Promise<SessionMessagesResult> {
  return request<SessionMessagesResult>({
    url: `/api/llm/sessions/${sessionId}/messages`,
    method: 'GET'
  });
}

/** 删除会话（软删） */
export function deleteSession(sessionId: number): Promise<{ message: string }> {
  return request<{ message: string }>({
    url: `/api/llm/sessions/${sessionId}`,
    method: 'DELETE'
  });
}
